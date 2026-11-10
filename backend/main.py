import os
import uuid
import time
import asyncio
import threading
from datetime import datetime
from typing import Dict, Any, List, Optional

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, BackgroundTasks, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse

from backend.models import ScrapeRequest, JobSummary, SessionStatus
from backend.scrapers.base import detect_platform_from_url
from backend.scrapers import get_scraper_for_platform
from backend.services.cleaner import process_comment_text
from backend.services.exporter import export_to_csv, export_to_excel, export_to_json
from backend.services.session_store import (
    load_config, save_config, has_facebook_session, has_instagram_session,
    has_twitter_session, save_custom_cookies, interactive_login_browser
)

app = FastAPI(title="Unified Multi-Platform Social Media Comment Scraper", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
@app.get("/api/health")
async def health_check():
    return {"status": "ok", "service": "omniscrape"}

# In-memory store for jobs
class JobRecord:
    def __init__(self, job_id: str, request: ScrapeRequest):
        self.job_id = job_id
        self.request = request
        self.status = "queued"
        self.comments: List[Dict[str, Any]] = []
        self.logs: List[Dict[str, Any]] = []
        self.progress = 0.0
        self.current_status_text = "Job queued..."
        self.platform = request.platform or "auto"
        self.created_at = datetime.now().isoformat()
        self.completed_at: Optional[str] = None
        self.error: Optional[str] = None
        self.stop_event = threading.Event()
        self.export_files: Dict[str, str] = {}
        self.interim_count = 0

JOBS: Dict[str, JobRecord] = {}

# Active WebSocket connections
ACTIVE_WEBSOCKETS: List[WebSocket] = []
MAIN_LOOP: Optional[asyncio.AbstractEventLoop] = None

@app.on_event("startup")
async def startup_event():
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()

async def broadcast_message(msg: Dict[str, Any]):
    disconnected = []
    for ws in list(ACTIVE_WEBSOCKETS):
        try:
            await ws.send_json(msg)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        if ws in ACTIVE_WEBSOCKETS:
            ACTIVE_WEBSOCKETS.remove(ws)

def sync_broadcast(msg: Dict[str, Any]):
    """Thread-safe WebSocket broadcast that safely dispatches to the server's main event loop."""
    global MAIN_LOOP
    if MAIN_LOOP is not None and MAIN_LOOP.is_running():
        try:
            asyncio.run_coroutine_threadsafe(broadcast_message(msg), MAIN_LOOP)
            return
        except Exception:
            pass
    try:
        current_loop = asyncio.get_running_loop()
        current_loop.create_task(broadcast_message(msg))
    except RuntimeError:
        try:
            temp_loop = asyncio.new_event_loop()
            temp_loop.run_until_complete(broadcast_message(msg))
            temp_loop.close()
        except Exception:
            pass

def run_scrape_task(job: JobRecord):
    def log(msg: str, status: str = "scraping", count: Optional[int] = None):
        entry = {
            "timestamp": datetime.now().strftime("%H:%M:%S"),
            "log": msg,
            "status": status,
            "count": count if count is not None else len(job.comments),
            "job_id": job.job_id
        }
        job.logs.append(entry)
        job.current_status_text = msg
        if count is not None:
            job.progress = min(95.0, (count / max(1, job.request.max_comments_per_url * len(job.request.urls))) * 100)
        sync_broadcast({"type": "log", "data": entry})

    try:
        job.status = "running"
        log(f"Starting extraction task with {len(job.request.urls)} URL(s)...", "running")

        total_urls = len(job.request.urls)
        for url_idx, raw_url in enumerate(job.request.urls):
            if job.stop_event.is_set():
                log("Job halted by user.", "stopped")
                job.status = "stopped"
                break

            url = raw_url.strip()
            if not url:
                continue

            target_platform = job.request.platform
            if not target_platform or target_platform == "auto":
                target_platform = detect_platform_from_url(url)
                if target_platform == "unknown":
                    log(f"Could not identify platform for URL: {url}", "warning")
                    continue

            job.platform = target_platform
            log(f"[{target_platform.upper()}] Scraping: {url} ({url_idx + 1}/{total_urls})", "connecting")

            scraper = get_scraper_for_platform(target_platform)

            def scraper_cb(data: Dict[str, Any]):
                cnt = data.get("count", 0)
                job.interim_count = len(job.comments) + cnt
                log(data.get("log", ""), data.get("status", "scraping"), job.interim_count)

            try:
                extracted = scraper.scrape(
                    url=url,
                    max_comments=job.request.max_comments_per_url,
                    include_replies=job.request.include_replies,
                    progress_callback=scraper_cb,
                    stop_event=job.stop_event
                )

                for item in extracted:
                    # Apply Bangla text filter if requested
                    if job.request.filter_bangla_only and item.get("language") not in ["bn", "mixed"]:
                        continue
                    if len(item.get("text", "")) < job.request.min_length:
                        continue
                    job.comments.append(item)

                log(f"Extracted {len(extracted)} comments from current URL. Total in dataset: {len(job.comments)}", "progress")

            except Exception as e:
                log(f"Error scraping {url}: {str(e)}", "error")

        if job.status != "stopped":
            job.status = "completed"
            job.progress = 100.0
            job.completed_at = datetime.now().isoformat()
            
            # Auto generate exports (.xlsx format)
            if job.comments:
                job.export_files["excel"] = export_to_excel(job.comments, f"thesis_{job.platform}")
                log(f"Dataset successfully saved in Excel (.xlsx) format!", "completed", len(job.comments))
            else:
                hint = ""
                if job.platform in ["facebook", "instagram"]:
                    hint = " (Tip: Meta requires a login session to view comments. Please use 'Session & Accounts' at the top right to log in once.)"
                log(f"Completed with 0 comments matching criteria{hint}.", "warning", 0)

    except Exception as e:
        job.status = "failed"
        job.error = str(e)
        log(f"Job failed with error: {str(e)}", "error")
    finally:
        sync_broadcast({
            "type": "job_status",
            "data": {
                "job_id": job.job_id,
                "status": job.status,
                "total_comments": len(job.comments),
                "progress": job.progress
            }
        })

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    await websocket.accept()
    ACTIVE_WEBSOCKETS.append(websocket)
    try:
        while True:
            # Keep alive and handle client pings
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        if websocket in ACTIVE_WEBSOCKETS:
            ACTIVE_WEBSOCKETS.remove(websocket)
    except Exception:
        if websocket in ACTIVE_WEBSOCKETS:
            ACTIVE_WEBSOCKETS.remove(websocket)

# REST Endpoints
@app.post("/api/scrape")
async def start_scrape(req: ScrapeRequest, background_tasks: BackgroundTasks):
    global MAIN_LOOP
    MAIN_LOOP = asyncio.get_running_loop()
    if not req.urls:
        raise HTTPException(status_code=400, detail="At least one URL must be provided.")
        
    job_id = str(uuid.uuid4())[:8]
    job = JobRecord(job_id, req)
    JOBS[job_id] = job
    
    # Run in background thread
    thread = threading.Thread(target=run_scrape_task, args=(job,), daemon=True)
    thread.start()
    
    return {"job_id": job_id, "status": "queued", "message": "Scraping task started successfully!"}

@app.post("/api/jobs/{job_id}/stop")
async def stop_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
    job.stop_event.set()
    job.status = "stopped"
    return {"job_id": job_id, "status": "stopped", "message": "Job stop requested."}

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
        
    return {
        "job_id": job.job_id,
        "status": job.status,
        "platform": job.platform,
        "total_comments": max(len(job.comments), getattr(job, "interim_count", 0)),
        "progress": job.progress,
        "current_status_text": job.current_status_text,
        "logs": job.logs[-50:],  # return last 50 logs
        "created_at": job.created_at,
        "completed_at": job.completed_at,
        "error": job.error,
        "has_exports": len(job.export_files) > 0
    }

@app.get("/api/jobs/{job_id}/comments")
async def get_comments(
    job_id: str,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=500),
    search: Optional[str] = None,
    language: Optional[str] = None
):
    job = JOBS.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found.")
        
    filtered = job.comments
    
    if search:
        s_lower = search.lower()
        filtered = [c for c in filtered if s_lower in c.get("text", "").lower() or s_lower in c.get("author", "").lower()]
        
    if language and language != "all":
        filtered = [c for c in filtered if c.get("language") == language]
        
    total = len(filtered)
    start_idx = (page - 1) * limit
    end_idx = start_idx + limit
    page_data = filtered[start_idx:end_idx]
    
    # Calculate stats
    bangla_count = sum(1 for c in job.comments if c.get("language") == "bn")
    english_count = sum(1 for c in job.comments if c.get("language") == "en")
    mixed_count = sum(1 for c in job.comments if c.get("language") == "mixed")
    
    return {
        "total": total,
        "page": page,
        "limit": limit,
        "data": page_data,
        "stats": {
            "total_in_job": len(job.comments),
            "bangla": bangla_count,
            "english": english_count,
            "mixed": mixed_count,
            "other": len(job.comments) - (bangla_count + english_count + mixed_count)
        }
    }

@app.get("/api/export/{job_id}/{fmt}")
async def download_export(job_id: str, fmt: str):
    job = JOBS.get(job_id)
    if not job or not job.comments:
        raise HTTPException(status_code=404, detail="No comments available to export.")
        
    fmt = fmt.lower()
    if fmt == "csv":
        filepath = export_to_csv(job.comments, f"thesis_{job.platform}")
        media_type = "text/csv; charset=utf-8"
    elif fmt in ["excel", "xlsx"]:
        filepath = export_to_excel(job.comments, f"thesis_{job.platform}")
        media_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    elif fmt == "json":
        filepath = export_to_json(job.comments, f"thesis_{job.platform}")
        media_type = "application/json"
    else:
        raise HTTPException(status_code=400, detail="Invalid format. Supported: csv, excel, json")
        
    return FileResponse(filepath, filename=os.path.basename(filepath), media_type=media_type)

@app.get("/api/sessions/status")
async def get_sessions():
    config = load_config()
    return {
        "facebook_logged_in": has_facebook_session(),
        "instagram_logged_in": has_instagram_session(),
        "twitter_logged_in": has_twitter_session(),
        "reddit_api_configured": bool(config.get("reddit_client_id")),
        "youtube_api_configured": bool(config.get("youtube_api_key"))
    }

@app.post("/api/sessions/login-interactive")
async def trigger_browser_login(payload: Dict[str, str], background_tasks: BackgroundTasks):
    platform = payload.get("platform", "").lower()
    if platform not in ["facebook", "instagram", "twitter", "x"]:
        raise HTTPException(status_code=400, detail="Platform must be facebook, instagram, or twitter.")
        
    # Run in background so request does not hang
    def do_login():
        interactive_login_browser(platform)
        sync_broadcast({
            "type": "session_update",
            "data": {
                "facebook_logged_in": has_facebook_session(),
                "instagram_logged_in": has_instagram_session(),
                "twitter_logged_in": has_twitter_session()
            }
        })
        
    thread = threading.Thread(target=do_login, daemon=True)
    thread.start()
    
    return {"message": f"Browser window opened for {platform.capitalize()} login. Please log in there, then close the browser window or wait for it to complete."}

@app.post("/api/sessions/save-cookies")
async def save_cookies_manual(payload: Dict[str, str]):
    platform = payload.get("platform", "").lower()
    cookies_raw = payload.get("cookies", "")
    if platform not in ["facebook", "instagram", "twitter", "x"] or not cookies_raw:
        raise HTTPException(status_code=400, detail="Platform (facebook, instagram, twitter) and cookies string required.")
        
    success = save_custom_cookies(platform, cookies_raw)
    return {"success": success, "message": "Cookies imported and saved!" if success else "Failed to parse cookies."}

@app.post("/api/settings")
async def save_settings_api(payload: Dict[str, Any]):
    config = load_config()
    for k, v in payload.items():
        if v:
            config[k] = v
    save_config(config)
    return {"success": True, "message": "Settings saved successfully."}

@app.get("/api/settings")
async def get_settings_api():
    config = load_config()
    return {
        "reddit_client_id": config.get("reddit_client_id", ""),
        "has_reddit_secret": bool(config.get("reddit_client_secret")),
        "has_youtube_key": bool(config.get("youtube_api_key"))
    }

# Mount static frontend
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))
if os.path.exists(FRONTEND_DIR):
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")

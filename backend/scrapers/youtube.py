import time
import re
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
import dateparser
from youtube_comment_downloader import YoutubeCommentDownloader, SORT_BY_POPULAR, SORT_BY_RECENT
from backend.scrapers.base import BaseScraper
from backend.services.cleaner import process_comment_text

class YoutubeScraper(BaseScraper):
    def __init__(self):
        super().__init__("youtube")
        self.downloader = YoutubeCommentDownloader()

    def scrape(
        self,
        url: str,
        max_comments: int = 200,
        include_replies: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        
        if progress_callback:
            progress_callback({
                "status": "connecting",
                "count": 0,
                "log": f"[YouTube] Connecting to video: {url}"
            })
            
        try:
            generator = self.downloader.get_comments_from_url(url, sort_by=SORT_BY_POPULAR)
            count = 0
            
            for item in generator:
                if stop_event and stop_event.is_set():
                    if progress_callback:
                        progress_callback({
                            "status": "stopped",
                            "count": len(results),
                            "log": "[YouTube] Scraping paused/stopped by user."
                        })
                    break
                    
                is_reply = bool(item.get("reply", False))
                if is_reply and not include_replies:
                    continue
                    
                raw_text = str(item.get("text", "")).strip()
                if not raw_text:
                    continue
                    
                cleaned, lang, word_count = process_comment_text(raw_text)
                
                # Parse likes / votes
                votes_raw = str(item.get("votes", "0")).replace(",", "").strip()
                try:
                    likes = int(votes_raw) if votes_raw.isdigit() else 0
                except Exception:
                    likes = 0
                    
                # Parse timestamp
                time_parsed = item.get("time_parsed")
                if time_parsed:
                    try:
                        pub_time = datetime.fromtimestamp(float(time_parsed), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
                    except Exception:
                        pub_time = ""
                else:
                    pub_time = ""

                if not pub_time:
                    raw_time = str(item.get("time", "")).strip()
                    try:
                        dt = dateparser.parse(raw_time) if raw_time else None
                        pub_time = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else (raw_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
                    except Exception:
                        pub_time = raw_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                author_name = item.get("author", "Unknown")

                # Extract @mention in reply if present
                replying_to = "-"
                if is_reply:
                    m_at = re.match(r"^(@[a-zA-Z0-9_\.\-]+)", raw_text.strip())
                    if m_at:
                        replying_to = m_at.group(1)
                    else:
                        replying_to = "Creator"

                comment_data = {
                    "id": item.get("cid", f"yt_{len(results)+1}"),
                    "platform": "youtube",
                    "post_url": url,
                    "author": author_name,
                    "author_id": item.get("channel", ""),
                    "text": raw_text,
                    "cleaned_text": cleaned,
                    "timestamp": pub_time,
                    "likes": likes,
                    "reply_count": 0,
                    "is_reply": is_reply,
                    "parent_id": None,
                    "replying_to": replying_to,
                    "language": lang,
                    "word_count": word_count,
                    "Type": "REPLY" if is_reply else "MAIN COMMENT",
                    "Author": author_name,
                    "Comment": raw_text,
                    "Replying_To": replying_to,
                    "Likes": likes,
                    "Published_At": pub_time
                }
                
                results.append(comment_data)
                count += 1
                
                if progress_callback and (count % 20 == 0 or count == 1):
                    progress_callback({
                        "status": "scraping",
                        "count": count,
                        "log": f"[YouTube] Extracted {count} comments so far..."
                    })
                    
                if 0 < max_comments <= count:
                    break
                    
            if progress_callback:
                progress_callback({
                    "status": "done",
                    "count": len(results),
                    "log": f"[YouTube] Finished successfully. Extracted {len(results)} comments."
                })
                
        except Exception as e:
            if progress_callback:
                progress_callback({
                    "status": "error",
                    "count": len(results),
                    "log": f"[YouTube] Error while scraping: {str(e)}"
                })
            raise e
            
        return results

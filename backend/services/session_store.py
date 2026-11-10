import os
import json
from typing import Dict, Any, Optional

SESSIONS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "sessions"))
CONFIG_FILE = os.path.join(SESSIONS_DIR, "config.json")
FB_SESSION_FILE = os.path.join(SESSIONS_DIR, "facebook_session.json")
IG_SESSION_FILE = os.path.join(SESSIONS_DIR, "instagram_session.json")
TWITTER_SESSION_FILE = os.path.join(SESSIONS_DIR, "twitter_session.json")

os.makedirs(SESSIONS_DIR, exist_ok=True)

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(config: Dict[str, Any]) -> None:
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)

def has_facebook_session() -> bool:
    return os.path.exists(FB_SESSION_FILE) and os.path.getsize(FB_SESSION_FILE) > 50

def has_instagram_session() -> bool:
    return os.path.exists(IG_SESSION_FILE) and os.path.getsize(IG_SESSION_FILE) > 50

def has_twitter_session() -> bool:
    return os.path.exists(TWITTER_SESSION_FILE) and os.path.getsize(TWITTER_SESSION_FILE) > 50

def get_facebook_session_path() -> Optional[str]:
    return FB_SESSION_FILE if has_facebook_session() else None

def get_instagram_session_path() -> Optional[str]:
    return IG_SESSION_FILE if has_instagram_session() else None

def get_twitter_session_path() -> Optional[str]:
    return TWITTER_SESSION_FILE if has_twitter_session() else None

def save_custom_cookies(platform: str, cookies_raw: str) -> bool:
    """
    Allows user to paste raw cookies string (e.g., from browser developer tools)
    or JSON array of cookies, and converts into Playwright storage state format.
    """
    p = platform.lower()
    if p in ["twitter", "x"]:
        target_file = TWITTER_SESSION_FILE
        domain = ".x.com"
    elif p == "facebook":
        target_file = FB_SESSION_FILE
        domain = ".facebook.com"
    else:
        target_file = IG_SESSION_FILE
        domain = ".instagram.com"
    
    cookies_list = []
    
    # Try parsing as JSON first
    try:
        parsed = json.loads(cookies_raw)
        if isinstance(parsed, list):
            cookies_list = parsed
        elif isinstance(parsed, dict) and "cookies" in parsed:
            cookies_list = parsed["cookies"]
    except Exception:
        # Parse standard header string: "key1=val1; key2=val2"
        pairs = cookies_raw.split(";")
        for pair in pairs:
            if "=" in pair:
                k, v = pair.strip().split("=", 1)
                cookies_list.append({
                    "name": k.strip(),
                    "value": v.strip(),
                    "domain": domain,
                    "path": "/"
                })
                
    if cookies_list:
        storage_state = {
            "cookies": cookies_list,
            "origins": []
        }
        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(storage_state, f, indent=2)
        return True
    return False

def interactive_login_browser(platform: str, timeout_seconds: int = 120) -> Dict[str, Any]:
    """
    Launches a visible Chromium browser window where user can log in to Facebook, Instagram, or Twitter/X.
    Once logged in or when user closes window, the authenticated session cookies are saved!
    """
    from playwright.sync_api import sync_playwright
    
    p = platform.lower().strip()
    if p in ["twitter", "x"]:
        target_url = "https://x.com/i/flow/login"
        target_session_file = TWITTER_SESSION_FILE
    elif p == "facebook":
        target_url = "https://www.facebook.com"
        target_session_file = FB_SESSION_FILE
    else:
        target_url = "https://www.instagram.com"
        target_session_file = IG_SESSION_FILE
    
    try:
        with sync_playwright() as p_ctx:
            browser = p_ctx.chromium.launch(headless=False)
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1280, "height": 800}
            )
            page = context.new_page()
            page.goto(target_url)
            
            # Wait for user to interact and log in
            # We poll every 2 seconds up to timeout_seconds or until user closes page
            import time
            start = time.time()
            logged_in = False
            
            while time.time() - start < timeout_seconds:
                try:
                    if page.is_closed():
                        break
                    # Check cookies
                    cookies = context.cookies()
                    cookie_names = [c["name"] for c in cookies]
                    
                    if p == "facebook" and ("c_user" in cookie_names or "xs" in cookie_names):
                        logged_in = True
                        break
                    elif p == "instagram" and "sessionid" in cookie_names:
                        logged_in = True
                        break
                    elif p in ["twitter", "x"] and ("auth_token" in cookie_names or "ct0" in cookie_names):
                        logged_in = True
                        break
                        
                    page.wait_for_timeout(1000)
                except Exception:
                    break
                    
            # Save storage state
            try:
                context.storage_state(path=target_session_file)
            except Exception:
                pass
                
            browser.close()
            
            return {
                "success": logged_in or os.path.exists(target_session_file),
                "message": f"{platform.capitalize()} session saved successfully!" if logged_in else f"Browser closed. Session state saved to {target_session_file}."
            }
    except Exception as e:
        return {"success": False, "message": str(e)}

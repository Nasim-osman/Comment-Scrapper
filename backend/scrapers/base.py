import re
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Callable, Optional
import threading

class BaseScraper(ABC):
    def __init__(self, platform_name: str):
        self.platform_name = platform_name
        
    @abstractmethod
    def scrape(
        self,
        url: str,
        max_comments: int = 200,
        include_replies: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrapes comments from the given URL.
        progress_callback is called with dict like:
        {"status": "scraping", "count": 45, "log": "Extracted 45 comments..."}
        """
        pass

def detect_platform_from_url(url: str) -> str:
    url_lower = url.lower()
    if "youtube.com" in url_lower or "youtu.be" in url_lower:
        return "youtube"
    elif "reddit.com" in url_lower or "redd.it" in url_lower:
        return "reddit"
    elif "instagram.com" in url_lower or "instagr.am" in url_lower:
        return "instagram"
    elif "facebook.com" in url_lower or "fb.watch" in url_lower or "fb.com" in url_lower:
        return "facebook"
    elif "twitter.com" in url_lower or "x.com" in url_lower:
        return "twitter"
    return "unknown"

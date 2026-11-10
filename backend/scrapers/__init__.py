from backend.scrapers.base import BaseScraper, detect_platform_from_url
from backend.scrapers.youtube import YoutubeScraper
from backend.scrapers.reddit import RedditScraper
from backend.scrapers.instagram import InstagramScraper
from backend.scrapers.facebook import FacebookScraper
from backend.scrapers.twitter import TwitterScraper

def get_scraper_for_platform(platform: str) -> BaseScraper:
    p = platform.lower().strip()
    if p == "youtube":
        return YoutubeScraper()
    elif p == "reddit":
        return RedditScraper()
    elif p == "instagram":
        return InstagramScraper()
    elif p == "facebook":
        return FacebookScraper()
    elif p in ["twitter", "x"]:
        return TwitterScraper()
    else:
        raise ValueError(f"Unsupported platform: {platform}")

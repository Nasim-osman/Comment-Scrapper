import re
import time
import threading
from datetime import datetime
from typing import List, Dict, Any, Callable, Optional
from urllib.parse import urlparse

from playwright.sync_api import sync_playwright
from backend.scrapers.base import BaseScraper
from backend.services.cleaner import process_comment_text
from backend.services.session_store import get_twitter_session_path, has_twitter_session

class TwitterScraper(BaseScraper):
    def __init__(self):
        super().__init__("twitter")

    def _parse_likes(self, aria_or_text: str) -> int:
        if not aria_or_text:
            return 0
        cleaned = aria_or_text.lower().replace(",", "").strip()
        # Look for numbers like "1,234 Likes" or "12.5K Likes" or "5"
        m = re.search(r"([\d\.]+)\s*([km])?", cleaned)
        if not m:
            return 0
        num = float(m.group(1))
        mult = m.group(2)
        if mult == "k":
            num *= 1000
        elif mult == "m":
            num *= 1000000
        return int(num)

    def scrape(
        self,
        url: str,
        max_comments: int = 200,
        include_replies: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        
        # Standardize URL
        clean_url = url.strip()
        if "twitter.com" in clean_url:
            clean_url = clean_url.replace("twitter.com", "x.com")

        if progress_callback:
            progress_callback({
                "status": "connecting",
                "count": 0,
                "log": f"[Twitter/X] Connecting to post: {clean_url}"
            })

        session_path = get_twitter_session_path()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--disable-blink-features=AutomationControlled',
                    '--no-sandbox',
                    '--disable-infobars',
                    '--disable-dev-shm-usage',
                    '--disable-gpu'
                ]
            )

            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 900}
            }
            if session_path and has_twitter_session():
                context_kwargs["storage_state"] = session_path

            context = browser.new_context(**context_kwargs)
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            
            page = context.new_page()

            try:
                page.goto(clean_url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(3000)
            except Exception as e:
                if progress_callback:
                    progress_callback({
                        "status": "warning",
                        "count": 0,
                        "log": f"[Twitter/X] Page load timeout or issue: {str(e)[:100]}, attempting extraction..."
                    })

            # Dismiss cookie banners or login popups if present
            try:
                close_selectors = [
                    "div[data-testid='app-bar-close']",
                    "div[aria-label='Close']",
                    "button[aria-label='Close']",
                    "div[role='button']:has-text('Refuse non-essential cookies')",
                    "div[role='button']:has-text('Accept all cookies')",
                    "div[role='button']:has-text('Not now')"
                ]
                for sel in close_selectors:
                    btn = page.query_selector(sel)
                    if btn and btn.is_visible():
                        btn.click()
                        page.wait_for_timeout(500)
            except Exception:
                pass

            seen_keys = set()
            main_author = "Unknown"

            # 1. Extract Main Tweet
            try:
                tweet_articles = page.query_selector_all("article[data-testid='tweet']")
                if tweet_articles:
                    main_art = tweet_articles[0]
                    
                    # Extract handle / author
                    author_elem = main_art.query_selector("div[data-testid='User-Name']")
                    if author_elem:
                        full_name = author_elem.inner_text().split("\n")
                        main_author = full_name[1] if len(full_name) > 1 and full_name[1].startswith("@") else full_name[0]
                    
                    # Extract text
                    text_elem = main_art.query_selector("div[data-testid='tweetText']")
                    main_text = text_elem.inner_text().strip() if text_elem else ""

                    # Extract time
                    time_elem = main_art.query_selector("time")
                    raw_time = time_elem.get_attribute("datetime") if time_elem else ""
                    main_time = raw_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                    # Extract likes
                    like_elem = main_art.query_selector("div[data-testid='like'], button[data-testid='like']")
                    main_likes = self._parse_likes(like_elem.get_attribute("aria-label") or like_elem.inner_text() if like_elem else "0")

                    if main_text:
                        cleaned, lang, word_count = process_comment_text(main_text)
                        main_item = {
                            "id": "tw_main",
                            "platform": "twitter",
                            "post_url": clean_url,
                            "author": main_author,
                            "author_id": main_author,
                            "text": main_text,
                            "cleaned_text": cleaned,
                            "timestamp": str(main_time),
                            "likes": main_likes,
                            "reply_count": 0,
                            "is_reply": False,
                            "parent_id": None,
                            "replying_to": "-",
                            "language": lang,
                            "word_count": word_count,
                            "Type": "MAIN COMMENT",
                            "Author": main_author,
                            "Comment": main_text,
                            "Replying_To": "-",
                            "Likes": main_likes,
                            "Published_At": str(main_time)
                        }
                        results.append(main_item)
                        seen_keys.add(f"{main_author}_{main_text[:40]}")
                        
                        if progress_callback:
                            progress_callback({
                                "status": "scraping",
                                "count": 1,
                                "log": f"[Twitter/X] Found main post by {main_author}. Extracting replies..."
                            })
            except Exception as e:
                if progress_callback:
                    progress_callback({
                        "status": "warning",
                        "count": len(results),
                        "log": f"[Twitter/X] Error reading main post: {str(e)}"
                    })

            # 2. Extract Replies
            if include_replies:
                consecutive_no_new = 0
                max_scroll_attempts = 35

                for scroll_round in range(max_scroll_attempts):
                    if stop_event and stop_event.is_set():
                        break
                    if 0 < max_comments <= len(results):
                        break

                    # Check for "Show replies" or "Show more replies" buttons
                    try:
                        show_buttons = page.query_selector_all("div[role='button']:has-text('Show replies'), div[role='button']:has-text('Show more replies'), div[role='button']:has-text('Show')")
                        for sbtn in show_buttons:
                            if sbtn.is_visible():
                                sbtn.click()
                                page.wait_for_timeout(1000)
                    except Exception:
                        pass

                    articles = page.query_selector_all("article[data-testid='tweet']")
                    new_found = 0

                    for art in articles[1:]:  # skip main tweet
                        if 0 < max_comments <= len(results):
                            break

                        try:
                            # Author
                            auth_div = art.query_selector("div[data-testid='User-Name']")
                            reply_author = "Unknown"
                            reply_handle = ""
                            if auth_div:
                                lines = [line.strip() for line in auth_div.inner_text().split("\n") if line.strip()]
                                handles = [l for l in lines if l.startswith("@")]
                                if handles:
                                    reply_author = handles[0]
                                    reply_handle = handles[0]
                                elif lines:
                                    reply_author = lines[0]

                            # Text
                            t_div = art.query_selector("div[data-testid='tweetText']")
                            if not t_div:
                                continue
                            raw_text = t_div.inner_text().strip()
                            if not raw_text:
                                continue

                            key = f"{reply_author}_{raw_text[:40]}"
                            if key in seen_keys:
                                continue
                            seen_keys.add(key)
                            new_found += 1

                            # Replying to
                            replying_to = main_author
                            # Check if tweet has "Replying to @..." line
                            replying_elem = art.query_selector("div:has-text('Replying to')")
                            if replying_elem:
                                m_rep = re.search(r"(@[a-zA-Z0-9_]+)", replying_elem.inner_text())
                                if m_rep:
                                    replying_to = m_rep.group(1)

                            # Time
                            time_elem = art.query_selector("time")
                            raw_time = time_elem.get_attribute("datetime") if time_elem else ""
                            pub_time = raw_time or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            # Likes
                            like_elem = art.query_selector("div[data-testid='like'], button[data-testid='like']")
                            likes_val = self._parse_likes(like_elem.get_attribute("aria-label") or like_elem.inner_text() if like_elem else "0")

                            cleaned, lang, word_count = process_comment_text(raw_text)

                            item = {
                                "id": f"tw_reply_{len(results)+1}",
                                "platform": "twitter",
                                "post_url": clean_url,
                                "author": reply_author,
                                "author_id": reply_handle,
                                "text": raw_text,
                                "cleaned_text": cleaned,
                                "timestamp": str(pub_time),
                                "likes": likes_val,
                                "reply_count": 0,
                                "is_reply": True,
                                "parent_id": "tw_main",
                                "replying_to": replying_to,
                                "language": lang,
                                "word_count": word_count,
                                "Type": "REPLY",
                                "Author": reply_author,
                                "Comment": raw_text,
                                "Replying_To": replying_to,
                                "Likes": likes_val,
                                "Published_At": str(pub_time)
                            }
                            results.append(item)

                        except Exception:
                            continue

                    if new_found > 0:
                        consecutive_no_new = 0
                        if progress_callback:
                            progress_callback({
                                "status": "scraping",
                                "count": len(results),
                                "log": f"[Twitter/X] Extracted {len(results)} comments/replies so far..."
                            })
                    else:
                        consecutive_no_new += 1
                        if consecutive_no_new >= 4:
                            break

                    # Scroll down
                    page.evaluate("window.scrollBy(0, 800)")
                    page.wait_for_timeout(1800)

            browser.close()

        if progress_callback:
            progress_callback({
                "status": "done",
                "count": len(results),
                "log": f"[Twitter/X] Scraping complete! Collected {len(results)} comments."
            })

        return results


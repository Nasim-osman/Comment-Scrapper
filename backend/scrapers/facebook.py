import time
import re
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
import dateparser
from playwright.sync_api import sync_playwright
from backend.scrapers.base import BaseScraper
from backend.services.cleaner import process_comment_text
from backend.services.session_store import get_facebook_session_path

class FacebookScraper(BaseScraper):
    def __init__(self):
        super().__init__("facebook")

    def scrape(
        self,
        url: str,
        max_comments: int = 200,
        include_replies: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_texts = set()
        
        session_path = get_facebook_session_path()
        
        if progress_callback:
            session_status_str = "with saved Facebook session" if session_path else "in guest mode"
            progress_callback({
                "status": "connecting",
                "count": 0,
                "log": f"[Facebook] Connecting {session_status_str} to: {url}"
            })

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            context_kwargs = {
                "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                "viewport": {"width": 1280, "height": 900},
                "locale": "en-US"
            }
            if session_path:
                context_kwargs["storage_state"] = session_path

            context = browser.new_context(**context_kwargs)
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=40000)
                page.wait_for_timeout(4000)

                # Try to dismiss cookie/login dialogs
                try:
                    cookie_btn = page.query_selector("div[aria-label='Decline optional cookies'], div[role='button']:has-text('Decline optional cookies'), div[aria-label='Close'], div[role='button']:has-text('Not Now')")
                    if cookie_btn:
                        cookie_btn.click(timeout=1500)
                except Exception:
                    pass

                # Check if Facebook redirected to login page
                if "login" in page.url:
                    if not session_path:
                        if progress_callback:
                            progress_callback({
                                "status": "warning",
                                "count": 0,
                                "log": "[Facebook] Meta login wall encountered. Please click 'Session & Accounts' at the top to log in once for full access."
                            })

                # Try to switch from "Most Relevant" to "All Comments"
                try:
                    sort_btn = page.query_selector("div[role='button']:has-text('Most relevant'), div[role='button']:has-text('সবচেয়ে প্রাসঙ্গিক')")
                    if sort_btn:
                        sort_btn.click(timeout=2000)
                        page.wait_for_timeout(1000)
                        all_btn = page.query_selector("div[role='menuitem']:has-text('All comments'), div[role='menuitem']:has-text('সব মন্তব্য')")
                        if all_btn:
                            all_btn.click(timeout=2000)
                            page.wait_for_timeout(2000)
                except Exception:
                    pass

                def is_facebook_ui_text(text_val: str) -> bool:
                    import re
                    val = text_val.strip()
                    if not val:
                        return True
                    # Relative timestamps like 3d, 4h, 2w, a day ago, 4 days ago
                    if re.fullmatch(r"(\d+|a|an)\s*(d|h|w|m|s|y|days?|hours?|weeks?|months?|years?|mins?|minutes?|secs?|seconds?)(\s+ago)?", val, re.I):
                        return True
                    # UI Buttons and action phrases
                    if val.lower() in [
                        "like", "reply", "share", "follow", "see more", "see translation", "edited",
                        "most relevant", "all comments", "write a comment...", "top fan", "author",
                        "view more comments", "view previous comments",
                        "পছন্দ করুন", "উত্তর দিন", "শেয়ার করুন", "আরও দেখুন", "সবচেয়ে প্রাসঙ্গিক", "সব মন্তব্য"
                    ]:
                        return True
                    return False

                scroll_rounds = 0
                max_rounds = 20 if max_comments > 100 else 10
                consecutive_no_new = 0

                while scroll_rounds < max_rounds:
                    if stop_event and stop_event.is_set():
                        break

                    prev_count = len(results)

                    # Click "View more comments" or "View previous comments" or "See more"
                    try:
                        view_more_buttons = page.query_selector_all(
                            "div[role='button']:has-text('View more comments'), "
                            "div[role='button']:has-text('View previous comments'), "
                            "div[role='button']:has-text('আরও মন্তব্য দেখুন'), "
                            "div[role='button']:has-text('আগের মন্তব্য দেখুন'), "
                            "span:has-text('See more'), span:has-text('আরও দেখুন')"
                        )
                        for btn in view_more_buttons[:3]:
                            try:
                                btn.click(timeout=1000)
                                page.wait_for_timeout(600)
                            except Exception:
                                pass
                    except Exception:
                        pass

                    # Locate comments: Facebook renders comments in div[role='article'] or elements with aria-label containing 'Comment by'
                    comment_articles = page.query_selector_all("div[role='article'], div[aria-label*='Comment by'], div[aria-label*='মন্তব্য করেছেন']")

                    for art in comment_articles:
                        try:
                            # Author link / name and timestamp
                            author = ""
                            pub_time = ""
                            aria = art.get_attribute("aria-label") or ""
                            is_reply = "reply" in aria.lower()

                            if "Comment by " in aria or "Reply by " in aria:
                                split_key = "Reply by " if "Reply by " in aria else "Comment by "
                                is_reply = split_key == "Reply by "
                                author_part = aria.split(split_key, 1)[1]

                                # Extract relative time string from aria
                                m_time = re.search(r"(\d+|a|an)\s+(days?|hours?|hrs?|minutes?|mins?|seconds?|weeks?|months?|years?|d|h|m|s|w)\s+ago", author_part, flags=re.IGNORECASE)
                                if m_time:
                                    raw_t = m_time.group(0)
                                    try:
                                        dt = dateparser.parse(raw_t)
                                        pub_time = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else raw_t
                                    except Exception:
                                        pub_time = raw_t

                                author = re.sub(r"\s+(\d+|a|an)\s+(days?|hours?|hrs?|minutes?|mins?|seconds?|weeks?|months?|years?|d|h|m|s|w)\s+ago.*", "", author_part, flags=re.IGNORECASE).strip()
                                author = re.sub(r"\s+[·•]?\s*\d+[dhwmsy]$", "", author, flags=re.IGNORECASE).strip()
                            elif " মন্তব্য করেছেন" in aria:
                                author = aria.split(" মন্তব্য করেছেন")[0].strip()

                            if not author or author.lower() in ["facebook user", ""]:
                                author_elem = art.query_selector("span[dir='auto'] a, a[role='link'] span, a[role='link'], h2 a, h3 a")
                                if author_elem and author_elem.inner_text().strip():
                                    author = author_elem.inner_text().strip()
                                else:
                                    author = "Facebook User"

                            if not pub_time:
                                time_elem = art.query_selector("abbr, time, a[href*='comment_id']")
                                if time_elem:
                                    raw_t = time_elem.inner_text().strip()
                                    try:
                                        dt = dateparser.parse(raw_t)
                                        pub_time = dt.strftime("%Y-%m-%d %H:%M:%S") if dt else raw_t
                                    except Exception:
                                        pub_time = raw_t

                            if not pub_time:
                                pub_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                            # Comment body text (usually in div/span with dir="auto")
                            text_candidates = art.query_selector_all("div[dir='auto'], span[dir='auto']")
                            raw_text = ""
                            for cand in text_candidates:
                                t = cand.inner_text().strip()
                                if t and t != author and not is_facebook_ui_text(t):
                                    if len(t) > len(raw_text):
                                        raw_text = t

                            if not raw_text or len(raw_text) < 2 or is_facebook_ui_text(raw_text) or raw_text.lower() == author.lower():
                                continue

                            dedup_key = f"{author}_{raw_text[:35]}"
                            if dedup_key in seen_texts:
                                continue
                            seen_texts.add(dedup_key)

                            # Reaction count
                            likes = 0
                            react_elem = art.query_selector("span[role='toolbar'], div[aria-label*='reaction'], span[aria-label*='like']")
                            if react_elem:
                                r_text = react_elem.inner_text().strip()
                                num_match = [int(s) for s in r_text.split() if s.isdigit()]
                                if num_match:
                                    likes = num_match[0]

                            cleaned, lang, word_count = process_comment_text(raw_text)

                            results.append({
                                "id": f"fb_{len(results)+1}",
                                "platform": "facebook",
                                "post_url": url,
                                "author": author,
                                "author_id": "",
                                "text": raw_text,
                                "cleaned_text": cleaned,
                                "timestamp": pub_time,
                                "likes": likes,
                                "reply_count": 0,
                                "is_reply": is_reply,
                                "parent_id": None,
                                "replying_to": "Author" if is_reply else "-",
                                "language": lang,
                                "word_count": word_count,
                                "Type": "REPLY" if is_reply else "MAIN COMMENT",
                                "Author": author,
                                "Comment": raw_text,
                                "Replying_To": "Author" if is_reply else "-",
                                "Likes": likes,
                                "Published_At": pub_time
                            })

                            if 0 < max_comments <= len(results):
                                break
                        except Exception:
                            continue

                    if progress_callback:
                        progress_callback({
                            "status": "scraping",
                            "count": len(results),
                            "log": f"[Facebook] Extracted {len(results)} comments..."
                        })

                    if 0 < max_comments <= len(results):
                        break

                    # Check for early completion: if no new comments after checking buttons & scrolling
                    if len(results) == prev_count:
                        consecutive_no_new += 1
                        if consecutive_no_new >= 2:
                            break
                    else:
                        consecutive_no_new = 0

                    # Scroll down to trigger more comment loading
                    page.evaluate("window.scrollBy(0, 1500)")
                    page.wait_for_timeout(1500)
                    scroll_rounds += 1

                if progress_callback:
                    progress_callback({
                        "status": "done",
                        "count": len(results),
                        "log": f"[Facebook] Finished extraction. Total comments: {len(results)}"
                    })

            except Exception as e:
                if progress_callback:
                    progress_callback({
                        "status": "error",
                        "count": len(results),
                        "log": f"[Facebook] Scraper error: {str(e)}"
                    })
            finally:
                browser.close()

        return results

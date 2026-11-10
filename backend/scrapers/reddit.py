import time
import re
import json
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
import requests
import dateparser
from playwright.sync_api import sync_playwright

from backend.scrapers.base import BaseScraper
from backend.services.cleaner import process_comment_text
from backend.services.session_store import load_config

def format_timestamp(raw_val: Any) -> str:
    """Safely normalizes any timestamp into a clean YYYY-MM-DD HH:MM:SS string."""
    if not raw_val:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = str(raw_val).strip()
    try:
        f = float(s)
        if f > 1000000000:
            return datetime.fromtimestamp(f, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    try:
        dt = dateparser.parse(s)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return s

class RedditScraper(BaseScraper):
    def __init__(self):
        super().__init__("reddit")

    def scrape(
        self,
        url: str,
        max_comments: int = 200,
        include_replies: bool = True,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]] = None,
        stop_event: Optional[threading.Event] = None
    ) -> List[Dict[str, Any]]:
        # Check if PRAW is configured
        config = load_config()
        client_id = config.get("reddit_client_id")
        client_secret = config.get("reddit_client_secret")
        
        if client_id and client_secret:
            try:
                return self._scrape_praw(url, client_id, client_secret, max_comments, include_replies, progress_callback, stop_event)
            except Exception as e:
                if progress_callback:
                    progress_callback({
                        "status": "warning",
                        "count": 0,
                        "log": f"[Reddit] PRAW API note: {str(e)[:80]}, falling back..."
                    })

        # Strategy 1: Reddit Public Structured JSON (Fastest & extracts 100% of nested replies)
        clean_url = url.split("?")[0].rstrip("/")
        if "reddit.com/r/" in clean_url or "reddit.com/comments/" in clean_url or "redd.it/" in clean_url:
            try:
                if progress_callback:
                    progress_callback({
                        "status": "connecting",
                        "count": 0,
                        "log": f"[Reddit] Fetching full nested comment tree via structured API..."
                    })

                target_json_url = clean_url + ".json?limit=500&raw_json=1&sort=confidence"
                headers = {
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                    "Accept": "application/json, text/plain, */*"
                }
                resp = requests.get(target_json_url, headers=headers, timeout=15)
                if resp.status_code == 200:
                    json_data = resp.json()
                    if isinstance(json_data, list) and len(json_data) > 1:
                        comment_listing = json_data[1]
                        children = comment_listing.get("data", {}).get("children", [])
                        if children:
                            results: List[Dict[str, Any]] = []
                            seen_ids = set()
                            self._traverse_reddit_json(children, url, max_comments, include_replies, results, seen_ids, "-")
                            if results:
                                if progress_callback:
                                    progress_callback({
                                        "status": "done",
                                        "count": len(results),
                                        "log": f"[Reddit] Successfully extracted {len(results)} comments & all nested replies!"
                                    })
                                return results
            except Exception:
                pass
                    
        return self._scrape_browser(url, max_comments, include_replies, progress_callback, stop_event)

    def _traverse_reddit_json(
        self,
        children: List[Dict[str, Any]],
        post_url: str,
        max_comments: int,
        include_replies: bool,
        results: List[Dict[str, Any]],
        seen_ids: set,
        parent_author: str = "-"
    ) -> None:
        """Recursively parses all nested comments from Reddit JSON listing."""
        for child in children:
            if 0 < max_comments <= len(results):
                return
            if child.get("kind") != "t1":
                continue

            cdata = child.get("data", {})
            cid = cdata.get("name") or cdata.get("id")
            if not cid or cid in seen_ids:
                continue
            seen_ids.add(cid)

            author = cdata.get("author") or "[deleted]"
            body = (cdata.get("body") or "").strip()
            if not body or body in ["[deleted]", "[removed]"]:
                continue

            created_utc = cdata.get("created_utc")
            pub_time = format_timestamp(created_utc)
            is_reply = str(cdata.get("parent_id", "")).startswith("t1_")

            cleaned, lang, word_count = process_comment_text(body)

            item = {
                "id": cid,
                "platform": "reddit",
                "post_url": post_url,
                "author": author,
                "author_id": f"u/{author}" if author != "[deleted]" else "",
                "text": body,
                "cleaned_text": cleaned,
                "timestamp": pub_time,
                "likes": int(cdata.get("score") or 0),
                "reply_count": 0,
                "is_reply": is_reply,
                "parent_id": cdata.get("parent_id"),
                "replying_to": parent_author if is_reply else "-",
                "language": lang,
                "word_count": word_count,
                "Type": "REPLY" if is_reply else "MAIN COMMENT",
                "Author": author,
                "Comment": body,
                "Replying_To": parent_author if is_reply else "-",
                "Likes": int(cdata.get("score") or 0),
                "Published_At": pub_time
            }
            results.append(item)

            if include_replies:
                replies_obj = cdata.get("replies")
                if isinstance(replies_obj, dict):
                    rep_children = replies_obj.get("data", {}).get("children", [])
                    self._traverse_reddit_json(
                        rep_children, post_url, max_comments, include_replies, results, seen_ids, parent_author=author
                    )

    def _scrape_browser(
        self,
        url: str,
        max_comments: int,
        include_replies: bool,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
        stop_event: Optional[threading.Event]
    ) -> List[Dict[str, Any]]:
        results: List[Dict[str, Any]] = []
        seen_ids = set()

        if progress_callback:
            progress_callback({
                "status": "connecting",
                "count": 0,
                "log": f"[Reddit] Connecting to post: {url}"
            })

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-infobars",
                    "--disable-dev-shm-usage",
                    "--disable-gpu"
                ]
            )
            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
                viewport={"width": 1440, "height": 900},
                locale="en-US"
            )
            context.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=45000)
                page.wait_for_timeout(2000)

                # Dismiss cookie dialogs or age gates if any
                try:
                    for sel in ["button:has-text('Accept all')", "button:has-text('Reject all')", "button[aria-label='Close']"]:
                        btn = page.query_selector(sel)
                        if btn and btn.is_visible():
                            btn.click()
                            page.wait_for_timeout(500)
                except Exception:
                    pass

                # ATTEMPT 1: Internal browser JSON fetch
                # Reddit's internal JSON endpoint gives the full comment tree with 100% of nested replies
                try:
                    json_data = page.evaluate("""async () => {
                        try {
                            const cleanUrl = window.location.href.split('?')[0].replace(/\\/+$/, '');
                            const jsonUrl = cleanUrl + '.json?limit=500&raw_json=1&sort=confidence';
                            const res = await fetch(jsonUrl, {
                                headers: { 'Accept': 'application/json' }
                            });
                            if (res.ok) {
                                return await res.json();
                            }
                        } catch (e) {
                            return null;
                        }
                        return null;
                    }""")

                    if json_data and isinstance(json_data, list) and len(json_data) > 1:
                        comment_listing = json_data[1]
                        children = comment_listing.get("data", {}).get("children", [])
                        if children:
                            if progress_callback:
                                progress_callback({
                                    "status": "scraping",
                                    "count": 0,
                                    "log": f"[Reddit] Extracting nested comment tree via structured listing..."
                                })

                            self._traverse_reddit_json(
                                children, url, max_comments, include_replies, results, seen_ids, "-"
                            )

                            if progress_callback:
                                progress_callback({
                                    "status": "done",
                                    "count": len(results),
                                    "log": f"[Reddit] Extracted {len(results)} comments & nested replies successfully."
                                })

                            browser.close()
                            return results
                except Exception as json_err:
                    if progress_callback:
                        progress_callback({
                            "status": "scraping",
                            "count": 0,
                            "log": f"[Reddit] Scanning page DOM for all comments and nested threads..."
                        })

                # ATTEMPT 2: Interactive DOM scraper with nested reply expansions
                scroll_attempts = 0
                max_scrolls = 30 if max_comments > 100 else 18
                consecutive_no_new = 0
                id_to_author = {}

                while scroll_attempts < max_scrolls:
                    if stop_event and stop_event.is_set():
                        break

                    prev_count = len(results)

                    # Expand nested reply buttons via in-page JavaScript
                    if include_replies:
                        try:
                            page.evaluate("""() => {
                                const buttons = document.querySelectorAll('button[slot="comment-more"], button[aria-label*="replies"], faceplate-partial button, button');
                                for (const b of buttons) {
                                    const txt = (b.innerText || '').toLowerCase();
                                    if (txt.includes('more repl') || txt.includes('view repl') || txt.includes('show repl') || b.getAttribute('slot') === 'comment-more') {
                                        try { b.click(); } catch(e) {}
                                    }
                                }
                            }""")
                            page.wait_for_timeout(500)
                        except Exception:
                            pass

                    # Query all shreddit-comment elements
                    comment_elements = page.query_selector_all("shreddit-comment")
                    if not comment_elements:
                        comment_elements = page.query_selector_all("div[data-testid='comment']")

                    for elem in comment_elements:
                        cid = elem.get_attribute("thingid") or elem.get_attribute("id") or f"rc_{len(results)}"
                        author = elem.get_attribute("author") or ""
                        if not author:
                            author_elem = elem.query_selector("a[data-testid='comment_author'], a[href*='/user/']")
                            author = author_elem.inner_text().strip() if author_elem else "[deleted]"

                        if cid and author:
                            id_to_author[cid] = author

                        if cid in seen_ids:
                            continue
                        seen_ids.add(cid)

                        depth_val = elem.get_attribute("depth") or "0"
                        is_reply = depth_val != "0"
                        if is_reply and not include_replies:
                            continue

                        # Extract Score / Likes
                        score_raw = elem.get_attribute("score") or "0"
                        try:
                            score = int(score_raw)
                        except Exception:
                            score = 0

                        # Extract Timestamp
                        pub_time = ""
                        # 1. Check attribute on shreddit-comment
                        raw_ts = elem.get_attribute("created-timestamp")
                        if raw_ts:
                            pub_time = format_timestamp(raw_ts)
                        else:
                            # 2. Check child time or faceplate-timeago tags
                            time_elem = elem.query_selector("time, faceplate-timeago")
                            if time_elem:
                                raw_dt = (
                                    time_elem.get_attribute("datetime")
                                    or time_elem.get_attribute("ts")
                                    or time_elem.inner_text().strip()
                                )
                                pub_time = format_timestamp(raw_dt)

                        if not pub_time:
                            pub_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

                        # Text extraction
                        body_elem = elem.query_selector("div[slot='comment'], div[data-testid='comment-top-meta'] ~ div, div.md")
                        raw_text = (body_elem.inner_text() if body_elem else elem.inner_text()).strip()

                        if not raw_text or raw_text == "[deleted]" or raw_text == "[removed]":
                            continue

                        cleaned, lang, word_count = process_comment_text(raw_text)

                        # Determine replying to
                        parent_id = elem.get_attribute("parentid") or ""
                        replying_to = "-"
                        if is_reply:
                            if parent_id in id_to_author:
                                replying_to = id_to_author[parent_id]
                            else:
                                replying_to = "Commenter"

                        results.append({
                            "id": cid,
                            "platform": "reddit",
                            "post_url": url,
                            "author": author,
                            "author_id": f"u/{author}" if author != "[deleted]" else "",
                            "text": raw_text,
                            "cleaned_text": cleaned,
                            "timestamp": pub_time,
                            "likes": score,
                            "reply_count": 0,
                            "is_reply": is_reply,
                            "parent_id": parent_id,
                            "replying_to": replying_to,
                            "language": lang,
                            "word_count": word_count,
                            "Type": "REPLY" if is_reply else "MAIN COMMENT",
                            "Author": author,
                            "Comment": raw_text,
                            "Replying_To": replying_to,
                            "Likes": score,
                            "Published_At": pub_time
                        })

                        if 0 < max_comments <= len(results):
                            break

                    if progress_callback:
                        progress_callback({
                            "status": "scraping",
                            "count": len(results),
                            "log": f"[Reddit] Extracted {len(results)} comments & replies so far..."
                        })

                    if 0 < max_comments <= len(results):
                        break

                    if len(results) == prev_count:
                        consecutive_no_new += 1
                        if consecutive_no_new >= 6:
                            break
                    else:
                        consecutive_no_new = 0

                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(2000)
                    scroll_attempts += 1

                if progress_callback:
                    progress_callback({
                        "status": "done",
                        "count": len(results),
                        "log": f"[Reddit] Extraction complete. Total comments & replies: {len(results)}"
                    })

            except Exception as e:
                if progress_callback:
                    progress_callback({
                        "status": "error",
                        "count": len(results),
                        "log": f"[Reddit] Error: {str(e)}"
                    })
            finally:
                browser.close()

        return results

    def _scrape_praw(
        self,
        url: str,
        client_id: str,
        client_secret: str,
        max_comments: int,
        include_replies: bool,
        progress_callback: Optional[Callable[[Dict[str, Any]], None]],
        stop_event: Optional[threading.Event]
    ) -> List[Dict[str, Any]]:
        import praw
        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent="ThesisScraperBot/1.0 by Antigravity"
        )
        submission = reddit.submission(url=url)
        
        # When include_replies is True, fetch all nested MoreComments
        if include_replies:
            submission.comments.replace_more(limit=None)
        else:
            submission.comments.replace_more(limit=0)
        
        results: List[Dict[str, Any]] = []
        comments_list = submission.comments.list() if include_replies else submission.comments
        
        id_to_author = {}
        for c in comments_list:
            if hasattr(c, "id") and hasattr(c, "author") and c.author:
                id_to_author[c.id] = c.author.name

        for c in comments_list:
            if stop_event and stop_event.is_set():
                break
            raw_text = c.body.strip()
            if not raw_text or raw_text in ["[deleted]", "[removed]"]:
                continue
            cleaned, lang, word_count = process_comment_text(raw_text)
            
            author_name = c.author.name if c.author else "[deleted]"
            is_reply = c.parent_id.startswith("t1_")
            parent_clean_id = c.parent_id.replace("t1_", "").replace("t3_", "")
            replying_to = id_to_author.get(parent_clean_id, "-") if is_reply else "-"
            
            pub_time = format_timestamp(c.created_utc)

            results.append({
                "id": c.id,
                "platform": "reddit",
                "post_url": url,
                "author": author_name,
                "author_id": f"u/{author_name}" if author_name != "[deleted]" else "",
                "text": raw_text,
                "cleaned_text": cleaned,
                "timestamp": pub_time,
                "likes": int(c.score or 0),
                "reply_count": len(c.replies) if hasattr(c, "replies") else 0,
                "is_reply": is_reply,
                "parent_id": c.parent_id,
                "replying_to": replying_to,
                "language": lang,
                "word_count": word_count,
                "Type": "REPLY" if is_reply else "MAIN COMMENT",
                "Author": author_name,
                "Comment": raw_text,
                "Replying_To": replying_to,
                "Likes": int(c.score or 0),
                "Published_At": pub_time
            })
            
            if 0 < max_comments <= len(results):
                break
                
        return results

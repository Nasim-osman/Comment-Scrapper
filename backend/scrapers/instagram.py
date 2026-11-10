import time
import re
import threading
from datetime import datetime, timezone
from typing import List, Dict, Any, Callable, Optional
import dateparser
from playwright.sync_api import sync_playwright
from backend.scrapers.base import BaseScraper
from backend.services.cleaner import process_comment_text
from backend.services.session_store import get_instagram_session_path

def clean_ig_time(raw_ts: str) -> str:
    if not raw_ts:
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    s = raw_ts.strip()
    try:
        dt = dateparser.parse(s)
        if dt:
            return dt.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        pass
    return s

class InstagramScraper(BaseScraper):
    def __init__(self):
        super().__init__("instagram")

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
        
        session_path = get_instagram_session_path()
        
        if progress_callback:
            has_session_txt = "with saved session" if session_path else "in guest mode"
            progress_callback({
                "status": "connecting",
                "count": 0,
                "log": f"[Instagram] Connecting {has_session_txt} to: {url}"
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
                page.wait_for_timeout(3500)

                # Try to dismiss any blocking popup / cookie dialog
                try:
                    popup_close = page.query_selector("svg[aria-label='Close'], button:has-text('Not now'), button:has-text('Decline optional cookies'), div[role='dialog'] svg[aria-label='Close']")
                    if popup_close:
                        popup_close.click(timeout=1500)
                except Exception:
                    pass

                # Check if login wall blocked access
                if "accounts/login" in page.url or page.query_selector("input[name='username']"):
                    if not session_path:
                        if progress_callback:
                            progress_callback({
                                "status": "warning",
                                "count": 0,
                                "log": "[Instagram] Meta login wall encountered. Please click 'Session & Accounts' at the top to log in once for full access."
                            })

                scroll_rounds = 0
                max_rounds = 20 if max_comments > 100 else 10
                consecutive_no_new = 0

                while scroll_rounds < max_rounds:
                    if stop_event and stop_event.is_set():
                        break

                    prev_count = len(results)

                    # Click "Load more comments" or "+" buttons if present
                    try:
                        load_buttons = page.query_selector_all("button:has(svg[aria-label='Load more comments']), button:has-text('Load more comments'), button:has-text('View all comments')")
                        for btn in load_buttons[:2]:
                            btn.click(timeout=1500)
                            page.wait_for_timeout(800)
                    except Exception:
                        pass

                    # Method 1: Modern Instagram DOM evaluation
                    try:
                        raw_items = page.evaluate("""() => {
                            const items = [];
                            const allLinks = Array.from(document.querySelectorAll('a[role="link"], a[href^="/"]'));
                            for (const link of allLinks) {
                                const href = link.getAttribute('href') || '';
                                const parts = href.split('/').filter(Boolean);
                                if (parts.length === 1 && !['explore', 'reels', 'direct', 'stories', 'accounts', 'legal', 'p'].includes(parts[0])) {
                                    const author = link.innerText.trim();
                                    if (!author || author.startsWith('#')) continue;
                                    
                                    let container = link.closest('li') || link.parentElement;
                                    for (let step = 0; step < 5; step++) {
                                        if (!container) break;
                                        const spans = Array.from(container.querySelectorAll('span'))
                                            .map(s => s.innerText.trim())
                                            .filter(t => t.length > 0 && t !== author && !['Like', 'Reply', 'Liked', 'See translation'].includes(t));
                                            
                                        const textCandidate = spans.find(t => !t.includes('\\n') && !/^\\d+[wdhm]$/.test(t) && !/^\\d+ likes?$/.test(t));
                                        if (textCandidate && textCandidate.length >= 2) {
                                            const timeElem = container.querySelector("time");
                                            const timestamp = timeElem ? (timeElem.getAttribute("datetime") || timeElem.innerText.trim()) : "";
                                            items.push({ author, text: textCandidate, timestamp });
                                            break;
                                        }
                                        container = container.parentElement;
                                    }
                                }
                            }
                            return items;
                        }""")
                        for item in raw_items:
                            author = item.get("author", "Instagram User")
                            raw_text = item.get("text", "")
                            if not raw_text or len(raw_text) < 2:
                                continue
                            if author.lower().replace('@', '') == raw_text.lower().replace('@', ''):
                                continue
                            dedup_key = f"{author}_{raw_text[:30]}"
                            if dedup_key in seen_texts:
                                continue
                            seen_texts.add(dedup_key)

                            cleaned, lang, word_count = process_comment_text(raw_text)
                            pub_time = clean_ig_time(item.get("timestamp", ""))
                            results.append({
                                "id": f"ig_{len(results)+1}",
                                "platform": "instagram",
                                "post_url": url,
                                "author": author,
                                "author_id": f"https://instagram.com/{author}",
                                "text": raw_text,
                                "cleaned_text": cleaned,
                                "timestamp": pub_time,
                                "likes": 0,
                                "reply_count": 0,
                                "is_reply": False,
                                "parent_id": None,
                                "replying_to": "-",
                                "language": lang,
                                "word_count": word_count,
                                "Type": "MAIN COMMENT",
                                "Author": author,
                                "Comment": raw_text,
                                "Replying_To": "-",
                                "Likes": 0,
                                "Published_At": pub_time
                            })
                            if 0 < max_comments <= len(results):
                                break
                    except Exception:
                        pass

                    # Method 2: Query legacy/modal comment elements
                    if len(results) < max_comments:
                        comment_nodes = page.query_selector_all("ul ul, div[role='dialog'] ul > li, article ul > div > li, ul > div > li, li[role='menuitem']")
                        for node in comment_nodes:
                            try:
                                author_elem = node.query_selector("h3 a, span a, a[role='link']")
                                author = author_elem.inner_text().strip() if author_elem else "Instagram User"

                                text_elem = node.query_selector("span[dir='auto'], span._ap3a")
                                raw_text = text_elem.inner_text().strip() if text_elem else ""

                                if not raw_text or len(raw_text) < 2 or author.lower().replace('@', '') == raw_text.lower().replace('@', ''):
                                    continue

                                dedup_key = f"{author}_{raw_text[:30]}"
                                if dedup_key in seen_texts:
                                    continue
                                seen_texts.add(dedup_key)

                                time_elem = node.query_selector("time")
                                timestamp = time_elem.get_attribute("datetime") or time_elem.inner_text().strip() if time_elem else ""

                                likes = 0
                                likes_elem = node.query_selector("button:has-text('like'), span:has-text('likes')")
                                if likes_elem:
                                    txt = likes_elem.inner_text()
                                    num_match = [int(s) for s in txt.split() if s.isdigit()]
                                    if num_match:
                                        likes = num_match[0]

                                cleaned, lang, word_count = process_comment_text(raw_text)

                                pub_time = clean_ig_time(timestamp)
                                results.append({
                                    "id": f"ig_{len(results)+1}",
                                    "platform": "instagram",
                                    "post_url": url,
                                    "author": author,
                                    "author_id": f"https://instagram.com/{author}",
                                    "text": raw_text,
                                    "cleaned_text": cleaned,
                                    "timestamp": pub_time,
                                    "likes": likes,
                                    "reply_count": 0,
                                    "is_reply": False,
                                    "parent_id": None,
                                    "replying_to": "-",
                                    "language": lang,
                                    "word_count": word_count,
                                    "Type": "MAIN COMMENT",
                                    "Author": author,
                                    "Comment": raw_text,
                                    "Replying_To": "-",
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
                            "log": f"[Instagram] Extracted {len(results)} comments..."
                        })

                    if 0 < max_comments <= len(results):
                        break

                    # Check for early completion: if no new comments after checking
                    if len(results) == prev_count:
                        consecutive_no_new += 1
                        if consecutive_no_new >= 2:
                            break
                    else:
                        consecutive_no_new = 0

                    # Scroll comment container or page
                    page.evaluate("""() => {
                        const dialog = document.querySelector('div[role="dialog"] ul') || document.querySelector('article ul');
                        if (dialog) dialog.scrollTop += 1500;
                        window.scrollBy(0, 1000);
                    }""")
                    page.wait_for_timeout(1500)
                    scroll_rounds += 1

                if progress_callback:
                    progress_callback({
                        "status": "done",
                        "count": len(results),
                        "log": f"[Instagram] Extraction finished. Total comments: {len(results)}"
                    })

            except Exception as e:
                if progress_callback:
                    progress_callback({
                        "status": "error",
                        "count": len(results),
                        "log": f"[Instagram] Scraper error: {str(e)}"
                    })
            finally:
                browser.close()

        return results

import re
from typing import Tuple

# Regex patterns
URL_PATTERN = re.compile(r'https?://\S+|www\.\S+')
MENTION_PATTERN = re.compile(r'@[\w.-]+')
HASHTAG_PATTERN = re.compile(r'#[\w.-]+')
MULTIPLE_SPACES = re.compile(r'\s+')
MULTIPLE_NEWLINES = re.compile(r'\n{2,}')

# Bengali Unicode Range: \u0980 to \u09FF
BANGLA_CHAR_PATTERN = re.compile(r'[\u0980-\u09FF]')
ENGLISH_CHAR_PATTERN = re.compile(r'[a-zA-Z]')

def detect_language(text: str) -> str:
    """
    Detects whether the comment is Bengali, English, Mixed (Banglish/both), or Other.
    Crucial for Bengali NLP & Multilingual Thesis datasets.
    """
    if not text:
        return "unknown"
    
    has_bangla = bool(BANGLA_CHAR_PATTERN.search(text))
    has_english = bool(ENGLISH_CHAR_PATTERN.search(text))

    if has_bangla and has_english:
        return "mixed"
    elif has_bangla:
        return "bn"
    elif has_english:
        return "en"
    else:
        return "other"

def clean_text_for_nlp(text: str, remove_urls: bool = True, remove_mentions: bool = False, keep_emojis: bool = True) -> str:
    """
    Preprocesses raw social media comment text for academic thesis & NLP models:
    - Removes URLs
    - Normalizes Bengali characters & zero-width artifacts (\u200b, \u200c, \u200d)
    - Strips unwanted control characters
    - Normalizes repeated whitespaces and newlines
    """
    if not text:
        return ""
    
    cleaned = text
    
    # Remove URLs
    if remove_urls:
        cleaned = URL_PATTERN.sub(' ', cleaned)
        
    if remove_mentions:
        cleaned = MENTION_PATTERN.sub(' ', cleaned)
        
    # Remove invisible zero-width chars commonly causing tokenizer bugs
    cleaned = re.sub(r'[\u200B-\u200D\uFEFF]', '', cleaned)
    
    # Normalize multiple whitespace
    cleaned = MULTIPLE_SPACES.sub(' ', cleaned)
    
    return cleaned.strip()

def process_comment_text(raw_text: str) -> Tuple[str, str, int]:
    """
    Returns (cleaned_text, detected_language, word_count)
    """
    if not raw_text:
        return "", "unknown", 0
        
    cleaned = clean_text_for_nlp(raw_text)
    lang = detect_language(cleaned)
    # Word count estimation (split by whitespace)
    words = cleaned.split()
    word_count = len(words)
    
    return cleaned, lang, word_count

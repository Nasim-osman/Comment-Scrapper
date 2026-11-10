from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field
import datetime

class CommentItem(BaseModel):
    id: str = Field(default="", description="Unique identifier for the comment")
    platform: str = Field(..., description="Platform: youtube, reddit, instagram, facebook")
    post_url: str = Field(..., description="Source post or video URL")
    author: str = Field(default="Anonymous", description="Username or author name")
    author_id: Optional[str] = Field(default=None, description="Profile ID or channel URL")
    text: str = Field(..., description="Raw comment text")
    cleaned_text: Optional[str] = Field(default="", description="Preprocessed text for NLP / sentiment analysis")
    timestamp: str = Field(default="", description="Comment timestamp or relative time string")
    likes: int = Field(default=0, description="Like or upvote count")
    reply_count: int = Field(default=0, description="Number of replies")
    is_reply: bool = Field(default=False, description="Whether this is a nested reply")
    parent_id: Optional[str] = Field(default=None, description="Parent comment ID if reply")
    language: str = Field(default="unknown", description="Detected language: bn, en, mixed, other")
    word_count: int = Field(default=0, description="Word count in comment text")

class ScrapeRequest(BaseModel):
    urls: List[str] = Field(..., description="List of post/video URLs to scrape")
    platform: Optional[str] = Field(default="auto", description="youtube, reddit, instagram, facebook, or auto")
    max_comments_per_url: int = Field(default=200, description="Maximum comments to fetch per URL (0 for all)")
    include_replies: bool = Field(default=True, description="Whether to fetch nested replies")
    clean_text: bool = Field(default=True, description="Preprocess text for NLP (remove excessive spaces, urls, etc.)")
    filter_bangla_only: bool = Field(default=False, description="Keep only comments containing Bengali text")
    min_length: int = Field(default=1, description="Minimum comment length in characters")

class JobSummary(BaseModel):
    job_id: str
    status: str  # queued, running, completed, stopped, failed
    platform: str
    total_comments: int
    progress: float
    current_status_text: str
    urls_count: int
    created_at: str
    completed_at: Optional[str] = None
    error: Optional[str] = None

class SessionStatus(BaseModel):
    facebook_logged_in: bool
    instagram_logged_in: bool
    twitter_logged_in: bool = False
    reddit_api_configured: bool
    youtube_api_configured: bool

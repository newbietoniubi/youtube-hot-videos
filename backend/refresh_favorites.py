#!/usr/bin/env python3
"""
Scheduled script to refresh view counts for favorited videos.
Designed to be run by GitHub Actions every 12 hours.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).resolve().parent))

import requests
from dotenv import load_dotenv

from db import get_active_favorites_for_tracking, record_view_count

load_dotenv()

API_KEY = os.getenv("API_KEY")
YOUTUBE_VIDEOS_API = "https://www.googleapis.com/youtube/v3/videos"


def fetch_video_stats(video_ids: list[str]) -> dict[str, dict]:
    """Fetch current stats for a batch of videos (max 50)."""
    if not video_ids:
        return {}
    
    params = {
        "key": API_KEY,
        "part": "statistics",
        "id": ",".join(video_ids),
    }
    
    resp = requests.get(YOUTUBE_VIDEOS_API, params=params, timeout=15)
    if resp.status_code != 200:
        print(f"❌ YouTube API error: {resp.status_code} {resp.text}")
        return {}
    
    data = resp.json()
    result = {}
    for item in data.get("items", []):
        stats = item.get("statistics", {})
        result[item["id"]] = {
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        }
    
    return result


def refresh_favorites():
    """Main function to refresh all active favorites."""
    if not API_KEY:
        print("❌ API_KEY not configured")
        sys.exit(1)
    
    # Get favorites that are still within tracking period (2 weeks)
    favorites = get_active_favorites_for_tracking()
    
    if not favorites:
        print("ℹ️ No active favorites to track (empty or all expired)")
        return
    
    print(f"📊 Refreshing {len(favorites)} favorites...")
    
    # Batch video IDs (YouTube API allows up to 50 per request)
    video_ids = [f["video_id"] for f in favorites]
    batch_size = 50
    total_updated = 0
    
    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i:i + batch_size]
        stats = fetch_video_stats(batch)
        
        for video_id, video_stats in stats.items():
            record_view_count(
                video_id=video_id,
                view_count=video_stats["view_count"],
                like_count=video_stats["like_count"],
                comment_count=video_stats["comment_count"],
            )
            total_updated += 1
    
    print(f"✅ Updated {total_updated} videos")


if __name__ == "__main__":
    refresh_favorites()

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


def export_to_json():
    """Export favorites data to JSON file for frontend consumption."""
    import json
    from db import get_favorites, get_view_history
    
    favorites = get_favorites()
    output = []
    
    for fav in favorites:
        video_id = fav["video_id"]
        history = get_view_history(video_id, limit=100)
        
        # Get latest stats
        latest = history[0] if history else {}
        
        output.append({
            "video_id": video_id,
            "title": fav.get("title", ""),
            "channel_id": fav.get("channel_id", ""),
            "channel_title": fav.get("channel_title", ""),
            "thumbnail_url": fav.get("thumbnail_url", ""),
            "created_at": fav.get("created_at", ""),
            "latest_view_count": latest.get("view_count"),
            "latest_like_count": latest.get("like_count"),
            "latest_comment_count": latest.get("comment_count"),
            "last_updated": latest.get("recorded_at"),
            "history": [
                {
                    "view_count": h["view_count"],
                    "like_count": h.get("like_count"),
                    "comment_count": h.get("comment_count"),
                    "recorded_at": h["recorded_at"]
                }
                for h in history
            ]
        })
    
    # Write to project root
    output_path = Path(__file__).resolve().parent.parent / "favorites_data.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"favorites": output, "updated_at": datetime.now(timezone.utc).isoformat()}, f, ensure_ascii=False, indent=2)
    
    print(f"📦 Exported {len(output)} favorites to {output_path}")


if __name__ == "__main__":
    refresh_favorites()
    export_to_json()

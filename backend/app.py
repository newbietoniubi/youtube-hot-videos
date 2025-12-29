from __future__ import annotations
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List

import requests
from dotenv import load_dotenv
from flask import Flask, jsonify, request
from flask_cors import CORS

load_dotenv()

API_KEY = os.getenv("API_KEY")
HOST = os.getenv("HOST", "127.0.0.1")
PORT = int(os.getenv("PORT", "5000"))
ROOT_DIR = Path(__file__).resolve().parents[1]
DATA_FILE = ROOT_DIR / "shorts.json"
PREVIEW_FILE = ROOT_DIR / "shorts.preview.json"

app = Flask(__name__)
CORS(app)

DURATION_RE = re.compile(
    r"PT"  # prefix
    r"(?:(?P<hours>\d+)H)?"
    r"(?:(?P<minutes>\d+)M)?"
    r"(?:(?P<seconds>\d+)S)?",
    re.IGNORECASE,
)


def parse_iso_duration(duration: str) -> int:
    match = DURATION_RE.fullmatch(duration)
    if not match:
        return 0
    hours = int(match.group("hours") or 0)
    minutes = int(match.group("minutes") or 0)
    seconds = int(match.group("seconds") or 0)
    return hours * 3600 + minutes * 60 + seconds


def build_published_after(days: int | None) -> str | None:
    if not days:
        return None
    now = datetime.now(timezone.utc)
    target = now - timedelta(days=days)
    return target.isoformat().replace("+00:00", "Z")

def fetch_shorts(keywords: str, max_results: int, days: int | None, region: str | None = None) -> List[Dict]:
    if not API_KEY:
        raise RuntimeError("API_KEY is not configured in environment")

    collected: List[Dict] = []
    page_token = None
    published_after = build_published_after(days)
    per_page = 50

    while len(collected) < max_results:
        search_params = {
            "key": API_KEY,
            "part": "snippet",
            "type": "video",
            "q": keywords,
            "maxResults": per_page,
            "order": "viewCount",
            "videoDuration": "short",
        }
        if region:
            search_params["regionCode"] = region
        if published_after:
            search_params["publishedAfter"] = published_after
        if page_token:
            search_params["pageToken"] = page_token

        search_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search", params=search_params, timeout=15
        )
        if search_resp.status_code != 200:
            raise RuntimeError(f"YouTube search failed: {search_resp.status_code} {search_resp.text}")
        search_data = search_resp.json()
        video_ids = [item["id"].get("videoId") for item in search_data.get("items", [])]
        video_ids = [vid for vid in video_ids if vid]
        if not video_ids:
            break

        details_params = {
            "key": API_KEY,
            "part": "snippet,contentDetails,statistics",
            "id": ",".join(video_ids),
            "maxResults": per_page,
        }
        details_resp = requests.get(
            "https://www.googleapis.com/youtube/v3/videos", params=details_params, timeout=15
        )
        if details_resp.status_code != 200:
            raise RuntimeError(
                f"YouTube videos lookup failed: {details_resp.status_code} {details_resp.text}"
            )
        details_data = details_resp.json()
        for item in details_data.get("items", []):
            duration_seconds = parse_iso_duration(
                item.get("contentDetails", {}).get("duration", "")
            )
            if duration_seconds <= 0 or duration_seconds > 60:
                continue

            stats = item.get("statistics", {})
            snippet = item.get("snippet", {})
            collected.append(
                {
                    "video_id": item.get("id"),
                    "title": snippet.get("title", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": snippet.get("publishedAt", ""),
                    "duration_seconds": duration_seconds,
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "tags": snippet.get("tags", []),
                }
            )
            if len(collected) >= max_results:
                break

        page_token = search_data.get("nextPageToken")
        if not page_token:
            break

    return sorted(collected, key=lambda x: x.get('view_count', 0), reverse=True)[:max_results]


def fetch_video_stats(video_ids: List[str]) -> Dict[str, Dict]:
    if not video_ids:
        return {}
    params = {
        "key": API_KEY,
        "part": "statistics",
        "id": ",".join(video_ids),
    }
    resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=15)
    if resp.status_code != 200:
        raise RuntimeError(f"YouTube videos lookup failed: {resp.status_code} {resp.text}")
    data = resp.json()
    result: Dict[str, Dict] = {}
    for item in data.get("items", []):
        stats = item.get("statistics", {})
        result[item.get("id")] = {
            "view_count": int(stats.get("viewCount", 0)),
            "like_count": int(stats.get("likeCount", 0)),
            "comment_count": int(stats.get("commentCount", 0)),
        }
    return result


def save_data(records: List[Dict]) -> Dict:
    DATA_FILE.write_text(json.dumps(records, ensure_ascii=False, indent=2), encoding="utf-8")
    preview = records[:3]
    PREVIEW_FILE.write_text(json.dumps(preview, ensure_ascii=False, indent=2), encoding="utf-8")
    return {
        "data_file": str(DATA_FILE),
        "preview_file": str(PREVIEW_FILE),
        "saved": len(records),
        "preview_count": len(preview),
    }


@app.route("/collect", methods=["POST"])
def collect():
    payload = request.get_json(silent=True) or {}
    keywords = (payload.get("keywords") or "").strip()
    keyword_list_raw = payload.get("keyword_list") or []
    if isinstance(keyword_list_raw, str):
        keyword_list_raw = [keyword_list_raw]
    keyword_list = [k.strip() for k in keyword_list_raw if isinstance(k, str) and k.strip()]
    deduped: List[str] = []
    seen = set()
    for kw in keyword_list:
        key = kw.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(kw)
    keyword_list = deduped

    max_results = int(payload.get("max_results") or 20)
    days = payload.get("days")
    days_int = int(days) if days not in (None, "",) else 7
    region_raw = (payload.get("region") or "").strip().upper()
    region = None if not region_raw or region_raw == "ALL" else region_raw

    if not keyword_list and keywords:
        keyword_list = [keywords]
    if not keyword_list:
        return jsonify({"error": "keywords is required"}), 400
    if max_results < 1 or max_results > 10000:
        return jsonify({"error": "max_results must be between 1 and 10000"}), 400
    if days_int is not None and days_int < 0:
        return jsonify({"error": "days must be non-negative"}), 400

    try:
        merged: Dict[str, Dict] = {}
        for kw in keyword_list:
            part = fetch_shorts(kw, max_results, days_int, region)
            for item in part:
                vid = item.get("video_id")
                if not vid:
                    continue
                existing = merged.get(vid)
                if not existing or item.get("view_count", 0) > existing.get("view_count", 0):
                    merged[vid] = item
        records = sorted(merged.values(), key=lambda x: x.get("view_count", 0), reverse=True)[:max_results]
        summary = save_data(records)
        return jsonify({"total": len(records), "keywords_used": keyword_list, **summary})
    except Exception as exc:  # broad to surface API errors
        return jsonify({"error": str(exc)}), 500


# ============ Favorites API ============

@app.route("/favorites", methods=["GET"])
def get_favorites_list():
    """Get all favorites with history."""
    from db import get_favorites, get_view_history
    
    favorites = get_favorites()
    # Attach latest stats and history to each favorite
    for fav in favorites:
        history = get_view_history(fav["video_id"], limit=100)
        if history:
            fav["latest_view_count"] = history[0]["view_count"]
            fav["latest_like_count"] = history[0]["like_count"]
            fav["last_updated"] = history[0]["recorded_at"]
        fav["history"] = history  # Include full history for chart rendering
    
    return jsonify({"favorites": favorites, "total": len(favorites)})


@app.route("/favorites", methods=["POST"])
def add_favorite():
    """Add a video to favorites."""
    from db import add_favorite as db_add_favorite, record_view_count
    
    payload = request.get_json(silent=True) or {}
    video_id = payload.get("video_id")
    
    if not video_id:
        return jsonify({"error": "video_id is required"}), 400
    
    result = db_add_favorite(
        video_id=video_id,
        title=payload.get("title", ""),
        channel_id=payload.get("channel_id", ""),
        channel_title=payload.get("channel_title", ""),
        thumbnail_url=payload.get("thumbnail_url", ""),
        published_at=payload.get("published_at", "")
    )
    
    # Record initial view count if provided
    view_count = payload.get("view_count")
    if view_count is not None:
        record_view_count(
            video_id=video_id,
            view_count=int(view_count),
            like_count=payload.get("like_count"),
            comment_count=payload.get("comment_count")
        )
    
    return jsonify(result)


@app.route("/favorites/refresh", methods=["POST"])
def refresh_favorites():
    """Refresh stats for all active favorites."""
    if not API_KEY:
        return jsonify({"error": "API_KEY is not configured in environment"}), 500

    from db import get_favorites, record_view_count

    favorites = get_favorites()
    video_ids = [fav.get("video_id") for fav in favorites if fav.get("video_id")]
    if not video_ids:
        return jsonify({"total": 0, "updated": 0, "missing": []})

    batch_size = 50
    updated = 0
    missing: List[str] = []

    for i in range(0, len(video_ids), batch_size):
        batch = video_ids[i:i + batch_size]
        stats = fetch_video_stats(batch)
        for video_id in batch:
            video_stats = stats.get(video_id)
            if not video_stats:
                missing.append(video_id)
                continue
            record_view_count(
                video_id=video_id,
                view_count=video_stats["view_count"],
                like_count=video_stats.get("like_count"),
                comment_count=video_stats.get("comment_count"),
            )
            updated += 1

    return jsonify({"total": len(video_ids), "updated": updated, "missing": missing})


@app.route("/favorites/<video_id>", methods=["DELETE"])
def remove_favorite(video_id: str):
    """Remove a video from favorites."""
    from db import remove_favorite as db_remove_favorite
    
    result = db_remove_favorite(video_id)
    return jsonify(result)


@app.route("/favorites/<video_id>/history", methods=["GET"])
def get_favorite_history(video_id: str):
    """Get view count history for a favorited video."""
    from db import get_view_history, get_favorite_with_latest_stats
    
    favorite = get_favorite_with_latest_stats(video_id)
    if not favorite:
        return jsonify({"error": "Favorite not found"}), 404
    
    history = get_view_history(video_id)
    
    return jsonify({
        "video": favorite,
        "history": history
    })


if __name__ == "__main__":
    app.run(host=HOST, port=PORT)

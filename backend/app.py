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


def within_days(published_at: str, days: int | None) -> bool:
    if not days:
        return True
    try:
        dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
    except Exception:
        return True
    return dt >= datetime.now(timezone.utc) - timedelta(days=days)


def fetch_most_popular(max_results: int, days: int | None, region: str = "US") -> List[Dict]:
    collected: List[Dict] = []
    page_token = None
    per_page = 50

    while len(collected) < max_results:
        params = {
            "key": API_KEY,
            "part": "snippet,contentDetails,statistics",
            "chart": "mostPopular",
            "regionCode": region,
            "maxResults": per_page,
        }
        if page_token:
            params["pageToken"] = page_token

        resp = requests.get("https://www.googleapis.com/youtube/v3/videos", params=params, timeout=15)
        if resp.status_code != 200:
            raise RuntimeError(f"YouTube mostPopular failed: {resp.status_code} {resp.text}")
        data = resp.json()

        for item in data.get("items", []):
            snippet = item.get("snippet", {})
            published_at = snippet.get("publishedAt", "")
            if days and not within_days(published_at, days):
                continue
            duration_seconds = parse_iso_duration(item.get("contentDetails", {}).get("duration", ""))
            if duration_seconds <= 0 or duration_seconds > 60:
                continue
            stats = item.get("statistics", {})
            collected.append(
                {
                    "video_id": item.get("id"),
                    "title": snippet.get("title", ""),
                    "channel_id": snippet.get("channelId", ""),
                    "channel_title": snippet.get("channelTitle", ""),
                    "published_at": published_at,
                    "duration_seconds": duration_seconds,
                    "view_count": int(stats.get("viewCount", 0)),
                    "like_count": int(stats.get("likeCount", 0)),
                    "comment_count": int(stats.get("commentCount", 0)),
                    "tags": snippet.get("tags", []),
                }
            )
            if len(collected) >= max_results:
                break

        page_token = data.get("nextPageToken")
        if not page_token:
            break

    # 如果按天过滤后数量不足，再放宽天数重取
    if len(collected) < max_results and days:
        return fetch_most_popular(max_results, None, region)

    return sorted(collected, key=lambda x: x.get("view_count", 0), reverse=True)[:max_results]





def fetch_shorts(keywords: str, max_results: int, days: int | None, region: str = "US") -> List[Dict]:
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
    max_results = int(payload.get("max_results") or 100)
    days = payload.get("days")
    days_int = int(days) if days not in (None, "",) else 7
    region = (payload.get("region") or "US").strip().upper()

    if not keywords:
        return jsonify({"error": "keywords is required"}), 400
    if max_results < 1 or max_results > 10000:
        return jsonify({"error": "max_results must be between 1 and 10000"}), 400
    if days_int is not None and days_int < 0:
        return jsonify({"error": "days must be non-negative"}), 400
    if not region:
        region = "US"

    try:
        records = fetch_shorts(keywords, max_results, days_int, region)
        summary = save_data(records)
        return jsonify({"total": len(records), **summary})
    except Exception as exc:  # broad to surface API errors
        return jsonify({"error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host=HOST, port=PORT)

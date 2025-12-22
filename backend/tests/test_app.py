"""Unit tests for app.py core functions."""
from __future__ import annotations

import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app import (
    parse_iso_duration,
    build_published_after,
    within_days,
)


class TestParseIsoDuration:
    """Tests for parse_iso_duration function."""

    def test_seconds_only(self):
        assert parse_iso_duration("PT30S") == 30
        assert parse_iso_duration("PT1S") == 1
        assert parse_iso_duration("PT59S") == 59

    def test_minutes_only(self):
        assert parse_iso_duration("PT1M") == 60
        assert parse_iso_duration("PT2M") == 120

    def test_minutes_and_seconds(self):
        assert parse_iso_duration("PT1M30S") == 90
        assert parse_iso_duration("PT2M15S") == 135

    def test_hours(self):
        assert parse_iso_duration("PT1H") == 3600
        assert parse_iso_duration("PT1H30M") == 5400
        assert parse_iso_duration("PT1H30M45S") == 5445

    def test_invalid_format(self):
        assert parse_iso_duration("") == 0
        assert parse_iso_duration("invalid") == 0
        assert parse_iso_duration("P1D") == 0  # Days not supported
        assert parse_iso_duration("1M30S") == 0  # Missing PT prefix

    def test_case_insensitive(self):
        assert parse_iso_duration("pt1m30s") == 90
        assert parse_iso_duration("PT1m30S") == 90


class TestBuildPublishedAfter:
    """Tests for build_published_after function."""

    def test_none_days(self):
        assert build_published_after(None) is None

    def test_zero_days(self):
        assert build_published_after(0) is None

    def test_positive_days(self):
        result = build_published_after(7)
        assert result is not None
        assert result.endswith("Z")
        # Verify it's approximately 7 days ago
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        expected = datetime.now(timezone.utc) - timedelta(days=7)
        # Allow 1 minute tolerance
        assert abs((parsed - expected).total_seconds()) < 60

    def test_format_is_iso(self):
        result = build_published_after(1)
        # Should be parseable as ISO format
        parsed = datetime.fromisoformat(result.replace("Z", "+00:00"))
        assert isinstance(parsed, datetime)


class TestWithinDays:
    """Tests for within_days function."""

    def test_none_days_always_true(self):
        assert within_days("2020-01-01T00:00:00Z", None) is True
        assert within_days("2025-12-01T00:00:00Z", None) is True

    def test_recent_date_within_days(self):
        # A date from 1 day ago should be within 7 days
        recent = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat().replace("+00:00", "Z")
        assert within_days(recent, 7) is True

    def test_old_date_outside_days(self):
        # A date from 30 days ago should NOT be within 7 days
        old = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat().replace("+00:00", "Z")
        assert within_days(old, 7) is False

    def test_boundary_exactly_on_edge(self):
        # Exactly 7 days ago (with some tolerance)
        edge = (datetime.now(timezone.utc) - timedelta(days=7, seconds=1)).isoformat().replace("+00:00", "Z")
        assert within_days(edge, 7) is False

    def test_invalid_date_returns_true(self):
        # Invalid dates should return True (permissive behavior)
        assert within_days("not-a-date", 7) is True
        assert within_days("", 7) is True


class TestCollectEndpoint:
    """Tests for /collect API endpoint."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_missing_keywords_returns_400(self, client):
        response = client.post('/collect', json={})
        assert response.status_code == 400
        assert b'keywords is required' in response.data

    def test_empty_keywords_returns_400(self, client):
        response = client.post('/collect', json={'keywords': ''})
        assert response.status_code == 400

    def test_invalid_max_results_returns_400(self, client):
        # Note: max_results=0 is treated as "use default (20)" due to `or 20` logic
        # So we test with values that are explicitly out of range
        response = client.post('/collect', json={
            'keywords': 'test',
            'max_results': 10001  # Over the limit
        })
        assert response.status_code == 400

    def test_negative_days_returns_400(self, client):
        response = client.post('/collect', json={
            'keywords': 'test',
            'days': -1
        })
        assert response.status_code == 400


class TestDeduplication:
    """Tests for video deduplication logic when using multiple keywords."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        from app import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client

    def test_duplicate_video_ids_are_merged(self, client):
        """When same video appears in multiple keyword searches, keep only one."""
        # Mock data: same video_id appears in both keyword results
        mock_video_a = {
            "video_id": "video_123",
            "title": "Test Video",
            "channel_id": "channel_1",
            "channel_title": "Test Channel",
            "published_at": "2025-12-20T00:00:00Z",
            "duration_seconds": 30,
            "view_count": 1000,
            "like_count": 100,
            "comment_count": 10,
            "tags": [],
        }
        mock_video_b = {
            "video_id": "video_456",
            "title": "Another Video",
            "channel_id": "channel_2",
            "channel_title": "Another Channel",
            "published_at": "2025-12-20T00:00:00Z",
            "duration_seconds": 45,
            "view_count": 2000,
            "like_count": 200,
            "comment_count": 20,
            "tags": [],
        }

        def mock_fetch_shorts(keywords, max_results, days, region):
            if "keyword1" in keywords:
                return [mock_video_a, mock_video_b]
            elif "keyword2" in keywords:
                # Return same video_a again (duplicate)
                return [mock_video_a]
            return []

        with patch('app.fetch_shorts', side_effect=mock_fetch_shorts):
            with patch('app.save_data', return_value={"data_file": "test", "preview_file": "test", "saved": 2, "preview_count": 2}):
                response = client.post('/collect', json={
                    'keyword_list': ['keyword1', 'keyword2'],
                    'max_results': 10
                })

        assert response.status_code == 200
        data = response.get_json()
        # Should have 2 unique videos, not 3
        assert data['total'] == 2

    def test_different_video_ids_all_kept(self, client):
        """Different video_ids from multiple keywords are all kept."""
        mock_videos = [
            {"video_id": f"video_{i}", "title": f"Video {i}", "view_count": i * 100,
             "channel_id": "ch", "channel_title": "Ch", "published_at": "2025-12-20T00:00:00Z",
             "duration_seconds": 30, "like_count": 10, "comment_count": 1, "tags": []}
            for i in range(5)
        ]

        def mock_fetch_shorts(keywords, max_results, days, region):
            if "kw1" in keywords:
                return mock_videos[:3]
            elif "kw2" in keywords:
                return mock_videos[3:]
            return []

        with patch('app.fetch_shorts', side_effect=mock_fetch_shorts):
            with patch('app.save_data', return_value={"data_file": "test", "preview_file": "test", "saved": 5, "preview_count": 3}):
                response = client.post('/collect', json={
                    'keyword_list': ['kw1', 'kw2'],
                    'max_results': 10
                })

        assert response.status_code == 200
        data = response.get_json()
        # All 5 unique videos should be kept
        assert data['total'] == 5


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

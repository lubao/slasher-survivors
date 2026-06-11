"""Unit tests for the game's backend ApiClient using mocked requests."""
from unittest.mock import MagicMock, patch

import requests

from src.api_client import ApiClient


def _resp(status=200, json_data=None):
    m = MagicMock()
    m.status_code = status
    m.json.return_value = json_data or {}
    if status >= 400:
        m.raise_for_status.side_effect = requests.HTTPError("boom")
    else:
        m.raise_for_status.return_value = None
    return m


def test_submit_score_posts_expected_payload():
    client = ApiClient(base_url="http://test")
    with patch("src.api_client.requests.post", return_value=_resp(200)) as post:
        results = {}
        t = client.submit_score("alice", {"score": 100, "kills": 9, "survival_seconds": 42},
                                on_done=lambda ok: results.update(ok=ok))
        t.join(timeout=2)

    post.assert_called_once()
    _, kwargs = post.call_args
    assert kwargs["json"] == {
        "nickname": "alice", "score": 100, "kills": 9, "survival_seconds": 42,
    }
    assert results["ok"] is True


def test_submit_score_offline_reports_failure_without_raising():
    client = ApiClient(base_url="http://test")
    with patch("src.api_client.requests.post",
               side_effect=requests.ConnectionError("offline")):
        captured = {}
        t = client.submit_score("bob", {"score": 1, "kills": 0, "survival_seconds": 1},
                                on_done=lambda ok: captured.update(ok=ok))
        t.join(timeout=2)
    assert captured["ok"] is False


def test_get_leaderboard_parses_entries():
    client = ApiClient(base_url="http://test")
    data = {"entries": [{"nickname": "a", "score": 50}, {"nickname": "b", "score": 30}]}
    with patch("src.api_client.requests.get", return_value=_resp(200, data)):
        entries = client.get_leaderboard(limit=10)
    assert entries == data["entries"]


def test_get_leaderboard_offline_returns_empty():
    client = ApiClient(base_url="http://test")
    with patch("src.api_client.requests.get",
               side_effect=requests.ConnectionError("offline")):
        assert client.get_leaderboard() == []


def test_leaderboard_tracks_rtt_and_online_status():
    client = ApiClient(base_url="http://test")
    # before any call: unknown / offline
    assert client.last_rtt_ms is None and client.online is False

    data = {"entries": [{"nickname": "a", "score": 50}]}
    with patch("src.api_client.requests.get", return_value=_resp(200, data)):
        client.get_leaderboard()
    assert client.online is True
    assert isinstance(client.last_rtt_ms, float) and client.last_rtt_ms >= 0.0
    assert client.backend_info() == {
        "url": "http://test", "online": True, "rtt_ms": client.last_rtt_ms,
    }

    # a later failure resets telemetry to offline / unknown RTT
    with patch("src.api_client.requests.get",
               side_effect=requests.ConnectionError("offline")):
        client.get_leaderboard()
    assert client.online is False and client.last_rtt_ms is None


def test_get_achievements_parses_and_is_offline_safe():
    client = ApiClient(base_url="http://test")
    data = {"achievements": [{"id": "first_blood", "name": "First Blood"}]}
    with patch("src.api_client.requests.get", return_value=_resp(200, data)):
        assert client.get_achievements("alice") == data["achievements"]
    with patch("src.api_client.requests.get",
               side_effect=requests.Timeout("slow")):
        assert client.get_achievements("alice") == []

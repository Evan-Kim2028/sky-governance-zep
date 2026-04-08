from unittest.mock import MagicMock
import pytest
from zep_cloud.core.api_error import ApiError
from governance.ingest import ensure_graph, ingest_episodes, estimate_credits, ZEP_GRAPH_ID


def make_client():
    return MagicMock()


# ── ensure_graph ──────────────────────────────────────────────────────────────

def test_ensure_graph_creates_when_not_found():
    client = make_client()
    client.graph.get.side_effect = ApiError(status_code=404, body="not found")
    ensure_graph(client)
    client.graph.create.assert_called_once()
    kwargs = client.graph.create.call_args.kwargs
    assert kwargs["graph_id"] == ZEP_GRAPH_ID
    assert "governance" in kwargs["description"].lower()


def test_ensure_graph_skips_create_when_exists():
    client = make_client()
    client.graph.get.return_value = MagicMock(graph_id=ZEP_GRAPH_ID)
    ensure_graph(client)
    client.graph.create.assert_not_called()


def test_ensure_graph_get_called_with_correct_id():
    client = make_client()
    client.graph.get.return_value = MagicMock()
    ensure_graph(client)
    client.graph.get.assert_called_once_with(graph_id=ZEP_GRAPH_ID)


def test_ensure_graph_propagates_non_404_api_error():
    client = make_client()
    client.graph.get.side_effect = ApiError(status_code=500, body="server error")
    with pytest.raises(ApiError):
        ensure_graph(client)


# ── ingest_episodes ───────────────────────────────────────────────────────────

def test_ingest_episodes_calls_graph_add_for_each():
    client = make_client()
    episodes = [
        {"data": "Episode 1", "type": "text", "created_at": "2023-01-01T00:00:00Z", "source_description": "src-1"},
        {"data": "Episode 2", "type": "text", "created_at": "2023-02-01T00:00:00Z", "source_description": "src-2"},
    ]
    count = ingest_episodes(client, episodes)
    assert count == 2
    assert client.graph.add.call_count == 2


def test_ingest_episodes_passes_graph_id_not_user_id():
    client = make_client()
    ep = {
        "data": "Forum topic about RWA vaults.",
        "type": "text",
        "created_at": "2022-05-01T00:00:00Z",
        "source_description": "forum-topic-123",
    }
    ingest_episodes(client, [ep])
    client.graph.add.assert_called_once_with(
        graph_id=ZEP_GRAPH_ID,
        data="Forum topic about RWA vaults.",
        type="text",
        source_description="forum-topic-123",
        created_at="2022-05-01T00:00:00Z",
    )


def test_ingest_episodes_skips_none():
    client = make_client()
    episodes = [None, {"data": "Valid", "type": "text", "created_at": "2023-01-01T00:00:00Z"}]
    count = ingest_episodes(client, episodes)
    assert count == 1
    assert client.graph.add.call_count == 1


def test_ingest_episodes_skips_empty_data():
    client = make_client()
    episodes = [
        {"data": "", "type": "text"},
        {"data": "Non-empty", "type": "text", "created_at": "2023-01-01T00:00:00Z"},
    ]
    count = ingest_episodes(client, episodes)
    assert count == 1


def test_ingest_episodes_returns_zero_for_all_invalid():
    client = make_client()
    count = ingest_episodes(client, [None, None, {"data": ""}])
    assert count == 0
    client.graph.add.assert_not_called()


def test_ingest_episodes_skips_on_400_bad_request():
    """400 errors (bad episode data) are skipped; ingest continues and counts only successes."""
    episodes = [
        {"data": "good episode 1", "type": "text", "source_description": "ep-1"},
        {"data": "bad episode", "type": "text", "source_description": "ep-bad"},
        {"data": "good episode 2", "type": "text", "source_description": "ep-2"},
    ]
    bad_request = ApiError(status_code=400, body={"message": "invalid json"})
    client = MagicMock()
    client.graph.add.side_effect = [None, bad_request, None]
    count = ingest_episodes(client, episodes)
    assert count == 2
    assert client.graph.add.call_count == 3


def test_ingest_episodes_stops_on_403_usage_limit():
    """403 with 'usage limit' in body stops ingestion and returns count so far."""
    episodes = [
        {"data": "ep 1", "type": "text", "source_description": "ep-1"},
        {"data": "ep 2", "type": "text", "source_description": "ep-2"},
        {"data": "ep 3", "type": "text", "source_description": "ep-3"},
    ]
    credit_limit_error = ApiError(
        status_code=403, body={"message": "Account is over the episode usage limit"}
    )
    client = MagicMock()
    client.graph.add.side_effect = [None, credit_limit_error, None]
    count = ingest_episodes(client, episodes)
    assert count == 1
    assert client.graph.add.call_count == 2


# ── estimate_credits ──────────────────────────────────────────────────────────

def test_estimate_credits_counts_valid():
    episodes = [{"data": "Episode 1"}, {"data": "Episode 2"}, None, {"data": ""}]
    assert estimate_credits(episodes) == 2


def test_estimate_credits_all_valid():
    episodes = [{"data": f"Episode {i}"} for i in range(10)]
    assert estimate_credits(episodes) == 10


def test_estimate_credits_empty_list():
    assert estimate_credits([]) == 0


import json
import tempfile
from pathlib import Path
from governance.ingest import IngestLog


# ── IngestLog ─────────────────────────────────────────────────────────────────

def test_ingest_log_marks_and_checks():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / ".ingest_log.json"
        ingest_log = IngestLog(log_path)
        assert not ingest_log.seen("forum-post-123")
        ingest_log.mark("forum-post-123")
        assert ingest_log.seen("forum-post-123")


def test_ingest_log_persists_across_instances():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / ".ingest_log.json"
        log1 = IngestLog(log_path)
        log1.mark("ep-abc")
        log1.save()

        log2 = IngestLog(log_path)
        assert log2.seen("ep-abc")


def test_ingest_log_empty_file_is_ok():
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / ".ingest_log.json"
        ingest_log = IngestLog(log_path)
        assert not ingest_log.seen("anything")


def test_ingest_log_missing_file_is_ok():
    log_path = Path("/tmp/does_not_exist_sky_gov_test.json")
    if log_path.exists():
        log_path.unlink()
    ingest_log = IngestLog(log_path)
    assert not ingest_log.seen("anything")


def test_ingest_episodes_skips_seen_source_descriptions():
    """Episodes whose source_description is in the ingest log are skipped."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / ".ingest_log.json"
        ingest_log = IngestLog(log_path)
        ingest_log.mark("ep-already-done")
        ingest_log.save()

        client = MagicMock()
        episodes = [
            {"data": "already ingested content — repeated duplicate episode that should be skipped", "source_description": "ep-already-done"},
            {"data": "new governance content that has not been previously ingested into ZEP graph", "source_description": "ep-new"},
        ]
        count = ingest_episodes(client, episodes, ingest_log=ingest_log)
        assert count == 1
        assert client.graph.add.call_count == 1
        call_kwargs = client.graph.add.call_args.kwargs
        assert call_kwargs["source_description"] == "ep-new"


def test_ingest_episodes_does_not_mark_400_error_in_log():
    """Episodes that get a 400 error from ZEP are NOT marked in the ingest log — they will be retried next run."""
    with tempfile.TemporaryDirectory() as tmpdir:
        log_path = Path(tmpdir) / ".ingest_log.json"
        ingest_log = IngestLog(log_path)

        client = MagicMock()
        client.graph.add.side_effect = ApiError(status_code=400, body={"message": "bad request"})

        episodes = [{"data": "content that causes a 400 error from ZEP graph API endpoint", "source_description": "ep-bad"}]
        count = ingest_episodes(client, episodes, ingest_log=ingest_log)

        assert count == 0
        assert not ingest_log.seen("ep-bad")  # was NOT marked — will be retried

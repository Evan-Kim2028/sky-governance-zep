from unittest.mock import MagicMock, call, patch
import pytest
from zep_cloud.core.api_error import ApiError
from governance.ingest import ensure_user, ingest_episodes, estimate_credits, ZEP_USER_ID


def make_client():
    return MagicMock()


# ── ensure_user ───────────────────────────────────────────────────────────────

def test_ensure_user_creates_when_not_found():
    client = make_client()
    client.user.get.side_effect = ApiError(status_code=404, body="not found")
    ensure_user(client)
    client.user.add.assert_called_once()
    kwargs = client.user.add.call_args.kwargs
    assert kwargs["user_id"] == ZEP_USER_ID
    assert kwargs["metadata"]["domain"] == "DeFi governance"


def test_ensure_user_skips_create_when_exists():
    client = make_client()
    client.user.get.return_value = MagicMock(user_id=ZEP_USER_ID)
    ensure_user(client)
    client.user.add.assert_not_called()


def test_ensure_user_get_called_with_correct_id():
    client = make_client()
    client.user.get.return_value = MagicMock()
    ensure_user(client)
    client.user.get.assert_called_once_with(user_id=ZEP_USER_ID)


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


def test_ingest_episodes_passes_correct_args():
    client = make_client()
    ep = {"data": "Forum topic about RWA vaults.", "type": "text", "created_at": "2022-05-01T00:00:00Z", "source_description": "forum-topic-123"}
    ingest_episodes(client, [ep])
    client.graph.add.assert_called_once_with(
        user_id=ZEP_USER_ID,
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


# ── estimate_credits ──────────────────────────────────────────────────────────

def test_estimate_credits_counts_valid():
    episodes = [
        {"data": "Episode 1"},
        {"data": "Episode 2"},
        None,
        {"data": ""},
    ]
    assert estimate_credits(episodes) == 2


def test_estimate_credits_all_valid():
    episodes = [{"data": f"Episode {i}"} for i in range(10)]
    assert estimate_credits(episodes) == 10


def test_estimate_credits_empty_list():
    assert estimate_credits([]) == 0

import unittest.mock
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock, call
import pytest
from governance.fetchers import (
    fetch_governance_categories,
    fetch_all_topics_since,
    fetch_all_topic_post_records,
    fetch_polls_paginated,
    fetch_poll_tally,
    fetch_executives,
    fetch_top_posters,
    fetch_user_profile,
    fetch_delegates,
    fetch_poll_voters,
)


def mock_response(json_data, status_code=200):
    m = MagicMock()
    m.raise_for_status.return_value = None
    m.json.return_value = json_data
    m.status_code = status_code
    return m


# ── fetch_governance_categories ───────────────────────────────────────────────

CATEGORIES_PAYLOAD = {
    "category_list": {
        "categories": [
            {"id": 5, "name": "Governance", "slug": "governance", "topic_count": 200},
            {"id": 10, "name": "General Chat", "slug": "general-chat", "topic_count": 50},
            {"id": 15, "name": "Risk", "slug": "risk", "topic_count": 80},
            {"id": 20, "name": "MIPs", "slug": "mips", "topic_count": 300},
        ]
    }
}


def test_fetch_governance_categories_includes_governance_and_risk():
    with patch("governance.fetchers.requests.get", return_value=mock_response(CATEGORIES_PAYLOAD)):
        cats = fetch_governance_categories()
    names = [c["name"] for c in cats]
    assert "Governance" in names
    assert "Risk" in names
    assert "MIPs" in names


def test_fetch_governance_categories_excludes_general():
    with patch("governance.fetchers.requests.get", return_value=mock_response(CATEGORIES_PAYLOAD)):
        cats = fetch_governance_categories()
    names = [c["name"] for c in cats]
    assert "General Chat" not in names


# ── fetch_all_topics_since ────────────────────────────────────────────────────

RECENT_TOPIC = {"id": 100, "title": "New MIP", "created_at": "2025-01-01T00:00:00.000Z", "tags": []}
OLD_TOPIC    = {"id": 101, "title": "Old MIP", "created_at": "2020-01-01T00:00:00.000Z", "tags": []}
TOPICS_PAGE_PAYLOAD = {"topic_list": {"topics": [RECENT_TOPIC, OLD_TOPIC]}}
EMPTY_PAGE_PAYLOAD  = {"topic_list": {"topics": []}}


def test_fetch_all_topics_since_filters_old_topics():
    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with patch("governance.fetchers.requests.get", side_effect=[
        mock_response(TOPICS_PAGE_PAYLOAD),
        mock_response(EMPTY_PAGE_PAYLOAD),
    ]):
        topics = fetch_all_topics_since(5, "governance", since=cutoff, max_pages=2)
    titles = [t["title"] for t in topics]
    assert "New MIP" in titles
    assert "Old MIP" not in titles


def test_fetch_all_topics_since_stops_on_empty_page():
    cutoff = datetime(2024, 1, 1, tzinfo=timezone.utc)
    with patch("governance.fetchers.requests.get", side_effect=[
        mock_response(EMPTY_PAGE_PAYLOAD),
    ]) as mock_get:
        topics = fetch_all_topics_since(5, "governance", since=cutoff, max_pages=5)
    assert topics == []
    assert mock_get.call_count == 1  # stopped after first empty page


def test_fetch_all_topics_since_respects_max_pages():
    cutoff = datetime(2020, 1, 1, tzinfo=timezone.utc)  # old cutoff — accept everything
    page_payload = {"topic_list": {"topics": [RECENT_TOPIC]}}
    with patch("governance.fetchers.requests.get", return_value=mock_response(page_payload)) as mock_get:
        fetch_all_topics_since(5, "governance", since=cutoff, max_pages=3)
    assert mock_get.call_count == 3


# ── fetch_all_topic_post_records ──────────────────────────────────────────────

TOPIC_FIRST_PAGE = {
    "post_stream": {
        "stream": [101, 102, 103, 104, 105],
        "posts": [
            {"id": 101, "username": "alice", "created_at": "2026-01-10T10:00:00.000Z",
             "cooked": "<p>First post</p>", "post_number": 1, "like_count": 3,
             "reply_to_post_number": None},
            {"id": 102, "username": "bob", "created_at": "2026-01-10T11:00:00.000Z",
             "cooked": "<p>Second post</p>", "post_number": 2, "like_count": 1,
             "reply_to_post_number": 1},
        ],
    }
}

TOPIC_BATCH_PAGE = {
    "post_stream": {
        "posts": [
            {"id": 103, "username": "carol", "created_at": "2026-01-10T12:00:00.000Z",
             "cooked": "<p>Third</p>", "post_number": 3, "like_count": 0,
             "reply_to_post_number": None},
            {"id": 104, "username": "alice", "created_at": "2026-01-10T13:00:00.000Z",
             "cooked": "<p>Fourth</p>", "post_number": 4, "like_count": 2,
             "reply_to_post_number": 2},
            {"id": 105, "username": "bob", "created_at": "2026-01-10T14:00:00.000Z",
             "cooked": "<p>Fifth</p>", "post_number": 5, "like_count": 0,
             "reply_to_post_number": None},
        ]
    }
}


def test_fetch_all_topic_post_records_returns_all_posts():
    with patch("governance.fetchers.requests.get") as mock_get:
        with patch("governance.fetchers.time.sleep") as mock_sleep:
            mock_get.side_effect = [
                mock_response(TOPIC_FIRST_PAGE),
                mock_response(TOPIC_BATCH_PAGE),
            ]
            records = fetch_all_topic_post_records(topic_id=999)
    assert len(records) == 5
    assert mock_sleep.call_count == 0  # only 1 batch of remaining IDs, no inter-batch sleep


def test_fetch_all_topic_post_records_contains_author_fields():
    with patch("governance.fetchers.requests.get") as mock_get:
        mock_get.side_effect = [
            mock_response(TOPIC_FIRST_PAGE),
            mock_response(TOPIC_BATCH_PAGE),
        ]
        records = fetch_all_topic_post_records(topic_id=999)
    first = records[0]
    assert first["username"] == "alice"
    assert first["created_at"] == "2026-01-10T10:00:00.000Z"
    assert first["post_number"] == 1
    assert "cooked" in first
    assert "like_count" in first


def test_fetch_all_topic_post_records_no_batch_needed_when_all_in_first_page():
    payload = {
        "post_stream": {
            "stream": [101, 102],
            "posts": [
                {"id": 101, "username": "alice", "created_at": "2026-01-10T10:00:00.000Z",
                 "cooked": "<p>A</p>", "post_number": 1, "like_count": 0,
                 "reply_to_post_number": None},
                {"id": 102, "username": "bob", "created_at": "2026-01-10T11:00:00.000Z",
                 "cooked": "<p>B</p>", "post_number": 2, "like_count": 0,
                 "reply_to_post_number": None},
            ],
        }
    }
    with patch("governance.fetchers.requests.get", return_value=mock_response(payload)) as mock_get:
        with patch("governance.fetchers.time.sleep") as mock_sleep:
            records = fetch_all_topic_post_records(topic_id=999)
    assert mock_get.call_count == 1
    assert len(records) == 2
    assert mock_sleep.call_count == 0  # no sleep when no batch needed


def test_fetch_all_topic_post_records_returns_empty_on_error():
    with patch("governance.fetchers.requests.get", side_effect=Exception("network error")):
        records = fetch_all_topic_post_records(topic_id=999)
    assert records == []


def test_fetch_all_topic_post_records_skips_posts_without_cooked():
    payload = {
        "post_stream": {
            "stream": [101, 102],
            "posts": [
                {"id": 101, "username": "alice", "created_at": "2026-01-10T10:00:00.000Z",
                 "cooked": "", "post_number": 1, "like_count": 0, "reply_to_post_number": None},
                {"id": 102, "username": "bob", "created_at": "2026-01-10T11:00:00.000Z",
                 "cooked": "<p>Real content</p>", "post_number": 2, "like_count": 0,
                 "reply_to_post_number": None},
            ],
        }
    }
    with patch("governance.fetchers.requests.get", return_value=mock_response(payload)):
        records = fetch_all_topic_post_records(topic_id=999)
    assert len(records) == 1
    assert records[0]["username"] == "bob"


# ── fetch_polls_paginated ─────────────────────────────────────────────────────

PAGE_A = [
    {"pollId": 1, "title": "Poll A1", "slug": "a1", "startDate": "2023-01-01T00:00:00.000Z"},
    {"pollId": 2, "title": "Poll A2", "slug": "a2", "startDate": "2023-02-01T00:00:00.000Z"},
]
PAGE_B = [
    {"pollId": 3, "title": "Poll B1", "slug": "b1", "startDate": "2022-01-01T00:00:00.000Z"},
]


def test_fetch_polls_paginated_collects_across_pages():
    with patch("governance.fetchers.requests.get", side_effect=[
        mock_response(PAGE_A),
        mock_response(PAGE_B),
        mock_response([]),  # empty = done
    ]):
        polls = fetch_polls_paginated(max_polls=100)
    assert len(polls) == 3
    assert polls[0]["title"] == "Poll A1"
    assert polls[2]["title"] == "Poll B1"


def test_fetch_polls_paginated_stops_on_empty_page():
    with patch("governance.fetchers.requests.get", side_effect=[
        mock_response(PAGE_A),
        mock_response([]),
    ]) as mock_get:
        fetch_polls_paginated(max_polls=100)
    assert mock_get.call_count == 2


def test_fetch_polls_paginated_respects_max_polls():
    with patch("governance.fetchers.requests.get", return_value=mock_response(PAGE_A)):
        polls = fetch_polls_paginated(max_polls=1)
    assert len(polls) == 1


def test_fetch_polls_paginated_handles_dict_response():
    with patch("governance.fetchers.requests.get", side_effect=[
        mock_response({"polls": PAGE_A}),
        mock_response([]),
    ]):
        polls = fetch_polls_paginated(max_polls=100)
    assert len(polls) == 2


# ── fetch_poll_tally ──────────────────────────────────────────────────────────

TALLY_PAYLOAD = {
    "results": [{"optionName": "Yes", "mkrSupport": "45000"}],
    "totalMkrActiveParticipation": "52000",
}


def test_fetch_poll_tally_returns_dict():
    with patch("governance.fetchers.requests.get", return_value=mock_response(TALLY_PAYLOAD)):
        tally = fetch_poll_tally(1056)
    assert tally["totalMkrActiveParticipation"] == "52000"


def test_fetch_poll_tally_returns_none_on_error():
    with patch("governance.fetchers.requests.get", side_effect=Exception("404")):
        tally = fetch_poll_tally(9999)
    assert tally is None


# ── fetch_executives ──────────────────────────────────────────────────────────

EXECUTIVES_PAYLOAD = [
    {"key": "2023-01-15", "title": "Onboard wBTC-A", "date": "2023-01-15", "passed": True, "mkrSupport": "50000"},
    {"key": "2023-02-01", "title": "Update Stability Fees", "date": "2023-02-01", "passed": True, "mkrSupport": "30000"},
]


def test_fetch_executives_list_response():
    with patch("governance.fetchers.requests.get", return_value=mock_response(EXECUTIVES_PAYLOAD)):
        execs = fetch_executives(limit=5)
    assert len(execs) == 2
    assert execs[0]["title"] == "Onboard wBTC-A"


def test_fetch_executives_respects_limit():
    with patch("governance.fetchers.requests.get", return_value=mock_response(EXECUTIVES_PAYLOAD)):
        execs = fetch_executives(limit=1)
    assert len(execs) == 1


# ── fetch_top_posters ─────────────────────────────────────────────────────────

DIRECTORY_PAYLOAD = {
    "directory_items": [
        {
            "id": 1, "likes_received": 50, "post_count": 120, "topic_count": 15,
            "user": {"username": "hexonaut", "title": "Aligned Delegate (AD)", "trust_level": 4},
        },
        {
            "id": 2, "likes_received": 30, "post_count": 80, "topic_count": 8,
            "user": {"username": "rune", "title": "Facilitator", "trust_level": 4},
        },
        {
            "id": 3, "likes_received": 5, "post_count": 10, "topic_count": 2,
            "user": {"username": "lurker", "title": None, "trust_level": 1},
        },
    ]
}

PROFILE_PAYLOAD = {
    "user": {
        "username": "hexonaut",
        "title": "Aligned Delegate (AD)",
        "trust_level": 4,
        "badge_count": 22,
        "bio_raw": "Working on Sky protocol governance and risk.",
        "created_at": "2020-03-15T00:00:00.000Z",
        "last_posted_at": "2026-03-01T12:00:00.000Z",
        "groups": [{"name": "Aligned_Delegates"}, {"name": "trust_level_4"}],
    }
}


def test_fetch_top_posters_returns_usernames():
    with patch("governance.fetchers.requests.get", return_value=mock_response(DIRECTORY_PAYLOAD)) as mock_get:
        posters = fetch_top_posters(limit=3)
    usernames = [p["user"]["username"] for p in posters]
    assert "hexonaut" in usernames
    assert "rune" in usernames
    mock_get.assert_called_once_with(
        "https://forum.skyeco.com/directory_items.json",
        headers=unittest.mock.ANY,
        params={"order": "post_count", "period": "monthly", "page": 0},
        timeout=20,
    )


def test_fetch_top_posters_respects_limit():
    with patch("governance.fetchers.requests.get", return_value=mock_response(DIRECTORY_PAYLOAD)):
        posters = fetch_top_posters(limit=2)
    assert len(posters) <= 2


def test_fetch_top_posters_returns_empty_on_error():
    with patch("governance.fetchers.requests.get", side_effect=Exception("network")):
        posters = fetch_top_posters(limit=10)
    assert posters == []


def test_fetch_top_posters_uses_period_param():
    with patch("governance.fetchers.requests.get", return_value=mock_response(DIRECTORY_PAYLOAD)) as mock_get:
        fetch_top_posters(period="weekly")
    _, kwargs = mock_get.call_args
    assert kwargs["params"]["period"] == "weekly"


def test_fetch_user_profile_returns_user_dict():
    with patch("governance.fetchers.requests.get", return_value=mock_response(PROFILE_PAYLOAD)) as mock_get:
        profile = fetch_user_profile("hexonaut")
    assert profile["username"] == "hexonaut"
    assert profile["title"] == "Aligned Delegate (AD)"
    assert profile["trust_level"] == 4
    mock_get.assert_called_once_with(
        "https://forum.skyeco.com/u/hexonaut.json",
        headers=unittest.mock.ANY,
        params=None,
        timeout=20,
    )


def test_fetch_user_profile_returns_none_on_error():
    with patch("governance.fetchers.requests.get", side_effect=Exception("404")):
        profile = fetch_user_profile("nobody")
    assert profile is None


# ── fetch_delegates ───────────────────────────────────────────────────────────

DELEGATES_PAYLOAD = {
    "delegates": [
        {
            "name": "Bonapublica",
            "voteDelegateAddress": "0xabc000",
            "address": "0xabc001",
            "status": "aligned",
            "mkrDelegated": "50000",
            "delegatorCount": 12,
        },
        {
            "name": "hexonaut",
            "voteDelegateAddress": "0xdef000",
            "address": "0xdef001",
            "status": "aligned",
            "mkrDelegated": "72666",
            "delegatorCount": 8,
        },
    ]
}

TALLY_WITH_VOTES = {
    "winningOptionName": "Yes",
    "totalMkrActiveParticipation": "122666",
    "results": [
        {"optionId": 1, "optionName": "Yes", "mkrSupport": "122666", "winner": True},
        {"optionId": 2, "optionName": "No", "mkrSupport": "0", "winner": False},
    ],
    "votesByAddress": [
        {"voter": "0xabc000", "optionIdRaw": "1", "mkrSupport": "50000.0",
         "blockTimestamp": "2026-01-13T16:45:11+00:00"},
        {"voter": "0xdef000", "optionIdRaw": "1", "mkrSupport": "72666.0",
         "blockTimestamp": "2026-01-13T17:00:00+00:00"},
        {"voter": "0xunknown", "optionIdRaw": "2", "mkrSupport": "100.0",
         "blockTimestamp": "2026-01-13T17:30:00+00:00"},
    ],
}


def test_fetch_delegates_returns_address_to_name_map():
    with patch("governance.fetchers.requests.get", return_value=mock_response(DELEGATES_PAYLOAD)):
        delegates = fetch_delegates()
    assert "0xabc000" in delegates
    assert delegates["0xabc000"] == "Bonapublica"
    assert delegates["0xdef000"] == "hexonaut"


def test_fetch_delegates_returns_empty_on_error():
    with patch("governance.fetchers.requests.get", side_effect=Exception("fail")):
        delegates = fetch_delegates()
    assert delegates == {}


def test_fetch_poll_voters_resolves_known_addresses():
    with patch("governance.fetchers.requests.get") as mock_get:
        mock_get.side_effect = [
            mock_response(DELEGATES_PAYLOAD),
            mock_response(TALLY_WITH_VOTES),
        ]
        voters = fetch_poll_voters(poll_id=1246, poll_title="Atlas Edit - Jan 2026")
    assert len(voters) == 3
    bonapublica = next(v for v in voters if v["delegate_name"] == "Bonapublica")
    assert bonapublica["option_name"] == "Yes"
    assert bonapublica["mkr_support"] == "50000.0"


def test_fetch_poll_voters_labels_unknown_addresses():
    with patch("governance.fetchers.requests.get") as mock_get:
        mock_get.side_effect = [
            mock_response(DELEGATES_PAYLOAD),
            mock_response(TALLY_WITH_VOTES),
        ]
        voters = fetch_poll_voters(poll_id=1246, poll_title="Test Poll")
    unknown = next(v for v in voters if v["voter_address"] == "0xunknown")
    assert unknown["delegate_name"].startswith("0x")


def test_fetch_poll_voters_handles_null_voter_address():
    tally_with_null = {
        "results": [{"optionId": 1, "optionName": "Yes", "mkrSupport": "100"}],
        "votesByAddress": [
            {"voter": None, "optionIdRaw": "1", "mkrSupport": "100.0",
             "blockTimestamp": "2026-01-13T16:00:00+00:00"},
        ],
    }
    with patch("governance.fetchers.requests.get") as mock_get:
        mock_get.side_effect = [
            mock_response(DELEGATES_PAYLOAD),
            mock_response(tally_with_null),
        ]
        voters = fetch_poll_voters(poll_id=999, poll_title="Test")
    assert len(voters) == 1
    assert voters[0]["delegate_name"] == "unknown"


def test_fetch_poll_voters_returns_empty_on_tally_error():
    with patch("governance.fetchers.requests.get") as mock_get:
        mock_get.side_effect = [
            mock_response(DELEGATES_PAYLOAD),
            Exception("tally fetch failed"),
        ]
        voters = fetch_poll_voters(poll_id=9999, poll_title="Test")
    assert voters == []

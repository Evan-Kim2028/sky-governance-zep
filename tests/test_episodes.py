import pytest
from governance.episodes import (
    strip_html,
    _parse_date,
    topic_to_episode,
    poll_to_episode,
    executive_to_episode,
)


def test_strip_html_removes_tags():
    assert strip_html("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_html_none_returns_empty():
    assert strip_html(None) == ""


def test_strip_html_empty_returns_empty():
    assert strip_html("") == ""


def test_strip_html_caps_at_2000_chars():
    long_html = "<p>" + "x" * 3000 + "</p>"
    assert len(strip_html(long_html)) == 2000


def test_parse_date_returns_none_for_empty():
    assert _parse_date(None) is None
    assert _parse_date("") is None


def test_parse_date_passes_through_iso_string():
    assert _parse_date("2023-03-15") == "2023-03-15"
    assert _parse_date("2022-05-01T12:00:00.000Z") == "2022-05-01T12:00:00.000Z"


def test_parse_date_converts_js_date_string():
    js_date = "Thu May 15 2025 00:00:00 GMT+0000 (Coordinated Universal Time)"
    result = _parse_date(js_date)
    assert result == "2025-05-15T00:00:00Z"


def test_parse_date_returns_none_for_unparseable():
    assert _parse_date("not-a-date") is None


def test_executive_to_episode_js_date_is_converted():
    exec_ = {
        "key": "spell-2025-05-15",
        "title": "Test Spell",
        "date": "Thu May 15 2025 00:00:00 GMT+0000 (Coordinated Universal Time)",
        "passed": True,
        "mkrSupport": "50000",
    }
    ep = executive_to_episode(exec_)
    assert ep is not None
    assert ep["created_at"] == "2025-05-15T00:00:00Z"


def test_topic_to_episode_shape():
    topic = {
        "id": 123,
        "title": "MIP-65: Monetalis Clydesdale",
        "created_at": "2022-05-01T12:00:00.000Z",
        "tags": ["mips", "rwa"],
        "posts_count": 45,
        "like_count": 23,
        "views": 1200,
    }
    posts = [
        "<p>Proposal to allocate 500M DAI to US T-bills via Monetalis.</p>",
        "<p>Risk team: LTV looks acceptable given short duration.</p>",
    ]
    ep = topic_to_episode(topic, posts, "Governance")
    assert ep["type"] == "text"
    assert ep["created_at"] == "2022-05-01T12:00:00.000Z"
    assert ep["source_description"] == "forum-topic-123"
    assert "MIP-65" in ep["data"]
    assert "mips" in ep["data"]
    assert "45 replies" in ep["data"]
    assert "T-bills" in ep["data"]
    assert "Risk team" in ep["data"]       # second post bundled in


def test_topic_to_episode_multiple_posts_all_bundled():
    topic = {"id": 5, "title": "T", "created_at": "2023-01-01T00:00:00.000Z", "tags": []}
    posts = ["<p>Post one.</p>", "<p>Post two.</p>", "<p>Post three.</p>"]
    ep = topic_to_episode(topic, posts, "Governance")
    assert "Post one" in ep["data"]
    assert "Post two" in ep["data"]
    assert "Post three" in ep["data"]


def test_topic_to_episode_no_posts_omits_discussion():
    topic = {"id": 1, "title": "Test", "created_at": "2022-01-01T00:00:00.000Z", "tags": []}
    ep = topic_to_episode(topic, [], "General")
    assert "Discussion:" not in ep["data"]


def test_topic_to_episode_empty_tags_shows_none():
    topic = {"id": 2, "title": "X", "created_at": "2023-01-01T00:00:00.000Z", "tags": []}
    ep = topic_to_episode(topic, [], "Risk")
    assert "Tags: none" in ep["data"]


def test_topic_to_episode_caps_at_4000_chars():
    topic = {"id": 9, "title": "T", "created_at": "2023-01-01T00:00:00.000Z", "tags": []}
    posts = ["<p>" + "x" * 1000 + "</p>"] * 20  # 20 long posts
    ep = topic_to_episode(topic, posts, "Governance")
    assert len(ep["data"]) <= 4000


def test_poll_to_episode_with_tally():
    poll = {
        "pollId": 1056,
        "title": "Should we offboard USDC-A?",
        "slug": "offboard-usdc-a",
        "startDate": "2023-01-10T16:00:00.000Z",
        "endDate": "2023-01-13T16:00:00.000Z",
        "options": [{"label": "Yes"}, {"label": "No"}, {"label": "Abstain"}],
        "tags": ["collateral-offboard"],
    }
    tally = {
        "results": [{"optionName": "Yes", "mkrSupport": "45000"}],
        "totalMkrActiveParticipation": "52000",
    }
    ep = poll_to_episode(poll, tally)
    assert ep is not None
    assert ep["type"] == "text"
    assert ep["source_description"] == "poll-1056"
    assert ep["created_at"] == "2023-01-10T16:00:00.000Z"
    assert "offboard USDC-A" in ep["data"]
    assert "Yes" in ep["data"]
    assert "45000 MKR" in ep["data"]


def test_poll_to_episode_no_tally_omits_result():
    poll = {
        "pollId": 1,
        "title": "Stability Fee Change",
        "slug": "sf-change",
        "startDate": "2023-03-01T00:00:00.000Z",
        "endDate": "2023-03-04T00:00:00.000Z",
        "options": [{"label": "0.5%"}, {"label": "1%"}],
        "tags": [],
    }
    ep = poll_to_episode(poll, None)
    assert ep is not None
    assert "Result:" not in ep["data"]


def test_poll_to_episode_no_title_returns_none():
    assert poll_to_episode({"pollId": 1, "title": ""}, None) is None


def test_poll_to_episode_missing_title_returns_none():
    assert poll_to_episode({"pollId": 1}, None) is None


def test_executive_to_episode_shape():
    exec_ = {
        "key": "2023-03-15",
        "title": "Onboard wBTC as Collateral",
        "date": "2023-03-15",
        "passed": True,
        "mkrSupport": "78000",
        "about": "<p>This spell onboards wBTC-A vault type with 150% liquidation ratio.</p>",
    }
    ep = executive_to_episode(exec_)
    assert ep is not None
    assert ep["type"] == "text"
    assert ep["source_description"] == "executive-2023-03-15"
    assert ep["created_at"] == "2023-03-15"
    assert "wBTC" in ep["data"]
    assert "Passed: True" in ep["data"]
    assert "78000" in ep["data"]
    assert "wBTC-A vault" in ep["data"]  # from stripped HTML


def test_executive_to_episode_no_title_returns_none():
    assert executive_to_episode({"key": "abc", "title": ""}) is None


def test_executive_to_episode_missing_title_returns_none():
    assert executive_to_episode({"key": "abc"}) is None

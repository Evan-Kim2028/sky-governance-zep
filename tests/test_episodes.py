import pytest
from governance.episodes import (
    strip_html,
    _parse_date,
    topic_to_episode,
    poll_to_episode,
    executive_to_episode,
    post_to_episode,
    user_profile_to_episode,
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


def test_post_to_episode_basic_structure():
    post = {
        "id": 101,
        "username": "hexonaut",
        "created_at": "2026-01-15T14:23:00.000Z",
        "cooked": "<p>I support lowering the USDS borrow rate to 8.5%.</p>",
        "post_number": 3,
        "like_count": 7,
        "reply_to_post_number": None,
    }
    ep = post_to_episode(post, topic_id=999, topic_title="USDS Rate Discussion", category="Sky Core")
    assert ep["type"] == "text"
    assert ep["created_at"] == "2026-01-15T14:23:00.000Z"
    assert ep["source_description"] == "post-999-101"
    assert "@hexonaut" in ep["data"]
    assert "USDS Rate Discussion" in ep["data"]
    assert "Sky Core" in ep["data"]
    assert "8.5%" in ep["data"]


def test_post_to_episode_strips_html():
    post = {
        "id": 102,
        "username": "rune",
        "created_at": "2026-01-15T15:00:00.000Z",
        "cooked": "<p>This is <strong>bold</strong> text with <a href='#'>link</a>.</p>",
        "post_number": 4,
        "like_count": 0,
        "reply_to_post_number": None,
    }
    ep = post_to_episode(post, topic_id=999, topic_title="Test", category="Sky Core")
    assert "<p>" not in ep["data"]
    assert "<strong>" not in ep["data"]
    assert "bold" in ep["data"]


def test_post_to_episode_includes_reply_context():
    post = {
        "id": 103,
        "username": "alice",
        "created_at": "2026-01-16T09:00:00.000Z",
        "cooked": "<p>Agreed with your point.</p>",
        "post_number": 5,
        "like_count": 2,
        "reply_to_post_number": 3,
    }
    ep = post_to_episode(post, topic_id=999, topic_title="Test", category="Sky Core")
    assert "reply to post #3" in ep["data"].lower() or "replying" in ep["data"].lower()


def test_post_to_episode_caps_content_at_2500_chars():
    post = {
        "id": 104,
        "username": "longposter",
        "created_at": "2026-01-16T10:00:00.000Z",
        "cooked": "<p>" + ("x" * 5000) + "</p>",
        "post_number": 6,
        "like_count": 0,
        "reply_to_post_number": None,
    }
    ep = post_to_episode(post, topic_id=999, topic_title="Test", category="Sky Core")
    assert len(ep["data"]) <= 2500


def test_post_to_episode_includes_like_count_when_nonzero():
    post = {
        "id": 105,
        "username": "popular",
        "created_at": "2026-01-17T08:00:00.000Z",
        "cooked": "<p>Liked opinion.</p>",
        "post_number": 7,
        "like_count": 15,
        "reply_to_post_number": None,
    }
    ep = post_to_episode(post, topic_id=999, topic_title="Test", category="Sky Core")
    assert "15" in ep["data"]


def test_post_to_episode_no_reply_context_when_none():
    post = {
        "id": 106,
        "username": "solo",
        "created_at": "2026-01-17T09:00:00.000Z",
        "cooked": "<p>Standalone post.</p>",
        "post_number": 1,
        "like_count": 0,
        "reply_to_post_number": None,
    }
    ep = post_to_episode(post, topic_id=999, topic_title="Test", category="Sky Core")
    assert "replying" not in ep["data"].lower()
    assert "reply to post" not in ep["data"].lower()


# ── user_profile_to_episode ───────────────────────────────────────────────────

def test_user_profile_to_episode_basic_structure():
    profile = {
        "username": "hexonaut",
        "title": "Aligned Delegate (AD)",
        "trust_level": 4,
        "badge_count": 22,
        "bio_raw": "Working on Sky protocol governance and risk.",
        "created_at": "2020-03-15T00:00:00.000Z",
        "last_posted_at": "2026-03-01T12:00:00.000Z",
        "groups": [{"name": "Aligned_Delegates"}],
    }
    stats = {"post_count": 120, "likes_received": 50}
    ep = user_profile_to_episode(profile, stats)
    assert ep["type"] == "text"
    assert ep["source_description"] == "user-hexonaut"
    assert ep["created_at"] == "2020-03-15T00:00:00.000Z"
    assert "@hexonaut" in ep["data"]
    assert "Aligned Delegate" in ep["data"]
    assert "governance" in ep["data"].lower()


def test_user_profile_to_episode_includes_group_membership():
    profile = {
        "username": "rune",
        "title": "Facilitator",
        "trust_level": 4,
        "badge_count": 10,
        "bio_raw": "",
        "created_at": "2019-05-01T00:00:00.000Z",
        "last_posted_at": "2026-02-01T00:00:00.000Z",
        "groups": [{"name": "Aligned_Delegates"}, {"name": "trust_level_4"}],
    }
    stats = {"post_count": 80, "likes_received": 30}
    ep = user_profile_to_episode(profile, stats)
    assert "Aligned_Delegates" in ep["data"]
    assert "trust_level_4" not in ep["data"]  # trust_level groups filtered out


def test_user_profile_to_episode_handles_missing_bio():
    profile = {
        "username": "newuser",
        "title": None,
        "trust_level": 1,
        "badge_count": 2,
        "bio_raw": None,
        "created_at": "2026-01-01T00:00:00.000Z",
        "last_posted_at": "2026-01-10T00:00:00.000Z",
        "groups": [],
    }
    stats = {"post_count": 5, "likes_received": 1}
    ep = user_profile_to_episode(profile, stats)
    assert ep is not None
    assert "@newuser" in ep["data"]

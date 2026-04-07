# governance/ingest.py
from zep_cloud import Zep
from zep_cloud.core.api_error import ApiError

ZEP_USER_ID = "mkr-sky-governance-analyst"


def ensure_user(client: Zep, user_id: str = ZEP_USER_ID) -> None:
    """Create ZEP user if not already present."""
    try:
        client.user.get(user_id=user_id)
    except ApiError:
        client.user.add(
            user_id=user_id,
            first_name="MKR",
            last_name="Governance",
            metadata={
                "domain": "DeFi governance",
                "protocols": ["MakerDAO", "Sky"],
                "data_sources": ["forum.skyeco.com", "vote.makerdao.com"],
            },
        )


def ingest_episodes(client: Zep, episodes: list[dict | None], user_id: str = ZEP_USER_ID) -> int:
    """Send valid episodes to ZEP graph. Returns count of episodes ingested."""
    count = 0
    for ep in episodes:
        if not ep or not ep.get("data"):
            continue
        client.graph.add(
            user_id=user_id,
            data=ep["data"],
            type=ep.get("type", "text"),
            source_description=ep.get("source_description", "governance"),
            created_at=ep.get("created_at"),
        )
        count += 1
    return count


def estimate_credits(episodes: list[dict | None]) -> int:
    """Count valid episodes — each costs 1 ZEP free-tier credit."""
    return sum(1 for ep in episodes if ep and ep.get("data"))

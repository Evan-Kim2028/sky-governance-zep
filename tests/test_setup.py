from unittest.mock import MagicMock
from zep_cloud.core.api_error import ApiError
from governance.ingest import ZEP_GRAPH_ID
from governance.instructions import GOVERNANCE_INSTRUCTIONS


def test_governance_instructions_is_nonempty_string():
    assert isinstance(GOVERNANCE_INSTRUCTIONS, str)
    assert len(GOVERNANCE_INSTRUCTIONS) > 200


def test_governance_instructions_covers_key_terms():
    text = GOVERNANCE_INSTRUCTIONS.lower()
    for term in ["spell", "hat", "atlas", "endgame", "core unit", "mkr", "sky"]:
        assert term in text, f"Missing governance term: {term}"


def test_setup_instructions_calls_add_custom_instructions():
    from scripts.setup_graph import setup_instructions
    client = MagicMock()
    setup_instructions(client)
    client.graph.add_custom_instructions.assert_called_once()
    kwargs = client.graph.add_custom_instructions.call_args.kwargs
    assert ZEP_GRAPH_ID in kwargs["graph_ids"]
    assert len(kwargs["instructions"]) == 1
    assert kwargs["instructions"][0].name == "sky_governance"
    assert kwargs["instructions"][0].text == GOVERNANCE_INSTRUCTIONS

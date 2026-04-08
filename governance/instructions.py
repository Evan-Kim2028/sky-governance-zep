# governance/instructions.py
"""
Governance domain extraction instructions for ZEP Cloud.

Applied via client.graph.add_custom_instructions() during setup.
Requires Flex+ plan — code is always present; ZEP silently ignores on lower plans.

These instructions correct ZEP's general-purpose NLP for MakerDAO/Sky governance
terminology that would otherwise be misclassified.
"""

GOVERNANCE_INSTRUCTIONS = """
This application operates in the MakerDAO/Sky DeFi governance domain.

KEY TERMS AND THEIR GOVERNANCE MEANINGS:

Governance mechanics:
- "spell" or "executive spell": a smart contract that encodes governance-approved
  changes to the protocol. Not magic or sorcery.
- "hat": the executive vote currently holding the most MKR support and therefore
  authorized to cast governance changes. Not clothing.
- "lift": to promote an executive spell to the hat position.
- "delegate" or "aligned delegate": an individual or entity authorized to vote
  on governance polls on behalf of MKR holders. Not a general representative.
- "poll": an off-chain governance vote used to gauge community sentiment or
  choose between options. Not a survey in the general sense.
- "executive vote": an on-chain vote to authorize a spell.
- "MKR weight": the amount of MKR tokens backing a delegate's vote.

Protocol and framework:
- "Atlas": Sky's foundational governance framework document, not a book or mythology.
- "Endgame": MakerDAO's multi-year protocol restructuring plan, not a video game ending.
- "SubDAO": a governed sub-protocol entity within the Sky ecosystem.
- "Core Unit" or "CU": a DAO-recognized organizational unit providing services to governance.
- "Core Unit Facilitator": the lead role within a Core Unit.
- "MIP" or "Maker Improvement Proposal": a formal governance proposal to change the protocol.
- "Sagittarius Engine": a specific Sky protocol component for MKR/SKY tokenomics.

Tokens and assets:
- "MKR": the governance token of MakerDAO (now Sky). Not a person or generic abbreviation.
- "SKY": the new governance token of the Sky rebrand.
- "DAI": the decentralized stablecoin pegged to USD.
- "USDS": the upgraded stablecoin in the Sky ecosystem.
- "WBTC": Wrapped Bitcoin used as collateral in the protocol.

People and roles:
- "hexonaut", "Bonapublica", "Brendan_Navigator", "WPFS", "PALC", "Cloaky",
  "Ecosystem Actor": these are pseudonymous governance participants and roles.
- "BA Labs" (formerly Block Analitica): a risk assessment firm providing
  governance recommendations.
- "Sidestream": a team building governance tooling and executor agents.
- "GAIT": Governance AI Tooling initiative — an effort to use AI in governance.
- "Brendan_Navigator": an AI governance assistant built on ZEP Cloud's knowledge
  graph, not a human person.

Time and events:
- "signal request": a governance discussion thread used to gauge community
  opinion before a formal vote.
- "emergency shutdown" or "ESM": a protocol safety mechanism, not a company closure.
- "debt ceiling": the maximum amount of DAI that can be minted against a collateral type.
"""

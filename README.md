<div align="center">
  <img src="logo.svg" alt="SentinelOracle Logo" width="180" />
  <h1>SentinelOracle</h1>
  <p><b>Decentralized Multi-Agent AI Oracle & Evidence Verification Protocol on GenLayer</b></p>
  
  [![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
  [![GenLayer](https://img.shields.io/badge/Network-Studio_Dev_61997-6366f1.svg)]()
  [![GenVM](https://img.shields.io/badge/GenVM-v0.3.0-059669.svg)]()
  [![Python](https://img.shields.io/badge/Contract-Python-3776AB.svg)]()
</div>
---
**SentinelOracle** is a decentralized oracle protocol built on GenLayer (GenVM v0.3.0) that coordinates multiple invited agents to verify real-world web evidence and resolve missions into deterministic outcomes. It combines strict cryptographic SHA-256 content fingerprinting, nondeterministic LLM classification, comparative equivalence principles, and native GEN escrow mechanics with frozen post-convergence payout denominators.
## On-Chain Deployment

| Parameter | Value |
| :--- | :--- |
| **Network** | GenLayer Studio Dev / Studio Next |
| **Chain ID** | `61997` (`0xf22d`) |
| **GenVM Target** | `v0.3.0` |
| **Contract Address** | `0xA95f422ae4655099E962Fe2196a12155C7D1802d` |
| **Live dApp** | [https://dorinalunar.github.io/SentinelOracle/](https://dorinalunar.github.io/SentinelOracle/) |

## Key Features
- **Multi-Agent Evidence Roster:** Missions require a curated roster of 2 to 8 agents who must join and submit verifiable HTTPS source links along with 64-character SHA-256 content fingerprints.
- **Strict Content Fingerprint Enforcement:** Validators fetch live web content via `gl.nondet.web.render` (up to `MAX_PAYLOAD = 20000` characters) and verify its SHA-256 digest against each agent's submitted `content_hash`. Any fingerprint mismatch forces that agent's belief to `"UNDETERMINED"`, prevents mission convergence (forcing `DIVERGED`), and blocks reward settlement (`ERR_FINGERPRINT_MISMATCH`).
- **Nondeterministic AI Consensus:** Verified source text is classified against allowed outcomes using `gl.nondet.exec_prompt` and validated across nodes via `gl.eq_principle.prompt_comparative`.
- **Frozen Eligibility & Native GEN Payouts:** Initiators fund mission reward pools directly via `@gl.public.write.payable` (`establish_mission` and `fund_mission`). When a mission reaches `CONVERGED` status, the contract freezes `eligible_agents` and locks `payout_denominator`, blocking any post-convergence roster changes (`evict_unresponsive_agent`, `join_mission`, `provide_evidence` revert with `ERR_MISSION_CLOSED`). Eligible agents claim their exact `reward_pool // payout_denominator` share via external native transfers (`_Wallet(Address).emit_transfer`).
- **Zero-Stranding Credit Ledger & Refunds:** Any deposit attached to a call that fails validation is safely booked into `credits_json` and can be retrieved via `withdraw_credit()`. Unresolved or diverged missions can be refunded to the initiator via `refund_mission()`.
- **Command Center Dashboard:** A zero-build vanilla JS/HTML Bento dashboard mapped 1:1 to all 14 contract methods, featuring real content snapshot SHA-256 hashing (`Hash Content`, never URL digests), live mission inspection, escrow controls, and an on-chain transaction terminal.
## Architecture & Tech Stack
- **Smart Contract:** Python (`SentinelOracle.py`) targeting GenVM `v0.3.0` (`sentinel-strict-consensus-v0.3`)
- **Consensus Engine:** `gl.nondet.web.render` + SHA-256 content verification + `gl.nondet.exec_prompt` + `gl.eq_principle.prompt_comparative`
- **Frontend:** Vanilla HTML5, CSS3, ES6 JavaScript (`genlayer-js` SDK + EIP-1193 wallet integration)
- **Network:** GenLayer Studio Dev / Studio Next (Chain ID: `61997`)
## Repository Structure
- `SentinelOracle.py` — Core Intelligent Contract managing missions, rosters, strict SHA-256 content verification, AI consensus, frozen payout denominators, and native GEN escrow/payouts.
- `index.html` — Web interface and 14-method oracle Command Center.
- `main.js` — Frontend logic handling wallet connection, network switching (`61997`), content-based SHA-256 hashing, contract reads/writes, and native token transfers.
- `test_sentinel_oracle.py` — Pytest unit test suite covering mission escrow, anti-stranding credits, full consensus, content fingerprint mismatches, and post-convergence roster freeze protection.
- `SentinelOracle_ONCHAIN_PROOF.md` — On-chain verification guide and transaction lifecycle documentation.
- `ARCHITECTURE.md` — Deep-dive technical specification and state storage layout.
- `CHANGELOG.md` — Release history and security updates.
- `logo.svg` — Project vector emblem.
## Smart Contract Interface
**Escrow & Financial Methods:**
- `establish_mission(mission_id, description, outcomes_json, agents_json)` — *(Payable)* Create a new mission and lock attached GEN into the reward pool.
- `fund_mission(mission_id)` — *(Payable)* Top up the reward pool of an active `PENDING` or `DIVERGED` mission.
- `claim_reward(mission_id)` — Claim an equal share (`reward_pool // payout_denominator`) for a `CONVERGED` mission using the frozen `eligible_agents` snapshot.
- `refund_mission(mission_id)` — Reclaim escrowed GEN if the mission has not converged (initiator only).
- `withdraw_credit()` — Withdraw any GEN booked in the personal anti-stranding credit ledger.
**Agent & Consensus Methods:**
- `join_mission(mission_id)` — Accept an invitation and activate participation in the mission roster (pre-convergence only).
- `evict_unresponsive_agent(mission_id, target_agent)` — Remove an inactive agent from the roster prior to convergence (initiator only, minimum 2 agents preserved; blocked once `CONVERGED` or `REFUNDED`).
- `provide_evidence(mission_id, source_link, content_hash)` — Submit an HTTPS source URL and its 64-character SHA-256 content fingerprint for the current cycle.
- `execute_consensus(mission_id)` — Trigger GenVM web rendering, SHA-256 content verification, and LLM comparative consensus across all submitted evidence.
**Read-Only Views:**
- `fetch_mission(mission_id)` — Returns full mission state, roster, frozen `eligible_agents`, `payout_denominator`, and escrow balances as JSON.
- `fetch_resolution(mission_id, cycle)` — Returns detailed consensus audit logs, per-agent `hash_verified` flags, and security checksums for a specific cycle.
- `get_credit(address)` — Returns withdrawable GEN credit (in wei) for an address.
- `get_escrow_balance()` — Returns total native GEN held by the contract.
- `get_owner()` — Returns the deployer address.
## Getting Started
1. **Clone the repository:**
       git clone https://github.com/dorinalunar/SentinelOracle.git
       cd SentinelOracle
2. **Run the unit test suite:**
       pip install -r requirements.txt
       pytest -v
3. **Launch the dApp:**
   Open `index.html` in a modern browser (or visit [https://dorinalunar.github.io/SentinelOracle/](https://dorinalunar.github.io/SentinelOracle/)), connect your Web3 wallet to **GenLayer Studio Dev (Chain 61997)**, and interact with contract `0xA95f422ae4655099E962Fe2196a12155C7D1802d`.
## License
This project is licensed under the MIT License. See the `LICENSE` file for details.
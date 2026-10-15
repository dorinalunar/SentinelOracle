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

**SentinelOracle** is a decentralized oracle protocol built on GenLayer (GenVM v0.3.0) that coordinates multiple invited agents to verify real-world web evidence and resolve missions into deterministic outcomes. It combines cryptographic SHA-256 content fingerprinting, nondeterministic LLM classification, comparative equivalence principles, and native GEN escrow mechanics.
## On-Chain Deployment

| Parameter | Value |
| :--- | :--- |
| **Network** | GenLayer Studio Dev / Studio Next |
| **Chain ID** | `61997` (`0xf22d`) |
| **GenVM Target** | `v0.3.0` |
| **Contract Address** | `0xCD4E691161169F38DcD95DCBEd7029d5583073D1` |

## Key Features
- **Multi-Agent Evidence Roster:** Missions require a curated roster of 2 to 8 agents who must join and submit verifiable HTTPS source links along with SHA-256 content fingerprints.
- **Nondeterministic AI Consensus:** Validators fetch live web content via `gl.nondet.web.render`, classify evidence against allowed outcomes using `gl.nondet.exec_prompt`, and reach consensus via `gl.eq_principle.prompt_comparative`.
- **Native GEN Escrow & Payouts:** Initiators fund mission reward pools directly via `@gl.public.write.payable` (`establish_mission` and `fund_mission`). When a mission reaches `CONVERGED` status, active agents claim their equal share via external native transfers (`_Wallet(Address).emit_transfer`).
- **Zero-Stranding Credit Ledger & Refunds:** Any deposit attached to a call that fails validation is safely booked into `credits_json` and can be retrieved via `withdraw_credit()`. Unresolved or diverged missions can be refunded to the initiator via `refund_mission()`.
- **Minimalist Command Dashboard:** A clean, zero-build vanilla JS/HTML frontend featuring live mission inspection, SHA-256 hash calculation, escrow controls, and an on-chain transaction terminal.
## Architecture & Tech Stack
- **Smart Contract:** Python (`SentinelOracle.py`) targeting GenVM `v0.3.0`
- **Consensus Engine:** `gl.nondet.web.render` + `gl.nondet.exec_prompt` + `gl.eq_principle.prompt_comparative`
- **Frontend:** Vanilla HTML5, CSS3, ES6 JavaScript (`genlayer-js` SDK + EIP-1193 wallet integration)
- **Network:** GenLayer Studio Dev / Studio Next (Chain ID: `61997`)
## Repository Structure
- `SentinelOracle.py` — Core Intelligent Contract managing missions, rosters, SHA-256 evidence, AI consensus, and native GEN escrow/payouts.
- `index.html` — Minimalist web interface and oracle command center.
- `main.js` — Frontend logic handling wallet connection, network switching (`61997`), contract reads/writes, and native token transfers.
- `test_sentinel_oracle.py` — Unit test suite mocking GenVM v0.3.0 runtime and external EOA transfers.
- `SentinelOracle_ONCHAIN_PROOF.md` — On-chain verification guide and transaction lifecycle documentation.
- `logo.svg` — Project vector emblem.
## Smart Contract Interface
**Escrow & Financial Methods:**
- `establish_mission(mission_id, description, outcomes_json, agents_json)` — *(Payable)* Create a new mission and lock attached GEN into the reward pool.
- `fund_mission(mission_id)` — *(Payable)* Top up the reward pool of an active mission.
- `claim_reward(mission_id)` — Claim an equal share of the reward pool once the mission status is `CONVERGED`.
- `refund_mission(mission_id)` — Reclaim escrowed GEN if the mission has not converged (initiator only).
- `withdraw_credit()` — Withdraw any GEN booked in the personal credit ledger.
**Agent & Consensus Methods:**
- `join_mission(mission_id)` — Accept an invitation and activate participation in the mission roster.
- `evict_unresponsive_agent(mission_id, target_agent)` — Remove an inactive agent from the roster (initiator only, minimum 2 agents preserved).
- `provide_evidence(mission_id, source_link, content_hash)` — Submit an HTTPS source URL and its 64-character SHA-256 content hash for the current cycle.
- `execute_consensus(mission_id)` — Trigger GenVM web rendering and LLM comparative consensus across all submitted evidence.
**Read-Only Views:**
- `fetch_mission(mission_id)` — Returns full mission state, roster, and escrow balances as JSON.
- `fetch_resolution(mission_id, cycle)` — Returns detailed consensus audit logs and security checksums for a specific cycle.
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
   Open `index.html` in a modern browser (or serve locally with `python3 -m http.server 8000`), connect your Web3 wallet to **GenLayer Studio Dev (Chain 61997)**, and interact with contract `0xCD4E691161169F38DcD95DCBEd7029d5583073D1`.
## License
This project is licensed under the MIT License. See the `LICENSE` file for details.

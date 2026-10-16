# SentinelOracle — Technical Architecture & State Specification
## 1. System Overview
**SentinelOracle** (`0xA95f422ae4655099E962Fe2196a12155C7D1802d`) is an autonomous multi-agent oracle built for **GenLayer Studio Dev (Chain ID: 61997, GenVM v0.3.0)**. It resolves real-world questions into deterministic outcomes by combining:
1. **Curated Agent Rosters (`2..8` participants)** providing HTTPS evidence links and strict SHA-256 content fingerprints.
2. **Nondeterministic Web Rendering (`gl.nondet.web.render`)** to retrieve live source text inside the validator runtime.
3. **LLM Classification (`gl.nondet.exec_prompt`)** constrained to a strict JSON output schema.
4. **Comparative Equivalence Consensus (`gl.eq_principle.prompt_comparative`)** ensuring all validators agree on `agreed_outcome` and `resolution_status`.
5. **Native GEN Escrow & EOA Transfers (`_Wallet.emit_transfer`)** with zero-stranding credit protection and frozen post-convergence payout denominators.
---
## 2. Deterministic Storage Layout
To guarantee 100% serialization compatibility across GenVM v0.3.0 validators, contract state is persisted using canonical JSON strings (`sort_keys=True, separators=(",", ":")`):

| State Field | Key Format | Description |
| :--- | :--- | :--- |
| `owner` | `str` | Deployer address (`0x...`) |
| `missions_json` | `mission_id` | Mission metadata, allowed outcomes, roster map, frozen eligible agents, payout denominator, cycle counter, and escrow pool |
| `evidences_json` | `{mission_id}:{cycle}:{agent}` | HTTPS URL and 64-character SHA-256 content fingerprint submitted by an active agent |
| `resolutions_json` | `{mission_id}:{cycle}` | Finalized consensus payload, per-agent verification logs (`hash_verified`), and SHA-256 checksum |
| `credits_json` | `{address_lower}` | Booked native GEN (in wei) from unescrowed payable calls, withdrawable at any time |
| `claimed_rewards_json` | `{mission_id}:{agent}` | Boolean flag preventing double-claiming on `CONVERGED` missions |

---
## 3. State Machine & Financial Flows
### A. Payable Anti-Stranding Mechanism
In GenVM v0.3.0, reverting a transaction that carries `gl.message.value > 0` destroys the attached value. Therefore:
- `establish_mission` and `fund_mission` catch any validation error when `gl.message.value > 0`.
- Instead of reverting, the contract books the entire attached amount into `credits_json[sender]` and returns a structured refusal payload.
- The sender reclaims their tokens via `withdraw_credit()`.
### B. Consensus Pipeline (`execute_consensus`)
1. **Pre-flight Checks**: Verifies the mission is not closed, has at least 2 agents in `roster`, all invited agents have joined (`all(roster.values())`), and every active agent has submitted evidence for `current_cycle`.
2. **Leader Execution (`leader_fn`)**:
   - Iterates over `sorted(roster.keys())`.
   - Calls `gl.nondet.web.render(url, mode="text")` (with fallback to `mode="html"`), truncating at `MAX_PAYLOAD` (20,000 chars).
   - Computes the SHA-256 fingerprint of the fetched content and compares it strictly against the agent's `content_hash`.
   - If an agent's hash does not match, `hash_verified` is set to `False` and their belief is forced to `"UNDETERMINED"`, preventing convergence.
   - Prompts the LLM via `gl.nondet.exec_prompt(..., response_format="json")` to map valid source text to one of the allowed `outcomes`.
   - If all active agents have verified hashes and map to the exact same valid outcome, sets `resolution_status = "CONVERGED"` and `agreed_outcome = beliefs[0]`. Otherwise, sets `resolution_status = "DIVERGED"`.
3. **Validator Equivalence**:
   - `gl.eq_principle.prompt_comparative` enforces that `"agreed_outcome and resolution_status must be identical"`.
4. **State Freeze on Convergence**:
   - When a mission converges, the contract locks `eligible_agents` and `payout_denominator`, rejecting any subsequent roster modifications.
### C. Settlement (`claim_reward` & `refund_mission`)
- **Converged Payouts**: Any eligible agent in the frozen snapshot calls `claim_reward(mission_id)` to receive `reward_pool // payout_denominator` via `_Wallet(Address(caller)).emit_transfer(value=payout)`.
- **Unresolved / Diverged Refunds**: If a mission has not converged, the initiator can call `refund_mission(mission_id)` to recover `funded_amount` and mark the mission as `REFUNDED`.
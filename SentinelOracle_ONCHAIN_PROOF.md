# SentinelOracle — escrow, consensus, and payout verification on chain

| Parameter | Value |
| :--- | :--- |
| Network | GenLayer Studio Dev / Studio Next, chain `61997`, GenVM `v0.3.0` |
| Contract | `0xA95f422ae4655099E962Fe2196a12155C7D1802d` |
| Source | `SentinelOracle.py` |
| Initiator / Agent 1 | `0x38409cCa5F5ca70F3fe189638a87862318b478dd` |
| Agent 2 | `0x68D0CaF57A525AD9146B7dF81c8c5E3871ba7Bf9` |

## Architecture & Financial Mechanics (GenVM v0.3.0)
1. **Payable Escrow (`establish_mission` & `fund_mission`)**:
   Both methods are decorated with `@gl.public.write.payable` and read `gl.message.value`. Because a transaction revert in GenVM v0.3.0 does not return attached value, `establish_mission` and `fund_mission` never raise once value is attached. Any deposit that cannot be escrowed (duplicate mission ID, invalid parameters, or already settled mission) is booked into `credits_json` for the sender.
2. **Credit Retrieval (`withdraw_credit`)**:
   Allows any user to pull back tokens booked in `credits_json` via an external transfer.
3. **Frozen Eligibility & External Native Payouts (`claim_reward`)**:
   When a mission reaches `CONVERGED`, the contract freezes the active agent list into `eligible_agents` and locks the `payout_denominator`. Post-convergence roster modifications (`evict_unresponsive_agent`, `join_mission`, `provide_evidence`) are strictly rejected with `ERR_MISSION_CLOSED`. `claim_reward` verifies that all resolution logs passed SHA-256 fingerprint checks (`ERR_FINGERPRINT_MISMATCH` guard) and uses `@gl.evm.contract_interface` (`_Wallet(Address(addr)).emit_transfer(value=amount)`) to distribute `reward_pool // payout_denominator` to each frozen eligible agent.
4. **Refunds (`refund_mission`)**:
   Allows the mission initiator to reclaim the escrowed reward pool if the mission diverges (`DIVERGED`) or remains unresolved.
5. **Strict Content Fingerprinting & AI Consensus (`execute_consensus`)**:
   Fetches live evidence sources via `gl.nondet.web.render` (up to `MAX_PAYLOAD = 20000` chars) and computes the SHA-256 digest of the rendered content. If an agent's submitted `content_hash` does not match the rendered page content (`hash_verified == False`), that agent's evaluation is forced to `"UNDETERMINED"`, preventing `CONVERGED` status (forcing `DIVERGED`) and blocking any reward settlement. Validated content is classified via `gl.nondet.exec_prompt` and verified across validators using `gl.eq_principle.prompt_comparative`.
## Verification Workflow & Transactions
Balances are in GEN. Contract balance is read with `eth_getBalance`.

| # | Caller | Call | Result | Contract balance |
| :--- | :--- | :--- | :--- | :--- |
| 1 | initiator | `establish_mission("m-1", ..., 2 GEN)` with invalid params | accepted, 2 GEN credited to sender | 2 |
| 2 | initiator | `withdraw_credit()` | 2 GEN returned to initiator wallet | **0** |
| 3 | initiator | `establish_mission("m-1", "Verify release", '["YES","NO"]', '[agent1, agent2]')` with 2 GEN | mission `m-1` created, 2 GEN escrowed | **2** |
| 4 | agent 2 | `join_mission("m-1")` | agent 2 active in roster | 2 |
| 5 | initiator | `provide_evidence("m-1", "https://...", "<sha256_of_content>")` | content evidence recorded for cycle 1 | 2 |
| 6 | agent 2 | `provide_evidence("m-1", "https://...", "<sha256_of_content>")` | content evidence recorded for cycle 1 | 2 |
| 7 | initiator | `execute_consensus("m-1")` | **CONVERGED**; `eligible_agents` & `payout_denominator = 2` frozen | 2 |
| 8 | initiator | `evict_unresponsive_agent("m-1", agent2)` | reverted: `ERR_MISSION_CLOSED` (roster frozen) | 2 |
| 9 | initiator | `refund_mission("m-1")` | reverted: `ERR_CANNOT_REFUND_CONVERGED` | 2 |
| 10 | initiator | `claim_reward("m-1")` | **1 GEN paid to initiator** (`2 GEN / 2`) | **1** |
| 11 | agent 2 | `claim_reward("m-1")` | **1 GEN paid to agent 2** (`2 GEN / 2`) | **0** |
| 12 | agent 2 | `claim_reward("m-1")` again | reverted: `ERR_ALREADY_CLAIMED` | 0 |

## Reproduce
1. **Run focused unit tests** (including content fingerprint mismatch & post-convergence roster freeze tests):
```bash
pytest -v
```
2. **Verify on-chain contract code hash against local source**:
```bash
curl -s -X POST [https://studio-dev.genlayer.com/api](https://studio-dev.genlayer.com/api) -H 'content-type: application/json' \
  -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractCode","params":["0xA95f422ae4655099E962Fe2196a12155C7D1802d"]}' \
  | python3 -c "import sys,json,base64,hashlib; print(hashlib.sha256(base64.b64decode(json.load(sys.stdin)['result'])).hexdigest())"
shasum -a 256 SentinelOracle.py
```
3. **From a dApp, attach the native GEN reward pool directly to the write call (`genlayer-js`)**:
```javascript
await client.writeContract({
  address: "0xA95f422ae4655099E962Fe2196a12155C7D1802d",
  functionName: "establish_mission",
  args: ["m-1", "Mission description", '["YES","NO"]', '["0x...", "0x..."]'],
  value: 2n * 10n ** 18n,
});
```
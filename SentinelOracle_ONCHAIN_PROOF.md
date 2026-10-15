# SentinelOracle — escrow, consensus, and payout verification on chain
| | |
|---|---|
| Network | GenLayer Studio Dev / Studio Next, chain `61997`, GenVM `v0.3.0` |
| Contract | `0xCD4E691161169F38DcD95DCBEd7029d5583073D1` |
| Source | `SentinelOracle.py` |
| Initiator / Agent 1 | `0x38409cCa5F5ca70F3fe189638a87862318b478dd` |
| Agent 2 | `0x68D0CaF57A525AD9146B7dF81c8c5E3871ba7Bf9` |
## Architecture & Financial Mechanics (GenVM v0.3.0)
1. **Payable Escrow (`establish_mission` & `fund_mission`)**:
   Both methods are decorated with `@gl.public.write.payable` and read `gl.message.value`. Because a transaction revert in GenVM v0.3.0 does not return attached value, `establish_mission` and `fund_mission` never raise once value is attached. Any deposit that cannot be escrowed (duplicate mission ID, invalid parameters, or already settled mission) is booked into `credits_json` for the sender.
2. **Credit Retrieval (`withdraw_credit`)**:
   Allows any user to pull back tokens booked in `credits_json` via an external transfer.
3. **External Native Payouts (`claim_reward`)**:
   Uses `@gl.evm.contract_interface` (`_Wallet(Address(addr)).emit_transfer(value=amount)`) to execute external native GEN transfers to EOAs once a mission reaches the `CONVERGED` status. State ledgers (`claimed_rewards_json` and `funded_amount`) are updated prior to emitting the transfer.
4. **Refunds (`refund_mission`)**:
   Allows the mission initiator to reclaim the escrowed reward pool if the mission diverges (`DIVERGED`) or remains unresolved.
5. **Nondeterministic Web & AI Consensus (`execute_consensus`)**:
   Fetches evidence sources via `gl.nondet.web.render`, verifies SHA-256 content fingerprints, classifies outcomes via `gl.nondet.exec_prompt`, and enforces consensus across validators using `gl.eq_principle.prompt_comparative` with positional principle arguments.
## Verification Workflow & Transactions
Balances are in GEN. Contract balance is read with `eth_getBalance`.

| # | Caller | Call | Result | Contract balance |
| :--- | :--- | :--- | :--- | :--- |
| 1 | initiator | `establish_mission("m-1", ..., 2 GEN)` with invalid params | accepted, 2 GEN credited to sender | 2 |
| 2 | initiator | `withdraw_credit()` | 2 GEN returned to initiator wallet | **0** |
| 3 | initiator | `establish_mission("m-1", "Verify release", '["YES","NO"]', '[agent1, agent2]')` with 2 GEN | mission `m-1` created, 2 GEN escrowed | **2** |
| 4 | agent 2 | `join_mission("m-1")` | agent 2 active in roster | 2 |
| 5 | initiator | `provide_evidence("m-1", "https://...", "<sha256>")` | evidence recorded for cycle 1 | 2 |
| 6 | agent 2 | `provide_evidence("m-1", "https://...", "<sha256>")` | evidence recorded for cycle 1 | 2 |
| 7 | initiator | `execute_consensus("m-1")` | **CONVERGED** by AI consensus | 2 |
| 8 | initiator | `refund_mission("m-1")` | reverted: `ERR_CANNOT_REFUND_CONVERGED` | 2 |
| 9 | initiator | `claim_reward("m-1")` | **1 GEN paid to initiator** | **1** |
| 10 | agent 2 | `claim_reward("m-1")` | **1 GEN paid to agent 2** | **0** |
| 11 | agent 2 | `claim_reward("m-1")` again | reverted: `ERR_ALREADY_CLAIMED` | 0 |

## Reproduce
Verify on-chain contract code hash against local source:
    curl -s -X POST https://studio-dev.genlayer.com/api -H 'content-type: application/json' \
      -d '{"jsonrpc":"2.0","id":1,"method":"gen_getContractCode","params":["0xCD4E691161169F38DcD95DCBEd7029d5583073D1"]}' \
      | python3 -c "import sys,json,base64,hashlib; print(hashlib.sha256(base64.b64decode(json.load(sys.stdin)['result'])).hexdigest())"
    shasum -a 256 SentinelOracle.py
From a dApp, attach the native GEN reward pool directly to the write call (genlayer-js):
    await client.writeContract({
      address: "0xCD4E691161169F38DcD95DCBEd7029d5583073D1",
      functionName: "establish_mission",
      args: ["m-1", "Mission description", '["YES","NO"]', '["0x...", "0x..."]'],
      value: 2n * 10n ** 18n,
    });

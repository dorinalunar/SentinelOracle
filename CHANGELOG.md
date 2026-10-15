# Changelog

All notable changes to the **SentinelOracle** project are documented in this file.

## [1.0.0] - 2026-10-15

### Added
- **GenVM v0.3.0 Core Contract (`SentinelOracle.py`)**: Deployed on GenLayer Studio Dev (Chain ID `61997`) at `0xCD4E691161169F38DcD95DCBEd7029d5583073D1`.
- **Native GEN Payable Escrow**: Added `@gl.public.write.payable` support to `establish_mission` and `fund_mission`.
- **Zero-Stranding Credit Ledger**: Automatic booking of rejected payable deposits into `credits_json` with instant recovery via `withdraw_credit()`.
- **External Native EOA Transfers**: Integrated `@gl.evm.contract_interface` (`_Wallet.emit_transfer`) for trustless agent payouts (`claim_reward`) and initiator refunds (`refund_mission`).
- **Comparative AI Consensus**: Implemented `gl.nondet.web.render` evidence fetching, `gl.nondet.exec_prompt` JSON classification, and `gl.eq_principle.prompt_comparative` validation.
- **Bento Command Center dApp (`index.html`, `main.js`)**: Zero-build Web3 frontend mapped 1:1 to all 14 public contract methods with real-time escrow metrics and SHA-256 auto-hashing.
- **Unit Test Suite (`test_sentinel_oracle.py`)**: Comprehensive `pytest` suite mocking GenVM v0.3.0 runtime and EOA native transfers.

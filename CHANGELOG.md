# Changelog

All notable changes to the **SentinelOracle** project are documented in this file.

## [1.1.0] - 2026-10-15

### Added
- **Strict Content Fingerprinting**: Enforced that `content_hash` must match the SHA-256 digest of the rendered page content (never the URL string). Mismatched hashes automatically force `"UNDETERMINED"` and trigger `DIVERGED`.
- **Post-Convergence Roster Freeze**: Locked `eligible_agents` and `payout_denominator` upon mission convergence (`CONVERGED`), preventing post-settlement roster manipulation.
- **Targeted Unit Tests**: Added focused `pytest` regression cases for content fingerprint mismatches and post-convergence roster protection (`test_sentinel_oracle.py`).

## [1.0.0] - 2026-10-15

### Added
- **GenVM v0.3.0 Core Contract (`SentinelOracle.py`)**: Deployed on GenLayer Studio Dev (Chain `61997`) at `0xA95f422ae4655099E962Fe2196a12155C7D1802d`.
- **Native GEN Payable Escrow & Zero-Stranding Credits**: Supported `@gl.public.write.payable` with automatic `credits_json` booking and `withdraw_credit()`.
- **External Native EOA Transfers**: Integrated `_Wallet.emit_transfer` for trustless agent payouts (`claim_reward`) and initiator refunds (`refund_mission`).
- **Bento Command Center dApp (`index.html`, `main.js`)**: 14-method zero-build Web3 interface with real-time stats and content SHA-256 hashing.
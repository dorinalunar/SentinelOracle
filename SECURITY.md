# Security Policy
## Supported Versions

| Version | GenVM Target | Supported |
| :--- | :--- | :--- |
| 1.0.x | `v0.3.0` | Yes |
| < 1.0 | `v0.1.x` | No |

## Security Architecture & Safeguards
**SentinelOracle** (`0xCD4E691161169F38DcD95DCBEd7029d5583073D1`) implements strict security controls for both financial escrow and nondeterministic AI execution:
1. **Anti-Stranding Payable Guards**: In GenVM v0.3.0, value attached to a reverting transaction is not automatically returned. `establish_mission` and `fund_mission` catch validation failures when `gl.message.value > 0` and credit the full amount to `credits_json`, ensuring zero stranded tokens.
2. **Checks-Effects-Interactions (CEI)**: All payout functions (`withdraw_credit`, `claim_reward`, `refund_mission`) update contract state (`credits_json`, `claimed_rewards_json`, `missions_json`) before invoking `_Wallet(Address).emit_transfer(value=amount)`.
3. **SSRF & URL Validation**: Evidence links must use `https://`, cannot exceed 512 characters, and explicitly block `localhost` and `127.0.0.1` targets.
4. **Payload Truncation & Hash Verification**: Web payloads are capped at `MAX_PAYLOAD` (20,000 characters) and fingerprinted with SHA-256 to detect dynamic content tampering between agent submissions and validator execution.
5. **Strict Consensus Schema Verification**: `_verify_schema` validates every field, participant count, outcome set, and SHA-256 `security_hash` before recording a resolution.
## Reporting a Vulnerability
If you discover a security vulnerability within the smart contract or frontend interface:
1. **Do not** open a public GitHub issue.
2. Document the reproduction steps, affected contract method, and potential impact.
3. Contact the repository maintainer directly via GitHub profile channels for coordinated disclosure.

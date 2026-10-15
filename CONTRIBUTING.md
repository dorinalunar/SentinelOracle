# Contributing to SentinelOracle

Thank you for your interest in contributing to **SentinelOracle**, a decentralized AI-driven oracle and evidence verification protocol built on GenLayer (GenVM v0.3.0).

## Development Workflow

1. **Fork & Clone**: Fork the repository and clone it locally.
2. **Environment Setup**: Ensure you have Python 3.10+ installed and install the testing dependencies:

       pip install -r requirements.txt

3. **Run Unit Tests**: Before submitting any changes, verify that the entire test suite passes:

       pytest -v

## Smart Contract Guidelines (`SentinelOracle.py`)

- **GenVM v0.3.0 Compatibility**: Inherit from `gl.contract.Contract`, use `gl.nondet.web.render` for web fetching, and pass comparative principles positionally to `gl.eq_principle.prompt_comparative`.
- **Safe Native Escrow**: Never raise exceptions inside `@gl.public.write.payable` methods once `gl.message.value > 0` is attached. Always book unescrowed funds into `credits_json` so users can recover them via `withdraw_credit()`.
- **External Transfers**: Always use the `@gl.evm.contract_interface` `_Wallet` wrapper (`emit_transfer`) for EOA native payouts, and update internal state before emitting transfers.
- **Deterministic Serialization**: Use `_dumps()` (`json.dumps` with `sort_keys=True` and compact separators) for all state persistence and hash calculations.

## Submitting Pull Requests

- Keep pull requests focused on a single feature or bug fix.
- Add or update unit tests in `test_sentinel_oracle.py` to cover new contract logic or edge cases.
- Ensure all code comments, error identifiers, and documentation are written in clear English.

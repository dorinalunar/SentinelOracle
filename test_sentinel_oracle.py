import json
import hashlib
import sys
import types
import pytest


# ---------------------------------------------------------
# MOCK GENLAYER V0.3.0 ENVIRONMENT
# ---------------------------------------------------------

TRANSFERS = []
MOCK_WEB_CONTENT = "Official announcement: The protocol upgrade succeeded. Outcome is YES."
MOCK_LLM_OUTCOME = {"outcome": "YES"}


def _setup_genlayer_mock():
    gl_mod = types.ModuleType("genlayer")
    gl_types_mod = types.ModuleType("genlayer.types")

    class Address(str):
        def __new__(cls, val):
            return super().__new__(cls, str(val))

    gl_types_mod.Address = Address

    class Message:
        sender_address = Address("0x1111111111111111111111111111111111111111")
        value = 0

    gl_mod.message = Message()

    class ContractBase:
        balance = 0

    class ContractNamespace:
        Contract = ContractBase

    gl_mod.contract = ContractNamespace()

    class EvmNamespace:
        @staticmethod
        def contract_interface(cls):
            class _WalletWrapper:
                def __init__(self, addr):
                    self.addr = str(addr)

                def emit_transfer(self, value: int = 0):
                    TRANSFERS.append((self.addr, int(value)))

            return _WalletWrapper

    gl_mod.evm = EvmNamespace()

    class WriteDecorator:
        def __call__(self, fn):
            return fn

        @staticmethod
        def payable(fn):
            return fn

    class PublicNamespace:
        write = WriteDecorator()

        @staticmethod
        def view(fn):
            return fn

    gl_mod.public = PublicNamespace()

    class WebNamespace:
        @staticmethod
        def render(url: str, mode: str = "text"):
            if "fail.example.com" in url:
                raise RuntimeError("Network error")
            return MOCK_WEB_CONTENT

    class NondetNamespace:
        web = WebNamespace()

        @staticmethod
        def exec_prompt(prompt: str, response_format: str = "json"):
            return dict(MOCK_LLM_OUTCOME)

    gl_mod.nondet = NondetNamespace()

    class EqPrincipleNamespace:
        @staticmethod
        def prompt_comparative(leader_fn, principle: str):
            if not isinstance(principle, str) or not principle:
                raise TypeError("principle must be a non-empty positional string")
            return leader_fn()

    gl_mod.eq_principle = EqPrincipleNamespace()

    sys.modules["genlayer"] = gl_mod
    sys.modules["genlayer.types"] = gl_types_mod
    return gl_mod


gl = _setup_genlayer_mock()

from SentinelOracle import SentinelOracle  # noqa: E402


# ---------------------------------------------------------
# TEST FIXTURES & HELPERS
# ---------------------------------------------------------

AGENT_1 = "0x1111111111111111111111111111111111111111"
AGENT_2 = "0x2222222222222222222222222222222222222222"
AGENT_3 = "0x3333333333333333333333333333333333333333"


def _set_caller(address: str, value: int = 0):
    gl.message.sender_address = address
    gl.message.value = value


@pytest.fixture
def oracle():
    TRANSFERS.clear()
    _set_caller(AGENT_1, 0)
    contract = SentinelOracle()
    contract.balance = 0
    return contract


# ---------------------------------------------------------
# UNIT TESTS
# ---------------------------------------------------------

def test_establish_mission_and_escrow(oracle):
    _set_caller(AGENT_1, 200)
    oracle.balance = 200

    res_str = oracle.establish_mission(
        "mission-1",
        "Verify protocol upgrade status",
        json.dumps(["YES", "NO"]),
        json.dumps([AGENT_1, AGENT_2]),
    )
    res = json.loads(res_str)
    assert res["mission_id"] == "mission-1"
    assert res["escrowed"] == "200"
    assert res["credited"] == "0"

    mission = json.loads(oracle.fetch_mission("mission-1"))
    assert mission["reward_pool"] == "200"
    assert mission["funded_amount"] == "200"
    assert mission["roster"][AGENT_1.lower()] is True
    assert mission["roster"][AGENT_2.lower()] is False


def test_payable_validation_failure_credits_sender_and_withdraws(oracle):
    # First create a valid mission
    _set_caller(AGENT_1, 100)
    oracle.balance = 100
    oracle.establish_mission(
        "mission-dup",
        "Initial mission",
        json.dumps(["YES", "NO"]),
        json.dumps([AGENT_1, AGENT_2]),
    )

    # Attempt to create the same mission ID with 50 GEN attached -> should NOT revert, but credit
    _set_caller(AGENT_2, 50)
    oracle.balance += 50
    dup_res = json.loads(
        oracle.establish_mission(
            "mission-dup",
            "Duplicate mission",
            json.dumps(["YES", "NO"]),
            json.dumps([AGENT_2, AGENT_1]),
        )
    )
    assert dup_res["escrowed"] == "0"
    assert dup_res["credited"] == "50"
    assert dup_res["reason"] == "ERR_MISSION_ID_EXISTS"
    assert oracle.get_credit(AGENT_2) == "50"

    # Withdraw credit back to AGENT_2
    _set_caller(AGENT_2, 0)
    oracle.withdraw_credit()
    assert oracle.get_credit(AGENT_2) == "0"
    assert TRANSFERS[-1] == (AGENT_2, 50)


def test_full_consensus_and_reward_claims(oracle):
    global MOCK_LLM_OUTCOME
    MOCK_LLM_OUTCOME = {"outcome": "YES"}

    # 1. Establish mission with 100 GEN reward pool
    _set_caller(AGENT_1, 100)
    oracle.balance = 100
    oracle.establish_mission(
        "mission-consensus",
        "Did the upgrade succeed?",
        json.dumps(["YES", "NO"]),
        json.dumps([AGENT_1, AGENT_2]),
    )

    # 2. Agent 2 joins
    _set_caller(AGENT_2, 0)
    oracle.join_mission("mission-consensus")

    # 3. Both agents provide valid evidence
    expected_hash = hashlib.sha256(MOCK_WEB_CONTENT.encode()).hexdigest()
    _set_caller(AGENT_1, 0)
    oracle.provide_evidence("mission-consensus", "https://example.com/status", expected_hash)

    _set_caller(AGENT_2, 0)
    oracle.provide_evidence("mission-consensus", "https://example.com/status", expected_hash)

    # 4. Execute consensus
    _set_caller(AGENT_1, 0)
    resolution_json = oracle.execute_consensus("mission-consensus")
    resolution = json.loads(resolution_json)
    assert resolution["resolution_status"] == "CONVERGED"
    assert resolution["agreed_outcome"] == "YES"

    # 5. Initiator cannot refund a CONVERGED mission
    with pytest.raises(Exception, match="ERR_CANNOT_REFUND_CONVERGED"):
        oracle.refund_mission("mission-consensus")

    # 6. Both agents claim their 50 GEN share
    _set_caller(AGENT_1, 0)
    oracle.claim_reward("mission-consensus")
    assert TRANSFERS[-1] == (AGENT_1, 50)

    _set_caller(AGENT_2, 0)
    oracle.claim_reward("mission-consensus")
    assert TRANSFERS[-1] == (AGENT_2, 50)

    # 7. Double claim is blocked
    with pytest.raises(Exception, match="ERR_ALREADY_CLAIMED"):
        oracle.claim_reward("mission-consensus")


def test_refund_unconverged_mission(oracle):
    _set_caller(AGENT_1, 80)
    oracle.balance = 80
    oracle.establish_mission(
        "mission-refund",
        "Unresolved mission",
        json.dumps(["YES", "NO"]),
        json.dumps([AGENT_1, AGENT_2]),
    )

    # Non-initiator cannot refund
    _set_caller(AGENT_2, 0)
    with pytest.raises(Exception, match="ERR_UNAUTHORIZED"):
        oracle.refund_mission("mission-refund")

    # Initiator refunds full escrow
    _set_caller(AGENT_1, 0)
    oracle.refund_mission("mission-refund")
    assert TRANSFERS[-1] == (AGENT_1, 80)

    mission = json.loads(oracle.fetch_mission("mission-refund"))
    assert mission["is_refunded"] is True
    assert mission["reward_pool"] == "0"
    assert mission["latest_status"] == "REFUNDED"


def test_evict_unresponsive_agent(oracle):
    _set_caller(AGENT_1, 0)
    oracle.establish_mission(
        "mission-evict",
        "Three agent mission",
        json.dumps(["YES", "NO"]),
        json.dumps([AGENT_1, AGENT_2, AGENT_3]),
    )

    oracle.evict_unresponsive_agent("mission-evict", AGENT_3)
    mission = json.loads(oracle.fetch_mission("mission-evict"))
    assert AGENT_3.lower() not in mission["roster"]

    # Cannot evict when only 2 agents remain
    with pytest.raises(Exception, match="ERR_MIN_AGENTS_REQUIRED"):
        oracle.evict_unresponsive_agent("mission-evict", AGENT_2)

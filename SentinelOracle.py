# v0.3.0
# { "Depends": "py-genlayer:5jycge4q8k23462jtb0b9fyey1s9qz928sz2nbrd9mg4sxqg2qng" }

import genlayer as gl
from genlayer.types import Address
import hashlib
import json

LIMIT_AGENTS = 8
LIMIT_OUTCOMES = 12
MAX_PAYLOAD = 20000
ORACLE_POLICY = "sentinel-strict-consensus-v0.3"


def _dumps(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"))


@gl.evm.contract_interface
class _Wallet:
    """An account on the chain layer. A wallet (EOA) has no methods, only a balance."""

    class View:
        pass

    class Write:
        pass


def _pay(address: str, amount: int) -> None:
    """Send native GEN from this contract's balance to a wallet."""
    _Wallet(Address(address)).emit_transfer(value=amount)


class SentinelOracle(gl.contract.Contract):
    owner: str
    missions_json: str
    evidences_json: str
    resolutions_json: str
    credits_json: str
    claimed_rewards_json: str

    def __init__(self):
        self.owner = str(gl.message.sender_address)
        self.missions_json = "{}"
        self.evidences_json = "{}"
        self.resolutions_json = "{}"
        self.credits_json = "{}"
        self.claimed_rewards_json = "{}"

    def _load(self, field: str):
        return json.loads(getattr(self, field))

    def _save(self, field: str, data) -> None:
        setattr(self, field, _dumps(data))

    def _credit(self, address: str, amount: int) -> None:
        """Book GEN this contract holds for `address` and owes back on request."""
        if amount <= 0:
            return
        addr = str(address).lower()
        credits = self._load("credits_json")
        credits[addr] = str(int(credits.get(addr, "0")) + amount)
        self._save("credits_json", credits)

    # ---------------------------------------------------------
    # MISSION MANAGEMENT & FINANCE (ESCROW)
    # ---------------------------------------------------------

    @gl.public.write.payable
    def establish_mission(
        self,
        mission_id: str,
        description: str,
        outcomes_json: str,
        agents_json: str
    ) -> str:
        msg_value = int(gl.message.value)
        sender_str = str(gl.message.sender_address).lower()

        try:
            m_id = self._validate_slug(mission_id)
            outcomes = self._parse_strings(outcomes_json, 2, LIMIT_OUTCOMES, "outcomes")
            invited = self._parse_addresses(agents_json)
            clean_desc = self._clean_text(description)

            missions = self._load("missions_json")
            if m_id in missions:
                raise Exception("ERR_MISSION_ID_EXISTS")
            if "UNDETERMINED" in outcomes:
                raise Exception("ERR_RESERVED_KEYWORD_UNDETERMINED")

        except Exception as e:
            if msg_value > 0:
                self._credit(sender_str, msg_value)
                return _dumps({
                    "escrowed": "0",
                    "credited": str(msg_value),
                    "reason": str(e)
                })
            raise Exception(str(e))

        roster = {
            addr: (addr == sender_str)
            for addr in invited
        }

        missions[m_id] = {
            "mission_id": m_id,
            "initiator": str(gl.message.sender_address),
            "description": clean_desc,
            "outcomes": outcomes,
            "invited": invited,
            "roster": roster,
            "eligible_agents": [],
            "payout_denominator": 0,
            "current_cycle": 1,
            "latest_resolution_id": "",
            "latest_status": "PENDING",
            "reward_pool": str(msg_value),
            "funded_amount": str(msg_value),
            "is_refunded": False,
        }
        self._save("missions_json", missions)

        return _dumps({
            "mission_id": m_id,
            "escrowed": str(msg_value),
            "credited": "0",
            "status": "PENDING"
        })

    @gl.public.write.payable
    def fund_mission(self, mission_id: str) -> str:
        """Top up the reward pool of an existing PENDING mission."""
        msg_value = int(gl.message.value)
        if msg_value <= 0:
            raise Exception("ERR_NO_FUNDS_SENT")
        sender_str = str(gl.message.sender_address).lower()

        m_id = mission_id.strip()
        missions = self._load("missions_json")
        mission = missions.get(m_id)

        refusal = ""
        if mission is None:
            refusal = "ERR_MISSION_NOT_FOUND"
        elif mission.get("is_refunded", False):
            refusal = "ERR_MISSION_REFUNDED"
        elif mission.get("latest_status") == "CONVERGED":
            refusal = "ERR_MISSION_ALREADY_CONVERGED"

        if refusal:
            self._credit(sender_str, msg_value)
            return _dumps({"escrowed": "0", "credited": str(msg_value), "reason": refusal})

        new_pool = int(mission.get("reward_pool", "0")) + msg_value
        new_funded = int(mission.get("funded_amount", "0")) + msg_value
        mission["reward_pool"] = str(new_pool)
        mission["funded_amount"] = str(new_funded)
        missions[m_id] = mission
        self._save("missions_json", missions)

        return _dumps({
            "escrowed": str(msg_value),
            "credited": "0",
            "reward_pool": str(new_pool)
        })

    @gl.public.write
    def withdraw_credit(self) -> str:
        """Take back GEN that could not be escrowed."""
        caller = str(gl.message.sender_address).lower()
        credits = self._load("credits_json")
        amount = int(credits.get(caller, "0"))
        if amount <= 0:
            raise Exception("ERR_NO_CREDIT")
        if int(self.balance) < amount:
            raise Exception("ERR_INSUFFICIENT_CONTRACT_BALANCE")

        del credits[caller]
        self._save("credits_json", credits)
        _pay(str(gl.message.sender_address), amount)
        return f"Returned {amount} to {gl.message.sender_address}"

    @gl.public.write
    def claim_reward(self, mission_id: str) -> str:
        """Claim an equal share of the reward pool for a CONVERGED mission."""
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            raise Exception("ERR_MISSION_NOT_FOUND")
        mission = missions[m_id]

        caller_raw = str(gl.message.sender_address)
        sender = caller_raw.lower()

        if mission.get("latest_status") != "CONVERGED":
            raise Exception("ERR_MISSION_NOT_CONVERGED")

        res_id = mission.get("latest_resolution_id", "")
        resolutions = self._load("resolutions_json")
        latest_res = resolutions.get(res_id)
        if not latest_res or latest_res.get("status") != "CONVERGED":
            raise Exception("ERR_MISSION_NOT_CONVERGED")

        res_details = json.loads(latest_res.get("details_json", "{}"))
        res_logs = res_details.get("agent_logs", [])
        if not res_logs or not all(bool(log.get("hash_verified", False)) for log in res_logs):
            raise Exception("ERR_FINGERPRINT_MISMATCH")

        frozen_eligible = mission.get("eligible_agents") or []
        frozen_denominator = int(mission.get("payout_denominator", 0))

        if not frozen_eligible or frozen_denominator <= 0:
            raise Exception("ERR_EMPTY_ROSTER")

        if sender not in frozen_eligible:
            raise Exception("ERR_NOT_ACTIVE_AGENT")

        claim_key = f"{m_id}:{sender}"
        claimed = self._load("claimed_rewards_json")
        if claimed.get(claim_key, False):
            raise Exception("ERR_ALREADY_CLAIMED")

        pool = int(mission.get("reward_pool", "0"))
        payout = pool // frozen_denominator
        if payout <= 0:
            raise Exception("ERR_NOTHING_TO_PAY")
        if int(self.balance) < payout:
            raise Exception("ERR_INSUFFICIENT_CONTRACT_BALANCE")

        claimed[claim_key] = True
        self._save("claimed_rewards_json", claimed)

        current_funded = int(mission.get("funded_amount", "0"))
        mission["funded_amount"] = str(max(0, current_funded - payout))
        missions[m_id] = mission
        self._save("missions_json", missions)

        _pay(caller_raw, payout)
        return f"Reward of {payout} claimed by {caller_raw}"

    @gl.public.write
    def refund_mission(self, mission_id: str) -> str:
        """Return remaining escrow to the initiator if the mission has not CONVERGED."""
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            raise Exception("ERR_MISSION_NOT_FOUND")
        mission = missions[m_id]

        caller_raw = str(gl.message.sender_address)
        sender = caller_raw.lower()

        if sender != str(mission.get("initiator", "")).lower():
            raise Exception("ERR_UNAUTHORIZED")
        if mission.get("latest_status") == "CONVERGED":
            raise Exception("ERR_CANNOT_REFUND_CONVERGED")
        if mission.get("is_refunded", False):
            raise Exception("ERR_ALREADY_REFUNDED")

        amount = int(mission.get("funded_amount", "0"))
        if amount <= 0:
            raise Exception("ERR_NO_FUNDS_TO_REFUND")
        if int(self.balance) < amount:
            raise Exception("ERR_INSUFFICIENT_CONTRACT_BALANCE")

        mission["is_refunded"] = True
        mission["funded_amount"] = "0"
        mission["reward_pool"] = "0"
        mission["latest_status"] = "REFUNDED"
        missions[m_id] = mission
        self._save("missions_json", missions)

        _pay(caller_raw, amount)
        return f"Refunded {amount} to {caller_raw}"

    # ---------------------------------------------------------
    # AGENT AND EVIDENCE MANAGEMENT
    # ---------------------------------------------------------

    @gl.public.write
    def join_mission(self, mission_id: str) -> None:
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            raise Exception("ERR_MISSION_NOT_FOUND")
        mission = missions[m_id]

        if mission.get("is_refunded", False) or mission.get("latest_status") == "CONVERGED":
            raise Exception("ERR_MISSION_CLOSED")

        sender = str(gl.message.sender_address).lower()
        invited_list = mission.get("invited", [])

        if sender not in invited_list:
            raise Exception("ERR_NOT_INVITED")

        roster = mission.get("roster", {})
        if sender not in roster:
            raise Exception("ERR_ROSTER_INCONSISTENT")

        roster[sender] = True
        mission["roster"] = roster
        missions[m_id] = mission
        self._save("missions_json", missions)

    @gl.public.write
    def evict_unresponsive_agent(self, mission_id: str, target_agent: str) -> None:
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            raise Exception("ERR_MISSION_NOT_FOUND")
        mission = missions[m_id]

        if mission.get("is_refunded", False) or mission.get("latest_status") == "CONVERGED":
            raise Exception("ERR_MISSION_CLOSED")

        sender = str(gl.message.sender_address).lower()
        if sender != str(mission.get("initiator", "")).lower():
            raise Exception("ERR_UNAUTHORIZED")

        target = str(target_agent).strip().lower()
        roster = mission.get("roster", {})

        if target not in roster:
            raise Exception("ERR_AGENT_NOT_IN_ROSTER")
        if len(roster) <= 2:
            raise Exception("ERR_MIN_AGENTS_REQUIRED")

        del roster[target]
        mission["roster"] = roster
        missions[m_id] = mission
        self._save("missions_json", missions)

    @gl.public.write
    def provide_evidence(self, mission_id: str, source_link: str, content_hash: str) -> None:
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            raise Exception("ERR_MISSION_NOT_FOUND")
        mission = missions[m_id]

        if mission.get("is_refunded", False) or mission.get("latest_status") == "CONVERGED":
            raise Exception("ERR_MISSION_CLOSED")

        sender = str(gl.message.sender_address).lower()
        roster = mission.get("roster", {})

        if not roster.get(sender, False):
            raise Exception("ERR_NOT_ACTIVE_AGENT")

        cycle = int(mission.get("current_cycle", 1))
        key = self._build_evidence_key(m_id, cycle, sender)

        evidences = self._load("evidences_json")
        if key in evidences:
            raise Exception("ERR_EVIDENCE_ALREADY_PROVIDED")

        evidences[key] = {
            "mission_id": m_id,
            "cycle": cycle,
            "provider": str(gl.message.sender_address),
            "source_link": self._validate_url(source_link),
            "content_hash": self._validate_hash(content_hash)
        }
        self._save("evidences_json", evidences)

    # ---------------------------------------------------------
    # CONSENSUS & LLM V0.3
    # ---------------------------------------------------------

    @gl.public.write
    def execute_consensus(self, mission_id: str) -> str:
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            raise Exception("ERR_MISSION_NOT_FOUND")
        mission = missions[m_id]

        if mission.get("is_refunded", False) or mission.get("latest_status") == "CONVERGED":
            raise Exception("ERR_MISSION_CLOSED")

        roster = mission.get("roster", {})
        if len(roster) < 2:
            raise Exception("ERR_MIN_AGENTS_REQUIRED")
        if not all(roster.values()):
            raise Exception("ERR_PENDING_INVITATIONS")

        cycle = int(mission.get("current_cycle", 1))
        evidences = self._load("evidences_json")

        for agent in roster.keys():
            evidence_key = self._build_evidence_key(m_id, cycle, agent)
            if evidence_key not in evidences:
                raise Exception("ERR_MISSING_AGENT_EVIDENCE")

        resolution_data = self._process_llm_consensus(m_id, mission, evidences)

        if not self._verify_schema(resolution_data, m_id, mission):
            raise Exception("ERR_SCHEMA_VALIDATION_FAILED")

        payload_string = _dumps(resolution_data)
        res_id = f"{m_id}:{cycle}"

        record = {
            "mission_id": m_id,
            "cycle": cycle,
            "status": resolution_data["resolution_status"],
            "agreed_outcome": resolution_data["agreed_outcome"],
            "details_json": payload_string,
            "checksum": hashlib.sha256(payload_string.encode()).hexdigest()
        }

        resolutions = self._load("resolutions_json")
        resolutions[res_id] = record
        self._save("resolutions_json", resolutions)

        mission["latest_resolution_id"] = res_id
        mission["latest_status"] = record["status"]
        if record["status"] == "CONVERGED":
            frozen_agents = sorted(
                str(addr).lower() for addr, active in roster.items() if active
            )
            mission["eligible_agents"] = frozen_agents
            mission["payout_denominator"] = len(frozen_agents)
        mission["current_cycle"] = cycle + 1
        missions[m_id] = mission
        self._save("missions_json", missions)

        return payload_string

    def _process_llm_consensus(self, m_id: str, mission: dict, evidences: dict) -> dict:
        roster = mission["roster"]
        outcomes = mission["outcomes"]
        cycle = int(mission["current_cycle"])
        description = mission["description"]

        def leader_fn() -> str:
            logs = []
            for agent in sorted(roster.keys()):
                evidence_key = self._build_evidence_key(m_id, cycle, agent)
                evidence = evidences[evidence_key]
                web_data = self._grab_web_content(evidence["source_link"])

                hash_match = (
                    web_data["network_status"] == "SUCCESS"
                    and web_data["fingerprint"] == evidence["content_hash"]
                )
                evaluated_belief = "UNDETERMINED"

                if web_data["network_status"] == "SUCCESS" and hash_match:
                    prompt = (
                        f"Mission: {description}\n"
                        f"Allowed Outcomes: {_dumps(outcomes)}\n"
                        f"Source Data: {web_data['content']}\n\n"
                        "Act as a strict deterministic classifier. "
                        "Analyze the Source Data and map it to exactly ONE of the Allowed Outcomes.\n"
                        "Ignore minor variations, ads, or updated timestamps in the text.\n"
                        "Do not invent facts. Do not return explanations.\n"
                        'Return ONLY JSON in this exact form: {"outcome":"..."}'
                    )
                    try:
                        llm_reply = gl.nondet.exec_prompt(prompt, response_format="json")
                        if isinstance(llm_reply, str):
                            llm_reply = json.loads(llm_reply)
                        if isinstance(llm_reply, dict):
                            raw_outcome = str(llm_reply.get("outcome", "UNDETERMINED")).strip().upper()
                            if raw_outcome in outcomes:
                                evaluated_belief = raw_outcome
                    except Exception:
                        evaluated_belief = "UNDETERMINED"

                logs.append({
                    "agent": agent,
                    "fetch_status": web_data["network_status"],
                    "http_code": web_data["http_code"],
                    "hash_verified": hash_match,
                    "agent_belief": evaluated_belief
                })

            beliefs = [log["agent_belief"] for log in logs]
            all_hashes_verified = len(logs) > 0 and all(log["hash_verified"] for log in logs)
            is_unanimous = (
                len(beliefs) > 0
                and all_hashes_verified
                and "UNDETERMINED" not in beliefs
                and all(b == beliefs[0] for b in beliefs)
            )

            payload = {
                "engine_policy": ORACLE_POLICY,
                "mission_id": m_id,
                "cycle_number": cycle,
                "outcomes": outcomes,
                "total_participants": len(roster),
                "agent_logs": logs,
                "agreed_outcome": beliefs[0] if is_unanimous else "UNDETERMINED",
                "resolution_status": "CONVERGED" if is_unanimous else "DIVERGED"
            }
            payload["security_hash"] = self._calculate_security_hash(payload)
            return _dumps(payload)

        result_raw = gl.eq_principle.prompt_comparative(
            leader_fn,
            "`agreed_outcome` and `resolution_status` must be identical.",
        )

        if isinstance(result_raw, dict):
            return result_raw
        try:
            return json.loads(result_raw)
        except Exception:
            raise Exception("ERR_CONSENSUS_PARSE")

    # ---------------------------------------------------------
    # VIEWS
    # ---------------------------------------------------------

    @gl.public.view
    def fetch_mission(self, mission_id: str) -> str:
        m_id = self._validate_slug(mission_id)
        missions = self._load("missions_json")
        if m_id not in missions:
            return _dumps({"error": "ERR_MISSION_NOT_FOUND"})
        return _dumps(missions[m_id])

    @gl.public.view
    def fetch_resolution(self, mission_id: str, cycle: int) -> str:
        key = f"{self._validate_slug(mission_id)}:{int(cycle)}"
        resolutions = self._load("resolutions_json")
        if key not in resolutions:
            return _dumps({"error": "ERR_RESOLUTION_NOT_FOUND"})
        return _dumps(resolutions[key])

    @gl.public.view
    def get_credit(self, address: str) -> str:
        """GEN (in wei) this contract owes back to `address`."""
        addr = str(address).lower()
        return str(int(self._load("credits_json").get(addr, "0")))

    @gl.public.view
    def get_escrow_balance(self) -> str:
        """GEN (in wei) this contract actually holds right now."""
        return str(int(self.balance))

    @gl.public.view
    def get_owner(self) -> str:
        return self.owner

    # ---------------------------------------------------------
    # UTILITIES
    # ---------------------------------------------------------

    def _verify_schema(self, data: dict, m_id: str, mission: dict) -> bool:
        if not isinstance(data, dict):
            return False
        try:
            roster = mission["roster"]
            outcomes = mission["outcomes"]
            roster_agents = sorted(str(agent).lower() for agent in roster.keys())

            if data.get("engine_policy") != ORACLE_POLICY:
                return False
            if data.get("mission_id") != m_id:
                return False
            if int(data.get("cycle_number", -1)) != int(mission["current_cycle"]):
                return False
            if int(data.get("total_participants", -1)) != len(roster):
                return False
            if data.get("resolution_status") not in ("CONVERGED", "DIVERGED"):
                return False
            if not isinstance(data.get("outcomes"), list) or data["outcomes"] != outcomes:
                return False

            logs = data.get("agent_logs")
            if not isinstance(logs, list) or len(logs) != len(roster):
                return False

            logged_agents = []
            for log in logs:
                if not isinstance(log, dict):
                    return False
                for field in ("agent", "fetch_status", "http_code", "hash_verified", "agent_belief"):
                    if field not in log:
                        return False

                agent = str(log["agent"]).lower()
                if agent not in roster:
                    return False
                logged_agents.append(agent)

                if log["fetch_status"] not in ("SUCCESS", "FAILED"):
                    return False
                if not isinstance(log["hash_verified"], bool):
                    return False
                if not isinstance(log["http_code"], int):
                    return False

                belief = str(log["agent_belief"]).upper()
                if belief != "UNDETERMINED" and belief not in outcomes:
                    return False
                if not log["hash_verified"] and belief != "UNDETERMINED":
                    return False

            if sorted(logged_agents) != roster_agents:
                return False

            beliefs = [str(log["agent_belief"]).upper() for log in logs]
            all_hashes_verified = len(logs) > 0 and all(log["hash_verified"] is True for log in logs)
            expected_unanimous = (
                len(beliefs) > 0
                and all_hashes_verified
                and "UNDETERMINED" not in beliefs
                and all(b == beliefs[0] for b in beliefs)
            )
            expected_status = "CONVERGED" if expected_unanimous else "DIVERGED"
            expected_outcome = beliefs[0] if expected_unanimous else "UNDETERMINED"

            if data.get("resolution_status") != expected_status:
                return False
            if data.get("agreed_outcome") != expected_outcome:
                return False

            supplied_hash = str(data.get("security_hash", "")).lower()
            if len(supplied_hash) != 64 or any(c not in "0123456789abcdef" for c in supplied_hash):
                return False

            payload_without_hash = dict(data)
            del payload_without_hash["security_hash"]
            expected_hash = self._calculate_security_hash(payload_without_hash)

            return supplied_hash == expected_hash
        except Exception:
            return False

    def _calculate_security_hash(self, payload: dict) -> str:
        payload_str = _dumps(payload)
        return hashlib.sha256(payload_str.encode()).hexdigest()

    def _grab_web_content(self, url: str) -> dict:
        try:
            raw = gl.nondet.web.render(url, mode="text")
            if raw is None or str(raw).strip() == "":
                raw = gl.nondet.web.render(url, mode="html")

            text = str(raw)[:MAX_PAYLOAD] if raw is not None else ""
            is_valid = len(text.strip()) > 0
            return {
                "network_status": "SUCCESS" if is_valid else "FAILED",
                "http_code": 200 if is_valid else 0,
                "fingerprint": hashlib.sha256(text.encode()).hexdigest(),
                "content": text if is_valid else ""
            }
        except Exception:
            return {
                "network_status": "FAILED",
                "http_code": 0,
                "fingerprint": hashlib.sha256(b"").hexdigest(),
                "content": ""
            }

    def _parse_addresses(self, text: str) -> list:
        try:
            raw = json.loads(text)
        except Exception:
            raise Exception("ERR_INVALID_AGENT_FORMAT")
        if not isinstance(raw, list) or not (2 <= len(raw) <= LIMIT_AGENTS):
            raise Exception(f"ERR_AGENT_COUNT_BOUNDS_2_TO_{LIMIT_AGENTS}")

        validated = []
        for val in raw:
            addr_str = str(val).strip().lower()
            if not addr_str.startswith("0x") or len(addr_str) != 42:
                raise Exception("ERR_INVALID_ADDRESS")
            if addr_str in validated:
                raise Exception("ERR_DUPLICATE_AGENTS")
            validated.append(addr_str)

        sender_str = str(gl.message.sender_address).lower()
        if sender_str not in validated:
            raise Exception("ERR_INITIATOR_MUST_BE_IN_ROSTER")
        return validated

    def _parse_strings(self, text: str, min_len: int, max_len: int, label: str) -> list:
        try:
            raw = json.loads(text)
        except Exception:
            raise Exception(f"ERR_INVALID_{label.upper()}_JSON")
        if not isinstance(raw, list) or not (min_len <= len(raw) <= max_len):
            raise Exception(f"ERR_{label.upper()}_BOUNDS")

        validated = sorted(set(self._clean_text(str(x)).upper() for x in raw))
        if len(validated) != len(raw):
            raise Exception(f"ERR_DUPLICATE_{label.upper()}")
        return validated

    def _build_evidence_key(self, m_id: str, cycle: int, agent: str) -> str:
        return f"{m_id}:{int(cycle)}:{str(agent).lower()}"

    def _validate_slug(self, val: str) -> str:
        cleaned = str(val).strip()
        if not (1 <= len(cleaned) <= 80):
            raise Exception("ERR_INVALID_SLUG_LENGTH")
        return cleaned

    def _clean_text(self, val: str) -> str:
        cleaned = " ".join(str(val).replace('"', "'").split())
        if not (1 <= len(cleaned) <= 1000):
            raise Exception("ERR_TEXT_LENGTH_BOUNDS")
        return cleaned

    def _validate_hash(self, val: str) -> str:
        cleaned = str(val).strip().lower()
        if len(cleaned) != 64 or any(c not in "0123456789abcdef" for c in cleaned):
            raise Exception("ERR_INVALID_SHA256_HASH")
        return cleaned

    def _validate_url(self, val: str) -> str:
        cleaned = str(val).strip()
        if (
            len(cleaned) > 512
            or not cleaned.startswith("https://")
            or "localhost" in cleaned.lower()
            or "127.0.0.1" in cleaned
        ):
            raise Exception("ERR_INVALID_OR_UNSAFE_URL")
        return cleaned

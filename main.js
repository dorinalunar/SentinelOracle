import { createClient } from "https://esm.sh/genlayer-js@latest";
import { studionet } from "https://esm.sh/genlayer-js@latest/chains";

// Deployed SentinelOracle address on GenLayer Studio Dev (Chain 61997).
const DEFAULT_CONTRACT_ADDRESS =
  localStorage.getItem("sentinel_contract_address_v6") ||
  "0xA95f422ae4655099E962Fe2196a12155C7D1802d";

const STUDIO_CHAIN_ID_DEC = 61997;
const STUDIO_CHAIN_ID_HEX = "0xf22d";
const STUDIO_RPC_URL = "https://studio-dev.genlayer.com/api";
const EXPLORER_BASE_URL = "https://explorer-studio-dev.genlayer.com/address/";
const WEI_PER_GEN = 10n ** 18n;
const MAX_PAYLOAD = 20000;

const studioDevChain = {
  ...studionet,
  id: STUDIO_CHAIN_ID_DEC,
  name: "GenLayer Studio Dev",
  rpcUrls: {
    ...(studionet?.rpcUrls || {}),
    default: { http: [STUDIO_RPC_URL] },
    public: { http: [STUDIO_RPC_URL] },
  },
};

let connectedAccount = null;
let contractAddress = DEFAULT_CONTRACT_ADDRESS;
let cachedOwnerAddress = "";
let glClient = null;

// DOM Elements
const connectBtn = document.getElementById("connectBtn");
const connectInlineBtn = document.getElementById("connectInlineBtn");
const networkBadge = document.getElementById("networkBadge");
const kpiAccount = document.getElementById("kpiAccount");
const kpiEscrow = document.getElementById("kpiEscrow");
const metricEscrowPool = document.getElementById("metricEscrowPool");
const kpiCredit = document.getElementById("kpiCredit");
const kpiOwner = document.getElementById("kpiOwner");
const contractAddressInput = document.getElementById("contractAddressInput");
const inspectorOutput = document.getElementById("inspectorOutput");
const terminalLog = document.getElementById("terminalLog");
const liveMissionsBody = document.getElementById("liveMissionsBody");

contractAddressInput.value = contractAddress;

// =========================================================
// TABS NAVIGATION
// =========================================================
const tabButtons = document.querySelectorAll(".tab-btn");
const tabPanes = document.querySelectorAll(".tab-pane");

function activateTab(tabId) {
  tabButtons.forEach((btn) => {
    btn.classList.toggle("active", btn.dataset.tab === tabId);
  });
  tabPanes.forEach((pane) => {
    pane.classList.toggle("active", pane.id === tabId);
  });
}

tabButtons.forEach((btn) => {
  btn.addEventListener("click", () => activateTab(btn.dataset.tab));
});

// =========================================================
// LOGGING & FORMATTING HELPERS
// =========================================================
function logTerminal(message, type = "info") {
  const time = new Date().toLocaleTimeString();
  const div = document.createElement("div");
  div.className = "log-entry";
  const cssClass = type === "ok" ? "log-ok" : type === "err" ? "log-err" : "log-info";
  div.innerHTML = `<span class="log-time">[${time}]</span><span class="${cssClass}">${message}</span>`;
  terminalLog.prepend(div);
}

function formatGen(weiStr) {
  try {
    const wei = BigInt(weiStr || "0");
    const whole = wei / WEI_PER_GEN;
    const frac = (wei % WEI_PER_GEN).toString().padStart(18, "0").slice(0, 4).replace(/0+$/, "");
    return frac ? `${whole}.${frac} GEN` : `${whole} GEN`;
  } catch {
    return `${weiStr} wei`;
  }
}

function parseGenToWei(genAmount) {
  const num = Number(genAmount || 0);
  if (isNaN(num) || num <= 0) return 0n;
  const milli = BigInt(Math.round(num * 10000));
  return (milli * WEI_PER_GEN) / 10000n;
}

function shortAddr(addr) {
  if (!addr || String(addr).length < 12) return addr || "—";
  const s = String(addr);
  return `${s.slice(0, 6)}...${s.slice(-4)}`;
}

function upsertLiveMissionRow(missionObj) {
  if (!missionObj || !missionObj.mission_id) return;
  const emptyRow = document.getElementById("emptyMissionsRow");
  if (emptyRow) emptyRow.remove();

  const mId = missionObj.mission_id;
  const desc = missionObj.description || "On-chain mission";
  const escrow = formatGen(missionObj.reward_pool || "0");
  const roster = missionObj.roster || {};
  const totalAgents = Object.keys(roster).length || 0;
  const activeAgents = Object.values(roster).filter(Boolean).length;
  const frozenDenom = Number(missionObj.payout_denominator || 0);
  const statusRaw = (missionObj.latest_status || "PENDING").toUpperCase();
  const cycle = missionObj.current_cycle || 1;

  let badgeClass = "pending";
  let badgeText = statusRaw;
  if (statusRaw === "CONVERGED") {
    badgeClass = "converged";
  } else if (statusRaw === "DIVERGED" || statusRaw === "REFUNDED") {
    badgeClass = "diverged";
  }

  const rosterLabel =
    frozenDenom > 0
      ? `${activeAgents}/${totalAgents} (frozen: ${frozenDenom})`
      : `${activeAgents}/${totalAgents}`;

  const existingBtn = liveMissionsBody.querySelector(`button[data-mid="${mId}"]`);
  const tr = existingBtn ? existingBtn.closest("tr") : document.createElement("tr");

  tr.innerHTML = `
    <td style="font-family: var(--mono); color: var(--text);">${mId}</td>
    <td>${desc.slice(0, 48)}</td>
    <td style="font-family: var(--mono);">${escrow}</td>
    <td style="font-family: var(--mono); font-size: 0.76rem;">${rosterLabel}</td>
    <td><span class="status-pill ${badgeClass}">● ${badgeText}</span></td>
    <td>Cycle #${cycle}</td>
    <td><button class="btn-table-view" data-mid="${mId}">View</button></td>
  `;

  if (!existingBtn) {
    liveMissionsBody.prepend(tr);
  }
}

liveMissionsBody.addEventListener("click", (e) => {
  const btn = e.target.closest(".btn-table-view");
  if (!btn) return;
  const mId = btn.dataset.mid;
  document.getElementById("inspectMissionId").value = mId;
  activateTab("tab-results");
  document.getElementById("command-center").scrollIntoView({ behavior: "smooth" });
  if (contractAddressInput.value.trim()) {
    document.getElementById("fetchMissionBtn").click();
  }
});

document.getElementById("quickLookupBtn").addEventListener("click", () => {
  const mId = document.getElementById("quickLookupInput").value.trim();
  if (!mId) return;
  document.getElementById("inspectMissionId").value = mId;
  activateTab("tab-results");
  document.getElementById("fetchMissionBtn").click();
});

// =========================================================
// GENLAYER CLIENT & WALLET CONNECTION (CHAIN 61997)
// =========================================================
function rebuildClient() {
  try {
    const config = {
      chain: studioDevChain,
      endpoint: STUDIO_RPC_URL,
    };
    if (connectedAccount) {
      config.account = connectedAccount;
    }
    glClient = createClient(config);
  } catch (err) {
    logTerminal(`Client init warning: ${err.message}`, "err");
  }
}

async function ensureStudioNetwork() {
  if (!window.ethereum) {
    throw new Error("No Web3 wallet detected. Please install MetaMask or Rabby.");
  }
  const currentChain = await window.ethereum.request({ method: "eth_chainId" });
  if (String(currentChain).toLowerCase() !== STUDIO_CHAIN_ID_HEX) {
    try {
      await window.ethereum.request({
        method: "wallet_switchEthereumChain",
        params: [{ chainId: STUDIO_CHAIN_ID_HEX }],
      });
    } catch (switchErr) {
      if (switchErr.code === 4902) {
        await window.ethereum.request({
          method: "wallet_addEthereumChain",
          params: [
            {
              chainId: STUDIO_CHAIN_ID_HEX,
              chainName: "GenLayer Studio Dev",
              nativeCurrency: { name: "GEN", symbol: "GEN", decimals: 18 },
              rpcUrls: [STUDIO_RPC_URL],
              blockExplorerUrls: ["https://explorer-studio-dev.genlayer.com"],
            },
          ],
        });
      } else {
        throw switchErr;
      }
    }
  }
}

async function connectWallet() {
  try {
    await ensureStudioNetwork();
    const accounts = await window.ethereum.request({ method: "eth_requestAccounts" });
    if (!accounts || accounts.length === 0) {
      throw new Error("No wallet accounts authorized.");
    }
    connectedAccount = accounts[0];
    kpiAccount.textContent = shortAddr(connectedAccount);
    connectBtn.textContent = shortAddr(connectedAccount);
    connectInlineBtn.textContent = "Connected";
    networkBadge.innerHTML = `<span style="color: #10b981;">●</span> <span>GenLayer (Chain ID ${STUDIO_CHAIN_ID_DEC})</span>`;

    rebuildClient();
    logTerminal(`Wallet connected: ${connectedAccount}`, "ok");
    await refreshContractStats();
  } catch (err) {
    logTerminal(`Wallet error: ${err.message}`, "err");
    throw err;
  }
}

if (window.ethereum && window.ethereum.on) {
  window.ethereum.on("chainChanged", () => {
    rebuildClient();
  });

  window.ethereum.on("accountsChanged", (accounts) => {
    if (accounts && accounts.length > 0) {
      connectedAccount = accounts[0];
      kpiAccount.textContent = shortAddr(connectedAccount);
      connectBtn.textContent = shortAddr(connectedAccount);
      rebuildClient();
      logTerminal(`Active account changed to ${connectedAccount}`, "info");
    }
  });
}

function requireContract() {
  const addr = contractAddressInput.value.trim();
  if (!addr || !addr.startsWith("0x") || addr.length !== 42) {
    throw new Error("Enter a valid 42-character 0x SentinelOracle address in Contract Status.");
  }
  contractAddress = addr;
  localStorage.setItem("sentinel_contract_address_v6", contractAddress);
  return contractAddress;
}

async function readContract(functionName, args = []) {
  const address = requireContract();
  if (!glClient) rebuildClient();
  return await glClient.readContract({
    address,
    functionName,
    args,
  });
}

async function writeContract(functionName, args = [], valueWei = 0n) {
  const address = requireContract();
  if (!connectedAccount) {
    await connectWallet();
  } else {
    await ensureStudioNetwork();
  }
  rebuildClient();

  logTerminal(
    `Calling ${functionName}(${args.map((a) => JSON.stringify(a)).join(", ")})` +
      (valueWei > 0n ? ` [value: ${valueWei.toString()} wei]` : "") +
      "...",
    "info"
  );

  const txParams = {
    address,
    functionName,
    args,
  };
  if (valueWei > 0n) {
    txParams.value = valueWei;
  }

  const txHash = await glClient.writeContract(txParams);
  logTerminal(`Transaction accepted! TxHash: ${txHash}`, "ok");
  return txHash;
}

async function refreshContractStats() {
  if (!contractAddressInput.value.trim()) return;
  try {
    const [escrowRaw, ownerRaw] = await Promise.all([
      readContract("get_escrow_balance", []),
      readContract("get_owner", []),
    ]);
    const formattedEscrow = formatGen(escrowRaw);
    kpiEscrow.textContent = formattedEscrow;
    if (metricEscrowPool) {
      metricEscrowPool.textContent = formattedEscrow;
    }

    cachedOwnerAddress = String(ownerRaw || "");
    kpiOwner.textContent = shortAddr(cachedOwnerAddress);

    const targetAddr = connectedAccount || document.getElementById("inspectCreditAddr").value.trim();
    if (targetAddr) {
      const creditRaw = await readContract("get_credit", [targetAddr]);
      kpiCredit.textContent = formatGen(creditRaw);
    }
  } catch {
    // Silent catch to prevent background view sync noise during node state transitions
  }
}

// =========================================================
// UI CONTROLS & EXPLORER LINKS
// =========================================================
connectBtn.addEventListener("click", () => connectWallet().catch(() => {}));
connectInlineBtn.addEventListener("click", () => connectWallet().catch(() => {}));
document.getElementById("refreshStatsBtn").addEventListener("click", refreshContractStats);
document.getElementById("refreshTopBtn").addEventListener("click", refreshContractStats);

document.getElementById("saveContractBtn").addEventListener("click", async () => {
  try {
    const addr = requireContract();
    logTerminal(`Loaded SentinelOracle contract: ${addr}`, "ok");
    await refreshContractStats();
  } catch (err) {
    logTerminal(err.message, "err");
  }
});

document.getElementById("copyOwnerBtn").addEventListener("click", () => {
  if (!cachedOwnerAddress) return;
  navigator.clipboard.writeText(cachedOwnerAddress);
  logTerminal(`Copied owner address: ${cachedOwnerAddress}`, "info");
});

document.getElementById("copyContractBtn").addEventListener("click", () => {
  const addr = contractAddressInput.value.trim();
  if (!addr) return;
  navigator.clipboard.writeText(addr);
  logTerminal(`Copied contract address: ${addr}`, "info");
});

function openInExplorer() {
  const addr = contractAddressInput.value.trim();
  const url = addr ? `${EXPLORER_BASE_URL}${addr}` : "https://explorer-studio-dev.genlayer.com";
  window.open(url, "_blank", "noopener");
}

document.getElementById("openExplorerBtn").addEventListener("click", openInExplorer);
document.getElementById("explorerBottomBtn").addEventListener("click", openInExplorer);

document.getElementById("clearLogBtn").addEventListener("click", () => {
  terminalLog.innerHTML = "";
});

// Compute SHA-256 content_hash strictly from page content (never from the URL string)
document.getElementById("genHashBtn").addEventListener("click", async () => {
  try {
    const evContentEl = document.getElementById("evContent");
    const urlVal = document.getElementById("evUrl").value.trim();
    let rawContent = evContentEl ? evContentEl.value : "";

    if (!rawContent || rawContent.trim() === "") {
      if (!urlVal || !urlVal.startsWith("https://")) {
        throw new Error(
          "Paste the evidence page text into 'Evidence Content Snapshot' or enter a valid https:// URL to fetch its content."
        );
      }
      logTerminal(`Fetching live page content from ${urlVal} for SHA-256 fingerprinting...`, "info");
      const response = await fetch(urlVal, { method: "GET" });
      if (!response.ok) {
        throw new Error(`HTTP ${response.status} when fetching ${urlVal}`);
      }
      rawContent = await response.text();
      if (evContentEl) {
        evContentEl.value = rawContent.slice(0, MAX_PAYLOAD);
      }
    }

    const boundedContent = String(rawContent).slice(0, MAX_PAYLOAD);
    if (boundedContent.trim() === "") {
      throw new Error("Evidence content cannot be empty. URL digests are not permitted.");
    }

    const encoder = new TextEncoder();
    const data = encoder.encode(boundedContent);
    const hashBuffer = await crypto.subtle.digest("SHA-256", data);
    const hashHex = Array.from(new Uint8Array(hashBuffer))
      .map((b) => b.toString(16).padStart(2, "0"))
      .join("");

    document.getElementById("evHash").value = hashHex;
    logTerminal(
      `Computed SHA-256 content_hash from ${boundedContent.length} chars of evidence content: ${hashHex.slice(0, 18)}...`,
      "ok"
    );
  } catch (err) {
    logTerminal(
      `Content hash error: ${err.message}. Paste the rendered text directly into 'Evidence Content Snapshot' to hash it.`,
      "err"
    );
  }
});

// =========================================================
// ALL 9 CONTRACT WRITE METHODS
// =========================================================

// 1. establish_mission(mission_id, description, outcomes_json, agents_json) [@payable]
document.getElementById("establishBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("estMissionId").value.trim();
    const description = document.getElementById("estDescription").value.trim();
    const outcomes_json = document.getElementById("estOutcomes").value.trim();
    const agents_json = document.getElementById("estAgents").value.trim();
    const genVal = document.getElementById("estRewardGen").value;
    const valueWei = parseGenToWei(genVal);

    await writeContract("establish_mission", [mission_id, description, outcomes_json, agents_json], valueWei);
    await refreshContractStats();
  } catch (err) {
    logTerminal(`establish_mission error: ${err.message}`, "err");
  }
});

// 2. fund_mission(mission_id) [@payable]
document.getElementById("fundMissionBtn").addEventListener("click", async () => {
  try {
    const mission_id =
      document.getElementById("estMissionId").value.trim() ||
      document.getElementById("finMissionId").value.trim();
    const genVal = document.getElementById("topupGen").value;
    const valueWei = parseGenToWei(genVal);
    await writeContract("fund_mission", [mission_id], valueWei);
    await refreshContractStats();
  } catch (err) {
    logTerminal(`fund_mission error: ${err.message}`, "err");
  }
});

// 3. join_mission(mission_id)
document.getElementById("joinMissionBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("actMissionId").value.trim();
    await writeContract("join_mission", [mission_id]);
  } catch (err) {
    logTerminal(`join_mission error: ${err.message}`, "err");
  }
});

// 4. provide_evidence(mission_id, source_link, content_hash)
document.getElementById("provideEvidenceBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("actMissionId").value.trim();
    const source_link = document.getElementById("evUrl").value.trim();
    const content_hash = document.getElementById("evHash").value.trim();
    await writeContract("provide_evidence", [mission_id, source_link, content_hash]);
  } catch (err) {
    logTerminal(`provide_evidence error: ${err.message}`, "err");
  }
});

// 5. evict_unresponsive_agent(mission_id, target_agent)
document.getElementById("evictAgentBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("actMissionId").value.trim();
    const target_agent = document.getElementById("evictAgentAddr").value.trim();
    await writeContract("evict_unresponsive_agent", [mission_id, target_agent]);
  } catch (err) {
    logTerminal(`evict_unresponsive_agent error: ${err.message}`, "err");
  }
});

// 6. execute_consensus(mission_id)
document.getElementById("executeConsensusBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("finMissionId").value.trim();
    await writeContract("execute_consensus", [mission_id]);
  } catch (err) {
    logTerminal(`execute_consensus error: ${err.message}`, "err");
  }
});

// 7. claim_reward(mission_id)
document.getElementById("claimRewardBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("finMissionId").value.trim();
    await writeContract("claim_reward", [mission_id]);
    await refreshContractStats();
  } catch (err) {
    logTerminal(`claim_reward error: ${err.message}`, "err");
  }
});

// 8. refund_mission(mission_id)
document.getElementById("refundMissionBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("finMissionId").value.trim();
    await writeContract("refund_mission", [mission_id]);
    await refreshContractStats();
  } catch (err) {
    logTerminal(`refund_mission error: ${err.message}`, "err");
  }
});

// 9. withdraw_credit()
document.getElementById("withdrawCreditBtn").addEventListener("click", async () => {
  try {
    await writeContract("withdraw_credit", []);
    await refreshContractStats();
  } catch (err) {
    logTerminal(`withdraw_credit error: ${err.message}`, "err");
  }
});

// =========================================================
// ALL 5 CONTRACT VIEW METHODS
// =========================================================

// 10. fetch_mission(mission_id)
document.getElementById("fetchMissionBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("inspectMissionId").value.trim();
    const res = await readContract("fetch_mission", [mission_id]);
    const parsed = typeof res === "string" ? JSON.parse(res) : res;
    inspectorOutput.textContent = JSON.stringify(parsed, null, 2);
    if (parsed && !parsed.error) {
      upsertLiveMissionRow(parsed);
    }
    logTerminal(`fetch_mission("${mission_id}") succeeded.`, "ok");
  } catch (err) {
    inspectorOutput.textContent = `Error: ${err.message}`;
    logTerminal(`fetch_mission error: ${err.message}`, "err");
  }
});

// 11. fetch_resolution(mission_id, cycle)
document.getElementById("fetchResolutionBtn").addEventListener("click", async () => {
  try {
    const mission_id = document.getElementById("inspectMissionId").value.trim();
    const cycle = Number(document.getElementById("inspectCycle").value || 1);
    const res = await readContract("fetch_resolution", [mission_id, cycle]);
    const parsed = typeof res === "string" ? JSON.parse(res) : res;
    inspectorOutput.textContent = JSON.stringify(parsed, null, 2);
    logTerminal(`fetch_resolution("${mission_id}", ${cycle}) succeeded.`, "ok");
  } catch (err) {
    inspectorOutput.textContent = `Error: ${err.message}`;
    logTerminal(`fetch_resolution error: ${err.message}`, "err");
  }
});

// 12. get_credit(address)
document.getElementById("viewCreditBtn").addEventListener("click", async () => {
  try {
    const addr = document.getElementById("inspectCreditAddr").value.trim() || connectedAccount;
    if (!addr) throw new Error("Enter an address or connect wallet to query get_credit(address).");
    const res = await readContract("get_credit", [addr]);
    inspectorOutput.textContent = JSON.stringify(
      { method: "get_credit", address: addr, credit_wei: String(res), credit_formatted: formatGen(res) },
      null,
      2
    );
    kpiCredit.textContent = formatGen(res);
    logTerminal(`get_credit("${shortAddr(addr)}") -> ${formatGen(res)}`, "ok");
  } catch (err) {
    inspectorOutput.textContent = `Error: ${err.message}`;
    logTerminal(`get_credit error: ${err.message}`, "err");
  }
});

// 13. get_escrow_balance()
document.getElementById("viewEscrowBtn").addEventListener("click", async () => {
  try {
    const res = await readContract("get_escrow_balance", []);
    const formatted = formatGen(res);
    inspectorOutput.textContent = JSON.stringify(
      { method: "get_escrow_balance", escrow_wei: String(res), escrow_formatted: formatted },
      null,
      2
    );
    kpiEscrow.textContent = formatted;
    if (metricEscrowPool) {
      metricEscrowPool.textContent = formatted;
    }
    logTerminal(`get_escrow_balance() -> ${formatted}`, "ok");
  } catch (err) {
    inspectorOutput.textContent = `Error: ${err.message}`;
    logTerminal(`get_escrow_balance error: ${err.message}`, "err");
  }
});

// 14. get_owner()
document.getElementById("viewOwnerBtn").addEventListener("click", async () => {
  try {
    const res = await readContract("get_owner", []);
    cachedOwnerAddress = String(res || "");
    inspectorOutput.textContent = JSON.stringify({ method: "get_owner", owner: cachedOwnerAddress }, null, 2);
    kpiOwner.textContent = shortAddr(cachedOwnerAddress);
    logTerminal(`get_owner() -> ${cachedOwnerAddress}`, "ok");
  } catch (err) {
    inspectorOutput.textContent = `Error: ${err.message}`;
    logTerminal(`get_owner error: ${err.message}`, "err");
  }
});

// Initialize on load
rebuildClient();
if (contractAddress) {
  refreshContractStats();
}
logTerminal(
  `SentinelOracle Dashboard initialized with contract ${shortAddr(contractAddress)} (Chain ${STUDIO_CHAIN_ID_DEC}).`,
  "info"
);
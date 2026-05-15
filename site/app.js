const statusPill = document.getElementById("status-pill");
const updatedAt = document.getElementById("updated-at");
const libraryCount = document.getElementById("library-count");
const searchInput = document.getElementById("search-input");
const filterBar = document.getElementById("filter-bar");
const incidentList = document.getElementById("incident-list");
const rebuildDemoButton = document.getElementById("rebuild-demo-button");
const controlStatus = document.getElementById("control-status");
const API_BASE =
  window.CAPSTONE_API_BASE ||
  (["127.0.0.1", "localhost"].includes(window.location.hostname) ? "http://127.0.0.1:8000" : "");

const heroChain = document.getElementById("hero-chain");
const heroTitle = document.getElementById("hero-title");
const heroSummary = document.getElementById("hero-summary");
const heroSourceLabel = document.getElementById("hero-source-label");
const heroSourceCount = document.getElementById("hero-source-count");
const heroSourceNote = document.getElementById("hero-source-note");
const heroCompletenessLabel = document.getElementById("hero-completeness-label");
const heroCompleteness = document.getElementById("hero-completeness");
const heroCompletenessNote = document.getElementById("hero-completeness-note");
const heroEvidenceLabel = document.getElementById("hero-evidence-label");
const heroEvidenceMix = document.getElementById("hero-evidence-mix");
const heroEvidenceNote = document.getElementById("hero-evidence-note");
const discoveryModeSummary = document.getElementById("discovery-mode-summary");
const monitoredSourcesSummary = document.getElementById("monitored-sources-summary");
const latestDiscoverySummary = document.getElementById("latest-discovery-summary");
const discoveryGapSummary = document.getElementById("discovery-gap-summary");
const storyBlock = document.getElementById("story-block");
const timelineList = document.getElementById("timeline-list");
const factsGrid = document.getElementById("facts-grid");
const evidenceClaims = document.getElementById("evidence-claims");
const sourceGroups = document.getElementById("source-groups");
const coverageList = document.getElementById("coverage-list");
const agentStageList = document.getElementById("agent-stage-list");
const runStatusSection = document.getElementById("run-status-section");
const agentStagesSection = document.getElementById("agent-stages-section");
const runSource = document.getElementById("run-source");
const runIncident = document.getElementById("run-incident");
const runState = document.getElementById("run-state");
const runUpdated = document.getElementById("run-updated");

const authSignedOut = document.getElementById("auth-signed-out");
const authSignedIn = document.getElementById("auth-signed-in");
const authEmailInput = document.getElementById("auth-email-input");
const authPasswordInput = document.getElementById("auth-password-input");
const loginButton = document.getElementById("login-button");
const registerButton = document.getElementById("register-button");
const logoutButton = document.getElementById("logout-button");
const authUserEmail = document.getElementById("auth-user-email");
const authUserRole = document.getElementById("auth-user-role");
const authStatus = document.getElementById("auth-status");

const scheduleForm = document.getElementById("schedule-form");
const scheduleEnabledInput = document.getElementById("schedule-enabled-input");
const scheduleIntervalInput = document.getElementById("schedule-interval-input");
const scheduleSourcesInput = document.getElementById("schedule-sources-input");
const scheduleExecuteAugmentationInput = document.getElementById("schedule-execute-augmentation-input");
const scheduleSubmitButton = document.getElementById("schedule-submit-button");
const scheduleStatus = document.getElementById("schedule-status");

const augmentForm = document.getElementById("augment-form");
const augmentChainInput = document.getElementById("augment-chain-input");
const augmentProtocolInput = document.getElementById("augment-protocol-input");
const augmentIncidentInput = document.getElementById("augment-incident-input");
const augmentIncidentIdInput = document.getElementById("augment-incident-id-input");
const augmentSeedUrlsInput = document.getElementById("augment-seed-urls-input");
const augmentAttackTxInput = document.getElementById("augment-attack-tx-input");
const augmentTagsInput = document.getElementById("augment-tags-input");
const augmentSubmitButton = document.getElementById("augment-submit-button");

const discoveryForm = document.getElementById("discovery-form");
const discoverySourcesInput = document.getElementById("discovery-sources-input");
const discoveryExecuteAugmentationInput = document.getElementById("discovery-execute-augmentation-input");
const discoverySubmitButton = document.getElementById("discovery-submit-button");

const adminUsersSection = document.getElementById("admin-users-section");
const adminUsersList = document.getElementById("admin-users-list");
const adminUsersStatus = document.getElementById("admin-users-status");
const jobList = document.getElementById("job-list");

const AUTH_TOKEN_STORAGE_KEY = "signaldesk.authToken";
const DISCOVERY_SCHEDULE_NAME = "daily_discovery";

const state = {
  library: [],
  filtered: [],
  bundles: new Map(),
  selectedIncidentId: null,
  activeFilter: "All",
  dataMode: "live API",
  fallbackSamples: [],
  trackedJobs: [],
  jobPollTimer: null,
  currentUser: null,
  discoverySchedule: null,
  discoveryOverview: null,
  userDirectory: [],
};

function formatDate(value) {
  if (!value) {
    return "Unknown";
  }
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) {
    return value;
  }
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

function splitParagraphs(text) {
  return String(text || "")
    .split(/\n\s*\n/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function uniqueValues(values) {
  return [...new Set(values.filter(Boolean))];
}

function humanizeLabel(value) {
  const raw = String(value || "").trim();
  if (!raw) {
    return "-";
  }

  const mapped = {
    demo_live_dossier: "published brief",
    demo_corpus: "publishing set",
    auto_collected_lead: "auto-collected lead",
    snapshot_only: "local snapshot",
    local_snapshot: "local snapshot",
    fallback_only: "local snapshot",
  };

  const normalized = mapped[raw] || raw;
  return normalized
    .replace(/_/g, " ")
    .replace(/\bapi\b/gi, "API")
    .replace(/\btx\b/gi, "TX")
    .replace(/\bpoc\b/gi, "PoC")
    .replace(/\b[a-z]/g, (char) => char.toUpperCase());
}

function productizeText(value) {
  return String(value || "")
    .replace(/demo browsing/gi, "daily brief reading")
    .replace(/public demo incident set/gi, "published incident set")
    .replace(/public example set/gi, "published incident set")
    .replace(/demo corpus/gi, "published set")
    .replace(/demo live dossier/gi, "published brief");
}

function classifyTypeCount(entry) {
  return `${entry.report_count || 0} report / ${entry.explorer_count || 0} explorer / ${entry.social_count || 0} social / ${entry.poc_count || 0} PoC`;
}

function normalizeCompleteness(value) {
  const numeric = Number(value);
  if (!Number.isFinite(numeric)) {
    return 0;
  }
  if (numeric > 1) {
    return Math.max(0, Math.min(1, numeric / 100));
  }
  return Math.max(0, Math.min(1, numeric));
}

function formatCompleteness(value) {
  return `${Math.round(normalizeCompleteness(value) * 100)}%`;
}

function pluralize(value, singular, plural) {
  return `${value} ${value === 1 ? singular : plural}`;
}

function createLink(url, text) {
  const link = document.createElement("a");
  link.href = url;
  link.target = "_blank";
  link.rel = "noreferrer";
  link.textContent = text;
  return link;
}

function parseListInput(value, { separator = /\n|,/ } = {}) {
  return String(value || "")
    .split(separator)
    .map((item) => item.trim())
    .filter(Boolean);
}

function getAuthToken() {
  return window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY) || "";
}

function setAuthToken(token) {
  if (token) {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, token);
  } else {
    window.localStorage.removeItem(AUTH_TOKEN_STORAGE_KEY);
  }
}

function buildAuthHeaders() {
  const token = getAuthToken();
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function apiFetch(path, options = {}) {
  const headers = {
    ...(options.headers || {}),
    ...buildAuthHeaders(),
  };
  const requestUrl = API_BASE ? `${API_BASE}${path}` : path;
  const response = await fetch(requestUrl, {
    ...options,
    headers,
  });

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const payload = await response.clone().json();
      if (payload?.detail) {
        detail = payload.detail;
      }
    } catch {}

    if (response.status === 401) {
      throw new Error(detail || "Please sign in first.");
    }
    throw new Error(detail);
  }
  return response;
}

function setControlStatus(message) {
  controlStatus.textContent = message;
}

function setAuthStatus(message) {
  authStatus.textContent = message;
}

function setScheduleStatus(message) {
  scheduleStatus.textContent = message;
}

function setAdminUsersStatus(message) {
  adminUsersStatus.textContent = message;
}

function canOperate() {
  return Boolean(state.currentUser && ["operator", "admin"].includes(state.currentUser.role));
}

function isAdmin() {
  return Boolean(state.currentUser && state.currentUser.role === "admin");
}

function setOperationControlsEnabled(enabled) {
  const elements = [
    scheduleEnabledInput,
    scheduleIntervalInput,
    scheduleSourcesInput,
    scheduleExecuteAugmentationInput,
    scheduleSubmitButton,
    augmentChainInput,
    augmentProtocolInput,
    augmentIncidentInput,
    augmentIncidentIdInput,
    augmentSeedUrlsInput,
    augmentAttackTxInput,
    augmentTagsInput,
    augmentSubmitButton,
    discoverySourcesInput,
    discoveryExecuteAugmentationInput,
    discoverySubmitButton,
    rebuildDemoButton,
  ];

  for (const element of elements) {
    if (!element) {
      continue;
    }
    element.disabled = !enabled;
  }
}

function getAnalystReport(bundle) {
  return bundle.analyst_report || null;
}

function getTechnicalAnalysis(bundle) {
  return bundle.technical_analysis || bundle.augmented_incident?.technical_analysis || null;
}

function getExternalExplorerEnrichment(bundle) {
  return bundle.external_enrichment || bundle.technical_analysis?.external_validation || null;
}

function buildFallbackDiscoveryOverview() {
  const snapshotIncidents = state.library.length;
  return {
    intended_flow: [
      "automatic discovery",
      "evidence expansion",
      "chain analysis",
      "analyst report",
    ],
    monitored_sources: ["slowmist", "web3sec", "external_explorer", "defihacklabs"],
    schedule: {
      configured: false,
      status: "snapshot_only",
      interval_seconds: 0,
      execute_augmentation: false,
      last_enqueued_at: null,
    },
    latest_discovery_run: null,
    incident_origin_breakdown: {
      demo_corpus: snapshotIncidents,
    },
    current_gap: {
      status: "snapshot_only",
      summary: "This page is running from a stored snapshot, so the automatic discovery loop is not visible here yet.",
      details: [
        `${snapshotIncidents} incidents are being shown from static files.`,
        "The live backend is required for fresh automatic collection.",
      ],
    },
  };
}

function renderDiscoveryOverview() {
  const overview = state.discoveryOverview || buildFallbackDiscoveryOverview();
  const monitoredSources = overview.monitored_sources || [];
  const schedule = overview.schedule || {};
  const latestRun = overview.latest_discovery_run || null;
  const breakdown = overview.incident_origin_breakdown || {};
  const demoCount = breakdown.demo_corpus || 0;
  const autoCount = breakdown.discovery_sync || 0;

  discoveryModeSummary.textContent = schedule.configured
    ? `Watching ${monitoredSources.length} source${monitoredSources.length === 1 ? "" : "s"} and moving new leads into augmentation.`
    : "Live discovery exists, but the schedule is not configured yet.";

  monitoredSourcesSummary.textContent = monitoredSources.length
    ? monitoredSources.map((value) => humanizeLabel(value)).join(", ")
    : "No monitored source list is available yet.";

  latestDiscoverySummary.textContent = latestRun
    ? `${pluralize(latestRun.incident_count || 0, "incident", "incidents")} found from ${pluralize(latestRun.record_count || 0, "record", "records")} on ${formatDate(latestRun.completed_at)}.`
    : "No finished discovery run yet.";

  const breakdownSummary =
    autoCount || demoCount
      ? `Current public mix: ${pluralize(autoCount, "auto-discovered case", "auto-discovered cases")} and ${pluralize(demoCount, "curated demo case", "curated demo cases")}.`
      : "Public incident mix not available yet.";
  discoveryGapSummary.textContent = `${overview.current_gap?.summary || "No gap summary available."} ${breakdownSummary}`;
}

function describeDataMode() {
  if (state.dataMode === "live API") {
    return "live backend";
  }
  return "local snapshot";
}

function buildFallbackLibraryEntry(item) {
  const sourceCount = item.sources.length + (item.attack_tx_url ? 1 : 0) + (item.poc_url ? 1 : 0);
  return {
    incident_id: item.incident_id,
    title: item.project_name,
    protocol_name: item.project_name,
    chain: item.chain,
    incident_date: item.incident_date,
    summary: item.summary,
    status: "snapshot_only",
    completeness_score: 0.45,
    source_count: sourceCount,
    direct_source_count: item.sources.length,
    secondary_source_count: 0,
    social_count: item.sources.filter((source) => `${source.label} ${source.url}`.toLowerCase().includes("x / twitter")).length,
    poc_count: item.poc_url ? 1 : 0,
    explorer_count: item.attack_tx_url ? 1 : 0,
    report_count: item.sources.length,
    missing_fields: [],
    last_updated: "",
    pattern_label: item.attack_type.toLowerCase().replace(/\s+/g, "_"),
    attack_tx_hashes: [],
    source_preview: item.sources.map((source) => source.url).slice(0, 6),
  };
}

function buildFallbackBundle(item) {
  const sourceEntries = [];
  let index = 1;

  for (const source of item.sources) {
    sourceEntries.push({
      source_id: `src-${String(index).padStart(3, "0")}`,
      url: source.url,
      source_type: "report",
      discovered_from: "snapshot_bundle",
      depth: 0,
      fetch_status: "not_fetched",
    });
    index += 1;
  }

  if (item.attack_tx_url) {
    sourceEntries.push({
      source_id: `src-${String(index).padStart(3, "0")}`,
      url: item.attack_tx_url,
      source_type: "explorer",
      discovered_from: "snapshot_bundle",
      depth: 0,
      fetch_status: "not_fetched",
    });
    index += 1;
  }

  if (item.poc_url) {
    sourceEntries.push({
      source_id: `src-${String(index).padStart(3, "0")}`,
      url: item.poc_url,
      source_type: "poc",
      discovered_from: "snapshot_bundle",
      depth: 0,
      fetch_status: "not_fetched",
    });
  }

  const timeline = [
    {
      step_id: "step-001",
      order: 1,
      label: "Snapshot incident loaded",
      step_type: "entry",
      summary: `${item.project_name} is being shown from a local snapshot because the live backend is currently unavailable.`,
      confidence: 0.65,
    },
    {
      step_id: "step-002",
      order: 2,
      label: "Summary carried from the stored incident file",
      step_type: "summary",
      summary: splitParagraphs(item.summary)[0] || "No summary available.",
      confidence: 0.55,
    },
  ];

  return {
    incident_id: item.incident_id,
    incident_library_entry: buildFallbackLibraryEntry(item),
    augmented_incident: {
      incident_id: item.incident_id,
      title: item.project_name,
      chain: item.chain,
      incident_date: item.incident_date,
      protocol_name: item.project_name,
      status: "snapshot_only",
      summary: item.summary,
      key_addresses: [],
      key_contracts: [item.attack_contract_url, item.victim_contract_url].filter(Boolean),
      key_transactions: [],
      timeline,
      attacker_profile: {
        recent_activity_summary: "This snapshot is showing stored incident content rather than a fresh live run.",
      },
      pattern_hypotheses: [
        {
          label: item.attack_type.toLowerCase().replace(/\s+/g, "_"),
          summary: `This stored incident is tagged as ${item.attack_type}.`,
        },
      ],
      source_summary: {
        source_count: sourceEntries.length,
        direct_source_count: sourceEntries.length,
        secondary_source_count: 0,
      },
      quality_report: {
        completeness_score: 0.45,
        direct_source_count: sourceEntries.length,
        secondary_source_count: 0,
        fetched_source_count: 0,
        citation_coverage_count: 0,
        missing_fields: [
          "live_run_bundle",
          "agent_trace",
          "source_fetch_results",
        ],
        judge_summary: "You are reading the stored snapshot. Reconnect the backend to resume fresh discovery and augmentation.",
      },
    },
    source_index: { sources: sourceEntries },
    source_documents: { documents: [] },
    run_state: {
      current_stage: "snapshot_only",
      node_status: {},
      updated_at: "",
    },
    run_events: {
      events: [
        {
          stage: "snapshot_only",
          agent: "Local snapshot mode",
          status: "completed",
          note: "The UI loaded stored incident content because the live backend was unavailable.",
        },
      ],
    },
    agent_trace: {
      agents: [
        {
          agent_name: "Local snapshot mode",
          status: "completed",
          note: "No fresh live pipeline run exists in this mode.",
        },
      ],
    },
  };
}

function updateAuthUi() {
  const signedIn = Boolean(state.currentUser);
  authSignedOut.classList.toggle("is-hidden", signedIn);
  authSignedIn.classList.toggle("is-hidden", !signedIn);
  adminUsersSection.classList.toggle("is-hidden", !isAdmin());
  runStatusSection.classList.toggle("is-hidden", !canOperate());
  agentStagesSection.classList.toggle("is-hidden", !canOperate());

  if (!signedIn) {
    authUserEmail.textContent = "-";
    authUserRole.textContent = "reader";
    setAuthStatus("Read mode is open. Sign in to manage research operations.");
    setScheduleStatus("Sign in with operator access to configure the automatic discovery loop.");
    setAdminUsersStatus("Admin access required.");
    setOperationControlsEnabled(false);
    return;
  }

  authUserEmail.textContent = state.currentUser.email;
  authUserRole.textContent = state.currentUser.role;

  if (canOperate()) {
    setAuthStatus(`Signed in as ${state.currentUser.role}. Research tools are available.`);
    setOperationControlsEnabled(true);
  } else {
    setAuthStatus("Signed in successfully. This account can read, but research actions stay off until an admin promotes it.");
    setScheduleStatus("This account can read, but it cannot manage the discovery loop yet.");
    setOperationControlsEnabled(false);
  }

  if (!isAdmin()) {
    setAdminUsersStatus("Admin access required.");
  }
}

function renderFilters() {
  const filters = ["All", ...uniqueValues(state.library.map((item) => item.chain))];
  filterBar.replaceChildren();

  for (const filter of filters) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "filter-chip";
    if (filter === state.activeFilter) {
      button.classList.add("is-active");
    }
    button.textContent = filter;
    button.addEventListener("click", () => {
      state.activeFilter = filter;
      applyFilters();
    });
    filterBar.appendChild(button);
  }
}

function renderIncidentList() {
  incidentList.replaceChildren();
  libraryCount.textContent = `${state.filtered.length} visible`;

  if (state.filtered.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No incident matches this filter yet.";
    incidentList.appendChild(empty);
    return;
  }

  for (const item of state.filtered) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "incident-row";
    if (item.incident_id === state.selectedIncidentId) {
      button.classList.add("is-selected");
    }
    button.innerHTML = `
      <div class="incident-row-head">
        <strong>${item.title}</strong>
        <span>${item.chain}</span>
      </div>
      <p>${humanizeLabel(item.pattern_label || "incident")}</p>
      <div class="incident-row-meta">
        <span>${item.incident_date || "Unknown date"}</span>
        <span>${formatCompleteness(item.completeness_score || 0)} analysis complete</span>
      </div>
    `;
    button.addEventListener("click", async () => {
      state.selectedIncidentId = item.incident_id;
      renderIncidentList();
      try {
        await renderSelectedIncident();
      } catch (error) {
        setControlStatus(error instanceof Error ? error.message : String(error));
      }
    });
    incidentList.appendChild(button);
  }
}

function renderStory(bundle) {
  storyBlock.replaceChildren();
  const report = getAnalystReport(bundle);
  const technical = getTechnicalAnalysis(bundle);
  const external_explorer = getExternalExplorerEnrichment(bundle);
  const labels = external_explorerLabels(external_explorer).slice(0, 6);
  const fundTransfers = external_explorerFundTransfers(external_explorer);
  if (!report) {
    const node = document.createElement("p");
    node.textContent = productizeText(bundle.augmented_incident.summary || "No analyst profile is available yet.");
    storyBlock.appendChild(node);
    return;
  }

  const attackerProfile = report.attacker_profile || bundle.augmented_incident.attacker_profile || {};
  const attackerFacts = [
    attackerProfile.funding_source ? `Funding: ${attackerProfile.funding_source}` : "",
    attackerProfile.deployment_to_attack_time ? `Deploy timing: ${attackerProfile.deployment_to_attack_time}` : "",
    attackerProfile.pre_attack_activity ? `Pre-attack: ${attackerProfile.pre_attack_activity}` : "",
    attackerProfile.post_attack_fund_flow ? `Post-attack flow: ${attackerProfile.post_attack_fund_flow}` : "",
    attackerProfile.confidence ? `Confidence: ${humanizeLabel(attackerProfile.confidence)}` : "",
  ].filter(Boolean);
  const cards = [
    {
      title: "Case overview",
      body: report.case_overview?.what_happened || bundle.augmented_incident.summary,
    },
    {
      title: "Why this case matters",
      body: report.case_overview?.why_it_matters || bundle.quality_report?.judge_summary,
    },
    {
      title: "Attacker view",
      body: attackerProfile.summary || attackerProfile.recent_activity_summary,
    },
    {
      title: "Attack profile signals",
      body: attackerFacts.join(" · "),
    },
    labels.length
      ? {
          title: "ExternalExplorer address labels",
          body: labels.map((item) => `${shortAddr(item.address)} = ${item.label}`).join(" · "),
        }
      : null,
    fundTransfers.length
      ? {
          title: "ExternalExplorer fund flow",
          body: `${fundTransfers.length} transfer hop(s) cached from ExternalExplorer. First hop: ${shortAddr(fundTransfers[0].from)} to ${shortAddr(fundTransfers[0].to)} (${fundTransfers[0].amount || "unknown amount"}).`,
        }
      : null,
    {
      title: "Technical analysis",
      body: technical?.exploit_mechanism || technical?.validation_verdict || null,
    },
  ].filter((item) => item?.body);

  for (const cardData of cards) {
    const card = document.createElement("article");
    card.className = "analyst-card";
    card.innerHTML = `<strong>${cardData.title}</strong><p>${productizeText(cardData.body)}</p>`;
    storyBlock.appendChild(card);
  }
}

function renderTimeline(bundle) {
  timelineList.replaceChildren();
  const report = getAnalystReport(bundle);
  const chain = bundle.augmented_incident?.chain || bundle.incident_library_entry?.chain || "";
  const steps = report?.exploit_path?.steps || bundle.augmented_incident.timeline || [];

  for (const [index, step] of steps.entries()) {
    const row = document.createElement("li");
    row.className = "timeline-item";
    const txLinks = (step.tx_hashes || []).slice(0, 3).map((tx) => explorerLink(tx, step.chain || chain, "tx"));
    const meta = [
      step.timestamp ? `Time: ${step.timestamp}` : "",
      step.chain ? `Chain: ${step.chain}` : "",
      (step.called_contracts || []).length ? `Contracts: ${(step.called_contracts || []).length}` : "",
      (step.function_selectors || []).length ? `Selectors: ${(step.function_selectors || []).join(", ")}` : "",
      step.verification_status ? `Status: ${humanizeLabel(step.verification_status)}` : "",
    ].filter(Boolean);
    row.innerHTML = `
      <div class="timeline-order">${String(index + 1).padStart(2, "0")}</div>
      <div class="timeline-copy">
        <strong>${productizeText(step.title || step.label || `Step ${index + 1}`)}</strong>
        <p>${productizeText(step.detail || step.summary || step.description || "")}</p>
        ${meta.length ? `<span>${meta.map(escapeHtml).join(" · ")}</span>` : ""}
        ${txLinks.length ? `<span>Tx: ${txLinks.join(" · ")}</span>` : ""}
      </div>
    `;
    timelineList.appendChild(row);
  }
}

function renderFacts(bundle) {
  factsGrid.replaceChildren();
  const incident = bundle.augmented_incident;
  const entry = bundle.incident_library_entry || {};
  const report = getAnalystReport(bundle);
  const technical = getTechnicalAnalysis(bundle);
  const external_explorer = getExternalExplorerEnrichment(bundle);
  const chain = incident.chain || entry.chain || "";
  const txHashes = (technical?.tx_hashes || report?.fund_flow?.key_transactions || incident.key_transactions || []).filter(Boolean);
  const trackedAddresses = (report?.fund_flow?.key_addresses || report?.attacker_profile?.attacker_addresses || incident.key_addresses || []).filter(Boolean);
  const external_explorerProfit = summarizeExternalExplorerProfit(external_explorer, chain);
  const facts = [
    { label: "Project", value: incident.protocol_name || entry.protocol_name || "Unknown" },
    { label: "Chain", value: chain || "Unknown" },
    { label: "Incident date", value: incident.incident_date || entry.incident_date || "Unknown" },
    { label: "Pattern", value: humanizeLabel(entry.pattern_label || incident.pattern_hypotheses?.[0]?.label || "Unknown") },
    {
      label: "Key transactions",
      value: txHashes.length ? "" : "0",
      html: txHashes.slice(0, 3).map((tx) => explorerLink(tx, chain, "tx")).join(" · "),
    },
    {
      label: "Tracked addresses",
      value: trackedAddresses.length ? "" : "0",
      html: trackedAddresses.slice(0, 3).map((addr) => explorerLink(addr, chain, "address")).join(" · "),
    },
    external_explorerProfit
      ? { label: "ExternalExplorer balance-change", value: "", html: external_explorerProfit }
      : { label: "ExternalExplorer balance-change", value: external_explorer ? humanizeLabel(external_explorer.status || "Cached") : "Not cached" },
    { label: "Primary sources", value: String((report?.case_overview?.primary_sources || []).length || incident.source_summary?.direct_source_count || entry.direct_source_count || 0) },
    { label: "Technical status", value: humanizeLabel(technical?.status || "Not requested") },
    { label: "Analysis Completeness", value: formatCompleteness(bundle.quality_report?.completeness_score || entry.completeness_score || 0) },
  ].filter(Boolean);

  for (const fact of facts) {
    const row = document.createElement("div");
    row.className = "fact-card";
    row.innerHTML = `
      <span class="fact-label">${fact.label}</span>
      <strong class="fact-value">${fact.html || escapeHtml(fact.value)}</strong>
    `;
    factsGrid.appendChild(row);
  }
}

// ─── Fund Flow Section ────────────────────────────────────────────────────

function renderFundFlowSection(bundle) {
  const technical = getTechnicalAnalysis(bundle);
  const external_explorer  = getExternalExplorerEnrichment(bundle);
  const chain     = bundle.augmented_incident?.chain || "";

  // 1. TX Hash list
  const txListEl = document.getElementById("tx-hashes-list");
  if (txListEl) {
    const hashes = (technical?.tx_hashes || []).filter(Boolean);
    if (hashes.length) {
      txListEl.innerHTML = `
        <div class="ff-sub-head">Key Transactions</div>
        <ul class="tx-hash-list">
          ${hashes.map(h => `
            <li>
              <a href="${escapeHtml(explorerTxUrl(h, chain))}" target="_blank" rel="noopener"
                 class="tx-hash-link" title="${escapeHtml(h)}">
                <span class="tx-hash-mono">${h.slice(0,10)}…${h.slice(-6)}</span>
                <span class="tx-hash-full">${escapeHtml(h)}</span>
                ↗
              </a>
            </li>`).join("")}
        </ul>`;
    } else {
      txListEl.innerHTML = "";
    }
  }

  // 2. ExternalExplorer Fund Flow transfers table
  const ffEl = document.getElementById("fund-flow-transfers");
  if (ffEl) {
    const transfers = external_explorerFundTransfers(external_explorer);
    const labels    = Object.fromEntries((external_explorerLabels(external_explorer) || []).map(l => [l.address?.toLowerCase(), l.label]));
    if (transfers.length) {
      const labelOrShort = addr => labels[addr?.toLowerCase()] || (addr ? addr.slice(0,8)+"…"+addr.slice(-4) : "—");
      ffEl.innerHTML = `
        <div class="ff-sub-head">Fund Flow <span class="ff-badge">ExternalExplorer</span></div>
        <div class="ff-table-wrap">
          <table class="ff-table">
            <thead><tr><th>#</th><th>From</th><th>To</th><th>Amount</th><th>Token</th></tr></thead>
            <tbody>
              ${transfers.slice(0, 20).map(t => `
                <tr class="${t.isReverted ? "ff-reverted" : ""}">
                  <td class="ff-id">${t.id}</td>
                  <td><a href="${escapeHtml(explorerAddrUrl(t.from, chain))}" target="_blank" rel="noopener" class="ff-addr" title="${escapeHtml(t.from || "")}">${escapeHtml(labelOrShort(t.from))}</a></td>
                  <td><a href="${escapeHtml(explorerAddrUrl(t.to, chain))}" target="_blank" rel="noopener" class="ff-addr" title="${escapeHtml(t.to || "")}">${escapeHtml(labelOrShort(t.to))}</a></td>
                  <td class="ff-amount">${escapeHtml(String(t.amount || ""))}</td>
                  <td class="ff-token"><a href="${escapeHtml(explorerAddrUrl(t.token, chain))}" target="_blank" rel="noopener" title="${escapeHtml(t.token || "")}">${escapeHtml(labelOrShort(t.token))}</a></td>
                </tr>`).join("")}
            </tbody>
          </table>
        </div>`;
    } else {
      ffEl.innerHTML = "";
    }
  }

  // 3. Balance Changes (from ExternalExplorer)
  const bcEl = document.getElementById("balance-changes-table");
  if (bcEl) {
    const changes = external_explorerBalanceChanges(external_explorer)
      .filter(c => Number(c.totalValue || 0) > 0 || Number(c.totalValue || 0) < 0)
      .sort((a, b) => Math.abs(Number(b.totalValue)) - Math.abs(Number(a.totalValue)))
      .slice(0, 8);
    if (changes.length) {
      const labels = Object.fromEntries((external_explorerLabels(external_explorer) || []).map(l => [l.address?.toLowerCase(), l.label]));
      const labelOrShort = addr => labels[addr?.toLowerCase()] || (addr ? addr.slice(0,8)+"…"+addr.slice(-4) : "—");
      bcEl.innerHTML = `
        <div class="ff-sub-head">Balance Changes <span class="ff-badge">ExternalExplorer</span></div>
        <div class="ff-table-wrap">
          <table class="ff-table">
            <thead><tr><th>Address</th><th>Net Change (USD)</th><th>Assets</th></tr></thead>
            <tbody>
              ${changes.map(c => {
                const usd = Number(c.totalValue || 0);
                const sign = c.sign ? "+" : "-";
                const cls  = c.sign ? "ff-profit" : "ff-loss";
                const assets = (c.assets || []).slice(0,3).map(a =>
                  `${a.sign ? "+" : "-"}${escapeHtml(String(a.amount || ""))} ${escapeHtml(labelOrShort(a.address))}`
                ).join(", ");
                return `<tr>
                  <td><a href="${escapeHtml(explorerAddrUrl(c.account, chain))}" target="_blank" rel="noopener" class="ff-addr" title="${escapeHtml(c.account || "")}">${escapeHtml(labelOrShort(c.account))}</a></td>
                  <td class="${cls}">${sign}$${Math.abs(usd).toLocaleString(undefined,{maximumFractionDigits:0})}</td>
                  <td class="ff-assets">${assets}</td>
                </tr>`;
              }).join("")}
            </tbody>
          </table>
        </div>`;
    } else {
      bcEl.innerHTML = "";
    }
  }
}

// ─── Technical Evidence Graph ─────────────────────────────────────────────

const TECH_ROLE_ORDER = [
  "attacker_eoa",
  "attacker_contracts",
  "flash_loan_providers",
  "routers",
  "pairs",
  "victim",
  "tokens",
  "oracles",
];

const TECH_ROLE_COLUMNS = {
  attacker_eoa: 0,
  attacker_contracts: 1,
  flash_loan_providers: 2,
  routers: 3,
  pairs: 4,
  victim: 5,
  tokens: 5,
  oracles: 2,
};

const TECH_ROLE_LABELS = {
  attacker_eoa: "Attacker EOA",
  attacker_contracts: "Attacker contract",
  flash_loan_providers: "Flash loan",
  routers: "Router",
  pairs: "Pair",
  victim: "Victim",
  tokens: "Token",
  oracles: "Oracle",
  unknown: "Unknown",
};

const TECH_ROLE_KEY_SINGULAR = {
  attacker_eoa: "attacker_eoa",
  attacker_contracts: "attacker_contract",
  flash_loan_providers: "flash_loan_provider",
  routers: "router",
  pairs: "pair",
  victim: "victim",
  tokens: "token",
  oracles: "oracle",
  unknown: "unknown",
};

const TECH_EDGE_LABELS = {
  swap: "swap",
  flashloan: "flash loan",
  transfer: "transfer",
  mint: "mint",
  burn: "burn",
  create: "deployed",
};

function svgEl(name, attrs = {}, children = []) {
  const node = document.createElementNS("http://www.w3.org/2000/svg", name);
  for (const [k, v] of Object.entries(attrs)) {
    if (v !== undefined && v !== null) node.setAttribute(k, String(v));
  }
  for (const child of children) {
    if (child) node.appendChild(child);
  }
  return node;
}

function shortAddr(addr) {
  if (!addr) return "";
  const s = String(addr);
  return s.length > 12 ? `${s.slice(0, 6)}…${s.slice(-4)}` : s;
}

function explorerTxUrl(txHash, chain) {
  const ch = String(chain || "").toLowerCase();
  if (ch.includes("bsc") || ch.includes("bnb")) return `https://bscscan.com/tx/${txHash}`;
  if (ch.includes("arb")) return `https://arbiscan.io/tx/${txHash}`;
  if (ch.includes("base")) return `https://basescan.org/tx/${txHash}`;
  if (ch.includes("opt") || ch.includes("optimism")) return `https://optimistic.etherscan.io/tx/${txHash}`;
  return `https://etherscan.io/tx/${txHash}`;
}

function explorerAddrUrl(addr, chain) {
  const ch = String(chain || "").toLowerCase();
  if (ch.includes("bsc") || ch.includes("bnb")) return `https://bscscan.com/address/${addr}`;
  if (ch.includes("arb")) return `https://arbiscan.io/address/${addr}`;
  if (ch.includes("base")) return `https://basescan.org/address/${addr}`;
  return `https://etherscan.io/address/${addr}`;
}

function explorerLink(value, chain, kind = "tx") {
  if (!value) return "";
  const url = kind === "address" ? explorerAddrUrl(value, chain) : explorerTxUrl(value, chain);
  return `<a href="${url}" target="_blank" rel="noreferrer">${escapeHtml(shortAddr(value))}</a>`;
}

function external_explorerEndpoint(enrichment, suffix) {
  const endpoints = enrichment?.endpoints || {};
  return Object.entries(endpoints).find(([key]) => key.endsWith(suffix))?.[1] || null;
}

function external_explorerLabels(enrichment) {
  return external_explorerEndpoint(enrichment, "address-label")?.labels || [];
}

function external_explorerBalanceChanges(enrichment) {
  return external_explorerEndpoint(enrichment, "balance-change")?.balanceChanges || [];
}

function external_explorerFundTransfers(enrichment) {
  return external_explorerEndpoint(enrichment, "fundflow")?.transfers || [];
}

function summarizeExternalExplorerProfit(enrichment, chain) {
  const changes = external_explorerBalanceChanges(enrichment);
  const positive = changes
    .filter((row) => row.sign && Number(row.totalValue || 0) > 0)
    .sort((a, b) => Number(b.totalValue || 0) - Number(a.totalValue || 0))[0];
  if (!positive) return "";
  const usd = Number(positive.totalValue || 0);
  const account = positive.account || "";
  const amount = Number.isFinite(usd)
    ? `$${usd.toLocaleString(undefined, { maximumFractionDigits: 0 })}`
    : String(positive.totalValue);
  return `${amount} to ${account ? explorerLink(account, chain, "address") : "top positive balance-change account"}`;
}

function layoutTechnicalGraph(plan) {
  // Returns { nodes: Map<address, {x,y,role,label}>, columns: 6 }
  const columns = 6;
  const xAt = (col) => 80 + col * 140;
  const nodes = new Map();
  const roles = plan.roles || {};

  for (const roleKey of TECH_ROLE_ORDER) {
    const addrs = (roles[roleKey] || []).slice(0, 6); // cap each band at 6 nodes
    if (!addrs.length) continue;
    const col = TECH_ROLE_COLUMNS[roleKey] ?? 0;
    const baseX = xAt(col);
    const spacing = 56;
    const totalHeight = (addrs.length - 1) * spacing;
    const startY = 230 - totalHeight / 2;
    addrs.forEach((addr, i) => {
      if (nodes.has(addr)) return; // keep first-assigned role
      nodes.set(addr, {
        address: addr,
        x: baseX + (i % 2 === 0 ? 0 : 14), // small horizontal jitter
        y: startY + i * spacing,
        role: TECH_ROLE_KEY_SINGULAR[roleKey] || roleKey,
        roleBand: roleKey,
        label: shortAddr(addr),
      });
    });
  }
  return { nodes, columns };
}

function renderTechnicalGraph(plan, svg, legendEl) {
  svg.innerHTML = "";
  const layout = layoutTechnicalGraph(plan);
  if (layout.nodes.size === 0) {
    const note = svgEl("text", {
      x: 430, y: 240, class: "tech-graph-empty",
      "text-anchor": "middle", fill: "currentColor",
    });
    note.textContent = "No role-classified addresses were produced for this incident.";
    svg.appendChild(note);
    legendEl.innerHTML = "";
    return;
  }

  // Subtle band labels behind the graph
  const bandLabels = [
    { col: 0, label: "EOA" },
    { col: 1, label: "Attacker contracts" },
    { col: 2, label: "Flash loans" },
    { col: 3, label: "Routers" },
    { col: 4, label: "Pairs" },
    { col: 5, label: "Victim / tokens" },
  ];
  const bandsGroup = svgEl("g", { class: "tech-bands" });
  for (const b of bandLabels) {
    const t = svgEl("text", {
      x: 80 + b.col * 140, y: 26, class: "tech-band-label",
      "text-anchor": "middle",
    });
    t.textContent = b.label;
    bandsGroup.appendChild(t);
  }
  svg.appendChild(bandsGroup);

  // Edges layer (below nodes)
  const edgeGroup = svgEl("g", { class: "tech-edges" });
  const edges = plan.call_graph || [];
  const drawnEdges = new Set();

  const drawEdge = (fromAddr, toAddr, category, dashed = false) => {
    const a = layout.nodes.get(String(fromAddr || "").toLowerCase());
    const b = layout.nodes.get(String(toAddr || "").toLowerCase());
    if (!a || !b || a === b) return;
    const key = `${a.address}|${b.address}|${category}`;
    if (drawnEdges.has(key)) return;
    drawnEdges.add(key);
    const midX = (a.x + b.x) / 2;
    const dy = Math.abs(a.y - b.y);
    const path = `M ${a.x} ${a.y} C ${midX} ${a.y}, ${midX} ${b.y}, ${b.x} ${b.y}`;
    const edge = svgEl("path", {
      d: path,
      class: `tech-edge tech-edge-${category}${dashed ? " tech-edge-create" : ""}`,
      stroke: `var(--edge-${category})`,
      fill: "none",
    });
    const title = svgEl("title");
    title.textContent = `${TECH_EDGE_LABELS[category] || category}: ${shortAddr(a.address)} → ${shortAddr(b.address)}`;
    edge.appendChild(title);
    edgeGroup.appendChild(edge);
  };

  for (const edge of edges) {
    drawEdge(edge.from, edge.to, edge.category);
  }
  for (const dep of plan.newly_deployed || []) {
    drawEdge(dep.deployed_by, dep.address, "create", true);
  }

  // Fallback: if we have nodes but no edges drew, synthesize role-based edges
  if (!edgeGroup.childElementCount) {
    const roles = plan.roles || {};
    const firstOf = (k) => (roles[k] || [])[0];
    const eoa = firstOf("attacker_eoa");
    const attacker = firstOf("attacker_contracts");
    const flash = firstOf("flash_loan_providers");
    const router = firstOf("routers");
    const pair = firstOf("pairs");
    const victim = firstOf("victim");
    if (eoa && attacker) drawEdge(eoa, attacker, "transfer");
    if (flash && attacker) drawEdge(flash, attacker, "flashloan");
    if (attacker && router) drawEdge(attacker, router, "swap");
    if (router && pair) drawEdge(router, pair, "swap");
    if (pair && victim) drawEdge(pair, victim, "transfer");
    if (attacker && victim && !pair) drawEdge(attacker, victim, "transfer");
  }

  svg.appendChild(edgeGroup);

  // Nodes layer
  const nodeGroup = svgEl("g", { class: "tech-nodes" });
  for (const node of layout.nodes.values()) {
    const g = svgEl("g", {
      class: "tech-node",
      "data-role": node.role,
      transform: `translate(${node.x}, ${node.y})`,
    });
    const circle = svgEl("circle", {
      r: 14,
      class: "tech-node-core",
      fill: `var(--role-${node.role})`,
    });
    const title = svgEl("title");
    title.textContent = `${TECH_ROLE_LABELS[node.roleBand] || node.role}\n${node.address}`;
    circle.appendChild(title);
    const label = svgEl("text", {
      class: "tech-node-label",
      y: 32,
    });
    label.textContent = node.label;
    const roleTag = svgEl("text", {
      class: "tech-node-role-tag",
      y: -20,
    });
    roleTag.textContent = TECH_ROLE_LABELS[node.roleBand] || node.role;
    g.appendChild(circle);
    g.appendChild(roleTag);
    g.appendChild(label);
    nodeGroup.appendChild(g);
  }
  svg.appendChild(nodeGroup);

  // Legend
  const usedRoles = new Set();
  for (const node of layout.nodes.values()) usedRoles.add(node.roleBand);
  const usedEdgeCats = new Set();
  for (const e of edges) usedEdgeCats.add(e.category);
  if (plan.newly_deployed?.length) usedEdgeCats.add("create");

  legendEl.innerHTML = "";
  for (const roleKey of TECH_ROLE_ORDER) {
    if (!usedRoles.has(roleKey)) continue;
    const item = document.createElement("span");
    item.className = "tech-legend-item";
    const singular = TECH_ROLE_KEY_SINGULAR[roleKey];
    item.innerHTML = `<span class="tech-legend-swatch" style="background:var(--role-${singular})"></span>${TECH_ROLE_LABELS[roleKey]}`;
    legendEl.appendChild(item);
  }
  for (const cat of ["swap", "flashloan", "transfer", "create"]) {
    if (!usedEdgeCats.has(cat)) continue;
    const item = document.createElement("span");
    item.className = "tech-legend-item";
    item.innerHTML = `<span class="tech-legend-edge" style="background:var(--edge-${cat})"></span>${TECH_EDGE_LABELS[cat] || cat}`;
    legendEl.appendChild(item);
  }
}

function renderTechnicalInventory(inventory, container) {
  container.replaceChildren();
  const contracts = (inventory && inventory.contracts) || {};
  const entries = Object.entries(contracts);
  if (!entries.length) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No priority contracts resolved yet.";
    container.appendChild(empty);
    return;
  }

  // Sort: verified first, then unverified, then newly_deployed, then failed
  const weight = (row) => {
    if (row.newly_deployed_in_tx) return 3;
    const cls = row.classification || "";
    if (cls === "verified") return 0;
    if (cls === "unverified") return 1;
    if (cls === "failed") return 4;
    return 2;
  };
  entries.sort((a, b) => weight(a[1]) - weight(b[1]));

  for (const [addr, row] of entries) {
    const roleKey = row.role || "unknown";
    const rowEl = document.createElement("div");
    rowEl.className = "tech-inventory-row";

    const dot = document.createElement("span");
    dot.className = "tech-role-dot";
    dot.style.background = `var(--role-${roleKey})`;

    const main = document.createElement("div");
    main.className = "tech-inv-main";
    const addrText = document.createElement("span");
    addrText.className = "tech-inv-addr";
    addrText.textContent = shortAddr(addr);
    addrText.title = addr;
    const sub = document.createElement("span");
    sub.className = "tech-inv-sub";
    const bits = [];
    bits.push(`<strong>${humanizeLabel(row.role || "unknown")}</strong>`);
    if (row.contract_name) bits.push(row.contract_name);
    if (row.is_proxy && row.implementation_address) {
      bits.push(`proxy → ${shortAddr(row.implementation_address)}`);
    }
    if (row.create_type) bits.push(row.create_type);
    sub.innerHTML = bits.join(" · ");
    main.appendChild(addrText);
    main.appendChild(sub);

    const badges = document.createElement("div");
    badges.className = "tech-inv-badges";
    const cls = row.classification || "unknown";
    if (cls === "verified") badges.innerHTML += `<span class="tech-badge tech-badge-verified">verified</span>`;
    else if (cls === "unverified") badges.innerHTML += `<span class="tech-badge tech-badge-unverified">unverified</span>`;
    else if (cls === "failed") badges.innerHTML += `<span class="tech-badge tech-badge-failed">failed</span>`;
    if (row.is_proxy) badges.innerHTML += `<span class="tech-badge tech-badge-proxy">${row.proxy_type || "proxy"}</span>`;
    if (row.newly_deployed_in_tx) badges.innerHTML += `<span class="tech-badge tech-badge-newly">in-tx deploy</span>`;

    rowEl.appendChild(dot);
    rowEl.appendChild(main);
    rowEl.appendChild(badges);
    container.appendChild(rowEl);
  }
}

function renderTechnicalValidation(validation, container) {
  container.replaceChildren();
  const checks = (validation && validation.semantic_checks) || {};
  const order = [
    ["tx_role_consistency", "Tx role consistency", "Do claimed tx roles match trace selectors?"],
    ["funds_flow_consistency", "Funds flow consistency", "Do claimed transfers exist in the logs?"],
    ["mechanism_source_consistency", "Mechanism / source consistency", "Does the mechanism match the verified contracts?"],
  ];
  for (const [key, label, hint] of order) {
    const check = checks[key] || { status: "pass", mismatches: [] };
    const row = document.createElement("div");
    const status = check.status || "pass";
    row.className = `tech-check-row is-${status}`;
    const head = document.createElement("div");
    head.className = "tech-check-head";
    head.innerHTML = `<span class="tech-check-name">${label}</span><span class="tech-check-status is-${status}">${status}</span>`;
    const detail = document.createElement("ul");
    detail.className = "tech-check-detail";
    const mismatches = check.mismatches || [];
    if (mismatches.length === 0) {
      const li = document.createElement("li");
      li.textContent = hint;
      li.style.color = "var(--ink-muted)";
      detail.appendChild(li);
    } else {
      for (const m of mismatches.slice(0, 4)) {
        const li = document.createElement("li");
        const pieces = [];
        if (m.claimed_role) pieces.push(`<strong>${m.claimed_role}</strong>`);
        if (m.tx_hash) pieces.push(`tx ${shortAddr(m.tx_hash)}`);
        if (m.mechanism_mentions) pieces.push(`mentions <strong>${m.mechanism_mentions}</strong>`);
        if (m.claim) pieces.push(`claim: "${m.claim.length > 60 ? m.claim.slice(0, 60) + "…" : m.claim}"`);
        li.innerHTML = `${pieces.join(" · ")}${pieces.length ? " — " : ""}${m.finding || ""}`;
        detail.appendChild(li);
      }
    }
    row.appendChild(head);
    row.appendChild(detail);
    container.appendChild(row);
  }
}

function buildAugmentPayloadFromBundle(bundle) {
  if (!bundle) return null;
  const incident = bundle.augmented_incident || {};
  const entry = bundle.incident_library_entry || {};
  const tech = getTechnicalAnalysis(bundle);
  const sourceIndex = bundle.source_index || {};
  const directSources = (sourceIndex.sources || [])
    .filter((s) => s && (s.depth ?? 0) === 0 && typeof s.url === "string")
    .map((s) => s.url)
    .slice(0, 8);

  const payload = {
    incident_id: bundle.incident_id || incident.incident_id || entry.incident_id || null,
    chain: incident.chain || entry.chain || "",
    protocol_name: incident.protocol_name || entry.protocol_name || "",
    incident_name: incident.title || entry.title || "",
    seed_urls: directSources,
    attack_tx_hashes: (tech?.tx_hashes || incident.key_transactions || entry.attack_tx_hashes || []).filter(Boolean),
    tags: [],
    seed_type: "manual",
    trigger_type: "ui_rerun_full_analysis",
  };
  return payload;
}

function setTechRerunStatus(message, variant = "") {
  const el = document.getElementById("tech-rerun-status");
  if (!el) return;
  el.textContent = message || "";
  el.classList.remove("is-ok", "is-err");
  if (variant === "ok") el.classList.add("is-ok");
  if (variant === "err") el.classList.add("is-err");
}

async function handleTechRerunClick() {
  const button = document.getElementById("tech-rerun-button");
  if (!button) return;

  if (state.dataMode !== "live API") {
    setTechRerunStatus("Backend unavailable — connect to the live API to trigger augmentation.", "err");
    return;
  }
  if (!state.currentUser || !["operator", "admin"].includes(state.currentUser.role)) {
    setTechRerunStatus("Sign in as operator or admin in the Ops rail before re-running analysis.", "err");
    return;
  }

  const bundle = state.bundles.get(state.selectedIncidentId);
  if (!bundle) {
    setTechRerunStatus("Select an incident first.", "err");
    return;
  }

  const payload = buildAugmentPayloadFromBundle(bundle);
  if (!payload || !payload.chain) {
    setTechRerunStatus("This incident has no chain on record — cannot re-run.", "err");
    return;
  }
  if (!payload.attack_tx_hashes.length && !payload.seed_urls.length && !payload.incident_id) {
    setTechRerunStatus("This incident has no tx hash or seed URL — nothing to re-augment.", "err");
    return;
  }

  button.disabled = true;
  setTechRerunStatus("Queuing augmentation…");
  try {
    const response = await apiFetch("/api/jobs/augment", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const job = await response.json();
    if (typeof trackJob === "function") trackJob(job);
    setTechRerunStatus(`Queued job ${job.job_id?.slice(0, 8) || job.job_id}. The Jobs rail will show progress.`, "ok");
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error);
    setTechRerunStatus(message, "err");
  } finally {
    // Re-enable after a short delay so the spinner is visible enough to register.
    setTimeout(() => { button.disabled = false; }, 1200);
  }
}

function wireTechRerunButton() {
  const button = document.getElementById("tech-rerun-button");
  if (!button || button.dataset.wired === "1") return;
  button.dataset.wired = "1";
  button.addEventListener("click", handleTechRerunClick);
}

// ─── Agent Trace ─────────────────────────────────────────────────────────────

function renderAgentTrace(bundle, containerOverride) {
  const section = document.getElementById("agent-trace-section");
  const container = containerOverride || document.getElementById("agent-trace-root");
  if (!container) return;

  const tech = getTechnicalAnalysis(bundle);
  const trace = tech?.pipeline_trace || bundle?.pipeline_trace || null;

  container.replaceChildren();

  if (!trace || !Array.isArray(trace.records) || trace.records.length === 0) {
    if (section) section.classList.add("is-hidden");
    const msg = document.createElement("p");
    msg.className = "at-empty";
    msg.textContent = "Pipeline trace not available for this incident (older fixture).";
    container.appendChild(msg);
    return;
  }

  if (section) section.classList.remove("is-hidden");

  const records = trace.records;
  const revisionOn = !!trace.revision_triggered;
  const retryOn = !!trace.qa_retry_triggered;

  // ── Banner badges ──────────────────────────────────────────────────────────
  const bannerEl = document.createElement("div");
  bannerEl.className = "at-banner";

  function makeBadge(label, on, critique) {
    const badge = document.createElement("div");
    badge.className = `at-badge ${on ? "at-badge-on" : "at-badge-off"}`;
    const icon = document.createElement("span");
    icon.className = "at-badge-icon";
    icon.textContent = on ? "●" : "○";
    const text = document.createElement("span");
    text.textContent = `${label}: ${on ? "ON" : "OFF"}`;
    badge.appendChild(icon);
    badge.appendChild(text);
    if (on && critique) {
      const details = document.createElement("details");
      details.className = "at-critique";
      const summary = document.createElement("summary");
      summary.textContent = "View critique";
      const body = document.createElement("p");
      body.textContent = critique;
      details.appendChild(summary);
      details.appendChild(body);
      badge.appendChild(details);
    }
    return badge;
  }

  bannerEl.appendChild(makeBadge("Revision", revisionOn, trace.revision_critique));
  bannerEl.appendChild(makeBadge("QA Retry", retryOn, trace.qa_retry_critique));
  container.appendChild(bannerEl);

  // ── Timeline SVG ──────────────────────────────────────────────────────────
  const PILL_W = 124, PILL_H = 40, PILL_R = 8;
  const GAP = 18;
  const ROW_Y = 80;           // center-line of pills within SVG
  const ARROW_Y = ROW_Y;
  const ARC_ABOVE_Y = 28;     // apex of feedback-loop arc

  const totalW = records.length * PILL_W + (records.length - 1) * GAP + 24;
  const svgH = 160;

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${totalW} ${svgH}`);
  svg.setAttribute("preserveAspectRatio", "xMidYMid meet");
  svg.setAttribute("class", "at-svg");
  svg.setAttribute("aria-label", "Agent pipeline timeline");
  svg.setAttribute("role", "img");

  // ── Arrow marker defs ──────────────────────────────────────────────────────
  const defs = document.createElementNS("http://www.w3.org/2000/svg", "defs");

  function makeMarker(id, color) {
    const marker = document.createElementNS("http://www.w3.org/2000/svg", "marker");
    marker.setAttribute("id", id);
    marker.setAttribute("viewBox", "0 0 6 6");
    marker.setAttribute("refX", "5");
    marker.setAttribute("refY", "3");
    marker.setAttribute("markerWidth", "5");
    marker.setAttribute("markerHeight", "5");
    marker.setAttribute("orient", "auto-start-reverse");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", "M 0 0 L 6 3 L 0 6 Z");
    path.setAttribute("fill", color);
    marker.appendChild(path);
    return marker;
  }
  defs.appendChild(makeMarker("at-arrow-gray", "#8e8e93"));
  defs.appendChild(makeMarker("at-arrow-red",  "#ff3b30"));
  svg.appendChild(defs);

  // ── pill x helper ──────────────────────────────────────────────────────────
  function pillX(idx) { return 12 + idx * (PILL_W + GAP); }
  function pillCX(idx) { return pillX(idx) + PILL_W / 2; }

  // ── Connecting arrows ──────────────────────────────────────────────────────
  for (let i = 0; i < records.length - 1; i++) {
    const x1 = pillX(i) + PILL_W + 2;
    const x2 = pillX(i + 1) - 2;
    const line = document.createElementNS("http://www.w3.org/2000/svg", "line");
    line.setAttribute("x1", x1); line.setAttribute("y1", ARROW_Y);
    line.setAttribute("x2", x2); line.setAttribute("y2", ARROW_Y);
    line.setAttribute("class", "at-arrow");
    line.setAttribute("marker-end", "url(#at-arrow-gray)");
    svg.appendChild(line);
  }

  // ── Feedback loop arcs ─────────────────────────────────────────────────────
  function findLastIndex(name) {
    for (let i = records.length - 1; i >= 0; i--) {
      if (records[i].agent_name === name) return i;
    }
    return -1;
  }
  function findFirstIndex(name) {
    return records.findIndex(r => r.agent_name === name);
  }

  function drawLoopArc(fromIdx, toIdx) {
    if (fromIdx < 0 || toIdx < 0) return;
    const x1 = pillCX(fromIdx);
    const x2 = pillCX(toIdx);
    const y  = ROW_Y - PILL_H / 2;
    // Bezier arc above the pills
    const mx = (x1 + x2) / 2;
    const arcPath = document.createElementNS("http://www.w3.org/2000/svg", "path");
    arcPath.setAttribute("d", `M ${x1} ${y} C ${x1} ${ARC_ABOVE_Y}, ${x2} ${ARC_ABOVE_Y}, ${x2} ${y}`);
    arcPath.setAttribute("class", "at-loop-arc");
    arcPath.setAttribute("marker-end", "url(#at-arrow-red)");
    svg.appendChild(arcPath);
  }

  if (revisionOn) {
    const fromIdx = findLastIndex("semantic_validator");
    const toIdx   = findFirstIndex("technical_reasoner");
    drawLoopArc(fromIdx, toIdx);
  }
  if (retryOn) {
    const fromIdx = findLastIndex("quality_assessor");
    const toIdx   = records.findIndex((r, i) => r.agent_name === "evidence_extractor" && (r.notes || "").toLowerCase().includes("retry"));
    drawLoopArc(fromIdx, toIdx < 0 ? findFirstIndex("evidence_extractor") : toIdx);
  }

  // ── Pills ──────────────────────────────────────────────────────────────────
  // Track per-name appearance count to label retries
  const nameCount = {};

  records.forEach((rec, idx) => {
    nameCount[rec.agent_name] = (nameCount[rec.agent_name] || 0) + 1;
    const isRetry = nameCount[rec.agent_name] > 1;
    const isLLM   = rec.agent_type === "llm";

    const g = document.createElementNS("http://www.w3.org/2000/svg", "g");
    g.setAttribute("class", `at-pill-group ${isLLM ? "at-pill-llm" : "at-pill-rule"} ${isRetry ? "at-pill-retry" : ""}`);
    g.setAttribute("tabindex", "0");
    g.setAttribute("role", "button");
    g.setAttribute("aria-label", `${rec.agent_name}${isRetry ? " retry" : ""}: ${rec.duration_ms}ms`);

    const rx = pillX(idx);
    const ry = ROW_Y - PILL_H / 2;

    // Shadow rect (depth effect)
    const shadow = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    shadow.setAttribute("x", rx + 2); shadow.setAttribute("y", ry + 3);
    shadow.setAttribute("width", PILL_W); shadow.setAttribute("height", PILL_H);
    shadow.setAttribute("rx", PILL_R); shadow.setAttribute("class", "at-pill-shadow");
    g.appendChild(shadow);

    // Main rect
    const rect = document.createElementNS("http://www.w3.org/2000/svg", "rect");
    rect.setAttribute("x", rx); rect.setAttribute("y", ry);
    rect.setAttribute("width", PILL_W); rect.setAttribute("height", PILL_H);
    rect.setAttribute("rx", PILL_R); rect.setAttribute("class", "at-pill-rect");
    g.appendChild(rect);

    // Agent name label
    const nameLabel = rec.agent_name.replace(/_/g, " ");
    const textName = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textName.setAttribute("x", pillCX(idx));
    textName.setAttribute("y", ry + (isRetry ? 14 : 16));
    textName.setAttribute("class", "at-pill-name");
    textName.setAttribute("text-anchor", "middle");
    textName.textContent = nameLabel;
    g.appendChild(textName);

    // Duration label
    const dur = rec.duration_ms != null ? `${rec.duration_ms >= 1000 ? (rec.duration_ms / 1000).toFixed(1) + "s" : rec.duration_ms + "ms"}` : "—";
    const textDur = document.createElementNS("http://www.w3.org/2000/svg", "text");
    textDur.setAttribute("x", pillCX(idx));
    textDur.setAttribute("y", ry + (isRetry ? 27 : 30));
    textDur.setAttribute("class", "at-pill-dur");
    textDur.setAttribute("text-anchor", "middle");
    textDur.textContent = dur;
    g.appendChild(textDur);

    // Retry mark
    if (isRetry) {
      const retryText = document.createElementNS("http://www.w3.org/2000/svg", "text");
      retryText.setAttribute("x", rx + PILL_W - 6);
      retryText.setAttribute("y", ry + 12);
      retryText.setAttribute("class", "at-pill-retry-mark");
      retryText.setAttribute("text-anchor", "end");
      retryText.textContent = "↻";
      g.appendChild(retryText);
    }

    // Click / keyboard → accordion detail
    const triggerDetail = () => showAgentTraceDetail(rec, idx, container);
    g.addEventListener("click", triggerDetail);
    g.addEventListener("keydown", (ev) => { if (ev.key === "Enter" || ev.key === " ") { ev.preventDefault(); triggerDetail(); } });

    svg.appendChild(g);
  });

  // Wrap SVG in a scrollable frame
  const frame = document.createElement("div");
  frame.className = "at-svg-frame";
  frame.appendChild(svg);
  container.appendChild(frame);

  // ── Detail accordion ───────────────────────────────────────────────────────
  const detail = document.createElement("div");
  detail.id = "at-detail";
  detail.className = "at-detail is-hidden";
  detail.setAttribute("aria-live", "polite");
  container.appendChild(detail);
}

function showAgentTraceDetail(rec, idx, container) {
  const detail = container?.querySelector("#at-detail") || document.getElementById("at-detail");
  if (!detail) return;

  // Toggle off if same pill clicked again
  if (detail.dataset.activeIdx === String(idx) && !detail.classList.contains("is-hidden")) {
    detail.classList.add("is-hidden");
    detail.dataset.activeIdx = "";
    // deactivate pills
    container.querySelectorAll(".at-pill-group.is-active").forEach(g => g.classList.remove("is-active"));
    return;
  }

  container.querySelectorAll(".at-pill-group.is-active").forEach(g => g.classList.remove("is-active"));
  const groups = container.querySelectorAll(".at-pill-group");
  if (groups[idx]) groups[idx].classList.add("is-active");

  detail.dataset.activeIdx = String(idx);

  const tokens = (rec.prompt_tokens ?? 0) + (rec.completion_tokens ?? 0);
  const isLLM  = rec.agent_type === "llm";
  const started = rec.started_at ? new Date(rec.started_at).toLocaleString() : "—";

  detail.innerHTML = `
    <button class="at-detail-close" type="button" aria-label="Close detail">×</button>
    <div class="at-detail-grid">
      <div class="at-detail-col">
        <div class="at-detail-row"><span>Agent</span><strong>${rec.agent_name.replace(/_/g, " ")}</strong></div>
        <div class="at-detail-row"><span>Type</span><span class="at-type-badge at-type-${rec.agent_type}">${rec.agent_type?.toUpperCase()}</span></div>
        <div class="at-detail-row"><span>Started</span><strong>${started}</strong></div>
        <div class="at-detail-row"><span>Duration</span><strong>${rec.duration_ms != null ? rec.duration_ms + " ms" : "—"}</strong></div>
        ${isLLM ? `<div class="at-detail-row"><span>LLM</span><strong>${rec.llm_provider || "—"}</strong></div>` : ""}
        ${isLLM ? `<div class="at-detail-row"><span>Tokens</span><strong>${rec.prompt_tokens ?? "—"} prompt / ${rec.completion_tokens ?? "—"} completion${tokens ? " = " + tokens + " total" : ""}</strong></div>` : ""}
        ${rec.notes ? `<div class="at-detail-row"><span>Notes</span><em>${rec.notes}</em></div>` : ""}
      </div>
      <div class="at-detail-col">
        <div class="at-detail-block"><span class="at-detail-label">Input</span><p>${rec.input_summary || "—"}</p></div>
        <div class="at-detail-block"><span class="at-detail-label">Output</span><p>${rec.output_summary || "—"}</p></div>
      </div>
    </div>`;

  detail.querySelector(".at-detail-close")?.addEventListener("click", () => {
    detail.classList.add("is-hidden");
    detail.dataset.activeIdx = "";
    container.querySelectorAll(".at-pill-group.is-active").forEach(g => g.classList.remove("is-active"));
  });

  detail.classList.remove("is-hidden");
  detail.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

// ─── End Agent Trace ──────────────────────────────────────────────────────────

function renderTechnicalEvidence(bundle) {
  const section = document.getElementById("tech-evidence-section");
  if (!section) return;
  const tech = getTechnicalAnalysis(bundle);

  // Hide the section entirely when there's no usable stage-2 data
  const plan = tech?.analysis_plan;
  const inventory = tech?.contract_inventory;
  const validation = tech?.validation;
  const hasPlan = plan && Object.keys(plan.roles || {}).some((k) => (plan.roles[k] || []).length > 0);
  const hasInventory = inventory && Object.keys(inventory.contracts || {}).length > 0;
  const hasValidation = validation && validation.semantic_checks;

  if (!hasPlan && !hasInventory && !hasValidation) {
    section.classList.add("is-hidden");
    return;
  }
  section.classList.remove("is-hidden");
  wireTechRerunButton();

  // Meta chips
  const sevEl = document.getElementById("tech-severity-chip");
  if (sevEl) {
    const sev = validation?.severity || "pass";
    sevEl.textContent = `Validation: ${sev}`;
    sevEl.className = `tech-chip tech-sev-${sev}`;
  }
  const revEl = document.getElementById("tech-revision-chip");
  if (revEl) {
    const round = tech?.revision_round ?? 0;
    revEl.textContent = round > 0 ? `Revised once after critique` : "No revision needed";
  }
  const txEl = document.getElementById("tech-tx-chip");
  if (txEl) {
    txEl.textContent = `${(tech?.tx_hashes || []).length} tx analyzed`;
  }
  const mechEl = document.getElementById("tech-mechanism-chip");
  if (mechEl) {
    const mech = tech?.reasoning?.exploit_mechanism || "";
    mechEl.textContent = mech ? `Mechanism: ${mech}` : "";
    mechEl.style.display = mech ? "" : "none";
  }

  const svg = document.getElementById("tech-graph");
  const legend = document.getElementById("tech-legend");
  if (svg && legend && hasPlan) {
    const planKey = JSON.stringify({ r: plan.roles, a: plan.address_count });
    if (svg.dataset.planKey !== planKey) {
      svg.dataset.planKey = planKey;
      renderTechnicalGraph(plan, svg, legend);
    }
  } else if (svg) {
    svg.innerHTML = "";
    svg.dataset.planKey = "";
    if (legend) legend.innerHTML = "";
  }

  const inv = document.getElementById("tech-inventory");
  if (inv) renderTechnicalInventory(inventory || {}, inv);

  const valEl = document.getElementById("tech-validation");
  if (valEl) renderTechnicalValidation(validation || {}, valEl);
}

function renderSources(bundle) {
  evidenceClaims.replaceChildren();
  sourceGroups.replaceChildren();
  const report = getAnalystReport(bundle);
  const claims = report?.evidence_chain?.claims || [];
  for (const claim of claims) {
    const card = document.createElement("article");
    card.className = "claim-card";
    const supportMarkup = (claim.support || [])
      .slice(0, 4)
      .map((item) => `<a class="support-chip" href="${item.url}" target="_blank" rel="noreferrer">${humanizeLabel(item.source_type)}</a>`)
      .join("");
    card.innerHTML = `
      <strong>${productizeText(claim.title || "Claim")}</strong>
      <p>${productizeText(claim.statement || "")}</p>
      <div class="support-list">${supportMarkup}</div>
    `;
    evidenceClaims.appendChild(card);
  }

  const grouped = {
    report: [],
    explorer: [],
    social: [],
    poc: [],
  };

  for (const source of bundle.source_index?.sources || []) {
    if (source.depth > 0) {
      continue;
    }
    if (
      ["/tree/main", "/tree/main/src", "/tree/main/src/test", "/intent/tweet", "/share/url", "/settings", "/gastracker", "/chart/"].some((marker) =>
        String(source.url || "").toLowerCase().includes(marker)
      )
    ) {
      continue;
    }
    const type = source.source_type in grouped ? source.source_type : "report";
    grouped[type].push(source);
  }

  for (const [groupName, items] of Object.entries(grouped)) {
    if (items.length === 0) {
      continue;
    }

    const section = document.createElement("section");
    section.className = "source-group";
    section.innerHTML = `
      <div class="source-group-head">
        <strong>${humanizeLabel(groupName)}</strong>
        <span>${items.length} link${items.length === 1 ? "" : "s"}</span>
      </div>
    `;

    const list = document.createElement("div");
    list.className = "source-link-list";
    for (const item of items.slice(0, 12)) {
      const link = createLink(item.url, humanizeLabel(item.source_type));
      link.className = "source-link";
      list.appendChild(link);
    }

    section.appendChild(list);
    sourceGroups.appendChild(section);
  }
}

function renderCoverage(bundle) {
  coverageList.replaceChildren();
  const incident = bundle.augmented_incident;
  const quality = bundle.quality_report || incident.quality_report || {};
  const entry = bundle.incident_library_entry || {};
  const technical = getTechnicalAnalysis(bundle);
  const metrics = [
    { label: "Source count", value: String(incident.source_summary?.source_count || entry.source_count || 0) },
    { label: "Direct sources", value: String(quality.direct_source_count || entry.direct_source_count || 0) },
    { label: "Second-hop sources", value: String(quality.secondary_source_count || entry.secondary_source_count || 0) },
    { label: "Fetched documents", value: String(quality.fetched_source_count || 0) },
    { label: "Cited claims", value: String(quality.citation_coverage_count || 0) },
    { label: "Technical txs", value: String((technical?.transactions || []).length) },
    { label: "Technical status", value: humanizeLabel(technical?.status || "Not requested") },
    { label: "Analysis Completeness", value: formatCompleteness(quality.completeness_score || entry.completeness_score || 0) },
  ];

  for (const metric of metrics) {
    const row = document.createElement("div");
    row.className = "coverage-row";
    row.innerHTML = `<span>${metric.label}</span><strong>${metric.value}</strong>`;
    coverageList.appendChild(row);
  }
}

function renderAgentStages(bundle) {
  agentStageList.replaceChildren();
  const statuses = bundle.run_state?.node_status || {};
  const agents = bundle.agent_trace?.agents || [];
  const rows = agents.length
    ? agents.map((agent) => ({
        label: agent.agent_name,
        value: agent.status,
      }))
    : Object.entries(statuses).map(([label, value]) => ({ label, value }));

  for (const rowData of rows) {
    const row = document.createElement("div");
    row.className = "coverage-row";
    row.innerHTML = `<span>${humanizeLabel(rowData.label)}</span><strong>${humanizeLabel(rowData.value)}</strong>`;
    agentStageList.appendChild(row);
  }
}

function renderRunRail(bundle) {
  const incident = bundle.augmented_incident;
  const runStatePayload = bundle.run_state || {};
  runSource.textContent = state.dataMode;
  runIncident.textContent = productizeText(incident.title || bundle.incident_id);
  runState.textContent = `${humanizeLabel(incident.status || "unknown")} / ${humanizeLabel(runStatePayload.current_stage || "unknown")}`;
  runUpdated.textContent = formatDate(incident.generated_at || runStatePayload.updated_at);
  updatedAt.textContent = `Updated ${formatDate(incident.generated_at || runStatePayload.updated_at)}`;
  statusPill.textContent = `${humanizeLabel(incident.status || "unknown")} / ${describeDataMode()}`;
}

function isLeadCase(bundle) {
  const incident = bundle.augmented_incident || {};
  return incident.status === "auto_collected_lead";
}

function renderHeroMetricCopy(bundle) {
  if (isLeadCase(bundle)) {
    heroSourceLabel.textContent = "Lead links";
    heroSourceNote.textContent = "Source links currently attached to this initial lead.";
    heroCompletenessLabel.textContent = "Lead";
    heroCompletenessNote.textContent = "Initial collection evidence, not a fully built analyst report yet.";
    heroEvidenceLabel.textContent = "Evidence";
    heroEvidenceNote.textContent = "What kinds of evidence are visible before the deeper augmentation pass.";
    return;
  }

  heroSourceLabel.textContent = "Links";
  heroSourceNote.textContent = "Source links currently attached to this case.";
  heroCompletenessLabel.textContent = "Analysis Completeness";
  heroCompletenessNote.textContent = "Analysis completeness score (informational — report renders regardless of score).";
  heroEvidenceLabel.textContent = "Trail";
  heroEvidenceNote.textContent = "What kinds of evidence are attached so far.";
}

function renderBundle(bundle) {
  const incident = bundle.augmented_incident;
  const entry = bundle.incident_library_entry || {};
  const report = getAnalystReport(bundle);
  const leadCase = isLeadCase(bundle);
  heroChain.textContent = `${incident.chain || entry.chain || "Unknown"} / ${humanizeLabel(entry.pattern_label || incident.pattern_hypotheses?.[0]?.label || "unknown")}`;
  heroTitle.textContent = productizeText(report?.case_overview?.headline || incident.title || entry.title || "Untitled incident");
  heroSummary.textContent = productizeText(
    leadCase
      ? report?.case_overview?.what_happened ||
          splitParagraphs(incident.summary)[0] ||
          "This is an auto-collected lead. A deeper augmentation run is still needed before it becomes a fuller analyst report."
      : report?.case_overview?.what_happened || splitParagraphs(incident.summary)[0] || "No summary available."
  );
  heroSourceCount.textContent = String(incident.source_summary?.source_count || entry.source_count || 0);
  heroCompleteness.textContent = formatCompleteness(bundle.quality_report?.completeness_score || entry.completeness_score || 0);
  heroEvidenceMix.textContent = classifyTypeCount(entry);
  renderHeroMetricCopy(bundle);

  renderStory(bundle);
  renderTimeline(bundle);
  renderFacts(bundle);
  renderFundFlowSection(bundle);
  renderSources(bundle);
  renderAgentTrace(bundle);
  renderTechnicalEvidence(bundle);
  renderCoverage(bundle);
  renderAgentStages(bundle);
  renderRunRail(bundle);
  renderRunIntel(incident.incident_id);
}

function renderJobList() {
  jobList.replaceChildren();
  if (state.trackedJobs.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No jobs yet.";
    jobList.appendChild(empty);
    return;
  }

  for (const job of state.trackedJobs) {
    const card = document.createElement("article");
    card.className = "job-card";
    const stages = job.progress?.stages || [];
    const stageListMarkup = stages.length
      ? `<ol class="job-stage-list">${stages
          .map((stage) => `<li>${humanizeLabel(stage.name)}: ${humanizeLabel(stage.status)}</li>`)
          .join("")}</ol>`
      : "";
    card.innerHTML = `
      <div class="job-card-head">
        <strong>${humanizeLabel(job.job_type)}</strong>
        <strong>${humanizeLabel(job.progress?.status || job.status)}</strong>
      </div>
      <div class="job-card-meta">
        <span>${job.job_id}</span>
        <span>${formatDate(job.updated_at || job.created_at)}</span>
      </div>
      <p>${job.progress?.current_stage ? `Current stage: ${humanizeLabel(job.progress.current_stage)}` : "Waiting for stage updates."}</p>
      ${stageListMarkup}
    `;
    jobList.appendChild(card);
  }
}

function trackJob(job) {
  const existingIndex = state.trackedJobs.findIndex((item) => item.job_id === job.job_id);
  if (existingIndex >= 0) {
    state.trackedJobs[existingIndex] = { ...state.trackedJobs[existingIndex], ...job };
  } else {
    state.trackedJobs.unshift(job);
    state.trackedJobs = state.trackedJobs.slice(0, 8);
  }
  renderJobList();
  ensureJobPolling();
}

function renderScheduleUi() {
  const schedule = state.discoverySchedule;

  if (!canOperate()) {
    scheduleEnabledInput.checked = true;
    scheduleIntervalInput.value = "6";
    scheduleSourcesInput.value = "slowmist, web3sec, external_explorer, defihacklabs";
    scheduleExecuteAugmentationInput.checked = true;
    return;
  }

  if (!schedule) {
    setScheduleStatus("The automatic discovery loop is not configured yet. Save this form to start it.");
    return;
  }

  scheduleEnabledInput.checked = schedule.status === "active";
  scheduleIntervalInput.value = String(Math.max(1, Math.round(schedule.interval_seconds / 3600)));
  scheduleSourcesInput.value = (schedule.payload?.sources || []).join(", ");
  scheduleExecuteAugmentationInput.checked = Boolean(schedule.payload?.execute_augmentation);
  setScheduleStatus(
    `${schedule.status === "active" ? "Active" : "Paused"} and checked every ${Math.max(1, Math.round(schedule.interval_seconds / 3600))} hour${Math.max(1, Math.round(schedule.interval_seconds / 3600)) === 1 ? "" : "s"}.`
  );
}

function renderAdminUsers() {
  adminUsersList.replaceChildren();

  if (!isAdmin()) {
    return;
  }

  if (state.userDirectory.length === 0) {
    const empty = document.createElement("p");
    empty.className = "empty-state";
    empty.textContent = "No user accounts found yet.";
    adminUsersList.appendChild(empty);
    return;
  }

  for (const user of state.userDirectory) {
    const row = document.createElement("article");
    row.className = "admin-user-row";

    const meta = document.createElement("div");
    meta.className = "admin-user-meta";
    meta.innerHTML = `
      <div>
        <div class="admin-user-email">${user.email}</div>
        <div class="admin-user-role-note">Current role: ${user.role}</div>
      </div>
      <span class="account-role">${user.role}</span>
    `;

    const controls = document.createElement("div");
    controls.className = "admin-user-controls";

    const select = document.createElement("select");
    select.className = "admin-user-role-select";
    for (const role of ["viewer", "operator", "admin"]) {
      const option = document.createElement("option");
      option.value = role;
      option.textContent = role;
      if (role === user.role) {
        option.selected = true;
      }
      select.appendChild(option);
    }

    const button = document.createElement("button");
    button.type = "button";
    button.className = "secondary-button";
    button.textContent = "Save role";

    const editingSelf = state.currentUser?.user_id === user.user_id;
    if (editingSelf) {
      select.disabled = true;
      button.disabled = true;
      button.textContent = "Current account";
    } else {
      button.addEventListener("click", async () => {
        await updateUserRole(user.user_id, select.value);
      });
    }

    controls.appendChild(select);
    controls.appendChild(button);
    row.appendChild(meta);
    row.appendChild(controls);
    adminUsersList.appendChild(row);
  }
}

async function refreshIncidentLibraryPreservingSelection() {
  const previousSelection = state.selectedIncidentId;
  state.bundles.clear();
  state.library = await loadIncidentLibrary();
  await refreshDiscoveryOverview();
  state.filtered = state.library;
  state.selectedIncidentId = previousSelection;
  applyFilters();
  await renderSelectedIncident();
}

async function pollTrackedJobs() {
  if (state.trackedJobs.length === 0 || state.dataMode !== "live API") {
    return;
  }

  let shouldRefreshLibrary = false;

  await Promise.all(
    state.trackedJobs.map(async (job) => {
      const response = await apiFetch(`/api/jobs/${job.job_id}/progress`);
      const progress = await response.json();
      job.progress = progress;
      job.status = progress.status;
      if (["completed", "failed"].includes(progress.status) && !job._finishedHandled) {
        job._finishedHandled = true;
        shouldRefreshLibrary = shouldRefreshLibrary || progress.status === "completed";
      }
    })
  ).catch((error) => {
    setControlStatus(error instanceof Error ? error.message : String(error));
  });

  renderJobList();

  if (shouldRefreshLibrary) {
    await refreshIncidentLibraryPreservingSelection();
    setControlStatus("A background job finished. The incident library has been refreshed.");
  }

  state.trackedJobs = state.trackedJobs.filter((job) => !job._finishedHandled || job.status === "completed" || job.status === "failed");
  renderJobList();
}

function ensureJobPolling() {
  if (state.jobPollTimer || state.dataMode !== "live API") {
    return;
  }
  state.jobPollTimer = window.setInterval(() => {
    pollTrackedJobs().catch((error) => {
      setControlStatus(error instanceof Error ? error.message : String(error));
    });
  }, 4000);
}

async function loadLibraryFromApi() {
  const response = await apiFetch("/api/incidents");
  const payload = await response.json();
  return payload.incidents || [];
}

async function loadFallbackSamples() {
  try {
    const response = await fetch("./data/live_incident_library.json");
    if (response.ok) {
      const payload = await response.json();
      state.fallbackSamples = [];
      return payload.incidents || [];
    }
  } catch {}

  const response = await fetch("./data/sample_incidents.json");
  if (!response.ok) {
    throw new Error(`snapshot HTTP ${response.status}`);
  }
  const payload = await response.json();
  state.fallbackSamples = payload.incidents || [];
  return state.fallbackSamples.map(buildFallbackLibraryEntry);
}

async function loadIncidentLibrary() {
  try {
    const incidents = await loadLibraryFromApi();
    state.dataMode = "live API";
    return incidents;
  } catch {
    const fallback = await loadFallbackSamples();
    state.dataMode = "local snapshot";
    return fallback;
  }
}

async function refreshDiscoveryOverview() {
  if (state.dataMode !== "live API") {
    state.discoveryOverview = buildFallbackDiscoveryOverview();
    renderDiscoveryOverview();
    return;
  }

  try {
    const response = await apiFetch("/api/discovery/overview");
    state.discoveryOverview = await response.json();
  } catch {
    state.discoveryOverview = buildFallbackDiscoveryOverview();
  }

  renderDiscoveryOverview();
}

async function loadIncidentBundle(incidentId) {
  if (state.bundles.has(incidentId)) {
    return state.bundles.get(incidentId);
  }

  let bundle;
  if (state.dataMode === "live API") {
    const response = await apiFetch(`/api/incidents/${incidentId}`);
    bundle = await response.json();
    // Supplement the live bundle with static synthetic fields (e.g. pipeline_trace)
    // when the backend's persistent data pre-dates them.  Additive-only: never
    // overwrites keys that the API already returned.
    try {
      const staticResp = await fetch(`./data/incidents/${incidentId}.json`);
      if (staticResp.ok) {
        const staticBundle = await staticResp.json();
        const liveTa = bundle.technical_analysis || {};
        const staticTa = staticBundle.technical_analysis || {};
        for (const key of Object.keys(staticTa)) {
          if (!(key in liveTa)) liveTa[key] = staticTa[key];
        }
        if (!bundle.technical_analysis) bundle.technical_analysis = liveTa;
      }
    } catch {
      // static file missing or parse error — ignore, live data is fine
    }
  } else {
    try {
      const response = await fetch(`./data/incidents/${incidentId}.json`);
      if (response.ok) {
        bundle = await response.json();
      } else {
        const sample = state.fallbackSamples.find((item) => item.incident_id === incidentId);
        bundle = buildFallbackBundle(sample);
      }
    } catch {
      const sample = state.fallbackSamples.find((item) => item.incident_id === incidentId);
      bundle = buildFallbackBundle(sample);
    }
  }
  state.bundles.set(incidentId, bundle);
  return bundle;
}

function applyFilters() {
  const query = searchInput.value.trim().toLowerCase();
  state.filtered = state.library.filter((item) => {
    const matchesFilter = state.activeFilter === "All" || item.chain === state.activeFilter;
    const matchesQuery = !query || `${item.title} ${item.protocol_name} ${item.chain} ${item.summary}`.toLowerCase().includes(query);
    return matchesFilter && matchesQuery;
  });

  if (!state.filtered.some((item) => item.incident_id === state.selectedIncidentId)) {
    state.selectedIncidentId = state.filtered[0]?.incident_id || null;
  }

  renderFilters();
  renderIncidentList();
}

async function renderSelectedIncident() {
  const primary =
    state.filtered.find((item) => item.incident_id === state.selectedIncidentId) ||
    state.library.find((item) => item.incident_id === state.selectedIncidentId);
  const candidates = uniqueValues([
    primary?.incident_id,
    ...state.filtered.map((item) => item.incident_id),
    ...state.library.map((item) => item.incident_id),
  ])
    .map((incidentId) => state.library.find((item) => item.incident_id === incidentId) || state.filtered.find((item) => item.incident_id === incidentId))
    .filter(Boolean);

  if (candidates.length === 0) {
    return;
  }

  let lastError = null;
  for (const candidate of candidates) {
    try {
      const bundle = await loadIncidentBundle(candidate.incident_id);
      state.selectedIncidentId = candidate.incident_id;
      renderBundle(bundle);
      renderIncidentList();
      return;
    } catch (error) {
      lastError = error;
    }
  }

  throw lastError || new Error("No incident report could be loaded.");
}

async function submitSchedule(event) {
  event.preventDefault();

  if (state.dataMode !== "live API") {
    setScheduleStatus("The backend is unavailable, so the automatic discovery loop cannot be configured right now.");
    return;
  }

  const intervalHours = Number(scheduleIntervalInput.value);
  if (!Number.isFinite(intervalHours) || intervalHours < 1) {
    setScheduleStatus("Enter a valid refresh interval in hours.");
    return;
  }

  const payload = {
    schedule_name: DISCOVERY_SCHEDULE_NAME,
    interval_seconds: Math.round(intervalHours * 3600),
    enabled: scheduleEnabledInput.checked,
    payload: {
      sources: parseListInput(scheduleSourcesInput.value),
      execute_augmentation: scheduleExecuteAugmentationInput.checked,
    },
  };

  scheduleSubmitButton.disabled = true;
  setScheduleStatus("Saving automatic discovery settings...");
  try {
    const response = await apiFetch("/api/schedules/discovery", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    state.discoverySchedule = await response.json();
    renderScheduleUi();
  } catch (error) {
    setScheduleStatus(error instanceof Error ? error.message : String(error));
  } finally {
    scheduleSubmitButton.disabled = false;
  }
}

async function submitAugmentation(event) {
  event.preventDefault();
  if (state.dataMode !== "live API") {
    setControlStatus("The backend is unavailable, so manual report build is disabled while the site is running from a local snapshot.");
    return;
  }

  const payload = {
    chain: augmentChainInput.value.trim(),
    protocol_name: augmentProtocolInput.value.trim(),
    incident_name: augmentIncidentInput.value.trim(),
    incident_id: augmentIncidentIdInput.value.trim() || null,
    seed_urls: parseListInput(augmentSeedUrlsInput.value, { separator: /\n/ }),
    attack_tx_hashes: parseListInput(augmentAttackTxInput.value, { separator: /\n/ }),
    tags: parseListInput(augmentTagsInput.value),
    seed_type: "manual",
    trigger_type: "product_manual_research",
  };

  if (!payload.chain) {
    setControlStatus("Chain is required before starting a manual report build.");
    return;
  }

  if (!payload.incident_id && payload.seed_urls.length === 0 && payload.attack_tx_hashes.length === 0) {
    setControlStatus("Add at least one seed URL, transaction hash, or existing incident ID before running a manual report build.");
    return;
  }

  augmentSubmitButton.disabled = true;
  setControlStatus("Submitting manual report build...");
  try {
    const response = await apiFetch("/api/jobs/augment", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const job = await response.json();
    trackJob(job);
    setControlStatus(`Manual report build ${job.job_id} was queued. Progress will update here.`);
    augmentForm.reset();
  } catch (error) {
    setControlStatus(error instanceof Error ? error.message : String(error));
  } finally {
    augmentSubmitButton.disabled = false;
  }
}

async function submitDiscovery(event) {
  event.preventDefault();
  if (state.dataMode !== "live API") {
    setControlStatus("The backend is unavailable, so one-off discovery is disabled while the site is running from a local snapshot.");
    return;
  }

  discoverySubmitButton.disabled = true;
  setControlStatus("Submitting one-off discovery...");
  try {
    const response = await apiFetch("/api/jobs/discovery", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        sources: parseListInput(discoverySourcesInput.value),
        execute_augmentation: discoveryExecuteAugmentationInput.checked,
      }),
    });
    const job = await response.json();
    trackJob(job);
    setControlStatus(`One-off discovery ${job.job_id} was queued. Progress will update here.`);
  } catch (error) {
    setControlStatus(error instanceof Error ? error.message : String(error));
  } finally {
    discoverySubmitButton.disabled = false;
  }
}

async function rebuildDemoCorpus() {
  if (!rebuildDemoButton) {
    return;
  }
  if (state.dataMode !== "live API") {
    setControlStatus("The backend is unavailable, so rebuilding the published set is disabled right now.");
    return;
  }
  rebuildDemoButton.disabled = true;
  setControlStatus("Submitting published-set rebuild...");
  try {
    const response = await apiFetch("/api/jobs/demo-corpus", {
      method: "POST",
    });
    const job = await response.json();
    trackJob(job);
    setControlStatus(`Rebuild job ${job.job_id} was queued. Progress will update here.`);
  } catch (error) {
    setControlStatus(error instanceof Error ? error.message : String(error));
  } finally {
    rebuildDemoButton.disabled = false;
  }
}

async function refreshCurrentUser() {
  const token = getAuthToken();
  if (!token) {
    state.currentUser = null;
    state.discoverySchedule = null;
    state.userDirectory = [];
    updateAuthUi();
    renderScheduleUi();
    renderAdminUsers();
    return;
  }

  try {
    const response = await apiFetch("/api/auth/me");
    state.currentUser = await response.json();
  } catch {
    setAuthToken("");
    state.currentUser = null;
  }

  updateAuthUi();
  await refreshOperatorContext();
}

async function submitLogin() {
  const email = authEmailInput.value.trim();
  const password = authPasswordInput.value;
  if (!email || !password) {
    setAuthStatus("Enter your email and password first.");
    return;
  }

  loginButton.disabled = true;
  registerButton.disabled = true;
  try {
    const response = await apiFetch("/api/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const payload = await response.json();
    setAuthToken(payload.token);
    state.currentUser = payload.user;
    authPasswordInput.value = "";
    updateAuthUi();
    await refreshOperatorContext();
  } catch (error) {
    setAuthStatus(error instanceof Error ? error.message : String(error));
  } finally {
    loginButton.disabled = false;
    registerButton.disabled = false;
  }
}

async function submitRegister() {
  const email = authEmailInput.value.trim();
  const password = authPasswordInput.value;
  if (!email || !password) {
    setAuthStatus("Enter your email and password first.");
    return;
  }

  loginButton.disabled = true;
  registerButton.disabled = true;
  try {
    const response = await apiFetch("/api/auth/register", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password }),
    });
    const payload = await response.json();
    setAuthToken(payload.token);
    state.currentUser = payload.user;
    authPasswordInput.value = "";
    updateAuthUi();
    await refreshOperatorContext();
  } catch (error) {
    setAuthStatus(error instanceof Error ? error.message : String(error));
  } finally {
    loginButton.disabled = false;
    registerButton.disabled = false;
  }
}

async function submitLogout() {
  logoutButton.disabled = true;
  try {
    await apiFetch("/api/auth/logout", { method: "POST" });
  } catch {}
  setAuthToken("");
  state.currentUser = null;
  state.discoverySchedule = null;
  state.userDirectory = [];
  updateAuthUi();
  renderScheduleUi();
  renderAdminUsers();
  logoutButton.disabled = false;
}

async function refreshDiscoverySchedule() {
  if (!canOperate()) {
    state.discoverySchedule = null;
    renderScheduleUi();
    return;
  }

  try {
    const response = await apiFetch("/api/schedules");
    const schedules = await response.json();
    state.discoverySchedule =
      schedules.find((item) => item.schedule_name === DISCOVERY_SCHEDULE_NAME) ||
      schedules.find((item) => item.job_type === "discovery") ||
      null;
  } catch (error) {
    state.discoverySchedule = null;
    setScheduleStatus(error instanceof Error ? error.message : String(error));
  }

  renderScheduleUi();
}

async function refreshAdminUsers() {
  if (!isAdmin()) {
    state.userDirectory = [];
    renderAdminUsers();
    return;
  }

  try {
    const response = await apiFetch("/api/auth/users");
    state.userDirectory = await response.json();
    setAdminUsersStatus("Manage who can read, operate, or administer the product.");
  } catch (error) {
    state.userDirectory = [];
    setAdminUsersStatus(error instanceof Error ? error.message : String(error));
  }

  renderAdminUsers();
}

async function updateUserRole(userId, role) {
  setAdminUsersStatus("Saving role change...");
  try {
    const response = await apiFetch(`/api/auth/users/${userId}/role`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ role }),
    });
    const updatedUser = await response.json();
    state.userDirectory = state.userDirectory.map((user) => (user.user_id === updatedUser.user_id ? updatedUser : user));
    renderAdminUsers();
    setAdminUsersStatus(`Updated ${updatedUser.email} to ${updatedUser.role}.`);
  } catch (error) {
    setAdminUsersStatus(error instanceof Error ? error.message : String(error));
  }
}

async function refreshOperatorContext() {
  await refreshDiscoverySchedule();
  await refreshAdminUsers();
}

function initializeAuth() {
  loginButton.addEventListener("click", submitLogin);
  registerButton.addEventListener("click", submitRegister);
  logoutButton.addEventListener("click", submitLogout);
  scheduleForm.addEventListener("submit", submitSchedule);
  setOperationControlsEnabled(false);
  updateAuthUi();
  renderScheduleUi();
  renderAdminUsers();
}

async function initialize() {
  try {
    initializeAuth();
    await refreshCurrentUser();
    state.library = await loadIncidentLibrary();
    await refreshDiscoveryOverview();
    state.filtered = state.library;
    state.selectedIncidentId = state.library[0]?.incident_id || null;

    searchInput.addEventListener("input", () => {
      applyFilters();
      renderSelectedIncident().catch((error) => {
        setControlStatus(error instanceof Error ? error.message : String(error));
      });
    });
    augmentForm.addEventListener("submit", submitAugmentation);
    discoveryForm.addEventListener("submit", submitDiscovery);
    if (rebuildDemoButton) {
      rebuildDemoButton.addEventListener("click", rebuildDemoCorpus);
    }

    applyFilters();
    await renderSelectedIncident();
    renderJobList();

    setControlStatus(
      state.dataMode === "live API"
        ? canOperate()
          ? "Live backend connected. You can manage discovery and run research jobs from this page."
          : "Live backend connected. Reading is open. Sign in with operator access to run research jobs."
        : "Running from a local snapshot because the live backend is unavailable."
    );
    statusPill.textContent = state.dataMode === "live API" ? "Live" : "Snapshot";

    if (state.dataMode === "live API") {
      ensureJobPolling();
    }
  } catch (error) {
    statusPill.textContent = "load_error";
    updatedAt.textContent = "Data unavailable";
    incidentList.innerHTML = `<p class="empty-state">${error instanceof Error ? error.message : String(error)}</p>`;
    setControlStatus(`Initialization failed: ${error instanceof Error ? error.message : String(error)}`);
  }
}

initialize();

/* ─────────────────────────────────────────────────────────────
   Run Intelligence — pipeline timeline + source discovery tree
   Makes the multi-agent orchestration + recursive source fetch
   visible. Powered by /api/runs/<id>/trace and /api/runs/<id>/sources.
   ───────────────────────────────────────────────────────────── */

const PIPELINE_PHASES = [
  {
    label: "Collect",
    agents: ["incident_collector", "source_finder", "source_expander", "discovery_supervisor"],
  },
  {
    label: "Understand",
    agents: ["evidence_normalizer", "technical_validation", "technical_planner", "contract_intelligence"],
  },
  {
    label: "Reason & Report",
    agents: [
      "technical_reasoner",
      "semantic_validator",
      "llm_timeline_synthesizer",
      "llm_narrative_writer",
      "quality_judge",
      "llm_quality_assessor",
      "dossier_assembler",
    ],
  },
];

const runIntelState = {
  currentRunId: null,
  trace: null,
  sources: null,
  replayTimers: [],
  replaying: false,
};

function $(id) { return document.getElementById(id); }

async function fetchRunIntel(runId) {
  const base = API_BASE || "";
  const [traceRes, sourcesRes] = await Promise.all([
    fetch(`${base}/api/runs/${runId}/trace`, { headers: buildAuthHeaders() }),
    fetch(`${base}/api/runs/${runId}/sources`, { headers: buildAuthHeaders() }),
  ]);
  const trace = traceRes.ok ? await traceRes.json() : null;
  const sources = sourcesRes.ok ? await sourcesRes.json() : null;
  return { trace, sources };
}

async function renderRunIntel(runId) {
  if (!runId) return;
  stopReplay();
  runIntelState.currentRunId = runId;

  const pipelineEl = $("pipeline-timeline");
  const treeEl = $("source-tree");
  if (!pipelineEl || !treeEl) return;

  pipelineEl.innerHTML = '<p class="empty-state">Loading run data…</p>';
  treeEl.innerHTML = '<p class="empty-state">Loading source tree…</p>';

  let trace = null;
  let sources = null;
  try {
    ({ trace, sources } = await fetchRunIntel(runId));
  } catch (err) {
    pipelineEl.innerHTML = `<p class="empty-state">Could not load run trace: ${err.message}</p>`;
    treeEl.innerHTML = "";
    return;
  }

  runIntelState.trace = trace;
  runIntelState.sources = sources;

  if (!trace || (trace.agents || []).length === 0) {
    pipelineEl.innerHTML = '<p class="empty-state">No agent trace recorded for this run yet.</p>';
  } else {
    renderPipelineTimeline(trace);
  }

  if (!sources || (sources.stats?.total || 0) === 0) {
    treeEl.innerHTML = '<p class="empty-state">No source discovery graph for this run.</p>';
    $("source-tree-stats").textContent = "—";
  } else {
    renderSourceTree(sources);
  }

  const elapsedChip = $("run-intel-elapsed");
  if (elapsedChip) {
    const ms = trace?.total_elapsed_ms;
    elapsedChip.textContent = ms != null ? `Total ${formatElapsed(ms)} · ${(trace.agents || []).length} agents` : "—";
  }
}

function formatElapsed(ms) {
  if (ms == null) return "—";
  if (ms < 1000) return `${ms}ms`;
  const sec = ms / 1000;
  if (sec < 60) return `${sec.toFixed(sec < 10 ? 1 : 0)}s`;
  const m = Math.floor(sec / 60);
  const s = Math.round(sec - m * 60);
  return `${m}m ${s}s`;
}

function renderPipelineTimeline(trace) {
  const pipelineEl = $("pipeline-timeline");
  pipelineEl.innerHTML = "";
  const agents = trace.agents || [];
  const byId = new Map(agents.map((a) => [a.agent_id, a]));
  const placed = new Set();

  const statsEl = $("pipeline-stats");
  const runCompleted = agents.filter((a) => a.status === "completed").length;
  statsEl.textContent = `${runCompleted}/${agents.length} agents completed · total ${formatElapsed(trace.total_elapsed_ms)}`;

  for (const phase of PIPELINE_PHASES) {
    const phaseAgents = phase.agents.map((id) => byId.get(id)).filter(Boolean);
    if (phaseAgents.length === 0) continue;
    phaseAgents.forEach((a) => placed.add(a.agent_id));

    const phaseEl = document.createElement("div");
    phaseEl.className = "pipeline-phase";
    phaseEl.innerHTML = `<span class="pipeline-phase-label">${phase.label}</span>`;
    const nodesEl = document.createElement("div");
    nodesEl.className = "pipeline-nodes";
    for (const a of phaseAgents) nodesEl.appendChild(buildPipelineNode(a));
    phaseEl.appendChild(nodesEl);
    pipelineEl.appendChild(phaseEl);
  }

  const leftovers = agents.filter((a) => !placed.has(a.agent_id));
  if (leftovers.length) {
    const phaseEl = document.createElement("div");
    phaseEl.className = "pipeline-phase";
    phaseEl.innerHTML = `<span class="pipeline-phase-label">Other</span>`;
    const nodesEl = document.createElement("div");
    nodesEl.className = "pipeline-nodes";
    for (const a of leftovers) nodesEl.appendChild(buildPipelineNode(a));
    phaseEl.appendChild(nodesEl);
    pipelineEl.appendChild(phaseEl);
  }
}

function buildPipelineNode(agent) {
  const el = document.createElement("div");
  el.className = `pipeline-node is-${agent.status || "pending"}`;
  el.dataset.agentId = agent.agent_id;
  el.innerHTML = `
    <span class="pipeline-node-dot"></span>
    <span class="pipeline-node-name">${escapeHtml(agent.agent_name || humanizeLabel(agent.agent_id))}</span>
    <span class="pipeline-node-meta">
      <span>${escapeHtml(formatElapsed(agent.elapsed_ms))}</span>
      ${renderMetricChips(agent.metrics)}
    </span>
  `;
  el.addEventListener("click", () => openDrawer(renderAgentDrawer(agent)));
  return el;
}

function renderMetricChips(metrics) {
  if (!metrics || typeof metrics !== "object") return "";
  const preferred = ["source_count", "fetched_documents", "evidence_count", "claim_count", "tx_count", "technical_status"];
  const pairs = preferred
    .filter((k) => metrics[k] != null && metrics[k] !== "")
    .slice(0, 2)
    .map((k) => `<span>· ${escapeHtml(String(metrics[k]))} ${humanizeLabel(k).toLowerCase()}</span>`);
  return pairs.join("");
}

function renderAgentDrawer(agent) {
  const outputs = (agent.outputs || []).map((p) => `<li><code>${escapeHtml(p)}</code></li>`).join("") || "<li>—</li>";
  const metrics = agent.metrics && Object.keys(agent.metrics).length
    ? `<dl class="drawer-kv">${Object.entries(agent.metrics)
        .map(([k, v]) => `<dt>${escapeHtml(humanizeLabel(k))}</dt><dd>${escapeHtml(String(v))}</dd>`)
        .join("")}</dl>`
    : '<p class="empty-state">No metrics recorded.</p>';
  return `
    <h4 class="drawer-title">${escapeHtml(agent.agent_name || humanizeLabel(agent.agent_id))}</h4>
    <p class="drawer-sub">${escapeHtml(agent.agent_id)} · status <strong>${escapeHtml(agent.status || "pending")}</strong></p>
    <div class="drawer-section">
      <h5>Timing</h5>
      <dl class="drawer-kv">
        <dt>Started</dt><dd>${escapeHtml(agent.started_at || "—")}</dd>
        <dt>Completed</dt><dd>${escapeHtml(agent.completed_at || "—")}</dd>
        <dt>Elapsed</dt><dd>${escapeHtml(formatElapsed(agent.elapsed_ms))}</dd>
        <dt>Offset from run start</dt><dd>${escapeHtml(formatElapsed(agent.offset_ms))}</dd>
      </dl>
    </div>
    <div class="drawer-section">
      <h5>Metrics</h5>
      ${metrics}
    </div>
    <div class="drawer-section">
      <h5>Output artifacts</h5>
      <ul>${outputs}</ul>
    </div>
    ${agent.note ? `<div class="drawer-section"><h5>Note</h5><p>${escapeHtml(agent.note)}</p></div>` : ""}
  `;
}

function renderSourceTree(sources) {
  const treeEl = $("source-tree");
  treeEl.innerHTML = "";
  const stats = sources.stats || {};
  const byDepth = stats.by_depth || {};
  $("source-tree-stats").textContent =
    `Seeds ${stats.seeds || 0} · Discovered ${stats.total || 0} · Depth reached ${stats.depth_reached || 0} · Fetched ${stats.fetched || 0}`;

  const list = document.createElement("ul");
  list.className = "source-tree-list";
  for (const root of sources.roots || []) list.appendChild(buildSourceNode(root));
  treeEl.appendChild(list);
  void byDepth;
}

function buildSourceNode(node) {
  const li = document.createElement("li");
  const row = document.createElement("div");
  row.className = "source-node";
  row.dataset.depth = String(node.depth || 0);
  row.dataset.sourceId = node.source_id;

  const hasChildren = (node.children || []).length > 0;
  const domain = extractDomain(node.url || "");
  row.innerHTML = `
    <button class="source-node-toggle ${hasChildren ? "" : "is-leaf"}" type="button" aria-label="Toggle">${hasChildren ? "▸" : ""}</button>
    <span class="source-node-depth">d${node.depth || 0}</span>
    <span class="source-node-label">
      <span class="source-node-domain">${escapeHtml(domain)}</span>
      <span class="source-node-title">${escapeHtml(node.title ? truncate(node.title, 70) : node.source_type || "")}</span>
    </span>
    <span class="source-node-badge">${node.discovered_link_count || 0} links</span>
  `;

  row.addEventListener("click", (ev) => {
    if (ev.target.closest(".source-node-toggle")) return;
    openDrawer(renderSourceDrawer(node));
  });

  li.appendChild(row);

  if (hasChildren) {
    const childList = document.createElement("ul");
    childList.className = "source-tree-list";
    childList.style.display = node.depth === 0 ? "" : "none"; // Depth-0 open by default.
    for (const child of node.children) childList.appendChild(buildSourceNode(child));
    li.appendChild(childList);
    row.querySelector(".source-node-toggle").textContent = childList.style.display === "none" ? "▸" : "▾";
    row.querySelector(".source-node-toggle").addEventListener("click", (ev) => {
      ev.stopPropagation();
      const open = childList.style.display === "none";
      childList.style.display = open ? "" : "none";
      row.querySelector(".source-node-toggle").textContent = open ? "▾" : "▸";
    });
  }

  return li;
}

function renderSourceDrawer(node) {
  return `
    <h4 class="drawer-title">${escapeHtml(extractDomain(node.url || ""))}</h4>
    <p class="drawer-sub">Depth ${node.depth || 0} · ${escapeHtml(node.source_type || "unknown")} · ${escapeHtml(node.fetch_status || "unknown")}</p>
    <div class="drawer-section">
      <h5>URL</h5>
      <p><a href="${escapeHtml(node.url || "#")}" target="_blank" rel="noopener">${escapeHtml(node.url || "—")}</a></p>
    </div>
    ${node.title ? `<div class="drawer-section"><h5>Title</h5><p>${escapeHtml(node.title)}</p></div>` : ""}
    <div class="drawer-section">
      <h5>Extraction</h5>
      <dl class="drawer-kv">
        <dt>Discovered links</dt><dd>${node.discovered_link_count || 0}</dd>
        <dt>Tx hashes</dt><dd>${node.extracted_tx_count || 0}</dd>
        <dt>Addresses</dt><dd>${node.extracted_address_count || 0}</dd>
        <dt>HTTP</dt><dd>${escapeHtml(String(node.status_code || "—"))}</dd>
        <dt>Priority</dt><dd>${escapeHtml(String(node.priority || "—"))}</dd>
      </dl>
    </div>
    <div class="drawer-section">
      <h5>Lineage</h5>
      <dl class="drawer-kv">
        <dt>Discovered from</dt><dd>${escapeHtml(node.discovered_from || "seed")}</dd>
        <dt>Source ID</dt><dd>${escapeHtml(node.source_id)}</dd>
      </dl>
    </div>
  `;
}

function extractDomain(url) {
  try {
    return new URL(url).hostname.replace(/^www\./, "");
  } catch {
    return url || "(no url)";
  }
}

function truncate(s, n) {
  if (!s) return "";
  return s.length > n ? s.slice(0, n - 1) + "…" : s;
}

function escapeHtml(s) {
  return String(s ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]
  ));
}

function openDrawer(html) {
  const drawer = $("run-intel-drawer");
  const body = $("run-intel-drawer-body");
  if (!drawer || !body) return;
  body.innerHTML = html;
  drawer.classList.remove("is-hidden");
  drawer.setAttribute("aria-hidden", "false");
}

function closeDrawer() {
  const drawer = $("run-intel-drawer");
  if (!drawer) return;
  drawer.classList.add("is-hidden");
  drawer.setAttribute("aria-hidden", "true");
}

/* Replay engine — re-animate a completed run from the agent_trace + source tree. */

function stopReplay() {
  for (const t of runIntelState.replayTimers) clearTimeout(t);
  runIntelState.replayTimers = [];
  runIntelState.replaying = false;
  const btn = $("run-intel-replay");
  if (btn) btn.textContent = "▶ Replay run";
}

function startReplay() {
  const trace = runIntelState.trace;
  const sources = runIntelState.sources;
  if (!trace || !trace.agents?.length) return;
  if (runIntelState.replaying) { stopReplay(); return; }

  const speed = Number($("run-intel-speed-input")?.value || 2);
  runIntelState.replaying = true;
  const btn = $("run-intel-replay");
  if (btn) btn.textContent = "⏹ Stop";

  // Reset all pipeline nodes to pending.
  for (const node of document.querySelectorAll(".pipeline-node")) {
    node.classList.remove("is-completed", "is-running", "is-failed");
    node.classList.add("is-pending");
  }
  // Re-render source tree empty, progressively re-add by depth with a small stagger.
  const treeEl = $("source-tree");
  if (sources && treeEl) {
    treeEl.innerHTML = "";
    const list = document.createElement("ul");
    list.className = "source-tree-list";
    treeEl.appendChild(list);
    const flat = flattenSourceTree(sources.roots || []);
    flat.sort((a, b) => (a.depth || 0) - (b.depth || 0));
    // Spread sources across the run timeline proportional to total duration.
    const totalMs = Math.max(trace.total_elapsed_ms || 5000, 1000);
    flat.forEach((node, idx) => {
      const t = (idx / flat.length) * totalMs;
      const timer = setTimeout(() => insertSourceLive(list, node), t / speed);
      runIntelState.replayTimers.push(timer);
    });
  }

  // Pipeline: light each node at its offset_ms, mark completed at offset + elapsed.
  for (const agent of trace.agents) {
    const nodeEl = document.querySelector(`.pipeline-node[data-agent-id="${agent.agent_id}"]`);
    if (!nodeEl) continue;
    const startT = (agent.offset_ms || 0) / speed;
    const endT = ((agent.offset_ms || 0) + (agent.elapsed_ms || 0)) / speed;
    runIntelState.replayTimers.push(setTimeout(() => {
      nodeEl.classList.remove("is-pending", "is-completed", "is-failed");
      nodeEl.classList.add("is-running");
    }, startT));
    runIntelState.replayTimers.push(setTimeout(() => {
      nodeEl.classList.remove("is-running");
      nodeEl.classList.add(agent.status === "completed" ? "is-completed" : `is-${agent.status || "completed"}`);
    }, Math.max(endT, startT + 400)));
  }

  const doneAt = (trace.total_elapsed_ms || 5000) / speed + 400;
  runIntelState.replayTimers.push(setTimeout(stopReplay, doneAt));
}

function flattenSourceTree(roots, acc = []) {
  for (const r of roots) {
    acc.push({ ...r, _parentId: r.discovered_from });
    if (r.children?.length) flattenSourceTree(r.children, acc);
  }
  return acc;
}

function insertSourceLive(rootList, node) {
  const li = document.createElement("li");
  li.classList.add("is-new-wrap");
  const row = document.createElement("div");
  row.className = "source-node is-new";
  row.dataset.depth = String(node.depth || 0);
  row.innerHTML = `
    <button class="source-node-toggle is-leaf" type="button"></button>
    <span class="source-node-depth">d${node.depth || 0}</span>
    <span class="source-node-label">
      <span class="source-node-domain">${escapeHtml(extractDomain(node.url || ""))}</span>
      <span class="source-node-title">${escapeHtml(node.title ? truncate(node.title, 70) : node.source_type || "")}</span>
    </span>
    <span class="source-node-badge">d${node.depth} · ${node.discovered_link_count || 0} links</span>
  `;
  li.appendChild(row);
  rootList.appendChild(li);
  // Update stats strip live.
  const statEl = $("source-tree-stats");
  if (statEl) {
    const existing = rootList.querySelectorAll(".source-node").length;
    statEl.textContent = `Discovered ${existing} so far…`;
  }
  // Scroll into view so the growth is visible.
  row.scrollIntoView({ behavior: "smooth", block: "nearest" });
}

/* Wire controls — module scripts run after DOM parse, bind immediately if ready. */
function initRunIntelControls() {
  $("run-intel-replay")?.addEventListener("click", startReplay);
  $("run-intel-drawer-close")?.addEventListener("click", closeDrawer);
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") closeDrawer(); });
}
if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", initRunIntelControls, { once: true });
} else {
  initRunIntelControls();
}

export interface IncidentEntry {
  incident_id: string;
  title: string;
  protocol_name: string;
  chain: string;
  incident_date: string;
  summary: string;
  completeness_score: number;
  source_count: number;
  pattern_label: string;
  attack_tx_hashes: string[];
  missing_fields: string[];
}

export interface IncidentListResponse {
  incidents: IncidentEntry[];
  total: number;
}

export interface AgentStep {
  agent_id: string;
  agent_name: string;
  status: string;
  started_at?: string;
  completed_at?: string;
  elapsed_ms?: number | null;
  offset_ms?: number | null;
  metrics?: Record<string, unknown>;
  note?: string;
  outputs?: string[];
}

export interface TraceResponse {
  run_id: string;
  incident_id: string;
  agents: AgentStep[];
  run_started_at?: string | null;
  run_completed_at?: string | null;
  total_elapsed_ms?: number | null;
  current_stage?: string | null;
  node_status?: Record<string, string>;
}

export interface SourceNode {
  source_id: string;
  url: string;
  source_type: string;
  fetch_status: string;
  title?: string;
  excerpt?: string;
  relevance_score?: number;
  is_direct?: boolean;
}

export interface SourcesResponse {
  run_id: string;
  sources: SourceNode[];
  total: number;
  fetched: number;
  failed: number;
}

export interface QualityReport {
  completeness_score: number;
  source_count: number;
  direct_source_count: number;
  secondary_source_count: number;
  fetched_count: number;
  cited_count: number;
  tx_count: number;
  pipeline_status?: string;
  missing_fields: string[];
}

export interface IncidentBundle {
  augmented_incident: {
    incident_id: string;
    title: string;
    chain: string;
    summary: string;
    pattern_hypotheses?: Array<{ label: string; confidence: number }>;
    source_summary?: { source_count: number };
  };
  incident_library_entry?: IncidentEntry;
  analyst_report?: {
    case_overview?: { headline: string; what_happened: string };
    attacker_profile?: {
      funding_source?: string;
      profit_usd?: number;
      profit_tokens?: string;
      techniques?: string[];
    };
    exploit_path?: Array<{
      step: number;
      action: string;
      contracts?: string[];
      tx_hash?: string;
    }>;
    evidence_chain?: {
      claims: Array<{ claim: string; support: string[]; confidence: number }>;
    };
  };
  quality_report?: QualityReport;
  technical_analysis?: {
    tx_hashes?: string[];
    chain?: string;
    analysis_plan?: {
      roles?: Record<string, string[]>;
      address_count?: number;
    };
  };
  external_enrichment?: {
    tx_hash: string;
    chain: string;
    endpoints?: Record<string, unknown>;
  };
  attacker_profile_v2?: AttackerProfileV2;
}

export interface AttackerProfileV2 {
  incident_id: string;
  tx_hash?: string;
  chain?: string;
  attacker_address?: string;
  attacker_role?: string;
  techniques?: string[];
  fields: {
    funding_source?: {
      summary?: string;
      source?: string;
      evidence_url?: string;
      details?: Record<string, unknown>;
    };
    net_profit_usd?: {
      value?: number;
      tokens?: Array<{
        symbol?: string;
        address?: string;
        amount?: string;
        value_usd?: number;
        token_type?: number;
      }>;
      evidence_url?: string;
    };
    deployment_to_exploit_time?: {
      seconds?: number;
      human?: string;
      deployment_block?: number;
      exploit_block?: number;
    };
    pre_attack_activity?: {
      summary?: string;
      tx_count?: number;
      first_seen?: string;
    };
    post_attack_fund_flow?: {
      transfers?: Array<{
        from?: string;
        to?: string;
        amount?: string;
        symbol?: string;
        value_usd?: number;
        tx_hash?: string;
      }>;
      summary?: string;
    };
    related_addresses?: {
      addresses?: Array<{ address: string; label?: string; role?: string }>;
    };
  };
}

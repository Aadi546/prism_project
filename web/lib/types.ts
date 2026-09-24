export type ExampleQuery = {
  id: string;
  domain: string;
  text: string;
};

export type Deeplink = {
  deeplink: string;
  description: string;
  message?: string | null;
  classes?: Record<string, string> | null;
  originalType?: string | null;
};

export type ValidationDeeplink = {
  deeplink: string;
  key: string;
  resultType?: "boolean" | "integer" | "str" | "float" | null;
  condition?: "greater" | "equal" | "less" | null;
  value?: string | null;
};

export type StepGroup = {
  steps: string[];
  actionableDeeplink: Deeplink | null;
  validationDeeplink: ValidationDeeplink | null;
};

export type Category = "auto" | "manual" | "critical";

export type Action = {
  actionName: string;
  description: string;
  category?: Category | null;
  stepGroups: StepGroup[];
};

export type Goal = {
  goal: string;
  title: string;
  score: number;
  actions: Action[];
};

export type Meta = {
  latency_ms: number;
  cache_hit: boolean;
  model: string;
  cost_usd: number;
  fallback?: string | null;
};

export type ProvenanceRow = {
  action: number;
  group: number;
  step: number;
  start: number;
  end: number;
  source: string;
  policy?: string;
};

export type MappingRow = {
  action: number;
  group: number;
  category: Category;
  deeplink: string | null;
  catalog_id: string | null;
  reason: string;
  candidates: { id: string; message: string; score: number }[];
};

export type Trace = {
  stages: { stage: string; ms: number; [k: string]: unknown }[];
  total_ms: number;
  enrichment: {
    cleaned: string;
    canonical: string;
    cache_key: string;
    symptoms: string[];
    device: string | null;
    intents: string[];
  };
  cache?: { hit: boolean; similarity?: number; matched?: string; method?: string };
  cache_store?: { stored: boolean; reason: string };
  retrieval?: {
    source: string;
    relevance?: number;
    gate?: string;
    candidates?: { id: string; title: string; score: number }[];
  }[];
  extraction?: {
    siis_text: string;
    sections_used: string[];
    sections_dropped: string[];
    provenance: ProvenanceRow[];
    mapping: MappingRow[];
    deeplink_coverage: number;
    verifiable_links: number;
    linked_groups: number;
  }[];
  violations?: string[][];
  llm?: { enabled: boolean };
};

export type TroubleshootResponse = {
  query: string;
  query_variations: string[];
  response: { contexts: Goal[] };
  meta: Meta;
  trace?: Trace;
};

export type SiisArticle = {
  id: string;
  title: string;
  query: string;
  siis_response: { title: string; content: string };
};

export type SimSnapshot = {
  id: string;
  state: Record<string, string>;
  labels: Record<string, string>;
  screens: string[];
  log: Record<string, unknown>[];
};

export type VerifyResult = {
  deeplink: string;
  key: string;
  observed: string | null;
  expected: string | null;
  condition: string | null;
  resultType: string | null;
  verifiable: boolean;
  passed: boolean;
};

export type Health = {
  status: string;
  catalog: number;
  catalog_phone_screens: number;
  siis_articles: number;
  cache_entries: number;
  model: string;
  llm: { provider: string; enabled: boolean; model: string };
};

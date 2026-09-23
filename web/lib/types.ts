export type ExampleQuery = {
  id: string;
  domain: string;
  text: string;
};

export type Deeplink = {
  deeplink: string;
  description: string;
  message?: string;
};

export type StepGroup = {
  steps: string[];
  actionableDeeplink: Deeplink | null;
};

export type Action = {
  actionName: string;
  description: string;
  category?: string;
  stepGroups: StepGroup[];
};

export type Goal = {
  goal: string;
  title: string;
  score: number;
  actions: Action[];
};

export type TroubleshootResponse = {
  query: string;
  query_variations: string[];
  response: { contexts: Goal[] };
  meta: {
    latency_ms: number;
    cache_hit: boolean;
    model: string;
    cost_usd: number;
    fallback?: string | null;
  };
};

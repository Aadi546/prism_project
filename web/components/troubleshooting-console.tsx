"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  Copy,
  Loader2,
  Radio,
  TriangleAlert,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import type { ExampleQuery, TroubleshootResponse } from "@/lib/types";

const FALLBACK_EXAMPLES: ExampleQuery[] = [
  {
    id: "q_swipe",
    domain: "display",
    text: "phone swipe gestures wrong direction after app install",
  },
  {
    id: "q_battery",
    domain: "battery",
    text: "the battery dies fast even when I barely use the phone",
  },
  {
    id: "q_camera",
    domain: "camera",
    text: "camera got blurry after the update",
  },
  {
    id: "q_slow",
    domain: "performance",
    text: "My phone got slow after the update",
  },
];

function categoryVariant(cat?: string) {
  if (cat === "critical") return "destructive" as const;
  if (cat === "manual") return "outline" as const;
  return "default" as const;
}

export function TroubleshootingConsole() {
  const [query, setQuery] = useState("");
  const [siis, setSiis] = useState("");
  const [examples, setExamples] = useState<ExampleQuery[]>(FALLBACK_EXAMPLES);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TroubleshootResponse | null>(null);
  const [copied, setCopied] = useState<string | null>(null);
  const [engineOk, setEngineOk] = useState<boolean | null>(null);

  useEffect(() => {
    fetch("/health")
      .then((r) => r.json())
      .then((b) => setEngineOk(b.status === "ok"))
      .catch(() => setEngineOk(false));
    fetch("/v1/examples")
      .then((r) => r.json())
      .then((b) => {
        if (Array.isArray(b.queries) && b.queries.length) {
          setExamples(b.queries.slice(0, 6));
        }
      })
      .catch(() => undefined);
  }, []);

  async function submit(nextQuery = query) {
    const q = nextQuery.trim();
    if (!q) {
      setError("Enter a customer complaint before running the engine.");
      return;
    }
    setQuery(q);
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/v1/troubleshoot", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: q,
          siis_response: siis.trim() || null,
        }),
      });
      if (!res.ok) {
        throw new Error(`Engine returned HTTP ${res.status}`);
      }
      const body = (await res.json()) as TroubleshootResponse;
      setResult(body);
    } catch (err) {
      setResult(null);
      setError(
        err instanceof Error
          ? err.message
          : "Could not reach the troubleshooting engine."
      );
    } finally {
      setLoading(false);
    }
  }

  async function copyText(value: string) {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(value);
      setTimeout(() => setCopied(null), 1500);
    } catch {
      setError("Clipboard permission denied.");
    }
  }

  const goal = result?.response.contexts[0];
  const emptyReason = useMemo(() => {
    if (!result || goal) return null;
    if (result.meta.fallback === "no_siis_context") {
      return "No SIIS article scored high enough for this complaint. Paste customer-care text or try a Battery, Display, Camera, or Performance issue.";
    }
    if (result.meta.fallback === "no_match") {
      return "The reference text has no viable on-device fix. The engine returned an empty plan instead of inventing steps.";
    }
    return "No troubleshooting plan was produced.";
  }, [result, goal]);

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-8 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-3 border-b border-border pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-2">
          <p className="text-xs font-medium tracking-[0.18em] text-muted-foreground uppercase">
            Galaxy device care
          </p>
          <h1 className="font-heading text-3xl font-semibold tracking-tight text-pretty sm:text-4xl">
            Smart Guided Troubleshooting
          </h1>
          <p className="max-w-2xl text-sm leading-6 text-muted-foreground sm:text-base">
            Paste a vague complaint. The engine normalizes it, retrieves SIIS,
            maps leaf Settings screens, and returns a one-tap Bixby plan —
            cached under 300 ms the next time a paraphrase lands.
          </p>
        </div>
        <div className="flex items-center gap-2 text-sm">
          <span
            className={`size-2 rounded-full ${engineOk ? "bg-emerald-500" : engineOk === false ? "bg-destructive" : "bg-muted-foreground"}`}
          />
          {engineOk === null
            ? "Checking engine"
            : engineOk
              ? "Engine ready"
              : "Engine unreachable"}
        </div>
      </header>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)]">
        <Card className="h-fit">
          <CardHeader>
            <CardTitle>Customer complaint</CardTitle>
            <CardDescription>
              SIIS context is optional. If you omit it, the engine searches the
              local article index.
            </CardDescription>
          </CardHeader>
          <CardContent className="flex flex-col gap-4">
            <label className="text-sm font-medium" htmlFor="query">
              What did the customer say?
            </label>
            <Textarea
              id="query"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Screen flickers and the battery dies fast"
              className="min-h-28"
            />
            <label className="text-sm font-medium" htmlFor="siis">
              Optional SIIS reference
            </label>
            <Textarea
              id="siis"
              value={siis}
              onChange={(e) => setSiis(e.target.value)}
              placeholder="Paste customer-care article text. Leave blank to use the indexed corpus."
              className="min-h-24"
            />
            <div className="flex flex-wrap gap-2">
              <Button
                onClick={() => submit()}
                disabled={loading}
                size="lg"
              >
                {loading ? (
                  <>
                    <Loader2 className="animate-spin" />
                    Running pipeline
                  </>
                ) : (
                  <>
                    <Radio />
                    Build plan
                  </>
                )}
              </Button>
              <Button
                variant="outline"
                size="lg"
                disabled={loading}
                onClick={() => {
                  setQuery("");
                  setSiis("");
                  setResult(null);
                  setError(null);
                }}
              >
                Clear
              </Button>
            </div>
            <div>
              <p className="mb-2 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Try a known issue
              </p>
              <div className="flex flex-col gap-2">
                {examples.map((ex) => (
                  <button
                    key={ex.id}
                    type="button"
                    className="rounded-lg border border-border px-3 py-2 text-left text-sm hover:bg-muted"
                    onClick={() => submit(ex.text)}
                  >
                    <span className="mr-2 font-medium text-muted-foreground">
                      {ex.domain}
                    </span>
                    {ex.text}
                  </button>
                ))}
              </div>
            </div>
            {error ? (
              <p className="text-sm text-destructive" role="alert">
                {error}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <div className="flex min-h-[28rem] flex-col gap-4">
          {!result && !loading ? (
            <Card className="flex flex-1 items-center justify-center py-16">
              <CardContent className="max-w-md text-center">
                <CardTitle className="mb-2">No plan yet</CardTitle>
                <CardDescription>
                  Run a complaint from the left. Cached paraphrases skip the
                  extractor and return the same validated JSON.
                </CardDescription>
              </CardContent>
            </Card>
          ) : null}

          {loading ? (
            <Card>
              <CardContent className="flex items-center gap-3 py-8">
                <Loader2 className="size-5 animate-spin" />
                Enriching query, retrieving SIIS, mapping deeplinks…
              </CardContent>
            </Card>
          ) : null}

          {result && !loading ? (
            <>
              <div className="flex flex-wrap gap-2">
                <Badge variant={result.meta.cache_hit ? "default" : "secondary"}>
                  {result.meta.cache_hit ? "Cache hit" : "Cache miss"}
                </Badge>
                <Badge variant="outline">{result.meta.latency_ms} ms</Badge>
                <Badge variant="outline">${result.meta.cost_usd.toFixed(2)}</Badge>
                <Badge variant="ghost">{result.meta.model}</Badge>
                {result.meta.fallback ? (
                  <Badge variant="destructive">{result.meta.fallback}</Badge>
                ) : null}
              </div>

              {emptyReason ? (
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <TriangleAlert className="size-4" />
                      Empty plan
                    </CardTitle>
                    <CardDescription>{emptyReason}</CardDescription>
                  </CardHeader>
                </Card>
              ) : null}

              {goal ? (
                <Card>
                  <CardHeader>
                    <CardDescription>{goal.goal}</CardDescription>
                    <CardTitle className="text-2xl">{goal.title}</CardTitle>
                    <p className="text-xs text-muted-foreground">
                      Confidence {goal.score.toFixed(2)}
                    </p>
                  </CardHeader>
                  <CardContent className="flex flex-col gap-6">
                    {goal.actions.map((action, idx) => (
                      <div
                        key={`${action.actionName}-${idx}`}
                        className="border-t border-border pt-4 first:border-t-0 first:pt-0"
                      >
                        <div className="mb-2 flex flex-wrap items-center gap-2">
                          <h3 className="font-medium">{action.actionName}</h3>
                          <Badge variant={categoryVariant(action.category)}>
                            {action.category}
                          </Badge>
                        </div>
                        <p className="mb-3 text-sm text-muted-foreground">
                          {action.description}
                        </p>
                        {action.stepGroups.map((group, gi) => (
                          <div key={gi} className="space-y-3">
                            <ol className="list-decimal space-y-1 pl-5 text-sm leading-6">
                              {group.steps.map((step) => (
                                <li key={step}>{step}</li>
                              ))}
                            </ol>
                            {group.actionableDeeplink ? (
                              <div className="flex flex-col gap-2 rounded-lg bg-muted/60 px-3 py-2 sm:flex-row sm:items-center sm:justify-between">
                                <div className="min-w-0">
                                  <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                                    One-tap Settings
                                  </p>
                                  <p className="truncate font-mono text-xs sm:text-sm">
                                    {group.actionableDeeplink.deeplink}
                                  </p>
                                  <p className="text-xs text-muted-foreground">
                                    {group.actionableDeeplink.description}
                                  </p>
                                </div>
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() =>
                                    copyText(group.actionableDeeplink!.deeplink)
                                  }
                                >
                                  {copied === group.actionableDeeplink.deeplink ? (
                                    <Check />
                                  ) : (
                                    <Copy />
                                  )}
                                  Copy
                                </Button>
                              </div>
                            ) : (
                              <p className="text-xs text-muted-foreground">
                                Manual or critical step — no catalog deeplink.
                              </p>
                            )}
                          </div>
                        ))}
                      </div>
                    ))}
                  </CardContent>
                </Card>
              ) : null}

              {goal && result.query_variations.length ? (
                <Card>
                  <CardHeader>
                    <CardTitle>Cached paraphrases</CardTitle>
                    <CardDescription>
                      These 8–10 variants are indexed as semantic cache keys.
                    </CardDescription>
                  </CardHeader>
                  <CardContent className="flex flex-wrap gap-2">
                    {result.query_variations.map((v) => (
                      <button
                        key={v}
                        type="button"
                        className="rounded-full border border-border px-3 py-1 text-left text-xs hover:bg-muted"
                        onClick={() => submit(v)}
                      >
                        {v}
                      </button>
                    ))}
                  </CardContent>
                </Card>
              ) : null}
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}

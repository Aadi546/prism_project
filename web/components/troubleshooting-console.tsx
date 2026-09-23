"use client";

import { useEffect, useMemo, useState } from "react";
import {
  Check,
  Copy,
  Hand,
  Loader2,
  Phone,
  ShieldAlert,
  Sparkles,
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
    id: "kit_cracked",
    domain: "screen",
    text: "My Galaxy phone's screen is completely cracked, it's a total crack and I can't use the device.",
  },
  {
    id: "kit_black",
    domain: "screen",
    text: "My Galaxy S24 Ultra screen is completely black and won't turn on, even though the phone powers on.",
  },
  {
    id: "kit_touch",
    domain: "touch",
    text: "My Galaxy S22 screen inputs are delayed and the touch responsiveness is laggy.",
  },
  {
    id: "kit_float",
    domain: "display",
    text: "My Galaxy S25 has a floating circle that constantly hovers on my screen.",
  },
];

function shortLabel(text: string) {
  const clean = text.replace(/^\d+\.\s*/, "").replace(/^"+|"+$/g, "");
  return clean.length > 92 ? `${clean.slice(0, 90)}…` : clean;
}

function categoryMeta(cat?: string) {
  if (cat === "critical") {
    return {
      label: "Last resort",
      hint: "Only after the earlier steps",
      icon: ShieldAlert,
      className: "bg-destructive/10 text-destructive border-destructive/20",
    };
  }
  if (cat === "manual") {
    return {
      label: "By hand",
      hint: "Repair desk, cable, or looking at the phone",
      icon: Hand,
      className: "border-border bg-secondary text-secondary-foreground",
    };
  }
  return {
    label: "On the phone",
    hint: "Settings you can tap yourself",
    icon: Phone,
    className: "bg-primary text-primary-foreground border-transparent",
  };
}

export function TroubleshootingConsole() {
  const [query, setQuery] = useState("");
  const [siis, setSiis] = useState("");
  const [showSiis, setShowSiis] = useState(false);
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
          const keys = [
            /cracked/i,
            /completely black/i,
            /floating circle/i,
            /laggy/i,
            /flickers and goes blank/i,
          ];
          const picked: ExampleQuery[] = [];
          for (const key of keys) {
            const hit = b.queries.find(
              (q: ExampleQuery) => key.test(q.text) && !picked.some((p) => p.id === q.id)
            );
            if (hit) picked.push(hit);
          }
          setExamples(picked.length ? picked : b.queries.slice(0, 4));
        }
      })
      .catch(() => undefined);
  }, []);

  async function submit(nextQuery = query) {
    const q = nextQuery.trim();
    if (!q) {
      setError("Type what is going wrong with the phone, then tap Get checklist.");
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
        throw new Error("The helper could not build a plan. Try again in a moment.");
      }
      const body = (await res.json()) as TroubleshootResponse;
      setResult(body);
    } catch {
      setResult(null);
      setError("Could not reach the helper. Check that it is running, then try again.");
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
      setError("Could not copy. Select the text instead.");
    }
  }

  const goal = result?.response.contexts[0];
  const emptyReason = useMemo(() => {
    if (!result || goal) return null;
    if (result.meta.fallback === "no_siis_context") {
      return "This helper only knows the sample screen problems in the kit (black display, cracks, laggy touch, and similar). Try one of the example problems, or paste a help article under Advanced.";
    }
    if (result.meta.fallback === "no_match") {
      return "The help article has no safe on-phone fix. The helper left the plan empty on purpose instead of making steps up.";
    }
    return "No checklist could be built for that description.";
  }, [result, goal]);

  return (
    <div className="relative min-h-full overflow-x-hidden">
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-[radial-gradient(1200px_280px_at_20%_-10%,oklch(0.82_0.08_255/0.35),transparent_70%)]"
      />
      <div className="relative mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-8 pb-28 sm:px-6 sm:pb-10 lg:px-8">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl space-y-3">
            <p className="text-xs font-semibold tracking-[0.2em] text-primary uppercase">
              Galaxy care helper
            </p>
            <h1 className="font-heading text-4xl leading-[1.1] font-semibold tracking-tight text-pretty sm:text-5xl">
              Say the problem.
              <span className="text-primary"> Get a checklist.</span>
            </h1>
            <p className="text-base leading-7 text-muted-foreground">
              Type what the phone is doing in everyday words. You will get
              ordered steps to try on the Galaxy. Links under a step are demo
              Settings IDs — they will not open the screen on a real phone.
            </p>
          </div>
          <div className="flex items-center gap-2 self-start rounded-full border border-border bg-card px-3 py-1.5 text-sm shadow-sm">
            <span
              className={`size-2 rounded-full ${engineOk ? "bg-emerald-600" : engineOk === false ? "bg-destructive" : "bg-muted-foreground"}`}
            />
            {engineOk === null
              ? "Starting…"
              : engineOk
                ? "Ready"
                : "Helper offline"}
          </div>
        </header>

        <ol className="grid gap-3 sm:grid-cols-3">
          {[
            ["1", "Describe it", "Black screen, crack, laggy touch — however they said it."],
            ["2", "Read the plan", "Safer Settings steps first. Repair or restart last."],
            ["3", "Do it on the phone", "Follow the list. Ignore the bixby:// codes unless you are testing."],
          ].map(([n, t, d]) => (
            <li
              key={n}
              className="flex gap-3 rounded-2xl border border-border bg-card/80 px-4 py-3"
            >
              <span className="font-heading text-2xl text-primary">{n}</span>
              <span>
                <span className="block font-medium">{t}</span>
                <span className="text-sm leading-5 text-muted-foreground">{d}</span>
              </span>
            </li>
          ))}
        </ol>

        <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,0.92fr)_minmax(0,1.18fr)]">
          <Card className="lg:sticky lg:top-4">
            <CardHeader>
              <CardTitle className="font-heading text-2xl">What’s going wrong?</CardTitle>
              <CardDescription>
                Write it like a customer would. Examples below fill this box for you.
              </CardDescription>
            </CardHeader>
            <CardContent className="flex flex-col gap-4">
              <label className="text-sm font-medium" htmlFor="query">
                The problem
              </label>
              <Textarea
                id="query"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                placeholder="My Galaxy screen went black but the phone still rings…"
                className="min-h-32 bg-background text-base"
              />

              <button
                type="button"
                className="text-left text-sm text-primary underline-offset-4 hover:underline"
                onClick={() => setShowSiis((v) => !v)}
              >
                {showSiis ? "Hide extra help article" : "I have a help article to paste (optional)"}
              </button>
              {showSiis ? (
                <div className="space-y-2">
                  <label className="text-sm font-medium" htmlFor="siis">
                    Help article
                  </label>
                  <Textarea
                    id="siis"
                    value={siis}
                    onChange={(e) => setSiis(e.target.value)}
                    placeholder="Paste support notes if you have them. Leave blank otherwise."
                    className="min-h-24 bg-background"
                  />
                </div>
              ) : null}

              <div className="hidden flex-wrap gap-2 sm:flex">
                <Button onClick={() => submit()} disabled={loading} size="lg">
                  {loading ? (
                    <>
                      <Loader2 className="animate-spin" />
                      Building checklist
                    </>
                  ) : (
                    <>
                      <Sparkles />
                      Get checklist
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
                <p className="mb-2 text-xs font-semibold tracking-wide text-muted-foreground uppercase">
                  Try a sample
                </p>
                <div className="flex flex-col gap-2">
                  {examples.map((ex) => (
                    <button
                      key={ex.id}
                      type="button"
                      className="rounded-xl border border-border bg-background px-3 py-2.5 text-left text-sm leading-5 hover:border-primary/40 hover:bg-muted"
                      onClick={() => submit(ex.text)}
                    >
                      {shortLabel(ex.text)}
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
              <Card className="flex flex-1 items-center justify-center border-dashed py-16">
                <CardContent className="max-w-md text-center">
                  <Sparkles className="mx-auto mb-3 text-primary" />
                  <CardTitle className="font-heading mb-2 text-2xl">
                    Your checklist will show here
                  </CardTitle>
                  <CardDescription className="text-base leading-6">
                    Tap a sample on the left, or type a screen problem and press
                    Get checklist.
                  </CardDescription>
                </CardContent>
              </Card>
            ) : null}

            {loading ? (
              <Card>
                <CardContent className="flex items-center gap-3 py-10 text-muted-foreground">
                  <Loader2 className="size-5 animate-spin text-primary" />
                  Matching the problem to a help article and Settings screens…
                </CardContent>
              </Card>
            ) : null}

            {result && !loading ? (
              <>
                {emptyReason ? (
                  <Card>
                    <CardHeader>
                      <CardTitle className="font-heading flex items-center gap-2 text-2xl">
                        <TriangleAlert className="size-5 text-accent-foreground" />
                        No checklist this time
                      </CardTitle>
                      <CardDescription className="text-base leading-6">
                        {emptyReason}
                      </CardDescription>
                    </CardHeader>
                  </Card>
                ) : null}

                {goal ? (
                  <Card>
                    <CardHeader className="gap-2">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant="secondary">
                          {result.meta.cache_hit ? "Instant (seen before)" : "Fresh lookup"}
                        </Badge>
                        <Badge variant="outline">
                          {Math.round(result.meta.latency_ms)} ms
                        </Badge>
                      </div>
                      <CardTitle className="font-heading text-3xl leading-tight">
                        {goal.title}
                      </CardTitle>
                      <CardDescription className="text-base">
                        {goal.goal}
                      </CardDescription>
                    </CardHeader>
                    <CardContent className="flex flex-col gap-5">
                      {goal.actions.map((action, idx) => {
                        const meta = categoryMeta(action.category);
                        const Icon = meta.icon;
                        return (
                          <article
                            key={`${action.actionName}-${idx}`}
                            className="rounded-2xl border border-border bg-background/70 p-4"
                          >
                            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                              <div>
                                <p className="text-xs font-medium text-muted-foreground">
                                  Step {idx + 1}
                                </p>
                                <h3 className="font-heading text-xl leading-snug">
                                  {action.actionName}
                                </h3>
                              </div>
                              <span
                                className={`inline-flex items-center gap-1 rounded-full border px-2.5 py-1 text-xs font-medium ${meta.className}`}
                              >
                                <Icon className="size-3.5" />
                                {meta.label}
                              </span>
                            </div>
                            <p className="mb-3 text-sm text-muted-foreground">
                              {action.description}
                            </p>
                            {action.stepGroups.map((group, gi) => (
                              <div key={gi} className="space-y-3">
                                <ol className="space-y-2">
                                  {group.steps.map((step, si) => (
                                    <li
                                      key={`${si}-${step.slice(0, 24)}`}
                                      className="flex gap-3 text-sm leading-6"
                                    >
                                      <span className="mt-0.5 flex size-6 shrink-0 items-center justify-center rounded-full bg-primary/10 text-xs font-semibold text-primary">
                                        {si + 1}
                                      </span>
                                      <span>{step}</span>
                                    </li>
                                  ))}
                                </ol>
                                {group.actionableDeeplink ? (
                                  <div className="rounded-xl border border-dashed border-primary/25 bg-card px-3 py-3">
                                    <p className="text-xs font-semibold tracking-wide text-primary uppercase">
                                      Settings screen (demo ID)
                                    </p>
                                    <p className="text-sm">
                                      {group.actionableDeeplink.message ||
                                        group.actionableDeeplink.description}
                                    </p>
                                    <p className="mt-1 font-mono text-[11px] break-all text-muted-foreground">
                                      {group.actionableDeeplink.deeplink}
                                    </p>
                                    <p className="mt-1 text-xs text-muted-foreground">
                                      This code is a stand-in. It will not open Settings
                                      on a Galaxy. Follow the numbered taps above.
                                    </p>
                                    <Button
                                      variant="outline"
                                      size="sm"
                                      className="mt-2"
                                      onClick={() =>
                                        copyText(group.actionableDeeplink!.deeplink)
                                      }
                                    >
                                      {copied === group.actionableDeeplink.deeplink ? (
                                        <Check />
                                      ) : (
                                        <Copy />
                                      )}
                                      Copy ID
                                    </Button>
                                  </div>
                                ) : (
                                  <p className="text-xs text-muted-foreground">
                                    {meta.hint}. No Settings shortcut for this part.
                                  </p>
                                )}
                              </div>
                            ))}
                          </article>
                        );
                      })}
                    </CardContent>
                  </Card>
                ) : null}
              </>
            ) : null}
          </div>
        </div>
      </div>

      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-border bg-card/95 p-3 backdrop-blur sm:hidden">
        <div className="flex gap-2">
          <Button className="flex-1" size="lg" disabled={loading} onClick={() => submit()}>
            {loading ? "Building…" : "Get checklist"}
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
      </div>
    </div>
  );
}

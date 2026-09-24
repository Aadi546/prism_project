"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Check, Copy, Download, FastForward, Loader2, RotateCcw, Sparkles, TriangleAlert } from "lucide-react";

import { PhoneSimulator, type PhoneScreen, type SettingRow } from "@/components/phone-simulator";
import { PlanView, groupKey } from "@/components/plan-view";
import { TraceView } from "@/components/trace-view";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { getSiis, simStart, simTap, simVerify, troubleshoot } from "@/lib/api";
import type { ExampleQuery, SiisArticle, TroubleshootResponse, VerifyResult } from "@/lib/types";

type Tab = "plan" | "trace" | "json";

const EXTRA_EXAMPLES: ExampleQuery[] = [
  {
    id: "multi",
    domain: "compound",
    text: '1. "My Galaxy Z Flip 7 screen is cracked again right where it folds." 2. "The touch doesn\'t work on certain parts of the screen." 3. "I can hardly see anything on the display."',
  },
  { id: "para", domain: "paraphrase", text: "s22 touch input delay laggy screen" },
  { id: "unknown", domain: "no match", text: "My phone's infrared blaster no longer controls my AC remote app" },
];

function short(text: string, n = 78) {
  const t = text.replace(/^\d+\.\s*/, "").replace(/^"+|"+$/g, "");
  return t.length > n ? `${t.slice(0, n - 1)}…` : t;
}

function kindOf(originalType?: string | null, uri?: string): PhoneScreen["kind"] {
  if (uri?.endsWith("dummy_positive")) return "dummy";
  if (originalType === "onURL") return "on";
  if (originalType === "offURL") return "off";
  if (originalType === "updateURL") return "update";
  return "open";
}

export function TroubleshootingConsole() {
  const [query, setQuery] = useState("");
  const [articles, setArticles] = useState<SiisArticle[]>([]);
  const [siisMode, setSiisMode] = useState<string>("none");
  const [customSiis, setCustomSiis] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<TroubleshootResponse | null>(null);
  const [tab, setTab] = useState<Tab>("plan");
  const [copied, setCopied] = useState(false);

  const [session, setSession] = useState<string | null>(null);
  const [simState, setSimState] = useState<Record<string, string>>({});
  const [simLabels, setSimLabels] = useState<Record<string, string>>({});
  const [screen, setScreen] = useState<PhoneScreen | null>(null);
  const [verify, setVerify] = useState<Record<string, VerifyResult>>({});
  const [lastVerify, setLastVerify] = useState<VerifyResult | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [criticalUnlocked, setCriticalUnlocked] = useState(false);
  const autopilot = useRef(false);

  useEffect(() => {
    getSiis()
      .then(setArticles)
      .catch(() => undefined);
  }, []);

  const examples = useMemo(() => {
    const seen = new Set<string>();
    const picks = articles.filter((a) => {
      if (seen.has(a.title)) return false;
      seen.add(a.title);
      return true;
    });
    return picks;
  }, [articles]);

  const goals = useMemo(() => result?.response.contexts ?? [], [result]);


  const loadSim = useCallback(async (res: TroubleshootResponse) => {
    setScreen(null);
    setVerify({});
    setLastVerify(null);
    setCriticalUnlocked(false);
    if (!res.response.contexts.length) {
      setSession(null);
      setSimState({});
      setSimLabels({});
      return;
    }
    try {
      const snap = await simStart(res.response);
      setSession(snap.id);
      setSimState(snap.state);
      setSimLabels(snap.labels);
    } catch {
      setSession(null);
    }
  }, []);

  async function submit(q = query, siisOverride?: unknown) {
    const text = q.trim();
    if (!text) {
      setError("Describe what the phone is doing first.");
      return;
    }
    setQuery(text);
    setLoading(true);
    setError(null);
    let siis: unknown = siisOverride ?? null;
    if (siisOverride === undefined) {
      if (siisMode === "custom") siis = customSiis.trim() || null;
      else if (siisMode !== "none") siis = articles.find((a) => a.id === siisMode)?.siis_response ?? null;
    }
    try {
      const res = await troubleshoot(text, siis);
      setResult(res);
      setTab("plan");
      await loadSim(res);
    } catch {
      setResult(null);
      setError("The engine did not answer. Start it with: python -m uvicorn app:app --port 8765");
    } finally {
      setLoading(false);
    }
  }

  async function runGroup(c: number, a: number, g: number) {
    if (!session || !result) return;
    const group = result.response.contexts[c]?.actions[a]?.stepGroups[g];
    const link = group?.actionableDeeplink;
    if (!group || !link) return;
    const key = groupKey(c, a, g);
    setRunning(key);
    setLastVerify(null);
    try {
      const val = group.validationDeeplink;
      const tapped = await simTap(session, link.deeplink, val);
      const kind = kindOf(link.originalType, link.deeplink);
      const row = tapped.row;
      setScreen({
        title: row?.message ?? link.message ?? "Settings",
        description: row?.description ?? link.description,
        detail: row?.qna_description ?? null,
        uri: link.deeplink,
        kind,
        settingKey: val?.key ?? row?.key ?? null,
        value: val ? tapped.state[val.deeplink] : null,
      });
      setSimState(tapped.state);
      if (val) {
        await new Promise((r) => setTimeout(r, 450));
        const v = await simVerify(session, val);
        setVerify((m) => ({ ...m, [key]: v }));
        setLastVerify(v);
      } else {
        const v: VerifyResult = {
          deeplink: link.deeplink,
          key: link.message ?? "screen",
          observed: null,
          expected: null,
          condition: null,
          resultType: null,
          verifiable: false,
          passed: true,
        };
        setVerify((m) => ({ ...m, [key]: v }));
        setLastVerify(v);
      }
    } finally {
      setRunning(null);
    }
  }

  const autoGroups = useMemo(() => {
    const out: [number, number, number][] = [];
    goals.forEach((goal, c) =>
      goal.actions.forEach((act, a) => {
        if (act.category !== "auto") return;
        act.stepGroups.forEach((g, gi) => g.actionableDeeplink && out.push([c, a, gi]));
      }),
    );
    return out;
  }, [goals]);

  async function runAll() {
    autopilot.current = true;
    for (const [c, a, g] of autoGroups) {
      if (!autopilot.current) break;
      await runGroup(c, a, g);
      await new Promise((r) => setTimeout(r, 700));
    }
    autopilot.current = false;
  }

  const verifiedCount = Object.values(verify).filter((v) => v.verifiable && v.passed).length;
  const verifiableTotal = goals.flatMap((g) => g.actions).filter((a) => a.category === "auto").flatMap((a) => a.stepGroups).filter((g) => g.validationDeeplink?.resultType).length;

  const settings: SettingRow[] = Object.keys(simState).map((uri) => ({
    uri,
    label: simLabels[uri] ?? uri,
    value: simState[uri],
  }));

  const contractJson = useMemo(() => {
    if (!result) return "";
    // eslint-disable-next-line @typescript-eslint/no-unused-vars
    const { trace, ...contract } = result;
    return JSON.stringify(contract, null, 2);
  }, [result]);

  const emptyReason =
    result && !goals.length
      ? result.meta.fallback === "no_siis_context"
        ? "No knowledge-base article covers this complaint, so the engine returned an empty plan (fallback: no_siis_context) instead of inventing steps."
        : "The reference text has no viable fix for this complaint, so the plan is empty on purpose (fallback: no_match)."
      : null;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex max-w-3xl flex-col gap-2">
        <h1 className="font-heading text-3xl leading-tight font-semibold tracking-tight text-pretty sm:text-4xl">
          Vague complaint in. <span className="text-primary">Verified one-tap plan out.</span>
        </h1>
        <p className="text-sm leading-6 text-muted-foreground sm:text-base">
          The engine reads the Samsung knowledge-base article, keeps only steps it can point to in the text, maps each
          Settings step to the exact catalog screen, orders safe → physical → disruptive, and then proves the fix on a
          simulated device by reading the validation deeplink back.
        </p>
      </header>

      <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_320px] xl:grid-cols-[340px_minmax(0,1fr)_320px]">
        {/* input */}
        <section className="flex flex-col gap-4 rounded-xl border border-border bg-card p-4 lg:col-span-2 xl:sticky xl:top-20 xl:col-span-1">
          <label className="text-sm font-medium" htmlFor="query">
            Customer complaint
          </label>
          <Textarea
            id="query"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) submit();
            }}
            placeholder="My Galaxy screen went black but the phone still rings…"
            className="min-h-28 bg-background text-sm"
          />
          <div className="flex flex-col gap-1.5">
            <label className="text-sm font-medium" htmlFor="siis">
              SIIS reference text
            </label>
            <select
              id="siis"
              value={siisMode}
              onChange={(e) => setSiisMode(e.target.value)}
              className="h-9 rounded-lg border border-input bg-background px-2 text-sm"
            >
              <option value="none">None — engine retrieves / uses cache</option>
              {articles.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.id}: {short(a.title, 48)}
                </option>
              ))}
              <option value="custom">Paste my own…</option>
            </select>
            {siisMode === "custom" ? (
              <Textarea
                value={customSiis}
                onChange={(e) => setCustomSiis(e.target.value)}
                placeholder="Paste a customer-care article…"
                className="min-h-28 bg-background font-mono text-xs"
              />
            ) : null}
          </div>
          <Button size="lg" onClick={() => submit()} disabled={loading}>
            {loading ? <Loader2 className="animate-spin" /> : <Sparkles />}
            Build plan
          </Button>
          {error ? (
            <p className="flex items-start gap-2 text-sm text-destructive">
              <TriangleAlert className="mt-0.5 size-4 shrink-0" /> {error}
            </p>
          ) : null}
          <div className="flex max-h-72 flex-col gap-1.5 overflow-auto pr-1 xl:max-h-none xl:overflow-visible">
            <span className="text-xs font-medium text-muted-foreground">Kit complaints (with their SIIS article)</span>
            {examples.map((a) => (
              <button
                key={a.id}
                type="button"
                onClick={() => {
                  setSiisMode(a.id);
                  submit(a.query, a.siis_response);
                }}
                className="rounded-lg border border-border px-2.5 py-1.5 text-left text-xs leading-5 hover:bg-muted"
              >
                {short(a.query)}
              </button>
            ))}
            <span className="mt-2 text-xs font-medium text-muted-foreground">Edge cases (no SIIS)</span>
            {EXTRA_EXAMPLES.map((e) => (
              <button
                key={e.id}
                type="button"
                onClick={() => {
                  setSiisMode("none");
                  submit(e.text, null);
                }}
                className="rounded-lg border border-dashed border-border px-2.5 py-1.5 text-left text-xs leading-5 hover:bg-muted"
              >
                <span className="mr-1 font-medium">{e.domain}:</span>
                {short(e.text, 70)}
              </button>
            ))}
          </div>
        </section>

        {/* result */}
        <section className="flex min-h-[28rem] min-w-0 flex-col gap-4">
          {result ? (
            <>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <span className={`rounded-full px-2.5 py-1 ${result.meta.cache_hit ? "bg-ok-soft text-ok" : "bg-muted"}`}>
                  {result.meta.cache_hit ? "Cache hit" : "Cold pipeline"}
                </span>
                <span className="rounded-full bg-muted px-2.5 py-1 font-mono tabular-nums">{result.meta.latency_ms} ms</span>
                <span className="rounded-full bg-muted px-2.5 py-1 font-mono">${result.meta.cost_usd.toFixed(4)}</span>
                <span className="rounded-full bg-muted px-2.5 py-1">{result.meta.model}</span>
                {result.meta.fallback ? (
                  <span className="rounded-full bg-bad-soft px-2.5 py-1 text-destructive">fallback: {result.meta.fallback}</span>
                ) : null}
                <div className="ml-auto flex rounded-lg border border-border p-0.5">
                  {(["plan", "trace", "json"] as Tab[]).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => setTab(t)}
                      className={`rounded-md px-2.5 py-1 capitalize ${tab === t ? "bg-secondary font-medium" : "text-muted-foreground"}`}
                    >
                      {t === "json" ? "JSON" : t}
                    </button>
                  ))}
                </div>
              </div>

              {tab === "plan" ? (
                emptyReason ? (
                  <div className="rounded-xl border border-dashed border-border p-6 text-sm leading-6 text-muted-foreground">
                    <p className="mb-2 font-medium text-foreground">Empty plan — by design</p>
                    {emptyReason}
                  </div>
                ) : (
                  <PlanView
                    goals={goals}
                    verify={verify}
                    running={running}
                    criticalUnlocked={criticalUnlocked}
                    onRun={runGroup}
                    onUnlock={() => setCriticalUnlocked(true)}
                    canRun={!!session}
                  />
                )
              ) : null}
              {tab === "trace" ? (
                result.trace ? (
                  <TraceView trace={result.trace} goals={goals} variations={result.query_variations} />
                ) : (
                  <p className="text-sm text-muted-foreground">No trace for this response.</p>
                )
              ) : null}
              {tab === "json" ? (
                <div className="flex flex-col gap-2">
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={async () => {
                        await navigator.clipboard.writeText(contractJson);
                        setCopied(true);
                        setTimeout(() => setCopied(false), 1400);
                      }}
                    >
                      {copied ? <Check /> : <Copy />} Copy
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => {
                        const blob = new Blob([contractJson], { type: "application/json" });
                        const url = URL.createObjectURL(blob);
                        const a = document.createElement("a");
                        a.href = url;
                        a.download = "troubleshoot_response.json";
                        a.click();
                        URL.revokeObjectURL(url);
                      }}
                    >
                      <Download /> Download
                    </Button>
                    <span className="self-center text-xs text-muted-foreground">Exactly what POST /v1/troubleshoot returns (trace excluded)</span>
                  </div>
                  <pre className="max-h-[40rem] overflow-auto rounded-xl border border-border bg-muted/40 p-3 text-xs leading-5">
                    {contractJson}
                  </pre>
                </div>
              ) : null}
            </>
          ) : (
            <div className="flex flex-1 flex-col items-center justify-center rounded-xl border border-dashed border-border p-10 text-center">
              <p className="font-heading text-xl">Pick a kit complaint or type one</p>
              <p className="mt-2 max-w-md text-sm text-muted-foreground">
                You will get the plan, a trace showing where every step came from, and a phone you can tap through to
                watch each fix get confirmed.
              </p>
            </div>
          )}
        </section>

        {/* phone */}
        <aside className="flex flex-col gap-3 lg:sticky lg:top-20">
          <PhoneSimulator
            screen={screen}
            settings={settings}
            verify={lastVerify}
            busy={running !== null && !lastVerify}
            onBack={() => setScreen(null)}
            sessionId={session}
          />
          <div className="flex flex-col gap-2 rounded-xl border border-border bg-card p-3 text-xs">
            <div className="flex items-center justify-between">
              <span className="font-medium">Closed-loop check</span>
              <span className="font-mono tabular-nums">
                {verifiedCount}/{verifiableTotal} verified
              </span>
            </div>
            <div className="flex gap-2">
              <Button size="sm" className="flex-1" disabled={!session || !autoGroups.length || running !== null} onClick={runAll}>
                <FastForward /> Run safe steps
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!result}
                onClick={() => {
                  autopilot.current = false;
                  if (result) loadSim(result);
                }}
              >
                <RotateCcw /> Reset
              </Button>
            </div>
            <p className="leading-4 text-muted-foreground">
              Each tap opens the target screen, flips the switch, then re-reads the <span className="font-mono">val/</span>{" "}
              URI against resultType / condition / value.
            </p>
          </div>
        </aside>
      </div>
    </div>
  );
}

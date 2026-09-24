"use client";

import { useEffect, useState } from "react";

type Lat = { n: number; p50: number; p95: number };
type Metrics = {
  generated: string;
  model: string;
  environment: string;
  compliance: Record<string, number>;
  accuracy: { step_accuracy: number; deeplink_relevance: number };
  latency: { exact: Lat; paraphrase: Lat; cold: Lat };
  cost: { cold_avg_usd: number };
  cache: { paraphrases: number; hit_pct: number; wrong_hit_pct: number; miss_pct: number };
  closed_loop: { plans?: number; verified_taps?: number; fixed_and_confirmed?: number; plans_with_verifiable_fix?: number };
  ablation?: { variant: string; step: number; links: number; p95: number; cost: number; note: string }[];
};

type Row = { label: string; target: string; before?: number; after: number; max: number; unit: string; higher: boolean };

function Compare({ row }: { row: Row }) {
  const w = (v?: number) => `${Math.max(1.5, Math.min(100, ((v ?? 0) / row.max) * 100))}%`;
  const fmt = (v?: number) => (v === undefined ? "—" : `${v}${row.unit}`);
  return (
    <li className="grid grid-cols-1 gap-1.5 border-t border-border py-3 first:border-t-0 sm:grid-cols-[minmax(0,16rem)_1fr] sm:gap-4">
      <div>
        <p className="text-sm font-medium">{row.label}</p>
        <p className="text-xs text-muted-foreground">target {row.target}</p>
      </div>
      <div className="flex flex-col gap-1">
        {[
          ["Before", row.before, "bg-muted-foreground/45"],
          ["After", row.after, "bg-primary"],
        ].map(([name, v, color]) => (
          <div key={name as string} className="grid grid-cols-[3.5rem_1fr_4.5rem] items-center gap-2 text-xs" title={`${name}: ${fmt(v as number)}`}>
            <span className="text-muted-foreground">{name as string}</span>
            <span className="h-2 rounded-full bg-muted">
              <span className={`block h-full rounded-full ${color}`} style={{ width: w(v as number) }} />
            </span>
            <span className="text-right font-mono tabular-nums">{fmt(v as number)}</span>
          </div>
        ))}
      </div>
    </li>
  );
}

function Tile({ label, value, sub }: { label: string; value: string; sub?: string }) {
  return (
    <div className="rounded-xl border border-border bg-card p-4">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 font-heading text-3xl tabular-nums">{value}</p>
      {sub ? <p className="mt-1 text-xs text-muted-foreground">{sub}</p> : null}
    </div>
  );
}

export default function MetricsPage() {
  const [data, setData] = useState<{ metrics?: Metrics; metrics_before?: Metrics } | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    fetch("/v1/metrics")
      .then((r) => r.json())
      .then(setData)
      .catch(() => setError(true));
  }, []);

  const m = data?.metrics;
  const b = data?.metrics_before;

  if (error) return <p className="p-8 text-sm text-destructive">Engine offline — start it on port 8765.</p>;
  if (!data) return <p className="p-8 text-sm text-muted-foreground">Loading metrics…</p>;
  if (!m)
    return (
      <p className="p-8 text-sm text-muted-foreground">
        No metrics yet. Run <span className="font-mono">python eval/run_metrics.py</span>.
      </p>
    );

  const rows: Row[] = [
    { label: "Rule compliance (goal / title / description / names)", target: "≥ 95%", before: b?.compliance.rule_compliance_pct, after: m.compliance.rule_compliance_pct, max: 100, unit: "%", higher: true },
    { label: "Step accuracy vs hand-labelled gold", target: "0 – 3", before: b?.accuracy.step_accuracy, after: m.accuracy.step_accuracy, max: 3, unit: "", higher: true },
    { label: "Deeplink relevance (exact screen)", target: "0 – 2", before: b?.accuracy.deeplink_relevance, after: m.accuracy.deeplink_relevance, max: 2, unit: "", higher: true },
    { label: "Cache hit rate on unseen paraphrases", target: "≥ 80%", before: b?.cache.hit_pct, after: m.cache.hit_pct, max: 100, unit: "%", higher: true },
    { label: "Linked steps with verifiable validation", target: "new", before: b?.compliance.verifiable_validation_pct, after: m.compliance.verifiable_validation_pct, max: 100, unit: "%", higher: true },
  ];

  const loop = m.closed_loop;

  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-6 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-1">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Metrics · Appendix C</h1>
        <p className="text-sm text-muted-foreground">
          {m.model} · {m.environment} · generated {m.generated} by <span className="font-mono">eval/run_metrics.py</span>. The
          scorer re-implements the brief&apos;s rules independently of the engine; “before” is the original v1 engine on the same data.
        </p>
      </header>

      <section className="grid grid-cols-2 gap-3 md:grid-cols-4">
        <Tile label="Schema-valid responses" value={`${m.compliance.schema_valid_pct}%`} sub={`${m.compliance.responses} responses`} />
        <Tile label="URL leaks" value={String(m.compliance.url_leaks)} sub="target 0" />
        <Tile label="Catalog-valid URIs" value={`${m.compliance.catalog_validity_pct}%`} sub="exact match, never invented" />
        <Tile label="Auto actions with a deeplink" value={`${m.compliance.auto_with_link_pct}%`} sub="target ≥ 90%" />
      </section>

      <section className="rounded-xl border border-border bg-card p-4">
        <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
          <h2 className="font-heading text-xl">Before → after</h2>
          <div className="flex gap-3 text-xs text-muted-foreground">
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-muted-foreground/45" /> Before (v1)</span>
            <span className="flex items-center gap-1.5"><span className="size-2.5 rounded-sm bg-primary" /> After (v2)</span>
          </div>
        </div>
        <ul>{rows.map((r) => <Compare key={r.label} row={r} />)}</ul>
      </section>

      <section className="grid gap-4 md:grid-cols-2">
        <div className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 font-heading text-xl">Latency (ms)</h2>
          <table className="w-full text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr><th className="py-1 font-medium">Path</th><th className="py-1 text-right font-medium">N</th><th className="py-1 text-right font-medium">P50</th><th className="py-1 text-right font-medium">P95</th><th className="py-1 text-right font-medium">Target</th></tr>
            </thead>
            <tbody className="font-mono tabular-nums">
              {([
                ["Cache hit · exact", m.latency.exact, "≤ 300"],
                ["Cache hit · paraphrase", m.latency.paraphrase, "≤ 300"],
                ["Cold · full pipeline", m.latency.cold, "≤ 8000"],
              ] as [string, Lat, string][]).map(([l, v, t]) => (
                <tr key={l} className="border-t border-border">
                  <td className="py-1.5 font-sans">{l}</td>
                  <td className="py-1.5 text-right">{v.n}</td>
                  <td className="py-1.5 text-right">{v.p50}</td>
                  <td className="py-1.5 text-right">{v.p95}</td>
                  <td className="py-1.5 text-right text-muted-foreground">{t}</td>
                </tr>
              ))}
            </tbody>
          </table>
          <p className="mt-3 text-xs text-muted-foreground">
            Cold-path cost ${m.cost.cold_avg_usd.toFixed(6)} / query · cache hits $0. Wrong-article cache hits {m.cache.wrong_hit_pct}%,
            misses {m.cache.miss_pct}% over {m.cache.paraphrases} hand-written paraphrases.
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 font-heading text-xl">Closed-loop verification</h2>
          <div className="grid grid-cols-2 gap-3">
            <Tile label="Plans with a verifiable one-tap fix" value={`${loop.plans_with_verifiable_fix ?? "—"}/${loop.plans ?? "—"}`} />
            <Tile label="Taps confirmed via val/ deeplink" value={`${loop.fixed_and_confirmed ?? "—"}/${loop.verified_taps ?? "—"}`} />
          </div>
          <p className="mt-3 text-xs leading-5 text-muted-foreground">
            On a simulated device each setting starts in its faulty state; the engine taps the actionable deeplink and re-reads
            the validation deeplink using the plan&apos;s resultType / condition / value. Screens without a readable state
            (open-a-page links) are counted as not verifiable.
          </p>
        </div>
      </section>

      {m.ablation?.length ? (
        <section className="overflow-x-auto rounded-xl border border-border bg-card p-4">
          <h2 className="mb-3 font-heading text-xl">Ablation · deeplink mapping</h2>
          <table className="w-full min-w-[40rem] text-left text-sm">
            <thead className="text-xs text-muted-foreground">
              <tr><th className="py-1 font-medium">Variant</th><th className="py-1 text-right font-medium">Step acc.</th><th className="py-1 text-right font-medium">Link rel.</th><th className="py-1 text-right font-medium">P95 cold</th><th className="py-1 font-medium pl-4">Observation</th></tr>
            </thead>
            <tbody>
              {b ? (
                <tr className="border-t border-border">
                  <td className="py-1.5">v1 baseline</td>
                  <td className="py-1.5 text-right font-mono">{b.accuracy.step_accuracy}</td>
                  <td className="py-1.5 text-right font-mono">{b.accuracy.deeplink_relevance}</td>
                  <td className="py-1.5 text-right font-mono">{b.latency.cold.p95} ms</td>
                  <td className="py-1.5 pl-4 text-xs text-muted-foreground">hashed n-grams, no relevance gate</td>
                </tr>
              ) : null}
              {m.ablation.map((r) => (
                <tr key={r.variant} className="border-t border-border">
                  <td className="py-1.5">{r.variant}</td>
                  <td className="py-1.5 text-right font-mono">{r.step}</td>
                  <td className="py-1.5 text-right font-mono">{r.links}</td>
                  <td className="py-1.5 text-right font-mono">{r.p95} ms</td>
                  <td className="py-1.5 pl-4 text-xs text-muted-foreground">{r.note}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </section>
      ) : null}
    </div>
  );
}

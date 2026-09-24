"use client";

import { useMemo, useState } from "react";

import type { Goal, Trace } from "@/lib/types";

const STAGE_LABEL: Record<string, string> = {
  enrich: "Query enrichment",
  cache_lookup: "Semantic cache lookup",
  retrieve: "SIIS retrieval + relevance gate",
  extract_map_validate: "Extract · map deeplinks · validate",
  assemble: "Assemble + URL scrub + cache store",
};

function Fact({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm break-words">{children}</dd>
    </div>
  );
}

export function TraceView({ trace, goals, variations }: { trace: Trace; goals: Goal[]; variations: string[] }) {
  const [focus, setFocus] = useState<{ ctx: number; start: number; end: number } | null>(null);
  const max = Math.max(...trace.stages.map((s) => s.ms), 0.001);

  const ex = useMemo(() => trace.extraction ?? [], [trace]);

  const highlighted = useMemo(() => {
    return ex.map((e, ci) => {
      const text = e.siis_text || "";
      const spans = [...e.provenance].sort((a, b) => a.start - b.start);
      const out: { text: string; used: boolean; active: boolean }[] = [];
      let cur = 0;
      for (const sp of spans) {
        if (sp.start < cur || sp.end <= sp.start) continue;
        out.push({ text: text.slice(cur, sp.start), used: false, active: false });
        out.push({
          text: text.slice(sp.start, sp.end),
          used: true,
          active: !!focus && focus.ctx === ci && focus.start === sp.start,
        });
        cur = sp.end;
      }
      out.push({ text: text.slice(cur), used: false, active: false });
      return out;
    });
  }, [ex, focus]);

  return (
    <div className="flex flex-col gap-6">
      <section>
        <h4 className="mb-2 text-sm font-semibold">Pipeline stages · {trace.total_ms} ms total</h4>
        <ol className="flex flex-col gap-1.5">
          {trace.stages.map((s, i) => (
            <li key={i} className="grid grid-cols-[minmax(0,11rem)_1fr_auto] items-center gap-3 text-xs">
              <span className="truncate text-muted-foreground">{STAGE_LABEL[s.stage] ?? s.stage}</span>
              <span className="h-2 overflow-hidden rounded-full bg-muted">
                <span className="block h-full rounded-full bg-primary" style={{ width: `${Math.max(2, (s.ms / max) * 100)}%` }} />
              </span>
              <span className="font-mono tabular-nums">{s.ms.toFixed(2)} ms</span>
            </li>
          ))}
        </ol>
      </section>

      <section className="grid gap-4 sm:grid-cols-2">
        <dl className="flex flex-col gap-3 rounded-xl border border-border p-4">
          <h4 className="text-sm font-semibold">[0] Enrichment</h4>
          <Fact label="Canonical cache key">
            <span className="font-mono text-xs">{trace.enrichment.canonical || "—"}</span>
          </Fact>
          <Fact label="Symptoms">{trace.enrichment.symptoms.join(", ") || "none detected"}</Fact>
          <Fact label="Device">{trace.enrichment.device ?? "not stated"}</Fact>
          {trace.enrichment.intents.length > 1 ? (
            <Fact label={`Split into ${trace.enrichment.intents.length} intents`}>
              <ul className="list-disc pl-4">
                {trace.enrichment.intents.map((i, k) => (
                  <li key={k}>{i}</li>
                ))}
              </ul>
            </Fact>
          ) : null}
        </dl>
        <dl className="flex flex-col gap-3 rounded-xl border border-border p-4">
          <h4 className="text-sm font-semibold">[3] Cache &amp; [1] retrieval</h4>
          <Fact label="Cache">
            {trace.cache?.hit
              ? `hit (${trace.cache.method}, similarity ${trace.cache.similarity}) on “${trace.cache.matched}”`
              : trace.cache
                ? "miss — full pipeline ran"
                : "skipped (SIIS text supplied or compound complaint)"}
          </Fact>
          {trace.cache_store ? (
            <Fact label="Stored for next time">
              {trace.cache_store.stored ? "yes" : `no — ${trace.cache_store.reason} (cache-poisoning guard)`}
            </Fact>
          ) : null}
          {(trace.retrieval ?? []).map((r, i) => (
            <Fact key={i} label={r.source === "request" ? "SIIS supplied in request" : `Knowledge-base retrieval${(trace.retrieval?.length ?? 0) > 1 ? ` #${i + 1}` : ""}`}>
              {r.source === "request" ? `relevance ${r.relevance}` : null}
              {r.candidates ? (
                <ul className="mt-1 flex flex-col gap-0.5">
                  {r.candidates.map((c) => (
                    <li key={c.id} className="flex justify-between gap-2 text-xs">
                      <span className="truncate">{c.title}</span>
                      <span className="font-mono tabular-nums">{c.score}</span>
                    </li>
                  ))}
                </ul>
              ) : null}
              {r.gate ? <p className="mt-1 text-xs text-destructive">{r.gate}</p> : null}
            </Fact>
          ))}
        </dl>
      </section>

      {ex.map((e, ci) => (
        <section key={ci} className="flex flex-col gap-3">
          <h4 className="text-sm font-semibold">
            [1–2] Extraction &amp; deeplink mapping{ex.length > 1 ? ` · issue ${ci + 1}` : ""}
          </h4>
          <p className="text-xs text-muted-foreground">
            Sections used: {e.sections_used.join(" · ") || "—"}
            {e.sections_dropped.length ? ` — dropped as informational / off-topic: ${e.sections_dropped.join(" · ")}` : ""}
          </p>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="flex flex-col gap-2">
              <p className="text-xs text-muted-foreground">Hover a step to see the sentence it came from.</p>
              <ol className="flex max-h-[28rem] flex-col gap-1 overflow-auto pr-1 text-sm">
                {(goals[ci]?.actions ?? []).map((a, ai) =>
                  a.stepGroups.map((g, gi) =>
                    g.steps.map((s, si) => {
                      const p = e.provenance.find((x) => x.action === ai && x.group === gi && x.step === si);
                      return (
                        <li
                          key={`${ai}-${gi}-${si}`}
                          onMouseEnter={() => p && setFocus({ ctx: ci, start: p.start, end: p.end })}
                          onMouseLeave={() => setFocus(null)}
                          className={`cursor-default rounded-md px-2 py-1 ${
                            focus && p && focus.start === p.start && focus.ctx === ci ? "bg-warn-soft" : "hover:bg-muted"
                          }`}
                        >
                          <span className="mr-2 font-mono text-[10px] text-muted-foreground">
                            {a.category?.[0]?.toUpperCase()}
                            {ai + 1}.{gi + 1}
                          </span>
                          {s}
                          {p?.policy ? <span className="ml-2 text-[10px] text-muted-foreground">(policy: {p.policy})</span> : null}
                        </li>
                      );
                    }),
                  ),
                )}
              </ol>
            </div>
            <div className="max-h-[30rem] overflow-auto rounded-xl border border-border bg-muted/30 p-3 text-xs leading-5 whitespace-pre-wrap">
              {highlighted[ci].map((part, k) =>
                part.used ? (
                  <mark
                    key={k}
                    ref={part.active ? (el) => el?.scrollIntoView({ block: "nearest", behavior: "smooth" }) : undefined}
                    className={`rounded-sm px-0.5 text-foreground ${part.active ? "bg-warn" : "bg-warn-soft"}`}
                  >
                    {part.text}
                  </mark>
                ) : (
                  <span key={k} className="text-muted-foreground">
                    {part.text}
                  </span>
                ),
              )}
            </div>
          </div>
          <div className="overflow-x-auto rounded-xl border border-border">
            <table className="w-full min-w-[36rem] text-left text-xs">
              <thead className="bg-muted/50 text-muted-foreground">
                <tr>
                  <th className="px-3 py-2 font-medium">Group</th>
                  <th className="px-3 py-2 font-medium">Chosen screen</th>
                  <th className="px-3 py-2 font-medium">Why</th>
                  <th className="px-3 py-2 font-medium">Top catalog candidates</th>
                </tr>
              </thead>
              <tbody>
                {e.mapping.map((m, k) => (
                  <tr key={k} className="border-t border-border align-top">
                    <td className="px-3 py-2 font-mono">
                      {m.category[0].toUpperCase()}
                      {m.action + 1}.{m.group + 1}
                    </td>
                    <td className="px-3 py-2">{m.catalog_id ?? (m.deeplink ? "dummy_positive" : "—")}</td>
                    <td className="px-3 py-2">{m.reason}</td>
                    <td className="px-3 py-2 text-muted-foreground">
                      {m.candidates.slice(0, 3).map((c) => `${c.id} ${c.message} (${c.score})`).join(" · ") || "—"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="text-xs text-muted-foreground">
            {e.linked_groups} linked step groups · {e.verifiable_links} carry a machine-checkable validation deeplink ·
            rule violations after validation: {trace.violations?.[ci]?.length ? trace.violations[ci].join(", ") : "none"}
          </p>
        </section>
      ))}

      <section>
        <h4 className="mb-2 text-sm font-semibold">Query variations ({variations.length}) — also stored as cache keys</h4>
        <ul className="grid gap-1 text-sm sm:grid-cols-2">
          {variations.map((v, i) => (
            <li key={i} className="rounded-md bg-muted/50 px-2 py-1">
              {v}
            </li>
          ))}
        </ul>
      </section>
    </div>
  );
}

"use client";

import { Download, Loader2, Play } from "lucide-react";
import { Fragment, useState } from "react";

import { Button } from "@/components/ui/button";
import type { TroubleshootResponse } from "@/lib/types";

type Row = {
  query: string;
  titles: string[];
  actions: number;
  score: number;
  fallback: string | null;
  cache_hit: boolean;
  latency_ms: number;
  response: TroubleshootResponse;
};

export default function BatchPage() {
  const [rows, setRows] = useState<Row[] | null>(null);
  const [jsonl, setJsonl] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<number | null>(null);

  async function run() {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch("/v1/batch");
      if (!res.ok) throw new Error();
      const body = await res.json();
      setRows(body.rows);
      setJsonl(body.jsonl);
    } catch {
      setError("The engine did not answer. Start it on port 8765.");
    } finally {
      setLoading(false);
    }
  }

  function download() {
    const blob = new Blob([jsonl], { type: "application/x-ndjson" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = "results.jsonl";
    a.click();
    URL.revokeObjectURL(url);
  }

  const hits = rows?.filter((r) => r.cache_hit).length ?? 0;
  const lat = rows?.map((r) => r.latency_ms).sort((a, b) => a - b) ?? [];
  const p95 = lat.length ? lat[Math.min(lat.length - 1, Math.round(0.95 * (lat.length - 1)))] : 0;

  return (
    <div className="mx-auto flex w-full max-w-7xl flex-col gap-5 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Batch run · data/input.txt</h1>
        <p className="max-w-3xl text-sm leading-6 text-muted-foreground">
          Runs all 20 kit complaints through <span className="font-mono">POST /v1/troubleshoot</span> without SIIS text —
          the fast path the brief describes: semantic lookup against the pre-warmed cache, knowledge-base retrieval on a
          miss. Download the output as <span className="font-mono">results.jsonl</span> (Appendix B format).
        </p>
      </header>
      <div className="flex flex-wrap items-center gap-2">
        <Button onClick={run} disabled={loading}>
          {loading ? <Loader2 className="animate-spin" /> : <Play />} Run 20 complaints
        </Button>
        <Button variant="outline" onClick={download} disabled={!jsonl}>
          <Download /> results.jsonl
        </Button>
        {rows ? (
          <span className="text-sm text-muted-foreground">
            {hits}/{rows.length} served from cache · P95 {p95.toFixed(2)} ms ·{" "}
            {rows.filter((r) => r.fallback).length} empty plans
          </span>
        ) : null}
        {error ? <span className="text-sm text-destructive">{error}</span> : null}
      </div>
      {rows ? (
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[48rem] text-left text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">#</th>
                <th className="px-3 py-2 font-medium">Complaint</th>
                <th className="px-3 py-2 font-medium">Plan title(s)</th>
                <th className="px-3 py-2 text-right font-medium">Actions</th>
                <th className="px-3 py-2 text-right font-medium">Score</th>
                <th className="px-3 py-2 font-medium">Path</th>
                <th className="px-3 py-2 text-right font-medium">ms</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r, i) => (
                <Fragment key={i}>
                  <tr
                    className="cursor-pointer border-t border-border align-top hover:bg-muted/40"
                    onClick={() => setOpen(open === i ? null : i)}
                  >
                    <td className="px-3 py-2 text-muted-foreground tabular-nums">{i + 1}</td>
                    <td className="max-w-md px-3 py-2">{r.query}</td>
                    <td className="px-3 py-2">{r.titles.join(" · ") || <span className="text-destructive">{r.fallback}</span>}</td>
                    <td className="px-3 py-2 text-right tabular-nums">{r.actions}</td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{r.score.toFixed(2)}</td>
                    <td className="px-3 py-2">
                      <span className={`rounded-full px-2 py-0.5 text-xs ${r.cache_hit ? "bg-ok-soft text-ok" : "bg-muted"}`}>
                        {r.cache_hit ? "cache" : "cold"}
                      </span>
                    </td>
                    <td className="px-3 py-2 text-right font-mono tabular-nums">{r.latency_ms.toFixed(2)}</td>
                  </tr>
                  {open === i ? (
                    <tr className="border-t border-border">
                      <td colSpan={7} className="p-0">
                        <pre className="max-h-96 overflow-auto bg-muted/30 p-3 text-xs">{JSON.stringify(r.response, null, 2)}</pre>
                      </td>
                    </tr>
                  ) : null}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>
      ) : null}
    </div>
  );
}

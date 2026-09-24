const SPEC_GAPS = [
  ["No rule for validationDeeplink", "The schema has key / resultType / condition / value but the brief never says how to fill them, so nothing proves a fix worked.", "Derived from the catalog twin (onURL → boolean = True, offURL → False, updateURL → integer >/<) and executed in a closed loop on a simulated device."],
  ["No abstain threshold", "“Return empty contexts when no viable solution” — but no definition of viable. Retrieval always returns *something*.", "Relevance gate on supplied and retrieved SIIS; calibrated score (complaint coverage + symptom agreement + deeplink coverage)."],
  ["Single-intent assumption", "Kit query #17 has three numbered complaints; the contract allows many Goals but the pipeline describes one.", "Intent splitter → one Goal per complaint, retrieved against article content only."],
  ["Cache poisoning", "The fast path replays whatever was stored — including a wrong plan — to every paraphrase.", "Only plans above a score floor are cached; entries carry the SIIS content hash for invalidation."],
  ["Destructive steps with no safety net", "Factory reset / clear data are just “ordered last”.", "Backup-first action (as in the official sample output), critical tier locked in the UI until safer steps fail, and never a one-tap link on a destructive step."],
  ["No provenance requirement", "“Derive purely from reference text” is not checkable from the output.", "Every step carries the character span of its source sentence (trace), shown side-by-side in the console."],
  ["Toggle direction", "The catalog has onURL/offURL twins for the same switch; the brief never mentions picking one.", "Direction is read from the step (enable / turn off) and the twin is chosen accordingly."],
  ["Self-graded metrics", "Appendix C has no gold labels, so teams report 100% by construction.", "Hand-labelled gold + 60 hand-written paraphrases + an independent scorer, run against the old engine too."],
];

const BASELINE = [
  "Titles cut to three words: “Some things to”, “Screen does not”, “Blank or black”.",
  "Descriptions padded with filler: “It will overview settings settings”, “It will what is casting?”.",
  "Headings such as Overview / What is casting / Understanding screen damage became actions.",
  "Generic steps mapped to random screens: Charge the device → Connected devices, Ink blots → Find My Mobile.",
  "“Perform a Factory Data Reset” categorised as auto (one-tap reset).",
  "Score was max-normalised BM25, so every plan scored ~0.93 — even for the wrong article.",
  "Paraphrases garbled every word (“the dveice dveice siwpe”); 0% cache hits on real paraphrases.",
  "The cache was pre-warmed with the evaluation queries themselves, so “cold” latency was really a cache hit.",
  "scripts/generate_data.py would overwrite the official kit in data/ with synthetic data.",
];

const STAGES = [
  ["0", "Enrichment", "canonical form · symptoms · device · intents · 8–10 paraphrases"],
  ["3", "Semantic cache", "exact → char-gram cosine, symptom-agreement gate"],
  ["1", "Retrieval + gate", "TF-IDF over SIIS · relevance floor · no_siis_context"],
  ["1", "Extraction", "sections → imperative atomic steps → one screen per action (Groq optional)"],
  ["2", "Deeplink mapping", "verbatim setting name → TF-IDF on descriptions · twin direction · dummy_positive"],
  ["✓", "Validation", "field rules · URL scrub · category rules · auto → manual → critical"],
  ["★", "Closed loop", "validationDeeplink → tap → read back on device"],
  ["4", "REST", "POST /v1/troubleshoot · GET /health · pure JSON"],
];

export default function AboutPage() {
  return (
    <div className="mx-auto flex w-full max-w-6xl flex-col gap-8 px-4 py-6 sm:px-6 lg:px-8">
      <header className="flex max-w-3xl flex-col gap-2">
        <h1 className="font-heading text-3xl font-semibold tracking-tight">Gaps, fixes and the innovation</h1>
        <p className="text-sm leading-6 text-muted-foreground">
          What the Theme 2 brief leaves open, what was wrong with the starting engine, and what this version does about
          each. Numbers for every claim are on the Metrics page.
        </p>
      </header>

      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-xl">Architecture</h2>
        <ol className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
          {STAGES.map(([n, t, d], i) => (
            <li key={t} className="relative rounded-xl border border-border bg-card p-3">
              <div className="flex items-center gap-2">
                <span className="flex size-6 items-center justify-center rounded-full bg-secondary font-mono text-xs">{n}</span>
                <span className="text-sm font-medium">{t}</span>
                <span className="ml-auto text-[10px] text-muted-foreground">{i + 1}/8</span>
              </div>
              <p className="mt-1.5 text-xs leading-5 text-muted-foreground">{d}</p>
            </li>
          ))}
        </ol>
        <p className="text-xs text-muted-foreground">
          Numbers match the brief&apos;s pipeline stages. The cache is checked before retrieval; stages 1–2 run only on a miss.
        </p>
      </section>

      <section className="flex flex-col gap-3">
        <h2 className="font-heading text-xl">Gaps in the brief → what we built</h2>
        <div className="overflow-x-auto rounded-xl border border-border">
          <table className="w-full min-w-[44rem] text-left text-sm">
            <thead className="bg-muted/50 text-xs text-muted-foreground">
              <tr>
                <th className="px-3 py-2 font-medium">Gap</th>
                <th className="px-3 py-2 font-medium">Why it matters</th>
                <th className="px-3 py-2 font-medium">Our answer</th>
              </tr>
            </thead>
            <tbody>
              {SPEC_GAPS.map(([g, why, fix]) => (
                <tr key={g} className="border-t border-border align-top">
                  <td className="px-3 py-2 font-medium">{g}</td>
                  <td className="px-3 py-2 text-muted-foreground">{why}</td>
                  <td className="px-3 py-2">{fix}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="grid gap-6 md:grid-cols-2">
        <div className="flex flex-col gap-2">
          <h2 className="font-heading text-xl">What was wrong with v1</h2>
          <ul className="list-disc space-y-1.5 pl-5 text-sm leading-6">
            {BASELINE.map((b) => (
              <li key={b}>{b}</li>
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-2">
          <h2 className="font-heading text-xl">Innovation: closed-loop verification</h2>
          <p className="text-sm leading-6">
            A one-tap deeplink only proves the right screen <em>opened</em>. Every auto step now also carries a
            machine-checkable <span className="font-mono">validationDeeplink</span>. The on-device agent (simulated here)
            taps the action, reads the setting back through the <span className="font-mono">val/</span> URI and compares it
            with <span className="font-mono">condition</span> / <span className="font-mono">value</span>. Only when every
            safe fix is confirmed and the customer still has the problem does the plan unlock restart / safe mode / reset.
          </p>
          <p className="text-sm leading-6 text-muted-foreground">
            Impact: fewer unnecessary factory resets and service visits, and an audit trail of which fix actually resolved
            the ticket — the signal needed to re-rank plans over time.
          </p>
          <h3 className="mt-2 text-sm font-semibold">Also</h3>
          <ul className="list-disc space-y-1 pl-5 text-sm leading-6">
            <li>Optional Groq LLM path (llama-3.3-70b): drafts are re-grounded against the SIIS text and re-validated; any failure falls back.</li>
            <li>Provenance view: hover any step to see the sentence it came from.</li>
            <li>Multi-intent complaints produce one Goal per issue.</li>
          </ul>
        </div>
      </section>
    </div>
  );
}

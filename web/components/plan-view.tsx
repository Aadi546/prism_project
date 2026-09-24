"use client";

import { Check, CircleDashed, Hand, Lock, Play, ShieldAlert, Smartphone, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import type { Action, Category, Goal, VerifyResult } from "@/lib/types";

export const groupKey = (c: number, a: number, g: number) => `${c}-${a}-${g}`;

const TIERS: { cat: Category; label: string; hint: string; icon: typeof Smartphone; tone: string }[] = [
  { cat: "auto", label: "On the phone", hint: "One tap opens the exact Settings screen", icon: Smartphone, tone: "text-primary" },
  { cat: "manual", label: "By hand", hint: "Physical checks, cables, repair desk — no one-tap link by design", icon: Hand, tone: "text-warn" },
  { cat: "critical", label: "Last resort", hint: "Restart, safe mode, reset — only after the steps above", icon: ShieldAlert, tone: "text-destructive" },
];

function ScoreMeter({ score }: { score: number }) {
  const pct = Math.round(score * 100);
  const tone = score >= 0.7 ? "bg-ok" : score >= 0.55 ? "bg-warn" : "bg-destructive";
  return (
    <div className="flex items-center gap-2" title="Calibrated confidence: complaint coverage by the reference, symptom agreement and deeplink coverage">
      <div className="h-1.5 w-24 overflow-hidden rounded-full bg-muted">
        <div className={`h-full ${tone}`} style={{ width: `${pct}%` }} />
      </div>
      <span className="font-mono text-xs tabular-nums">{score.toFixed(2)}</span>
    </div>
  );
}

function VerifyBadge({ v }: { v: VerifyResult | undefined }) {
  if (!v) return null;
  if (!v.verifiable)
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-muted px-2 py-0.5 text-xs">
        <CircleDashed className="size-3" /> Opened
      </span>
    );
  return v.passed ? (
    <span className="inline-flex items-center gap-1 rounded-full bg-ok-soft px-2 py-0.5 text-xs text-ok">
      <Check className="size-3" /> Verified
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 rounded-full bg-bad-soft px-2 py-0.5 text-xs text-destructive">
      <X className="size-3" /> Not fixed
    </span>
  );
}

type Props = {
  goals: Goal[];
  verify: Record<string, VerifyResult>;
  running: string | null;
  criticalUnlocked: boolean;
  onRun: (c: number, a: number, g: number) => void;
  onUnlock: () => void;
  canRun: boolean;
};

function ActionCard({
  action,
  c,
  a,
  props,
  locked,
}: {
  action: Action;
  c: number;
  a: number;
  props: Props;
  locked: boolean;
}) {
  return (
    <li className={`rounded-xl border border-border bg-card p-4 ${locked ? "opacity-60" : ""}`}>
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <h4 className="font-medium">{action.actionName}</h4>
        <span className="text-xs text-muted-foreground">{action.description}</span>
      </div>
      <div className="mt-3 flex flex-col gap-3">
        {action.stepGroups.map((g, gi) => {
          const key = groupKey(c, a, gi);
          const link = g.actionableDeeplink;
          const val = g.validationDeeplink;
          return (
            <div key={gi} className={gi ? "border-t border-dashed border-border pt-3" : ""}>
              <ol className="list-decimal space-y-1 pl-5 text-sm leading-6 marker:text-muted-foreground">
                {g.steps.map((s, si) => (
                  <li key={si}>{s}</li>
                ))}
              </ol>
              {link ? (
                <div className="mt-2 flex flex-wrap items-center gap-2">
                  <span className="rounded-md bg-muted px-2 py-1 font-mono text-[11px]" title={link.description}>
                    {link.deeplink}
                  </span>
                  {link.message ? <span className="text-xs text-muted-foreground">{link.message}</span> : null}
                  {val ? (
                    <span className="rounded-md border border-border px-2 py-0.5 font-mono text-[11px]" title={val.deeplink}>
                      check {val.key}
                      {val.condition ? ` ${val.condition === "equal" ? "=" : val.condition === "greater" ? ">" : "<"} ${val.value ?? "baseline"}` : ""}
                    </span>
                  ) : null}
                  <span className="ml-auto flex items-center gap-2">
                    <VerifyBadge v={props.verify[key]} />
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={!props.canRun || locked || props.running !== null}
                      onClick={() => props.onRun(c, a, gi)}
                    >
                      {props.running === key ? <CircleDashed className="animate-spin" /> : <Play />}
                      Tap on device
                    </Button>
                  </span>
                </div>
              ) : null}
            </div>
          );
        })}
      </div>
    </li>
  );
}

export function PlanView(props: Props) {
  const { goals, criticalUnlocked, onUnlock } = props;
  return (
    <div className="flex flex-col gap-6">
      {goals.map((goal, c) => (
        <section key={c} className="flex flex-col gap-4">
          <div className="rounded-xl border border-border bg-card p-4">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs tracking-wide text-muted-foreground uppercase">
                  {goals.length > 1 ? `Issue ${c + 1} of ${goals.length} · ` : ""}
                  {goal.title}
                </p>
                <h3 className="font-heading text-xl leading-snug">{goal.goal}</h3>
              </div>
              <ScoreMeter score={goal.score} />
            </div>
          </div>
          {TIERS.map((tier) => {
            const items = goal.actions
              .map((action, a) => ({ action, a }))
              .filter(({ action }) => (action.category ?? "manual") === tier.cat);
            if (!items.length) return null;
            const locked = tier.cat === "critical" && !criticalUnlocked;
            const Icon = tier.icon;
            return (
              <div key={tier.cat} className="flex flex-col gap-2">
                <div className="flex flex-wrap items-center gap-2">
                  <Icon className={`size-4 ${tier.tone}`} />
                  <h4 className="text-sm font-semibold">{tier.label}</h4>
                  <span className="text-xs text-muted-foreground">{tier.hint}</span>
                  {locked ? (
                    <Button size="xs" variant="outline" className="ml-auto" onClick={onUnlock}>
                      <Lock /> Problem still there — show last resort
                    </Button>
                  ) : null}
                </div>
                {locked ? (
                  <p className="rounded-xl border border-dashed border-border px-4 py-3 text-sm text-muted-foreground">
                    {items.length} disruptive step{items.length > 1 ? "s" : ""} hidden until the safer steps have been tried
                    ({items.map((i) => i.action.actionName).join(", ")}).
                  </p>
                ) : (
                  <ul className="flex flex-col gap-2">
                    {items.map(({ action, a }) => (
                      <ActionCard key={a} action={action} c={c} a={a} props={props} locked={false} />
                    ))}
                  </ul>
                )}
              </div>
            );
          })}
        </section>
      ))}
    </div>
  );
}

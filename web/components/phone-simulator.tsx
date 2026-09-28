"use client";

import { ArrowLeft, BatteryFull, Check, ChevronRight, CircleDashed, Signal, Wifi, X } from "lucide-react";

import type { VerifyResult } from "@/lib/types";

export type PhoneScreen = {
  title: string;
  description: string;
  detail?: string | null;
  uri: string;
  kind: "on" | "off" | "update" | "open" | "dummy";
  settingKey?: string | null;
  value?: string | null;
};

export type SettingRow = { uri: string; label: string; value: string };

type Props = {
  screen: PhoneScreen | null;
  settings: SettingRow[];
  verify: VerifyResult | null;
  busy: boolean;
  onBack: () => void;
  sessionId: string | null;
};

function ValueControl({ value, kind }: { value: string | null | undefined; kind: PhoneScreen["kind"] }) {
  if (value === "True" || value === "False") {
    const on = value === "True";
    return (
      <span
        role="switch"
        aria-checked={on}
        className={`relative inline-flex h-6 w-11 shrink-0 items-center rounded-full transition-colors duration-500 ${
          on ? "bg-primary" : "bg-muted-foreground/40"
        }`}
      >
        <span
          className={`inline-block size-5 rounded-full bg-background shadow transition-transform duration-500 ${
            on ? "translate-x-5.5" : "translate-x-0.5"
          }`}
        />
      </span>
    );
  }
  if (kind === "update" && value && !Number.isNaN(Number(value))) {
    return <span className="font-mono text-sm tabular-nums">{value}</span>;
  }
  return <ChevronRight className="size-4 text-muted-foreground" />;
}

export function PhoneSimulator({ screen, settings, verify, busy, onBack, sessionId }: Props) {
  return (
    <div className="mx-auto w-full max-w-[280px]">
      <div className="rounded-[2.2rem] bg-phone-frame p-2 shadow-lg ring-1 ring-foreground/10">
        <div className="relative flex h-[460px] flex-col overflow-hidden rounded-[1.8rem] bg-phone-screen text-foreground">
          {/* status bar */}
          <div className="flex items-center justify-between px-5 pt-2.5 pb-1 text-[11px] text-muted-foreground">
            <span className="font-medium tabular-nums">9:41</span>
            <span className="absolute left-1/2 top-2 size-2.5 -translate-x-1/2 rounded-full bg-phone-frame" />
            <span className="flex items-center gap-1">
              <Signal className="size-3" />
              <Wifi className="size-3" />
              <BatteryFull className="size-3.5" />
            </span>
          </div>

          {screen ? (
            <div key={screen.uri + screen.title} className="flex flex-1 flex-col animate-in fade-in slide-in-from-right-8 duration-300">
              <div className="flex items-center gap-2 px-3 py-1.5">
                <button
                  type="button"
                  onClick={onBack}
                  className="rounded-full p-1 hover:bg-muted"
                  aria-label="Back to Settings"
                >
                  <ArrowLeft className="size-4" />
                </button>
                <span className="text-xs text-muted-foreground">Settings</span>
              </div>
              <div className="px-4 pb-2">
                <h3 className="font-heading text-xl leading-tight">{screen.title}</h3>
              </div>
              <div className="mx-2.5 rounded-xl bg-card p-3 ring-1 ring-foreground/5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium">{screen.settingKey || screen.title}</span>
                  <ValueControl value={screen.value} kind={screen.kind} />
                </div>
                <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">{screen.description}</p>
                {screen.detail ? <p className="mt-1.5 text-[11px] leading-4 text-muted-foreground">{screen.detail}</p> : null}
              </div>
              <div className="mx-2.5 mt-2 rounded-lg bg-muted/60 px-2.5 py-1.5 font-mono text-[9px] break-all text-muted-foreground">
                {screen.uri}
              </div>
              <div className="mt-auto p-2.5">
                {busy ? (
                  <div className="flex items-center gap-2 rounded-xl bg-muted px-2.5 py-2 text-xs">
                    <CircleDashed className="size-3.5 animate-spin" /> Reading validation deeplink…
                  </div>
                ) : verify ? (
                  <div
                    className={`rounded-xl px-2.5 py-2 text-xs ${
                      !verify.verifiable ? "bg-muted" : verify.passed ? "bg-ok-soft" : "bg-bad-soft"
                    }`}
                  >
                    <div className="flex items-center gap-2 font-medium">
                      {!verify.verifiable ? (
                        <CircleDashed className="size-3.5" />
                      ) : verify.passed ? (
                        <Check className="size-3.5 text-ok" />
                      ) : (
                        <X className="size-3.5 text-destructive" />
                      )}
                      <span className="text-xs">
                        {!verify.verifiable
                          ? "Screen opened — nothing to read back"
                          : verify.passed
                            ? "Fix confirmed on device"
                            : "Setting did not change"}
                      </span>
                    </div>
                    {verify.verifiable ? (
                      <div className="mt-0.5 font-mono text-[9px] text-muted-foreground">
                        {verify.key}: {String(verify.observed)} {verify.condition} {verify.expected ?? "baseline"}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex flex-1 flex-col">
              <div className="px-4 pt-3 pb-2">
                <h3 className="font-heading text-2xl">Settings</h3>
                <p className="mt-0.5 text-[11px] text-muted-foreground">
                  {sessionId ? "Simulated device · settings this plan touches" : "Run a plan to load a simulated device"}
                </p>
              </div>
              <div className="mx-2.5 divide-y divide-border overflow-hidden rounded-xl bg-card ring-1 ring-foreground/5">
                {settings.length ? (
                  settings.map((s) => (
                    <div key={s.uri} className="flex items-center justify-between gap-2 px-3 py-2 text-xs">
                      <span className="truncate">{s.label}</span>
                      <ValueControl value={s.value} kind="open" />
                    </div>
                  ))
                ) : (
                  <div className="px-3 py-4 text-center text-xs text-muted-foreground">
                    {sessionId ? "This plan has no machine-checkable settings." : "No plan loaded yet."}
                  </div>
                )}
              </div>
              <p className="mt-auto px-4 pb-3 text-[10px] leading-3.5 text-muted-foreground">
                A mock of the on-device agent: it resolves each <span className="font-mono">val/</span> deeplink to a
                setting value. Not a real phone.
              </p>
            </div>
          )}
          <div className="mx-auto mb-1.5 h-1 w-20 rounded-full bg-foreground/20" />
        </div>
      </div>
    </div>
  );
}

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
    <div className="mx-auto w-full max-w-[235px]">
      <div className="rounded-[2.2rem] bg-phone-frame p-1.5 shadow-md ring-1 ring-foreground/10">
        <div className="relative flex h-[435px] flex-col overflow-hidden rounded-[1.8rem] bg-phone-screen text-foreground">
          {/* status bar */}
          <div className="flex items-center justify-between px-3.5 pt-2 pb-0.5 text-[9.5px] text-muted-foreground">
            <span className="font-medium tabular-nums">9:41</span>
            <span className="absolute left-1/2 top-2 size-2.5 -translate-x-1/2 rounded-full bg-phone-frame" />
            <span className="flex items-center gap-1">
              <Signal className="size-2.5" />
              <Wifi className="size-2.5" />
              <BatteryFull className="size-3" />
            </span>
          </div>

          {screen ? (
            <div key={screen.uri + screen.title} className="flex flex-1 flex-col animate-in fade-in slide-in-from-right-8 duration-300">
              <div className="flex items-center gap-1.5 px-2.5 py-1">
                <button
                  type="button"
                  onClick={onBack}
                  className="rounded-full p-1 hover:bg-muted"
                  aria-label="Back to Settings"
                >
                  <ArrowLeft className="size-3.5" />
                </button>
                <span className="text-[11px] text-muted-foreground">Settings</span>
              </div>
              <div className="px-3 pb-1.5">
                <h3 className="font-heading text-lg leading-tight">{screen.title}</h3>
              </div>
              <div className="mx-2 rounded-xl bg-card p-2.5 ring-1 ring-foreground/5">
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-medium">{screen.settingKey || screen.title}</span>
                  <ValueControl value={screen.value} kind={screen.kind} />
                </div>
                <p className="mt-1 text-[10px] leading-3.5 text-muted-foreground">{screen.description}</p>
                {screen.detail ? <p className="mt-1 text-[10px] leading-3.5 text-muted-foreground">{screen.detail}</p> : null}
              </div>
              <div className="mx-2 mt-1.5 rounded-lg bg-muted/60 px-2 py-1 font-mono text-[8.5px] break-all text-muted-foreground">
                {screen.uri}
              </div>
              <div className="mt-auto p-2">
                {busy ? (
                  <div className="flex items-center gap-1.5 rounded-lg bg-muted px-2 py-1.5 text-[11px]">
                    <CircleDashed className="size-3 animate-spin" /> Reading validation…
                  </div>
                ) : verify ? (
                  <div
                    className={`rounded-lg px-2 py-1.5 text-[11px] ${
                      !verify.verifiable ? "bg-muted" : verify.passed ? "bg-ok-soft" : "bg-bad-soft"
                    }`}
                  >
                    <div className="flex items-center gap-1.5 font-medium">
                      {!verify.verifiable ? (
                        <CircleDashed className="size-3" />
                      ) : verify.passed ? (
                        <Check className="size-3 text-ok" />
                      ) : (
                        <X className="size-3 text-destructive" />
                      )}
                      <span className="text-[11px]">
                        {!verify.verifiable
                          ? "Screen opened"
                          : verify.passed
                            ? "Fix confirmed on device"
                            : "Setting did not change"}
                      </span>
                    </div>
                    {verify.verifiable ? (
                      <div className="mt-0.5 font-mono text-[8.5px] text-muted-foreground">
                        {verify.key}: {String(verify.observed)} {verify.condition} {verify.expected ?? "baseline"}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="flex flex-1 flex-col">
              <div className="px-3 pt-2 pb-1">
                <h3 className="font-heading text-xl">Settings</h3>
                <p className="text-[10px] text-muted-foreground">
                  {sessionId ? "Simulated device · plan settings" : "Run a plan to load simulated device"}
                </p>
              </div>
              <div className="mx-2 divide-y divide-border overflow-hidden rounded-xl bg-card ring-1 ring-foreground/5">
                {settings.length ? (
                  settings.map((s) => (
                    <div key={s.uri} className="flex items-center justify-between gap-2 px-2.5 py-1.5 text-[11px]">
                      <span className="truncate">{s.label}</span>
                      <ValueControl value={s.value} kind="open" />
                    </div>
                  ))
                ) : (
                  <div className="px-3 py-3 text-center text-[11px] text-muted-foreground">
                    {sessionId ? "No checkable settings." : "No plan loaded yet."}
                  </div>
                )}
              </div>
              <p className="mt-auto px-3 pb-2 text-[9.5px] leading-3 text-muted-foreground">
                Mock on-device agent verifying <span className="font-mono">val/</span> deeplinks.
              </p>
            </div>
          )}
          <div className="mx-auto mb-1 h-0.5 w-16 rounded-full bg-foreground/20" />
        </div>
      </div>
    </div>
  );
}

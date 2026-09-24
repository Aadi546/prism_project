"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";

import { ThemeToggle } from "@/components/theme-toggle";
import { getHealth } from "@/lib/api";
import type { Health } from "@/lib/types";

const LINKS = [
  { href: "/", label: "Troubleshoot" },
  { href: "/batch", label: "Batch run" },
  { href: "/metrics", label: "Metrics" },
  { href: "/about", label: "Gaps & innovation" },
];

export function SiteNav() {
  const path = usePathname();
  const [health, setHealth] = useState<Health | null | false>(null);

  useEffect(() => {
    getHealth()
      .then(setHealth)
      .catch(() => setHealth(false));
  }, []);

  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur">
      <div className="mx-auto flex max-w-7xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="flex items-baseline gap-2">
          <span className="font-heading text-lg font-semibold tracking-tight">Smart Guided Troubleshooting</span>
          <span className="hidden text-xs text-muted-foreground sm:inline">Theme 2 · v2</span>
        </Link>
        <nav className="-mx-1 flex flex-1 gap-1 overflow-x-auto text-sm [scrollbar-width:none]">
          {LINKS.map((l) => {
            const active = l.href === "/" ? path === "/" : path.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                className={`rounded-md px-2.5 py-1.5 whitespace-nowrap transition-colors ${
                  active ? "bg-secondary font-medium text-foreground" : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <div
          className="flex items-center gap-2 rounded-full border border-border bg-card px-3 py-1 text-xs"
          title={health ? `${health.catalog} deeplinks · ${health.siis_articles} SIIS articles · ${health.cache_entries} cached plans` : ""}
        >
          <span
            className={`size-2 rounded-full ${health ? "bg-ok" : health === false ? "bg-destructive" : "bg-muted-foreground"}`}
          />
          {health === null ? "Connecting…" : health ? health.model : "Engine offline"}
        </div>
        <ThemeToggle />
      </div>
    </header>
  );
}

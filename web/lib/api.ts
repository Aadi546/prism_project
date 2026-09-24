import type {
  Health,
  SiisArticle,
  SimSnapshot,
  TroubleshootResponse,
  ValidationDeeplink,
  VerifyResult,
} from "@/lib/types";

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    throw new Error(`Engine returned ${res.status}`);
  }
  return (await res.json()) as T;
}

export async function getHealth(): Promise<Health> {
  return json(await fetch("/health", { cache: "no-store" }));
}

export async function troubleshoot(query: string, siis: unknown, trace = true): Promise<TroubleshootResponse> {
  return json(
    await fetch(`/v1/troubleshoot${trace ? "?trace=1" : ""}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query, siis_response: siis ?? null }),
    }),
  );
}

export async function getSiis(): Promise<SiisArticle[]> {
  const body = await json<{ articles: SiisArticle[] }>(await fetch("/v1/siis"));
  return body.articles;
}

export async function simStart(response: TroubleshootResponse["response"], seed = 7): Promise<SimSnapshot> {
  return json(
    await fetch("/v1/sim/start", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ response, seed }),
    }),
  );
}

export async function simTap(session: string, deeplink: string, validation: ValidationDeeplink | null) {
  return json<{ screen: string; row: Record<string, string> | null; state: Record<string, string> }>(
    await fetch("/v1/sim/tap", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, deeplink, validation }),
    }),
  );
}

export async function simVerify(session: string, validationDeeplink: ValidationDeeplink): Promise<VerifyResult> {
  return json(
    await fetch("/v1/verify", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session, validationDeeplink }),
    }),
  );
}

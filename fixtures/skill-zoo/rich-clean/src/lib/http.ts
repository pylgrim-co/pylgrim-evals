// All outbound HTTP goes through here (CLAUDE.md rule 8): 5s timeout, no exceptions.
const TIMEOUT_MS = 5000;

export async function httpGet(url: string): Promise<Response> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    return await fetch(url, { signal: controller.signal });
  } finally {
    clearTimeout(timer);
  }
}

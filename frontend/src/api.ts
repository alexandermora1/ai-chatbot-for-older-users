// Calls to the backend. Nothing is stored in the browser.

export interface Source {
  title: string;
  url: string;
}

export interface Answer {
  found: boolean;
  intro: string;
  steps: string[];
  closing: string;
  sources: Source[];
}

export interface Suggestions {
  suggestions: string[];
  reminder: string;
}

const TIMEOUT_MS = 60_000;

export class ApiError extends Error {}

export async function fetchSuggestions(): Promise<Suggestions> {
  const response = await fetch("/api/suggestions");
  if (!response.ok) throw new ApiError("Kunne ikke hente forslag.");
  return response.json();
}

export async function ask(question: string): Promise<Answer> {
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question }),
      signal: controller.signal,
    });
    if (!response.ok) {
      const body = await response.json().catch(() => null);
      const detail = typeof body?.detail === "string" ? body.detail : "";
      throw new ApiError(detail || "Noe gikk galt. Prøv igjen om litt.");
    }
    return await response.json();
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new ApiError("Jeg fikk ikke kontakt med hjelperen. Sjekk at den er startet, og prøv igjen.");
  } finally {
    window.clearTimeout(timer);
  }
}

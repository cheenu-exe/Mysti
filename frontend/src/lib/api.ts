const BASE = (process.env.NEXT_PUBLIC_MYSTI_API_URL || process.env.MYSTI_API_URL || "http://127.0.0.1:8000").replace(/\/$/, "");
export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(`${BASE}${path}`, { ...options, headers: { "Content-Type": "application/json", ...(options.headers || {}) } });
  if (!response.ok) throw new Error(`${response.status}: ${await response.text()}`);
  return response.json();
}
export const fetchStatus = () => api<{ status: string; storage: string; encryption: boolean }>("/status");
export const searchMemories = (query: string, category?: string) => api<{ results: any[] }>("/memory/search", { method: "POST", body: JSON.stringify({ query, category, limit: 20 }) });
export const storeMemory = (category: string, content: string) => api<{ id: string }>("/memory/store", { method: "POST", body: JSON.stringify({ category, content }) });
export const sendMessage = (sessionId: string, content: string) => api<{ response: string }>(`/conversation/${sessionId}/message`, { method: "POST", body: JSON.stringify({ content }) });
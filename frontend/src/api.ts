/**
 * 백엔드 API 클라이언트
 */
const BASE = import.meta.env.VITE_API_URL || "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

async function post<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}`);
  return res.json();
}

// ========== Types ==========

export interface DashboardData {
  post_stats: PostStats;
  vectordb_stats: { events: number; tasks: number; posts: number };
  recent_posts: PostSummary[];
}

export interface PostStats {
  total_posts: number;
  total_files: number;
  by_year: Record<string, number>;
  by_author: Record<string, number>;
  year_range: string;
}

export interface PostSummary {
  id: string;
  title: string;
  author: string;
  date: string;
  views?: number;
  files_count?: number;
}

export interface PostDetail extends PostSummary {
  content: string;
  url: string;
  files: { name: string; url: string; size: string; local_path: string }[];
}

export interface SearchResult extends PostSummary {
  content_preview: string;
  relevance: number;
}

export interface FileInfo {
  post_id: string;
  post_title: string;
  file_name: string;
  file_size: string;
  local_path: string;
  date: string;
}

export interface ChatResponse {
  response: string;
  status: string;
}

export interface NotionNode {
  id: string;
  title: string;
  children: NotionNode[];
  has_children?: boolean;
}

export interface NotionTree {
  public: NotionNode;
  admin: NotionNode;
}

export interface MinutesResult {
  full_text: string;
  summary: string;
  action_items: string;
  action_items_list: string[];
  transcript: string;
  notion_saved: boolean;
  notion_checklist_saved: boolean;
}

export interface VectorDocument {
  id: string;
  title: string;
  author?: string;
  date?: string;
  url?: string;
  type?: string;
  has_files?: string;
  score?: number;
}

export interface VectorDocumentsResult {
  count: number;
  total?: number;
  query?: string;
  documents: VectorDocument[];
}

export interface SttStreamHandlers {
  onStatus?: (phase: string, message: string) => void;
  onTranscript?: (transcript: string) => void;
  onChunk?: (text: string) => void;
  onDone?: (data: {
    summary: string;
    action_items: string;
    action_items_list: string[];
    notion_saved: boolean;
    notion_checklist_saved: boolean;
  }) => void;
  onError?: (message: string) => void;
}

export interface ChatStreamHandlers {
  onStatus?: (message: string) => void;
  onToken?: (text: string) => void;
  onPerf?: (data: Record<string, unknown>) => void;
  onDone?: () => void;
  onError?: (message: string) => void;
}

export interface FileAnalysisResult {
  filename: string;
  extracted_length?: number;
  extracted_preview?: string;
  analysis?: string;
  error?: string;
}

// ========== API ==========

export const api = {
  // Dashboard
  dashboard: () => get<DashboardData>("/dashboard"),
  stats: () => get<PostStats>("/stats"),
  health: () => get<{ status: string; connections: Record<string, unknown> }>("/health"),

  // Posts
  posts: (params?: { year?: number; author?: string; keyword?: string; limit?: number }) => {
    const q = new URLSearchParams();
    if (params?.year) q.set("year", String(params.year));
    if (params?.author) q.set("author", params.author);
    if (params?.keyword) q.set("keyword", params.keyword);
    if (params?.limit) q.set("limit", String(params.limit));
    const qs = q.toString();
    return get<PostSummary[]>(`/posts${qs ? `?${qs}` : ""}`);
  },
  post: (id: string) => get<PostDetail>(`/posts/${id}`),
  search: (query: string, limit = 5) =>
    get<SearchResult[]>(`/posts/search/${encodeURIComponent(query)}?limit=${limit}`),

  // Files
  files: (params?: { keyword?: string; year?: number }) => {
    const q = new URLSearchParams();
    if (params?.keyword) q.set("keyword", params.keyword);
    if (params?.year) q.set("year", String(params.year));
    const qs = q.toString();
    return get<FileInfo[]>(`/files${qs ? `?${qs}` : ""}`);
  },

  // Chat
  chat: (message: string, session_id = "web", file_context?: string) =>
    post<ChatResponse>("/chat", { message, session_id, file_context: file_context || null }),
  resetChat: (session_id = "web") =>
    post<{ status: string }>("/chat/reset", { session_id }),

  chatStream: (message: string, session_id = "web", file_context?: string): {
    start: (handlers: ChatStreamHandlers) => AbortController;
  } => {
    return {
      start(handlers: ChatStreamHandlers) {
        const controller = new AbortController();
        fetch(`${BASE}/chat/stream`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ message, session_id, file_context: file_context || null }),
          signal: controller.signal,
        })
          .then(async (res) => {
            if (!res.ok) {
              handlers.onError?.(`스트림 실패: ${res.status}`);
              return;
            }
            const reader = res.body?.getReader();
            if (!reader) return;
            const decoder = new TextDecoder();
            let buf = "";
            let eventType = "";

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              buf += decoder.decode(value, { stream: true });

              const lines = buf.split("\n");
              buf = lines.pop() || "";

              for (const line of lines) {
                if (line.startsWith("event: ")) {
                  eventType = line.slice(7).trim();
                } else if (line.startsWith("data: ")) {
                  const data = line.slice(6);
                  try {
                    const parsed = data ? JSON.parse(data) : {};
                    if (eventType === "token") handlers.onToken?.(String(parsed.content || ""));
                    else if (eventType === "status") handlers.onStatus?.(String(parsed.message || ""));
                    else if (eventType === "perf") handlers.onPerf?.(parsed);
                    else if (eventType === "done") handlers.onDone?.();
                    else if (eventType === "error") handlers.onError?.(String(parsed.message || "오류"));
                  } catch { /* skip malformed */ }
                  eventType = "";
                }
              }
            }
          })
          .catch((e) => {
            if (e?.name === "AbortError") return;
            handlers.onError?.(String(e));
          });
        return controller;
      },
    };
  },

  // Notion
  notionTree: (force = false) => get<NotionTree>(`/notion/tree${force ? "?force=true" : ""}`),
  notionChildren: (pageId: string) => get<NotionNode[]>(`/notion/children/${pageId}`),

  // VectorDB Documents
  vectorDocuments: (query?: string, limit = 50) => {
    const q = new URLSearchParams();
    if (query) q.set("query", query);
    q.set("limit", String(limit));
    return get<VectorDocumentsResult>(`/vectordb/documents?${q.toString()}`);
  },
  vectordbStatus: () => get<Record<string, unknown>>("/vectordb/status"),

  // File Analysis
  analyzeFile: async (file: File, query = ""): Promise<FileAnalysisResult> => {
    const form = new FormData();
    form.append("file", file);
    if (query) form.append("query", query);
    const res = await fetch(`${BASE}/files/analyze`, { method: "POST", body: form });
    if (!res.ok) throw new Error(`분석 실패: ${res.status}`);
    return res.json();
  },

  // STT (SSE streaming)
  sttMinutesStream: (file: File): { start: (handlers: SttStreamHandlers) => AbortController } => {
    return {
      start(handlers: SttStreamHandlers) {
        const controller = new AbortController();
        const form = new FormData();
        form.append("file", file);

        fetch(`${BASE}/stt/minutes`, { method: "POST", body: form, signal: controller.signal })
          .then(async (res) => {
            if (!res.ok) {
              handlers.onError?.(`STT 실패: ${res.status}`);
              return;
            }
            const reader = res.body?.getReader();
            if (!reader) return;
            const decoder = new TextDecoder();
            let buf = "";

            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              buf += decoder.decode(value, { stream: true });

              const lines = buf.split("\n");
              buf = lines.pop() || "";

              let eventType = "";
              for (const line of lines) {
                if (line.startsWith("event: ")) {
                  eventType = line.slice(7).trim();
                } else if (line.startsWith("data: ")) {
                  const data = line.slice(6);
                  try {
                    const parsed = JSON.parse(data);
                    if (eventType === "status") handlers.onStatus?.(parsed.phase, parsed.message);
                    else if (eventType === "transcript") handlers.onTranscript?.(parsed.transcript);
                    else if (eventType === "chunk") handlers.onChunk?.(parsed.text);
                    else if (eventType === "done") handlers.onDone?.(parsed);
                    else if (eventType === "error") handlers.onError?.(parsed.message);
                  } catch { /* skip malformed */ }
                  eventType = "";
                }
              }
            }
          })
          .catch((e) => {
            if (e.name !== "AbortError") handlers.onError?.(String(e));
          });

        return controller;
      },
    };
  },

  // Upload
  upload: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    const res = await fetch(`${BASE}/upload`, { method: "POST", body: form });
    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: "업로드 실패" }));
      throw new Error(err.detail || `API ${res.status}`);
    }
    return res.json() as Promise<{ filename: string; size: number; type: string; extracted_text: string }>;
  },
};

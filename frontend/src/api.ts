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

// ========== 대시보드 ==========

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

// ========== API ==========

export const api = {
  dashboard: () => get<DashboardData>("/dashboard"),
  stats: () => get<PostStats>("/stats"),
  health: () => get<{ status: string; connections: Record<string, unknown> }>("/health"),

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

  files: (params?: { keyword?: string; year?: number }) => {
    const q = new URLSearchParams();
    if (params?.keyword) q.set("keyword", params.keyword);
    if (params?.year) q.set("year", String(params.year));
    const qs = q.toString();
    return get<FileInfo[]>(`/files${qs ? `?${qs}` : ""}`);
  },

  chat: (message: string, session_id = "web") =>
    post<ChatResponse>("/chat", { message, session_id }),

  resetChat: (session_id = "web") =>
    post<{ status: string }>("/chat/reset", { session_id }),
};

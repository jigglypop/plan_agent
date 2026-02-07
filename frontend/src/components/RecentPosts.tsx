import { FileText } from "lucide-react";
import type { PostSummary } from "../api";

interface RecentPostsProps {
  posts: PostSummary[];
}

export function RecentPosts({ posts }: RecentPostsProps) {
  const display = posts.slice(0, 8);

  return (
    <div className="glass-dark p-5">
      <div className="flex items-center justify-between mb-4">
        <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">최근 게시글</span>
        <FileText size={16} className="text-slate-500" />
      </div>
      <div className="space-y-1">
        {display.length === 0 ? (
          <div className="text-center py-8 text-slate-500 text-sm">게시글이 없습니다</div>
        ) : (
          display.map((p) => (
            <div
              key={p.id}
              className="px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors"
            >
              <div className="text-sm font-medium text-slate-200 truncate">{p.title}</div>
              <div className="text-xs text-slate-500 mt-0.5">
                {p.author} {p.date && `| ${p.date}`}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

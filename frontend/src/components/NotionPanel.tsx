import { useState, useEffect, useCallback } from "react";
import {
  ChevronRight, ChevronDown, FileText, FolderOpen, Folder,
  RefreshCw, Loader2, Database, X, ExternalLink,
} from "lucide-react";
import { api } from "../api";
import type { NotionNode } from "../api";

interface NotionPanelProps {
  selectedPageId: string;
  onSelectPage: (pageId: string, title: string, target: "public" | "admin") => void;
  onClose?: () => void;
}

function notionUrl(pageId: string): string {
  return `https://www.notion.so/${pageId.replace(/-/g, "")}`;
}

function TreeNode({
  node,
  depth,
  selectedId,
  target,
  onSelect,
}: {
  node: NotionNode;
  depth: number;
  selectedId: string;
  target: "public" | "admin";
  onSelect: (id: string, title: string, target: "public" | "admin") => void;
}) {
  const [open, setOpen] = useState(depth < 1);
  const [children, setChildren] = useState<NotionNode[]>(node.children);
  const [loadingChildren, setLoadingChildren] = useState(false);
  const hasChildren = children.length > 0 || node.has_children;
  const isDB = node.title.startsWith("[DB]");
  const isSelected = node.id === selectedId;

  const handleClick = async () => {
    onSelect(node.id, node.title, target);
    if (!hasChildren) return;

    if (!open && node.has_children && children.length === 0) {
      setLoadingChildren(true);
      try {
        const fetched = await api.notionChildren(node.id);
        setChildren(fetched);
      } catch { /* */ }
      setLoadingChildren(false);
    }
    setOpen(!open);
  };

  return (
    <div>
      <div
        className={`group flex items-center gap-0.5 rounded-md transition-colors ${
          isSelected
            ? "bg-blue-500/20 text-blue-300"
            : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
        }`}
        style={{ paddingLeft: `${depth * 14 + 4}px` }}
      >
        <button
          onClick={handleClick}
          className="flex-1 flex items-center gap-1.5 px-1 py-1.5 text-left text-xs min-w-0"
        >
          {hasChildren ? (
            loadingChildren ? (
              <Loader2 size={12} className="shrink-0 animate-spin" />
            ) : open ? (
              <ChevronDown size={12} className="shrink-0" />
            ) : (
              <ChevronRight size={12} className="shrink-0" />
            )
          ) : (
            <span className="w-3 shrink-0" />
          )}
          {isDB ? (
            <Database size={13} className="shrink-0 text-purple-400" />
          ) : hasChildren ? (
            open ? <FolderOpen size={13} className="shrink-0 text-amber-400" /> : <Folder size={13} className="shrink-0 text-amber-400" />
          ) : (
            <FileText size={13} className="shrink-0 text-slate-500" />
          )}
          <span className="truncate">{isDB ? node.title.replace("[DB] ", "") : node.title}</span>
        </button>
        {/* Notion 링크 */}
        <a
          href={notionUrl(node.id)}
          target="_blank"
          rel="noopener noreferrer"
          onClick={(e) => e.stopPropagation()}
          className="p-1 opacity-0 group-hover:opacity-100 text-slate-600 hover:text-blue-400 transition-all shrink-0"
          title="노션에서 열기"
        >
          <ExternalLink size={11} />
        </a>
      </div>
      {open && children.length > 0 && (
        <div>
          {children.map((child) => (
            <TreeNode
              key={child.id}
              node={child}
              depth={depth + 1}
              selectedId={selectedId}
              target={target}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}

let _cachedTree: { public: NotionNode; admin: NotionNode } | null = null;

export function NotionPanel({ selectedPageId, onSelectPage, onClose }: NotionPanelProps) {
  const [tree, setTree] = useState<{ public: NotionNode; admin: NotionNode } | null>(_cachedTree);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchTree = useCallback(async (force = false) => {
    setLoading(true);
    setError("");
    try {
      const data = await api.notionTree(force);
      setTree(data);
      _cachedTree = data;
    } catch {
      setError("노션 연결 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!_cachedTree) fetchTree();
  }, [fetchTree]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-3 border-b border-white/5 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300">Notion</span>
        <div className="flex items-center gap-1">
          <button
            onClick={() => fetchTree(true)}
            disabled={loading}
            className="p-1 text-slate-500 hover:text-slate-300 rounded transition-colors disabled:opacity-30"
            title="새로고침"
          >
            <RefreshCw size={13} className={loading ? "animate-spin" : ""} />
          </button>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 text-slate-500 hover:text-slate-300 rounded transition-colors xl:hidden"
              title="닫기"
            >
              <X size={13} />
            </button>
          )}
        </div>
      </div>

      {/* 로딩 바 (초기 + 새로고침 공용) */}
      {loading && (
        <div className="relative h-0.5 w-full bg-white/5 overflow-hidden">
          <div className="absolute inset-y-0 w-1/3 bg-blue-500 rounded-full animate-slide" />
        </div>
      )}

      <div className="flex-1 overflow-y-auto px-1 py-2">
        {/* 초기 로딩 (트리 없을 때) */}
        {loading && !tree && (
          <div className="flex flex-col items-center justify-center gap-3 py-16">
            <Loader2 size={28} className="text-blue-400 animate-spin" />
            <span className="text-xs text-slate-400">노션 동기화 중...</span>
          </div>
        )}

        {error && <div className="px-3 py-6 text-center text-xs text-red-400">{error}</div>}

        {tree && (
          <>
            <div className="mb-3">
              <div className="px-3 py-1 text-xs font-semibold text-blue-400 uppercase tracking-wider">
                운영진
              </div>
              <TreeNode
                node={tree.admin}
                depth={0}
                selectedId={selectedPageId}
                target="admin"
                onSelect={onSelectPage}
              />
            </div>
            <div>
              <div className="px-3 py-1 text-xs font-semibold text-green-400 uppercase tracking-wider">
                공개
              </div>
              <TreeNode
                node={tree.public}
                depth={0}
                selectedId={selectedPageId}
                target="public"
                onSelect={onSelectPage}
              />
            </div>
          </>
        )}
      </div>

      {selectedPageId && (
        <div className="px-3 py-2 border-t border-white/5">
          <div className="text-xs text-slate-500">선택된 위치에 페이지가 생성됩니다</div>
        </div>
      )}
    </div>
  );
}

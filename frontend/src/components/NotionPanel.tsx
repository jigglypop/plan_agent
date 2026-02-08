import { useState, useEffect, useCallback } from "react";
import { ChevronRight, ChevronDown, FileText, FolderOpen, Folder, RefreshCw, Loader2, Database } from "lucide-react";
import { api } from "../api";
import type { NotionNode } from "../api";

interface NotionPanelProps {
  selectedPageId: string;
  onSelectPage: (pageId: string, title: string, target: "public" | "admin") => void;
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
  const hasChildren = node.children.length > 0;
  const isDB = node.title.startsWith("[DB]");
  const isSelected = node.id === selectedId;

  return (
    <div>
      <button
        onClick={() => {
          if (hasChildren) setOpen(!open);
          onSelect(node.id, node.title, target);
        }}
        className={`w-full flex items-center gap-1.5 px-2 py-1.5 rounded-md text-left text-xs transition-colors ${
          isSelected
            ? "bg-blue-500/20 text-blue-300"
            : "text-slate-400 hover:text-slate-200 hover:bg-white/5"
        }`}
        style={{ paddingLeft: `${depth * 16 + 8}px` }}
      >
        {hasChildren ? (
          open ? <ChevronDown size={12} className="shrink-0" /> : <ChevronRight size={12} className="shrink-0" />
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
      {open && hasChildren && (
        <div>
          {node.children.map((child) => (
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

export function NotionPanel({ selectedPageId, onSelectPage }: NotionPanelProps) {
  const [tree, setTree] = useState<{ public: NotionNode; admin: NotionNode } | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  const fetchTree = useCallback(async () => {
    setLoading(true);
    setError("");
    try {
      const data = await api.notionTree();
      setTree(data);
    } catch {
      setError("노션 연결 실패");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchTree();
  }, [fetchTree]);

  return (
    <div className="h-full flex flex-col">
      <div className="px-3 py-3 border-b border-white/5 flex items-center justify-between">
        <span className="text-xs font-semibold text-slate-300">Notion</span>
        <button
          onClick={fetchTree}
          disabled={loading}
          className="p-1 text-slate-500 hover:text-slate-300 rounded transition-colors disabled:opacity-30"
          title="새로고침"
        >
          {loading ? <Loader2 size={13} style={{ animation: "spin 1s linear infinite" }} /> : <RefreshCw size={13} />}
        </button>
      </div>

      <div className="flex-1 overflow-y-auto px-1 py-2">
        {error && <div className="px-3 text-xs text-red-400">{error}</div>}

        {tree && (
          <>
            {/* Admin */}
            <div className="mb-3">
              <div className="px-3 py-1 text-[10px] font-semibold text-blue-400 uppercase tracking-wider">
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

            {/* Public */}
            <div>
              <div className="px-3 py-1 text-[10px] font-semibold text-green-400 uppercase tracking-wider">
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

        {!tree && !loading && !error && (
          <div className="px-3 text-xs text-slate-600">노션 트리 로딩 중...</div>
        )}
      </div>

      {selectedPageId && (
        <div className="px-3 py-2 border-t border-white/5">
          <div className="text-[10px] text-slate-500">선택된 위치에 페이지가 생성됩니다</div>
        </div>
      )}
    </div>
  );
}

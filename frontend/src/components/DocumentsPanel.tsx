import { useState, useEffect, useRef } from "react";
import {
  Search,
  FileText,
  Upload,
  Loader2,
  Database,
  FileSpreadsheet,
  Calendar,
  User,
  ExternalLink,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { VectorDocument, FileAnalysisResult } from "../api";
import { api } from "../api";

type SubTab = "indexed" | "analyze";

export function DocumentsPanel() {
  const [subTab, setSubTab] = useState<SubTab>("indexed");

  return (
    <div className="flex-1 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="px-4 sm:px-8 pt-5 pb-3">
        <div className="flex items-center gap-2 mb-3">
          <Database size={20} className="text-blue-400" />
          <h2 className="text-lg font-bold text-white">문서 관리</h2>
        </div>
        <div className="flex gap-1 border-b border-white/5">
          <button
            onClick={() => setSubTab("indexed")}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              subTab === "indexed"
                ? "text-white border-b-2 border-blue-500"
                : "text-slate-400 hover:text-white"
            }`}
          >
            벡터 인덱스
          </button>
          <button
            onClick={() => setSubTab("analyze")}
            className={`px-4 py-2 text-xs font-medium transition-colors ${
              subTab === "analyze"
                ? "text-white border-b-2 border-violet-500"
                : "text-slate-400 hover:text-white"
            }`}
          >
            파일 분석
          </button>
        </div>
      </div>

      {subTab === "indexed" && <IndexedDocuments />}
      {subTab === "analyze" && <FileAnalyzer />}
    </div>
  );
}

function IndexedDocuments() {
  const [docs, setDocs] = useState<VectorDocument[]>([]);
  const [total, setTotal] = useState(0);
  const [query, setQuery] = useState("");
  const [searchInput, setSearchInput] = useState("");
  const [loading, setLoading] = useState(true);

  const fetch = async (q = "") => {
    setLoading(true);
    try {
      const res = await api.vectorDocuments(q || undefined, 50);
      setDocs(res.documents);
      setTotal(res.total ?? res.count);
      setQuery(q);
    } catch {
      /* */
    }
    setLoading(false);
  };

  useEffect(() => {
    fetch();
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    fetch(searchInput);
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-8 pb-6">
      {/* Search */}
      <form onSubmit={handleSearch} className="flex gap-2 my-4">
        <div className="relative flex-1">
          <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500" />
          <input
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="문서 시맨틱 검색 (예: 겨울행사 예산)"
            className="w-full pl-9 pr-3 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-blue-500/50"
          />
        </div>
        <button
          type="submit"
          className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white text-xs rounded-xl transition-colors"
        >
          검색
        </button>
        {query && (
          <button
            type="button"
            onClick={() => { setSearchInput(""); fetch(); }}
            className="px-3 py-2 text-xs text-slate-400 hover:text-white transition-colors"
          >
            초기화
          </button>
        )}
      </form>

      {/* Stats */}
      <div className="flex items-center gap-3 mb-4 text-xs text-slate-500">
        <span>총 {total}건 인덱싱</span>
        {query && <span className="text-blue-400">검색: &quot;{query}&quot; ({docs.length}건)</span>}
      </div>

      {loading ? (
        <div className="py-16 text-center text-slate-500 text-sm">
          <Loader2 size={20} className="inline-block mb-2" style={{ animation: "spin 1s linear infinite" }} />
          <div>로딩 중...</div>
        </div>
      ) : docs.length === 0 ? (
        <div className="py-16 text-center text-slate-500 text-sm">
          {query ? "검색 결과가 없습니다." : "인덱싱된 문서가 없습니다."}
        </div>
      ) : (
        <div className="space-y-2">
          {docs.map((doc) => (
            <div
              key={doc.id}
              className="glass-dark p-4 hover:border-white/20 transition-colors"
            >
              <div className="flex items-start gap-3">
                <FileText size={16} className="mt-0.5 text-blue-400 shrink-0" />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-white font-medium truncate">{doc.title}</span>
                    {doc.score !== undefined && (
                      <span className="text-xs px-1.5 py-0.5 bg-blue-500/20 text-blue-300 rounded">
                        {(doc.score * 100).toFixed(0)}%
                      </span>
                    )}
                    {doc.has_files === "yes" && (
                      <span title="첨부파일 포함"><FileSpreadsheet size={12} className="text-emerald-400" /></span>
                    )}
                  </div>
                  <div className="flex items-center gap-3 mt-1 text-xs text-slate-500">
                    {doc.date && (
                      <span className="flex items-center gap-1">
                        <Calendar size={10} /> {doc.date}
                      </span>
                    )}
                    {doc.author && (
                      <span className="flex items-center gap-1">
                        <User size={10} /> {doc.author}
                      </span>
                    )}
                    {doc.url && (
                      <a
                        href={doc.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-blue-400 hover:text-blue-300"
                      >
                        <ExternalLink size={10} /> 원본
                      </a>
                    )}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function FileAnalyzer() {
  const [file, setFile] = useState<File | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<FileAnalysisResult | null>(null);
  const [error, setError] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);

  const submit = async () => {
    if (!file) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await api.analyzeFile(file, query);
      if (res.error && !res.analysis) {
        setError(res.error);
      } else {
        setResult(res);
      }
    } catch (e) {
      setError(String(e));
    }
    setLoading(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (f) { setFile(f); setResult(null); setError(""); }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  return (
    <div className="flex-1 overflow-y-auto px-4 sm:px-8 pb-6">
      <div className="max-w-3xl mx-auto space-y-4 mt-4">
        <p className="text-xs text-slate-500">
          Excel, PDF, PPT, DOCX 파일을 업로드하면 AI가 내용을 분석합니다. 견적서 비교, 예산안 해석, 문서 요약 등.
        </p>

        {/* Upload */}
        <div
          onDrop={handleDrop}
          onDragOver={(e) => e.preventDefault()}
          onClick={() => inputRef.current?.click()}
          className="glass-dark p-8 flex flex-col items-center justify-center gap-3 cursor-pointer hover:border-violet-500/30 transition-colors"
        >
          <input
            ref={inputRef}
            type="file"
            accept=".xlsx,.xls,.pdf,.pptx,.docx,.txt,.csv"
            onChange={(e) => { const f = e.target.files?.[0]; if (f) { setFile(f); setResult(null); setError(""); } }}
            className="hidden"
          />
          {file ? (
            <>
              <FileSpreadsheet size={32} className="text-violet-400" />
              <p className="text-sm text-white">{file.name}</p>
              <p className="text-xs text-slate-500">{formatSize(file.size)}</p>
            </>
          ) : (
            <>
              <Upload size={32} className="text-slate-500" />
              <p className="text-sm text-slate-400">파일을 드래그하거나 클릭하여 선택</p>
              <p className="text-xs text-slate-600">XLSX, PDF, PPTX, DOCX, TXT, CSV (최대 10MB)</p>
            </>
          )}
        </div>

        {file && (
          <>
            <input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="분석 질문 (비워두면 전체 요약) - 예: 총 예산 금액, 항목별 비교"
              className="w-full px-4 py-2.5 bg-white/5 border border-white/10 rounded-xl text-sm text-white placeholder-slate-500 focus:outline-none focus:border-violet-500/50"
            />
            <button
              onClick={submit}
              disabled={loading}
              className="w-full py-3 bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/50 text-white text-sm rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              {loading ? (
                <>
                  <Loader2 size={16} style={{ animation: "spin 1s linear infinite" }} />
                  분석 중...
                </>
              ) : (
                <>
                  <FileText size={16} />
                  AI 분석
                </>
              )}
            </button>
          </>
        )}

        {error && (
          <div className="glass-dark p-4 border-red-500/30 text-red-300 text-sm">{error}</div>
        )}

        {result && (
          <div className="space-y-4">
            {result.analysis && (
              <div className="glass-dark p-5">
                <h3 className="text-sm font-semibold text-white mb-3">분석 결과</h3>
                <div className="prose prose-invert prose-sm max-w-none prose-headings:my-3 prose-p:my-2 prose-li:my-0.5">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{result.analysis}</ReactMarkdown>
                </div>
              </div>
            )}

            {result.extracted_preview && (
              <details className="glass-dark p-4">
                <summary className="text-xs text-slate-400 cursor-pointer hover:text-white">
                  원본 추출 텍스트 (총 {result.extracted_length?.toLocaleString()}자)
                </summary>
                <pre className="mt-3 text-xs text-slate-500 whitespace-pre-wrap max-h-60 overflow-y-auto">
                  {result.extracted_preview}
                </pre>
              </details>
            )}

            <button
              onClick={() => { setFile(null); setResult(null); setQuery(""); }}
              className="text-xs text-slate-400 hover:text-white transition-colors"
            >
              다른 파일 분석
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

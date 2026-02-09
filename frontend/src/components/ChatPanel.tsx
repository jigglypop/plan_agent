import { useState, useRef, useEffect, useCallback } from "react";
import {
  Send, Bot, Loader2, RotateCcw, Paperclip,
  Copy, Check, Download, X, FileText, Image as ImageIcon, Globe,
} from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface AttachedFile {
  file: File;
  name: string;
  type: "image" | "document";
  preview?: string;
  extractedText?: string;
  uploading: boolean;
  error?: string;
}

interface ChatPanelProps {
  notionTarget: "admin" | "public";
  notionPageId: string;
  notionPageTitle: string;
}

export function ChatPanel({ notionTarget, notionPageId, notionPageTitle }: ChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [webSearch, setWebSearch] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const copyMessage = useCallback(async (text: string, idx: number) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopiedIdx(idx);
      setTimeout(() => setCopiedIdx(null), 1500);
    } catch { /* */ }
  }, []);

  const handleFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (!files) return;

    for (const file of Array.from(files)) {
      const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
      const imgExts = [".png", ".jpg", ".jpeg", ".gif", ".webp"];
      const docExts = [".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".txt", ".csv"];
      const isImage = imgExts.includes(ext);
      const isDoc = docExts.includes(ext);

      if (!isImage && !isDoc) {
        setAttachedFiles((prev) => [...prev, {
          file, name: file.name, type: "document", uploading: false,
          error: "지원하지 않는 형식",
        }]);
        continue;
      }

      const attached: AttachedFile = {
        file, name: file.name,
        type: isImage ? "image" : "document",
        preview: isImage ? URL.createObjectURL(file) : undefined,
        uploading: true,
      };
      setAttachedFiles((prev) => [...prev, attached]);

      try {
        const result = await api.upload(file);
        setAttachedFiles((prev) =>
          prev.map((f) =>
            f.file === file ? { ...f, uploading: false, extractedText: result.extracted_text } : f
          )
        );
      } catch (err) {
        setAttachedFiles((prev) =>
          prev.map((f) =>
            f.file === file ? { ...f, uploading: false, error: String(err) } : f
          )
        );
      }
    }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const removeFile = (idx: number) => {
    setAttachedFiles((prev) => {
      const f = prev[idx];
      if (f?.preview) URL.revokeObjectURL(f.preview);
      return prev.filter((_, i) => i !== idx);
    });
  };

  const sendMessage = async () => {
    if ((!input.trim() && attachedFiles.length === 0) || isLoading) return;
    if (attachedFiles.some((f) => f.uploading)) return;

    const userMessage = input.trim();
    const fileContext = attachedFiles
      .filter((f) => f.extractedText)
      .map((f) => `[${f.name}]\n${f.extractedText}`)
      .join("\n\n");
    const fileNames = attachedFiles.map((f) => f.name);

    let displayContent = userMessage;
    if (fileNames.length > 0) {
      const fileList = fileNames.map((n) => `[${n}]`).join(" ");
      displayContent = displayContent ? `${fileList}\n${displayContent}` : fileList;
    }

    setInput("");
    setAttachedFiles([]);
    if (textareaRef.current) textareaRef.current.style.height = "auto";
    setMessages((prev) => [...prev, { role: "user", content: displayContent }]);
    setIsLoading(true);

    try {
      let prefix = `[notion_target=${notionTarget}]`;
      if (notionPageId) prefix += `[notion_page_id=${notionPageId}]`;
      if (webSearch) prefix += `[web_search=enabled]`;
      prefix += " ";
      const fullMessage = prefix + (userMessage || "첨부한 파일을 분석해주세요.");
      const data = await api.chat(fullMessage, "web", fileContext || undefined);
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "서버 연결에 실패했습니다." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const resetChat = async () => {
    try { await api.resetChat(); } catch { /* */ }
    setAttachedFiles([]);
    setMessages([]);
  };

  const downloadChat = () => {
    const text = messages
      .map((m) => `[${m.role === "user" ? "나" : "AI"}]\n${m.content}`)
      .join("\n\n---\n\n");
    const blob = new Blob([text], { type: "text/markdown;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `chat_${new Date().toISOString().slice(0, 10)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const targetLabel = notionPageId
    ? notionPageTitle
    : notionTarget === "admin" ? "운영진" : "공개";
  const targetColor = notionTarget === "admin" ? "blue" : "green";

  const isEmpty = messages.length === 0 && !isLoading;

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-6">
          {/* Empty state */}
          {isEmpty && (
            <div className="flex flex-col items-center justify-center py-16 sm:py-24 animate-fade-in">
              <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 flex items-center justify-center mb-5">
                <Bot size={28} className="text-blue-400" />
              </div>
              <h2 className="text-lg font-semibold text-white mb-1">염시코기 2세</h2>
              <p className="text-xs text-slate-500 mb-8">20년간의 게시판 데이터 기반 AI 에이전트</p>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 w-full max-w-lg">
                {[
                  "2024 겨울행사 예산 알려줘",
                  "글램핑 장소 견적 찾아줘",
                  "작년 회의록 보여줘",
                  "노션에 여름행사 등록해줘",
                ].map((q) => (
                  <button
                    key={q}
                    onClick={() => { setInput(q); textareaRef.current?.focus(); }}
                    className="text-left px-4 py-3 rounded-xl border border-white/8 bg-white/3 hover:bg-white/6 hover:border-white/15 text-xs text-slate-400 hover:text-slate-200 transition-all"
                  >
                    &ldquo;{q}&rdquo;
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages list */}
          {messages.map((msg, idx) => (
            <div key={idx} className={`group mb-6 ${msg.role === "user" ? "" : ""}`}>
              {/* User message */}
              {msg.role === "user" && (
                <div className="flex justify-end">
                  <div className="max-w-[85%] sm:max-w-[75%]">
                    <div className="bg-blue-600/90 text-white rounded-2xl rounded-br-md px-4 py-3 text-[14px] leading-relaxed whitespace-pre-wrap">
                      {msg.content}
                    </div>
                  </div>
                </div>
              )}

              {/* Assistant message */}
              {msg.role === "assistant" && (
                <div className="flex gap-3">
                  <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 flex items-center justify-center shrink-0 mt-0.5">
                    <Bot size={16} className="text-blue-400" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1.5">
                      <span className="text-xs font-medium text-slate-400">염시코기 2세</span>
                      <button
                        onClick={() => copyMessage(msg.content, idx)}
                        className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-600 hover:text-slate-300 p-0.5 rounded"
                        title="복사"
                      >
                        {copiedIdx === idx ? <Check size={12} className="text-emerald-400" /> : <Copy size={12} />}
                      </button>
                    </div>
                    <div className="text-[14px] text-slate-200 leading-7 prose prose-invert prose-sm max-w-none prose-p:my-2 prose-li:my-0.5 prose-ul:my-2 prose-ol:my-2 prose-headings:my-3 prose-headings:text-white prose-table:my-3 prose-th:px-3 prose-th:py-1.5 prose-td:px-3 prose-td:py-1.5 prose-th:border prose-th:border-white/10 prose-td:border prose-td:border-white/10 prose-a:text-blue-400 prose-code:text-emerald-300 prose-code:bg-white/5 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px] prose-pre:bg-white/5 prose-pre:border prose-pre:border-white/10 prose-blockquote:border-blue-500/40 prose-blockquote:text-slate-300">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}

          {/* Loading indicator */}
          {isLoading && (
            <div className="flex gap-3 mb-6">
              <div className="w-8 h-8 rounded-xl bg-gradient-to-br from-blue-500/20 to-violet-500/20 border border-white/10 flex items-center justify-center shrink-0">
                <Loader2 size={16} className="text-blue-400 animate-spin" />
              </div>
              <div className="flex-1">
                <span className="text-xs font-medium text-slate-400 block mb-2">염시코기 2세</span>
                <div className="flex items-center gap-1.5 py-2">
                  <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "0ms" }} />
                  <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "150ms" }} />
                  <span className="w-2 h-2 bg-slate-500 rounded-full animate-bounce" style={{ animationDelay: "300ms" }} />
                </div>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Attached files */}
      {attachedFiles.length > 0 && (
        <div className="max-w-3xl mx-auto w-full px-4 sm:px-6 pt-2 flex gap-2 flex-wrap">
          {attachedFiles.map((f, idx) => (
            <div
              key={idx}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border transition-colors ${
                f.error
                  ? "border-red-500/30 bg-red-500/10 text-red-300"
                  : "border-white/10 bg-white/5 text-slate-300"
              }`}
            >
              {f.type === "image" ? (
                f.preview ? (
                  <img src={f.preview} alt="" className="w-6 h-6 rounded object-cover" />
                ) : (
                  <ImageIcon size={14} />
                )
              ) : (
                <FileText size={14} />
              )}
              <span className="max-w-[120px] truncate">{f.name}</span>
              {f.uploading && <Loader2 size={12} className="animate-spin" />}
              {f.error && <span className="text-red-400 text-xs">{f.error}</span>}
              <button onClick={() => removeFile(idx)} className="hover:text-white">
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-white/5">
        <div className="max-w-3xl mx-auto px-4 sm:px-6 py-3">
          <div className="relative bg-white/[0.04] border border-white/10 rounded-2xl focus-within:ring-2 focus-within:ring-blue-500/30 focus-within:border-blue-500/30 transition-all shadow-lg shadow-black/20">
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => {
                setInput(e.target.value);
                const el = e.target;
                el.style.height = "auto";
                el.style.height = Math.min(el.scrollHeight, 200) + "px";
              }}
              onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
              placeholder="메시지를 입력하세요..."
              disabled={isLoading}
              rows={1}
              className="w-full bg-transparent px-4 pt-3.5 pb-12 text-sm text-slate-100 placeholder-slate-600 focus:outline-none resize-none overflow-y-auto leading-relaxed"
              style={{ maxHeight: "200px" }}
            />

            <div className="absolute bottom-0 left-0 right-0 px-3 pb-2.5 flex items-center justify-between">
              <div className="flex items-center gap-0.5">
                <input
                  ref={fileInputRef}
                  type="file"
                  multiple
                  accept=".pdf,.docx,.xlsx,.xls,.pptx,.txt,.csv,.png,.jpg,.jpeg,.gif,.webp"
                  onChange={handleFileSelect}
                  className="hidden"
                />
                <button
                  onClick={() => fileInputRef.current?.click()}
                  disabled={isLoading}
                  className="p-1.5 text-slate-600 hover:text-slate-300 transition-colors rounded-lg hover:bg-white/5 disabled:opacity-30"
                  title="파일 첨부"
                >
                  <Paperclip size={15} />
                </button>
                <button
                  onClick={downloadChat}
                  className="p-1.5 text-slate-600 hover:text-slate-300 transition-colors rounded-lg hover:bg-white/5"
                  title="대화 내보내기"
                >
                  <Download size={15} />
                </button>
                <button
                  onClick={resetChat}
                  className="p-1.5 text-slate-600 hover:text-slate-300 transition-colors rounded-lg hover:bg-white/5"
                  title="초기화"
                >
                  <RotateCcw size={15} />
                </button>

                <div className="h-4 w-px bg-white/8 mx-1" />

                <button
                  onClick={() => setWebSearch((v) => !v)}
                  className={`flex items-center gap-1 px-2 py-1 rounded-md text-xs font-medium border transition-colors ${
                    webSearch
                      ? "border-cyan-500/30 bg-cyan-500/10 text-cyan-400"
                      : "border-white/8 bg-white/3 text-slate-600 hover:text-slate-400"
                  }`}
                  title="웹 검색 활성화"
                >
                  <Globe size={13} />
                  <span>웹</span>
                </button>

                <div
                  className={`flex items-center gap-1.5 px-2 py-1 rounded-md text-xs font-medium border ${
                    targetColor === "blue"
                      ? "border-blue-500/20 bg-blue-500/8 text-blue-400"
                      : "border-green-500/20 bg-green-500/8 text-green-400"
                  }`}
                  title="Notion 패널에서 대상 선택"
                >
                  <span className={`w-1.5 h-1.5 rounded-full ${
                    targetColor === "blue" ? "bg-blue-400" : "bg-green-400"
                  }`} />
                  <span className="max-w-[80px] truncate">{targetLabel}</span>
                </div>
              </div>

              <button
                onClick={sendMessage}
                disabled={isLoading || (!input.trim() && attachedFiles.length === 0)}
                className="p-2 bg-blue-600 hover:bg-blue-500 text-white rounded-xl transition-all disabled:opacity-20 disabled:cursor-not-allowed"
              >
                <Send size={15} />
              </button>
            </div>
          </div>

          <p className="text-center text-xs text-slate-700 mt-2">
            Shift+Enter 줄바꿈 / 첨부: PDF, DOCX, XLSX, 이미지
          </p>
        </div>
      </div>
    </div>
  );
}

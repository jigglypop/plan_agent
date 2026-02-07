import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Loader2, RotateCcw, Paperclip, Copy, Check, Download, X, FileText, Image as ImageIcon } from "lucide-react";
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

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        '염시코기 2세입니다.\n20년간의 게시판 데이터를 바탕으로 답변합니다.\n\n예시 질문:\n- "2024 겨울행사 예산 알려줘"\n- "글램핑 장소 견적 찾아줘"\n- "작년 회의록 보여줘"\n- "노션에 여름행사 등록해줘"',
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [copiedIdx, setCopiedIdx] = useState<number | null>(null);
  const [attachedFiles, setAttachedFiles] = useState<AttachedFile[]>([]);
  const [notionTarget, setNotionTarget] = useState<"admin" | "public">("admin");
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
    } catch { /* clipboard not available */ }
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
        file,
        name: file.name,
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
      const prefix = `[notion_target=${notionTarget}] `;
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
    try { await api.resetChat(); } catch { /* ignore */ }
    setAttachedFiles([]);
    setMessages([{ role: "assistant", content: "대화가 초기화되었습니다. 무엇이든 물어보세요." }]);
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

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Messages */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-[48rem] mx-auto px-4 sm:px-6 py-6 space-y-6">
          {messages.map((msg, idx) => (
            <div key={idx} className="group">
              {/* Role label */}
              <div className="flex items-center gap-2 mb-2">
                <div className={`w-7 h-7 rounded-full flex items-center justify-center ${
                  msg.role === "user" ? "bg-blue-500" : "bg-white/10"
                }`}>
                  {msg.role === "user" ? <User size={14} className="text-white" /> : <Bot size={14} className="text-slate-300" />}
                </div>
                <span className="text-sm font-semibold text-slate-200">
                  {msg.role === "user" ? "나" : "염시코기 2세"}
                </span>
                <button
                  onClick={() => copyMessage(msg.content, idx)}
                  className="opacity-0 group-hover:opacity-100 transition-opacity text-slate-600 hover:text-slate-300 p-0.5 rounded"
                  title="복사"
                >
                  {copiedIdx === idx ? <Check size={13} /> : <Copy size={13} />}
                </button>
              </div>

              {/* Content */}
              <div className="pl-9">
                {msg.role === "user" ? (
                  <div className="text-[15px] text-slate-100 whitespace-pre-wrap leading-relaxed">{msg.content}</div>
                ) : (
                  <div className="text-[15px] text-slate-200 leading-7 prose prose-invert prose-base max-w-none prose-p:my-2.5 prose-li:my-0.5 prose-ul:my-2 prose-ol:my-2 prose-headings:my-3 prose-table:my-3 prose-th:px-3 prose-th:py-1.5 prose-td:px-3 prose-td:py-1.5 prose-th:border prose-th:border-white/10 prose-td:border prose-td:border-white/10 prose-a:text-blue-400 prose-code:text-emerald-300 prose-code:bg-white/5 prose-code:px-1.5 prose-code:py-0.5 prose-code:rounded prose-code:text-[13px]">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
                  </div>
                )}
              </div>

              {/* Divider */}
              {idx < messages.length - 1 && <div className="mt-6 border-b border-white/5" />}
            </div>
          ))}

          {isLoading && (
            <div className="group">
              <div className="flex items-center gap-2 mb-1.5">
                <div className="w-6 h-6 rounded-full bg-white/10 flex items-center justify-center">
                  <Loader2 size={12} className="text-slate-300" style={{ animation: "spin 1s linear infinite" }} />
                </div>
                <span className="text-xs font-medium text-slate-400">염시코기 2세</span>
              </div>
              <div className="pl-8 text-sm text-slate-500">생각 중...</div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Attached files */}
      {attachedFiles.length > 0 && (
        <div className="max-w-[48rem] mx-auto w-full px-4 sm:px-6 pt-2 flex gap-2 flex-wrap">
          {attachedFiles.map((f, idx) => (
            <div
              key={idx}
              className={`flex items-center gap-2 px-3 py-1.5 rounded-lg text-xs border ${
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
              {f.uploading && <Loader2 size={12} style={{ animation: "spin 1s linear infinite" }} />}
              {f.error && <span className="text-red-400">{f.error}</span>}
              <button onClick={() => removeFile(idx)} className="hover:text-white">
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input area */}
      <div className="border-t border-white/5 bg-black/20">
        <div className="max-w-[48rem] mx-auto px-4 sm:px-6 py-3">
          {/* Textarea */}
          <div className="relative bg-white/5 border border-white/10 rounded-2xl focus-within:ring-2 focus-within:ring-blue-500/40 focus-within:border-transparent transition-all">
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
              rows={2}
              className="w-full bg-transparent px-4 pt-3 pb-10 text-sm text-slate-100 placeholder-slate-500 focus:outline-none resize-none overflow-y-auto leading-relaxed"
              style={{ maxHeight: "200px" }}
            />

            {/* Bottom toolbar inside textarea */}
            <div className="absolute bottom-0 left-0 right-0 px-3 pb-2 flex items-center justify-between">
              <div className="flex items-center gap-1">
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
                  className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors rounded-lg hover:bg-white/5 disabled:opacity-30"
                  title="파일 첨부"
                >
                  <Paperclip size={16} />
                </button>
                <button
                  onClick={downloadChat}
                  className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors rounded-lg hover:bg-white/5"
                  title="대화 다운로드"
                >
                  <Download size={16} />
                </button>
                <button
                  onClick={resetChat}
                  className="p-1.5 text-slate-500 hover:text-slate-300 transition-colors rounded-lg hover:bg-white/5"
                  title="초기화"
                >
                  <RotateCcw size={16} />
                </button>

                <div className="h-4 w-px bg-white/10 mx-1" />

                <div className="flex rounded-md overflow-hidden border border-white/10">
                  <button
                    onClick={() => setNotionTarget("admin")}
                    className={`px-2 py-0.5 text-[10px] transition-colors ${
                      notionTarget === "admin"
                        ? "bg-blue-500/80 text-white"
                        : "bg-white/5 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    운영진
                  </button>
                  <button
                    onClick={() => setNotionTarget("public")}
                    className={`px-2 py-0.5 text-[10px] transition-colors ${
                      notionTarget === "public"
                        ? "bg-green-500/80 text-white"
                        : "bg-white/5 text-slate-500 hover:text-slate-300"
                    }`}
                  >
                    공개
                  </button>
                </div>
              </div>

              <button
                onClick={sendMessage}
                disabled={isLoading || (!input.trim() && attachedFiles.length === 0)}
                className="p-2 bg-white/90 hover:bg-white text-slate-900 rounded-lg transition-all disabled:opacity-20 disabled:cursor-not-allowed"
              >
                <Send size={16} />
              </button>
            </div>
          </div>

          <p className="text-center text-[10px] text-slate-600 mt-2">
            Shift+Enter로 줄바꿈 / 첨부파일: PDF, DOCX, XLSX, 이미지
          </p>
        </div>
      </div>
    </div>
  );
}

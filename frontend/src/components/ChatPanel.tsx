import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2, RotateCcw } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";

interface Message {
  role: "user" | "assistant";
  content: string;
}

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        '기획위원회 AI 에이전트입니다.\n20년간의 게시판 데이터를 바탕으로 답변합니다.\n\n예시 질문:\n- "2024 겨울행사 예산 알려줘"\n- "글램핑 장소 견적 찾아줘"\n- "작년 회의록 보여줘"\n- "노션에 여름행사 등록해줘"',
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;
    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const data = await api.chat(userMessage);
      setMessages((prev) => [...prev, { role: "assistant", content: data.response }]);
    } catch {
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: "서버 연결에 실패했습니다. 백엔드 서버가 실행 중인지 확인하세요." },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const resetChat = async () => {
    try { await api.resetChat(); } catch { /* ignore */ }
    setMessages([{ role: "assistant", content: "대화가 초기화되었습니다. 무엇이든 물어보세요." }]);
  };

  return (
    <div className="glass-dark overflow-hidden flex flex-col" style={{ height: "calc(100vh - 160px)", minHeight: "400px" }}>
      {/* Header */}
      <div className="px-4 sm:px-5 py-3 sm:py-4 border-b border-white/5 flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center">
            <Bot size={16} className="text-white" />
          </div>
          <span className="font-semibold text-sm text-white">AI 에이전트</span>
        </div>
        <button
          onClick={resetChat}
          className="text-slate-500 hover:text-slate-300 transition-colors p-1.5 rounded-lg hover:bg-white/5"
          title="대화 초기화"
        >
          <RotateCcw size={16} />
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto px-3 sm:px-5 py-3 sm:py-4 space-y-4">
        {messages.map((msg, idx) => (
          <div
            key={idx}
            className={`flex gap-2 sm:gap-3 ${msg.role === "user" ? "flex-row-reverse" : ""}`}
          >
            <div
              className={`w-7 h-7 rounded-full flex items-center justify-center shrink-0 hidden sm:flex ${
                msg.role === "user"
                  ? "bg-blue-500"
                  : "bg-white/10"
              }`}
            >
              {msg.role === "user" ? (
                <User size={14} className="text-white" />
              ) : (
                <Bot size={14} className="text-slate-300" />
              )}
            </div>
            <div
              className={`max-w-[90%] sm:max-w-[75%] px-3 sm:px-4 py-2.5 sm:py-3 rounded-2xl text-sm leading-relaxed ${
                msg.role === "user"
                  ? "bg-blue-500/90 text-white rounded-tr-sm whitespace-pre-wrap"
                  : "bg-white/5 text-slate-200 border border-white/5 rounded-tl-sm prose prose-invert prose-sm max-w-none prose-p:my-1 prose-li:my-0.5 prose-ul:my-1 prose-ol:my-1 prose-headings:my-2 prose-table:my-2 prose-th:px-2 prose-th:py-1 prose-td:px-2 prose-td:py-1 prose-th:border prose-th:border-white/10 prose-td:border prose-td:border-white/10 prose-a:text-blue-400"
              }`}
            >
              {msg.role === "user" ? msg.content : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.content}</ReactMarkdown>
              )}
            </div>
          </div>
        ))}

        {isLoading && (
          <div className="flex gap-2 sm:gap-3">
            <div className="w-7 h-7 rounded-full bg-white/10 flex items-center justify-center hidden sm:flex">
              <Loader2 size={14} className="text-slate-300" style={{ animation: "spin 1s linear infinite" }} />
            </div>
            <div className="px-3 sm:px-4 py-2.5 sm:py-3 rounded-2xl rounded-tl-sm bg-white/5 border border-white/5 text-slate-500 text-sm">
              생각 중...
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <div className="px-3 sm:px-5 py-3 sm:py-4 border-t border-white/5 flex gap-2 sm:gap-3">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); } }}
          placeholder="메시지를 입력하세요..."
          disabled={isLoading}
          className="flex-1 bg-black/40 border border-white/10 rounded-xl px-3 sm:px-4 py-3 text-sm text-slate-100 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/40"
        />
        <button
          onClick={sendMessage}
          disabled={isLoading || !input.trim()}
          className="px-3 sm:px-4 py-3 bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-400 hover:to-blue-500 text-white rounded-xl transition-all disabled:opacity-30 disabled:cursor-not-allowed"
        >
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}

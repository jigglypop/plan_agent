import { useState, useRef, useEffect } from "react";
import { Send, Bot, User, Loader2 } from "lucide-react";

interface Message {
  role: "user" | "assistant";
  content: string;
}

const API_URL = "http://localhost:8000";

export function ChatPanel() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: "assistant",
      content:
        '안녕하세요! 기획위원회 AI 어시스턴트입니다. 행사 통계, 일정 관리, 태스크 조회 등을 도와드립니다.\n\n예시 질문:\n- "이번 달 통계 알려줘"\n- "다가오는 행사 뭐 있어?"\n- "김철수 담당 태스크 보여줘"',
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || isLoading) return;

    const userMessage = input.trim();
    setInput("");
    setMessages((prev) => [...prev, { role: "user", content: userMessage }]);
    setIsLoading(true);

    try {
      const response = await fetch(`${API_URL}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: userMessage }),
      });

      if (!response.ok) throw new Error("API error");

      const data = await response.json();
      setMessages((prev) => [
        ...prev,
        { role: "assistant", content: data.response },
      ]);
    } catch {
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "서버 연결에 실패했습니다. 백엔드 서버가 실행 중인지 확인해주세요.\n\n실행 방법: py run_server.py",
        },
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  return (
    <div
      style={{
        display: "flex",
        flexDirection: "column",
        height: "600px",
        background: "white",
        borderRadius: "12px",
        boxShadow: "0 1px 3px rgba(0,0,0,0.1)",
        overflow: "hidden",
      }}
    >
      <div
        style={{
          padding: "1rem",
          borderBottom: "1px solid #e5e7eb",
          display: "flex",
          alignItems: "center",
          gap: "0.5rem",
        }}
      >
        <Bot size={20} color="#3b82f6" />
        <span style={{ fontWeight: 600 }}>AI 어시스턴트</span>
      </div>

      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "1rem",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
        }}
      >
        {messages.map((msg, idx) => (
          <div
            key={idx}
            style={{
              display: "flex",
              gap: "0.75rem",
              alignItems: "flex-start",
              flexDirection: msg.role === "user" ? "row-reverse" : "row",
            }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: msg.role === "user" ? "#3b82f6" : "#e5e7eb",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
              }}
            >
              {msg.role === "user" ? (
                <User size={16} color="white" />
              ) : (
                <Bot size={16} color="#374151" />
              )}
            </div>
            <div
              style={{
                maxWidth: "70%",
                padding: "0.75rem 1rem",
                borderRadius: "12px",
                background: msg.role === "user" ? "#3b82f6" : "#f3f4f6",
                color: msg.role === "user" ? "white" : "#374151",
                whiteSpace: "pre-wrap",
                fontSize: "0.9375rem",
                lineHeight: 1.5,
              }}
            >
              {msg.content}
            </div>
          </div>
        ))}

        {isLoading && (
          <div
            style={{ display: "flex", gap: "0.75rem", alignItems: "center" }}
          >
            <div
              style={{
                width: 32,
                height: 32,
                borderRadius: "50%",
                background: "#e5e7eb",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}
            >
              <Loader2
                size={16}
                color="#374151"
                style={{ animation: "spin 1s linear infinite" }}
              />
            </div>
            <div
              style={{
                padding: "0.75rem 1rem",
                borderRadius: "12px",
                background: "#f3f4f6",
                color: "#9ca3af",
              }}
            >
              생각 중...
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      <div
        style={{
          padding: "1rem",
          borderTop: "1px solid #e5e7eb",
          display: "flex",
          gap: "0.5rem",
        }}
      >
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="메시지를 입력하세요..."
          disabled={isLoading}
          style={{
            flex: 1,
            padding: "0.75rem 1rem",
            border: "1px solid #e5e7eb",
            borderRadius: "8px",
            fontSize: "0.9375rem",
            outline: "none",
          }}
        />
        <button
          onClick={sendMessage}
          disabled={isLoading || !input.trim()}
          style={{
            padding: "0.75rem",
            background: "#3b82f6",
            border: "none",
            borderRadius: "8px",
            cursor: isLoading || !input.trim() ? "not-allowed" : "pointer",
            opacity: isLoading || !input.trim() ? 0.5 : 1,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
          }}
        >
          <Send size={18} color="white" />
        </button>
      </div>

      <style>{`
        @keyframes spin {
          from { transform: rotate(0deg); }
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
}

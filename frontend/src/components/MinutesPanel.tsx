import { useState, useRef, useCallback } from "react";
import { Upload, Mic, FileAudio, Loader2, FileText, Copy, Check } from "lucide-react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { api } from "../api";

type Phase = "idle" | "uploading" | "stt" | "minutes" | "done" | "error";

export function MinutesPanel() {
  const [file, setFile] = useState<File | null>(null);
  const [phase, setPhase] = useState<Phase>("idle");
  const [statusMsg, setStatusMsg] = useState("");
  const [transcript, setTranscript] = useState("");
  const [minutesText, setMinutesText] = useState("");
  const [actionItems, setActionItems] = useState<string[]>([]);
  const [notionSaved, setNotionSaved] = useState(false);
  const [notionChecklist, setNotionChecklist] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);
  const [activeTab, setActiveTab] = useState<"minutes" | "transcript">("minutes");

  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const f = e.target.files?.[0];
    if (!f) return;
    setFile(f);
    reset();
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const f = e.dataTransfer.files?.[0];
    if (!f) return;
    setFile(f);
    reset();
  };

  const reset = () => {
    setPhase("idle");
    setStatusMsg("");
    setTranscript("");
    setMinutesText("");
    setActionItems([]);
    setNotionSaved(false);
    setNotionChecklist(false);
    setError("");
    setActiveTab("minutes");
  };

  const submit = useCallback(() => {
    if (!file) return;
    setPhase("uploading");
    setStatusMsg("파일 업로드 중...");
    setMinutesText("");
    setTranscript("");
    setError("");

    const stream = api.sttMinutesStream(file);
    const controller = stream.start({
      onStatus(p, msg) {
        if (p === "stt") setPhase("stt");
        else if (p === "minutes") setPhase("minutes");
        setStatusMsg(msg);
      },
      onTranscript(t) {
        setTranscript(t);
      },
      onChunk(text) {
        setMinutesText((prev) => prev + text);
      },
      onDone(data) {
        setPhase("done");
        setStatusMsg("");
        setActionItems(data.action_items_list || []);
        setNotionSaved(data.notion_saved);
        setNotionChecklist(data.notion_checklist_saved);
      },
      onError(msg) {
        setPhase("error");
        setError(msg);
        setStatusMsg("");
      },
    });
    abortRef.current = controller;
  }, [file]);

  const cancel = () => {
    abortRef.current?.abort();
    setPhase("idle");
    setStatusMsg("");
  };

  const copyText = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch { /* */ }
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes}B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)}KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)}MB`;
  };

  const isProcessing = phase === "uploading" || phase === "stt" || phase === "minutes";
  const hasResult = phase === "done" || (phase === "minutes" && minutesText.length > 0);

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="max-w-3xl mx-auto px-4 sm:px-8 py-6 space-y-6">
        <div className="flex items-center gap-2">
          <Mic size={20} className="text-violet-400" />
          <h2 className="text-lg font-bold text-white">회의록 생성</h2>
        </div>
        <p className="text-xs text-slate-500">
          음성파일(.mp3, .wav, .m4a, .ogg, .webm)을 업로드하면 AI가 실시간으로 회의록을 생성합니다.
        </p>

        {/* Upload area */}
        {!hasResult && phase !== "stt" && (
          <div
            onDrop={handleDrop}
            onDragOver={(e) => e.preventDefault()}
            onClick={() => !isProcessing && inputRef.current?.click()}
            className={`glass-dark p-8 flex flex-col items-center justify-center gap-3 transition-colors ${
              isProcessing ? "opacity-60 cursor-not-allowed" : "cursor-pointer hover:border-blue-500/30"
            }`}
          >
            <input ref={inputRef} type="file" accept=".mp3,.wav,.m4a,.ogg,.webm" onChange={handleFile} className="hidden" />
            {file ? (
              <>
                <FileAudio size={32} className="text-violet-400" />
                <p className="text-sm text-white">{file.name}</p>
                <p className="text-xs text-slate-500">{formatSize(file.size)}</p>
              </>
            ) : (
              <>
                <Upload size={32} className="text-slate-500" />
                <p className="text-sm text-slate-400">음성파일을 드래그하거나 클릭하여 선택</p>
                <p className="text-xs text-slate-600">MP3, WAV, M4A, OGG, WEBM (최대 25MB)</p>
              </>
            )}
          </div>
        )}

        {/* Submit / Cancel */}
        {file && !hasResult && (
          <div className="flex gap-2">
            <button
              onClick={submit}
              disabled={isProcessing}
              className="flex-1 py-3 bg-violet-600 hover:bg-violet-500 disabled:bg-violet-600/50 text-white text-sm rounded-xl transition-colors flex items-center justify-center gap-2"
            >
              {isProcessing ? (
                <>
                  <Loader2 size={16} className="animate-spin" />
                  {statusMsg || "처리 중..."}
                </>
              ) : (
                <>
                  <FileText size={16} />
                  회의록 생성
                </>
              )}
            </button>
            {isProcessing && (
              <button
                onClick={cancel}
                className="px-4 py-3 bg-white/10 hover:bg-white/20 text-slate-300 text-sm rounded-xl transition-colors"
              >
                취소
              </button>
            )}
          </div>
        )}

        {/* Progress indicator */}
        {isProcessing && (
          <div className="glass-dark p-4 space-y-3">
            <div className="flex items-center gap-3">
              <div className="relative">
                <Loader2 size={20} className="text-violet-400 animate-spin" />
              </div>
              <div>
                <div className="text-sm text-white font-medium">{statusMsg}</div>
                <div className="text-xs text-slate-500 mt-0.5">
                  {phase === "stt" && "Whisper API로 음성을 텍스트로 변환하는 중입니다."}
                  {phase === "minutes" && "GPT가 회의록을 작성하고 있습니다."}
                  {phase === "uploading" && "파일을 서버로 전송 중입니다."}
                </div>
              </div>
            </div>
            {/* Phase steps */}
            <div className="flex items-center gap-2 text-xs">
              <StepDot active={phase === "uploading"} done={phase !== "uploading"} />
              <span className={phase === "uploading" ? "text-white" : "text-slate-500"}>업로드</span>
              <span className="text-slate-700">--</span>
              <StepDot active={phase === "stt"} done={phase === "minutes"} />
              <span className={phase === "stt" ? "text-white" : "text-slate-500"}>음성 인식</span>
              <span className="text-slate-700">--</span>
              <StepDot active={phase === "minutes"} done={false} />
              <span className={phase === "minutes" ? "text-white" : "text-slate-500"}>회의록 생성</span>
            </div>
          </div>
        )}

        {error && (
          <div className="glass-dark p-4 border-red-500/30 text-red-300 text-sm">{error}</div>
        )}

        {/* Streaming / Final result */}
        {hasResult && (
          <div className="space-y-4 animate-fade-in">
            {/* Notion save status */}
            {phase === "done" && (notionSaved || notionChecklist) && (
              <div className="glass-dark p-3 border-l-2 border-emerald-500/50 text-xs text-emerald-300 space-y-1">
                {notionSaved && <div>회의록이 노션에 자동 저장되었습니다.</div>}
                {notionChecklist && (
                  <div>후속 조치 ({actionItems.length}건)가 노션 체크리스트로 생성되었습니다.</div>
                )}
              </div>
            )}

            {/* Action Items */}
            {phase === "done" && actionItems.length > 0 && (
              <div className="glass-dark p-4">
                <h3 className="text-xs font-semibold text-white mb-2">후속 조치 ({actionItems.length}건)</h3>
                <ul className="space-y-1.5">
                  {actionItems.map((item, i) => (
                    <li key={i} className="flex items-start gap-2 text-xs text-slate-300">
                      <span className="w-4 h-4 mt-0.5 border border-white/20 rounded shrink-0" />
                      {item}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {/* Tabs */}
            <div className="flex items-center gap-1 border-b border-white/5 pb-1">
              <button
                onClick={() => setActiveTab("minutes")}
                className={`px-3 py-1.5 text-xs rounded-t-lg transition-colors ${
                  activeTab === "minutes" ? "bg-white/10 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                회의록 {phase === "minutes" && <Loader2 size={10} className="inline animate-spin ml-1" />}
              </button>
              <button
                onClick={() => setActiveTab("transcript")}
                disabled={!transcript}
                className={`px-3 py-1.5 text-xs rounded-t-lg transition-colors disabled:opacity-30 ${
                  activeTab === "transcript" ? "bg-white/10 text-white" : "text-slate-400 hover:text-white"
                }`}
              >
                원본 텍스트
              </button>
              <button
                onClick={() => copyText(activeTab === "minutes" ? minutesText : transcript)}
                className="ml-auto p-1 text-slate-500 hover:text-white transition-colors"
                title="복사"
              >
                {copied ? <Check size={14} className="text-emerald-400" /> : <Copy size={14} />}
              </button>
            </div>

            <div className="glass-dark p-5">
              {activeTab === "minutes" ? (
                <div className="prose prose-invert prose-sm max-w-none prose-headings:my-3 prose-p:my-2 prose-li:my-0.5 prose-a:text-blue-400">
                  <ReactMarkdown remarkPlugins={[remarkGfm]}>{minutesText}</ReactMarkdown>
                  {phase === "minutes" && (
                    <span className="inline-block w-2 h-4 bg-violet-400 animate-pulse ml-0.5 align-middle" />
                  )}
                </div>
              ) : (
                <pre className="text-xs text-slate-300 whitespace-pre-wrap leading-relaxed">{transcript}</pre>
              )}
            </div>

            {phase === "done" && (
              <button
                onClick={() => { setFile(null); reset(); }}
                className="text-xs text-slate-400 hover:text-white transition-colors"
              >
                다른 파일 분석
              </button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function StepDot({ active, done }: { active: boolean; done: boolean }) {
  if (active) {
    return (
      <span className="relative flex h-2.5 w-2.5">
        <span className="absolute inline-flex h-full w-full rounded-full bg-violet-400 opacity-75 animate-ping" />
        <span className="relative inline-flex rounded-full h-2.5 w-2.5 bg-violet-500" />
      </span>
    );
  }
  if (done) {
    return <span className="h-2.5 w-2.5 rounded-full bg-emerald-500" />;
  }
  return <span className="h-2.5 w-2.5 rounded-full bg-slate-700" />;
}

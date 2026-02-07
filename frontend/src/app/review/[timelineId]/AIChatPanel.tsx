"use client";

/**
 * AIChatPanel - AI assistant for identifying interesting points in video
 *
 * Helps users:
 * 1. Identify interesting points at current timestamp
 * 2. Discuss video content to find highlights
 * 3. Get suggestions for observations
 */

import { useState, useRef, useEffect, useCallback } from "react";
import { API_BASE, pinCard } from "@/lib/api";
import type { Observation, InsightCard } from "@/lib/types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  timestamp: Date;
  messageTime?: number;  // Video timestamp when message was sent
  hasImage?: boolean;  // Whether message included a screenshot
}

interface AIChatPanelProps {
  timelineId: string;
  videoTitle?: string;
  currentTime: number;
  observations: Observation[];
  onCaptureFrame?: () => string | null;
  onInsightPinned?: () => void;  // Callback when insight is pinned
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default function AIChatPanel({
  timelineId,
  videoTitle,
  currentTime,
  observations,
  onCaptureFrame,
  onInsightPinned,
}: AIChatPanelProps) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [expanded, setExpanded] = useState(false);
  const [capturedImage, setCapturedImage] = useState<string | null>(null);
  const [savingInsightId, setSavingInsightId] = useState<string | null>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Save AI response as insight card
  const saveAsInsight = useCallback(async (message: Message) => {
    if (savingInsightId) return;
    setSavingInsightId(message.id);

    try {
      // Extract title from first line or first sentence
      const lines = message.content.split("\n").filter(l => l.trim());
      const firstLine = lines[0] || message.content;
      const title = firstLine.length > 50 ? firstLine.slice(0, 47) + "..." : firstLine;

      const insightData: InsightCard = {
        title,
        content: message.content,
        category: "general",
        related_text: null,
        frame_data: null,
      };

      await pinCard(timelineId, {
        card_type: "insight",
        card_id: `insight-${message.id}`,
        segment_id: 0,  // Not tied to specific segment
        timestamp: message.messageTime || currentTime,
        card_data: insightData,
      });

      onInsightPinned?.();
    } catch (err) {
      console.error("Failed to save insight:", err);
    } finally {
      setSavingInsightId(null);
    }
  }, [timelineId, currentTime, savingInsightId, onInsightPinned]);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (expanded) {
      messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, expanded]);

  // Focus input when expanded
  useEffect(() => {
    if (expanded) {
      inputRef.current?.focus();
    }
  }, [expanded]);

  const sendMessage = useCallback(
    async (messageText?: string) => {
      const trimmedInput = (messageText || input).trim();
      if (!trimmedInput || loading) return;

      const userMessage: Message = {
        id: `user-${Date.now()}`,
        role: "user",
        content: capturedImage ? `[附带截图] ${trimmedInput}` : trimmedInput,
        timestamp: new Date(),
        messageTime: currentTime,
        hasImage: !!capturedImage,
      };

      setMessages((prev) => [...prev, userMessage]);
      if (!messageText) setInput("");
      setLoading(true);

      try {
        const response = await fetch(`${API_BASE}/timelines/${timelineId}/chat`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            message: trimmedInput,
            include_transcript: true,
            current_time: currentTime,
            image: capturedImage || undefined,
          }),
        });

        // Clear captured image after sending
        if (capturedImage) {
          setCapturedImage(null);
        }

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        const assistantMessage: Message = {
          id: `assistant-${Date.now()}`,
          role: "assistant",
          content: data.response,
          timestamp: new Date(),
          messageTime: currentTime,
        };

        setMessages((prev) => [...prev, assistantMessage]);
      } catch (error) {
        console.error("Chat error:", error);
        const errorMessage: Message = {
          id: `error-${Date.now()}`,
          role: "assistant",
          content: "抱歉，发生了错误。请稍后重试。",
          timestamp: new Date(),
        };
        setMessages((prev) => [...prev, errorMessage]);
      } finally {
        setLoading(false);
      }
    },
    [input, loading, timelineId, currentTime, capturedImage]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage();
    }
  };

  // Context-aware quick questions
  const getQuickQuestions = () => {
    const timeStr = formatTime(currentTime);
    return [
      `${timeStr} 这里在说什么？`,
      "这个视频有哪些精彩片段？",
      "帮我找出值得做笔记的地方",
      observations.length > 0 ? "根据已有笔记，还有什么值得关注的？" : "这个视频的核心观点是什么？",
    ];
  };

  return (
    <div className="border-t border-gray-700 bg-gray-800/30 flex-shrink-0">
      {/* Header - always visible */}
      <button
        onClick={() => setExpanded(!expanded)}
        className="w-full flex items-center justify-between px-4 py-2 hover:bg-gray-700/50 transition-colors"
      >
        <div className="flex items-center gap-2">
          <svg
            className="w-4 h-4 text-purple-400"
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z"
            />
          </svg>
          <span className="text-sm font-medium">AI 助手</span>
          <span className="text-xs text-gray-500">找兴趣点</span>
          {messages.length > 0 && (
            <span className="px-1.5 py-0.5 text-xs bg-purple-500/20 text-purple-400 rounded">
              {messages.length}
            </span>
          )}
        </div>
        <div className="flex items-center gap-2">
          <span className="text-xs text-gray-500">{formatTime(currentTime)}</span>
          <svg
            className={`w-4 h-4 text-gray-400 transition-transform ${expanded ? "rotate-180" : ""}`}
            fill="none"
            stroke="currentColor"
            viewBox="0 0 24 24"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </div>
      </button>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-gray-700">
          {/* Messages area */}
          <div className="h-48 overflow-y-auto p-3 space-y-3">
            {messages.length === 0 ? (
              <div className="text-center text-gray-500 py-2">
                <p className="text-sm mb-3">问我关于视频的问题，帮你找到兴趣点</p>
                <div className="flex flex-wrap gap-2 justify-center">
                  {getQuickQuestions().map((q, i) => (
                    <button
                      key={i}
                      onClick={() => {
                        sendMessage(q);
                      }}
                      className="px-2 py-1 text-xs bg-gray-700 hover:bg-gray-600 rounded-full text-gray-300 transition-colors"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              </div>
            ) : (
              messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                >
                  <div
                    className={`max-w-[85%] rounded-lg text-sm ${
                      msg.role === "user"
                        ? "bg-blue-600 text-white"
                        : "bg-gray-700 text-gray-100"
                    }`}
                  >
                    <div className="px-3 py-2 whitespace-pre-wrap">{msg.content}</div>
                    {/* Save as insight button for assistant messages */}
                    {msg.role === "assistant" && (
                      <div className="px-3 pb-2 pt-1 border-t border-gray-600/50">
                        <button
                          onClick={() => saveAsInsight(msg)}
                          disabled={savingInsightId === msg.id}
                          className="flex items-center gap-1.5 text-xs text-purple-400 hover:text-purple-300 disabled:text-gray-500 transition-colors"
                        >
                          {savingInsightId === msg.id ? (
                            <>
                              <span className="w-3 h-3 border-2 border-purple-400/30 border-t-purple-400 rounded-full animate-spin" />
                              保存中...
                            </>
                          ) : (
                            <>
                              <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 24 24">
                                <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
                              </svg>
                              钉为兴趣点
                            </>
                          )}
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
            {loading && (
              <div className="flex justify-start">
                <div className="bg-gray-700 px-3 py-2 rounded-lg">
                  <div className="flex items-center gap-1">
                    <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                    <div
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: "0.1s" }}
                    />
                    <div
                      className="w-2 h-2 bg-gray-400 rounded-full animate-bounce"
                      style={{ animationDelay: "0.2s" }}
                    />
                  </div>
                </div>
              </div>
            )}
            <div ref={messagesEndRef} />
          </div>

          {/* Captured image preview */}
          {capturedImage && (
            <div className="border-t border-gray-700 px-2 pt-2">
              <div className="relative inline-block">
                <img
                  src={capturedImage}
                  alt="截图预览"
                  className="h-16 rounded border border-gray-600"
                />
                <button
                  onClick={() => setCapturedImage(null)}
                  className="absolute -top-1 -right-1 w-5 h-5 bg-red-500 hover:bg-red-600 rounded-full flex items-center justify-center text-white text-xs"
                  title="移除截图"
                >
                  ×
                </button>
              </div>
            </div>
          )}

          {/* Input area */}
          <div className="border-t border-gray-700 p-2">
            <div className="flex gap-2">
              {/* Capture button */}
              {onCaptureFrame && (
                <button
                  onClick={() => {
                    const image = onCaptureFrame();
                    if (image) {
                      setCapturedImage(image);
                    }
                  }}
                  disabled={loading}
                  className={`px-3 py-2 rounded-lg transition-colors ${
                    capturedImage
                      ? "bg-green-600 hover:bg-green-700"
                      : "bg-gray-600 hover:bg-gray-500"
                  } disabled:opacity-50`}
                  title="截取当前画面"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      strokeWidth={2}
                      d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                  </svg>
                </button>
              )}
              <textarea
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder={capturedImage ? "描述你想问的问题..." : `问关于 ${formatTime(currentTime)} 的问题...`}
                disabled={loading}
                rows={1}
                className="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-400 focus:outline-none focus:border-purple-500 resize-none disabled:opacity-50"
              />
              <button
                onClick={() => sendMessage()}
                disabled={(!input.trim() && !capturedImage) || loading}
                className="px-3 py-2 bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 disabled:cursor-not-allowed rounded-lg transition-colors"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8"
                  />
                </svg>
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

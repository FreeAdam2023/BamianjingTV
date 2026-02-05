"use client";

import React, { useState, useRef, useEffect, useCallback } from "react";
import { generateCreativeConfig, saveCreativeConfig } from "@/lib/api";
import type { RemotionConfig, CreativeStyle } from "@/lib/creative-types";

interface Message {
  id: string;
  role: "user" | "assistant";
  content: string;
  config?: RemotionConfig;
  tokensUsed?: number;
  costUsd?: number;
}

interface CreativeAIChatProps {
  timelineId: string;
  currentConfig: RemotionConfig;
  onConfigChange: (config: RemotionConfig) => void;
}

export default function CreativeAIChat({
  timelineId,
  currentConfig,
  onConfigChange,
}: CreativeAIChatProps) {
  const [messages, setMessages] = useState<Message[]>([
    {
      id: "welcome",
      role: "assistant",
      content: "Describe the subtitle effect you want. For example: \"Make it karaoke style with yellow word highlights\" or \"Bouncy popup effect with larger text\".",
    },
  ]);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isExpanded, setIsExpanded] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Focus input when expanded
  useEffect(() => {
    if (isExpanded) {
      inputRef.current?.focus();
    }
  }, [isExpanded]);

  const handleSubmit = useCallback(async (e?: React.FormEvent) => {
    e?.preventDefault();
    if (!input.trim() || isLoading) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: "user",
      content: input.trim(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setIsLoading(true);

    try {
      const response = await generateCreativeConfig(timelineId, {
        prompt: userMessage.content,
        previous_config: currentConfig,
      });

      const assistantMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: response.explanation || `Applied ${response.config.style} style.`,
        config: response.config,
        tokensUsed: response.tokens_used,
        costUsd: response.cost_usd,
      };

      setMessages((prev) => [...prev, assistantMessage]);

      // Apply the config
      onConfigChange(response.config);
    } catch (err) {
      const errorMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: "assistant",
        content: `Failed to generate config: ${err instanceof Error ? err.message : "Unknown error"}. Please try again.`,
      };
      setMessages((prev) => [...prev, errorMessage]);
    } finally {
      setIsLoading(false);
    }
  }, [input, isLoading, timelineId, currentConfig, onConfigChange]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSubmit();
    }
  }, [handleSubmit]);

  const handleApplyConfig = useCallback(async (config: RemotionConfig) => {
    onConfigChange(config);
    // Also save to backend
    try {
      await saveCreativeConfig(timelineId, config);
    } catch (err) {
      console.error("Failed to save config:", err);
    }
  }, [timelineId, onConfigChange]);

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="w-full px-3 py-2 bg-purple-600/20 border-t border-purple-500/30 text-purple-300 text-sm hover:bg-purple-600/30 transition-colors flex items-center justify-center gap-2"
      >
        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
        </svg>
        AI Style Assistant
      </button>
    );
  }

  return (
    <div className="flex flex-col border-t border-purple-500/30 bg-gray-900/50">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 bg-purple-600/20 border-b border-purple-500/30">
        <div className="flex items-center gap-2">
          <svg className="w-4 h-4 text-purple-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-5 5v-5z" />
          </svg>
          <span className="text-sm font-medium text-purple-300">AI Style Assistant</span>
        </div>
        <button
          onClick={() => setIsExpanded(false)}
          className="text-gray-400 hover:text-gray-300 p-1"
        >
          <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto max-h-48 p-3 space-y-3">
        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}
          >
            <div
              className={`max-w-[85%] rounded-lg px-3 py-2 text-sm ${
                msg.role === "user"
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-200"
              }`}
            >
              <p className="whitespace-pre-wrap">{msg.content}</p>
              {msg.config && (
                <div className="mt-2 pt-2 border-t border-gray-600/50">
                  <div className="flex items-center justify-between">
                    <span className="text-xs text-gray-400">
                      Style: {msg.config.style}
                    </span>
                    <button
                      onClick={() => handleApplyConfig(msg.config!)}
                      className="text-xs px-2 py-0.5 bg-purple-500 hover:bg-purple-400 rounded text-white transition-colors"
                    >
                      Apply & Save
                    </button>
                  </div>
                  {msg.tokensUsed !== undefined && msg.tokensUsed > 0 && (
                    <div className="text-xs text-gray-500 mt-1">
                      {msg.tokensUsed} tokens (${msg.costUsd?.toFixed(4)})
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>
        ))}
        {isLoading && (
          <div className="flex justify-start">
            <div className="bg-gray-700 rounded-lg px-3 py-2 text-sm text-gray-400">
              <span className="flex items-center gap-2">
                <span className="animate-spin w-3 h-3 border border-purple-400 border-t-transparent rounded-full" />
                Generating...
              </span>
            </div>
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* Input */}
      <form onSubmit={handleSubmit} className="p-2 border-t border-gray-700">
        <div className="flex gap-2">
          <textarea
            ref={inputRef}
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Describe the effect you want..."
            className="flex-1 px-3 py-2 bg-gray-800 border border-gray-600 rounded-lg text-sm text-white placeholder-gray-500 focus:outline-none focus:border-purple-500 resize-none"
            rows={1}
            disabled={isLoading}
          />
          <button
            type="submit"
            disabled={!input.trim() || isLoading}
            className="px-3 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-500 disabled:bg-gray-600 disabled:cursor-not-allowed transition-colors"
          >
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
            </svg>
          </button>
        </div>
        <div className="mt-1 flex flex-wrap gap-1">
          {["karaoke style", "bouncy popup", "smooth slide", "typewriter effect"].map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              onClick={() => setInput(suggestion)}
              className="text-xs px-2 py-0.5 bg-gray-700 text-gray-400 rounded hover:bg-gray-600 hover:text-gray-300 transition-colors"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </form>
    </div>
  );
}

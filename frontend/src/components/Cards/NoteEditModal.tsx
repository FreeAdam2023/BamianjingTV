"use client";

/**
 * NoteEditModal - Modal for creating/editing note cards
 */

import { useState, useEffect } from "react";
import type { PinnedCard } from "@/lib/types";
import { pinCard, updatePinnedCardData } from "@/lib/api";

interface NoteEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  timelineId: string;
  segmentId: number;
  currentTime: number;
  /** Existing card to edit, or undefined for creating new */
  existingCard?: PinnedCard;
  onSuccess: () => void;
}

export default function NoteEditModal({
  isOpen,
  onClose,
  timelineId,
  segmentId,
  currentTime,
  existingCard,
  onSuccess,
}: NoteEditModalProps) {
  const [title, setTitle] = useState("");
  const [content, setContent] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isEditing = !!existingCard;

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      if (existingCard?.card_data) {
        const data = existingCard.card_data as { title?: string; content?: string };
        setTitle(data.title || "");
        setContent(data.content || "");
      } else {
        setTitle("");
        setContent("");
      }
      setError(null);
    }
  }, [isOpen, existingCard]);

  const handleSave = async () => {
    if (!title.trim()) {
      setError("请输入笔记标题");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      if (isEditing) {
        // Update existing card data
        await updatePinnedCardData(timelineId, existingCard!.id, {
          title: title.trim(),
          content: content.trim(),
        });
      } else {
        // Create new note card
        const cardId = `note-${Math.random().toString(36).slice(2, 10)}`;
        await pinCard(timelineId, {
          card_type: "note",
          card_id: cardId,
          segment_id: segmentId,
          timestamp: currentTime,
          card_data: {
            title: title.trim(),
            content: content.trim(),
          },
        });
      }
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setLoading(false);
    }
  };

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-gray-800 rounded-lg shadow-xl w-full max-w-md mx-4 p-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-medium text-white">
            {isEditing ? "编辑笔记" : "添加笔记"}
          </h3>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Form */}
        <div className="space-y-4">
          {/* Title */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              标题 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="笔记标题..."
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-500 focus:border-green-500 focus:outline-none"
              autoFocus
            />
          </div>

          {/* Content */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              内容
            </label>
            <textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="笔记内容..."
              rows={5}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-500 focus:border-green-500 focus:outline-none resize-none"
            />
          </div>

          {/* Error message */}
          {error && (
            <div className="p-2 bg-red-500/20 border border-red-500/50 rounded text-sm text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-end mt-6 pt-4 border-t border-gray-700 gap-2">
          <button
            onClick={onClose}
            disabled={loading}
            className="px-4 py-1.5 text-sm text-gray-400 hover:text-white transition-colors"
          >
            取消
          </button>
          <button
            onClick={handleSave}
            disabled={loading}
            className="px-4 py-1.5 text-sm bg-green-600 hover:bg-green-700 disabled:bg-green-800 text-white rounded transition-colors flex items-center gap-2"
          >
            {loading && (
              <svg className="w-4 h-4 animate-spin" fill="none" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
            )}
            保存
          </button>
        </div>
      </div>
    </div>
  );
}

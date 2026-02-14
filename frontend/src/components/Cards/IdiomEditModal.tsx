"use client";

/**
 * IdiomEditModal - Modal for adding/editing/deleting idioms
 */

import { useState, useEffect } from "react";
import type { IdiomAnnotation } from "@/lib/types";
import { addManualIdiom, deleteSegmentIdiom } from "@/lib/api";

interface IdiomEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  timelineId: string;
  segmentId: number;
  segmentText: string;
  /** Existing idiom to edit, or null for adding new */
  idiom?: IdiomAnnotation | null;
  onSuccess: () => void;
}

const CATEGORY_OPTIONS = [
  { value: "idiom", label: "Idiom (惯用语)" },
  { value: "phrasal_verb", label: "Phrasal Verb (短语动词)" },
  { value: "slang", label: "Slang (口语/俚语)" },
  { value: "colloquial", label: "Colloquial (口语表达)" },
  { value: "proverb", label: "Proverb (谚语)" },
  { value: "expression", label: "Expression (常用表达/术语)" },
];

export default function IdiomEditModal({
  isOpen,
  onClose,
  timelineId,
  segmentId,
  segmentText,
  idiom,
  onSuccess,
}: IdiomEditModalProps) {
  const [text, setText] = useState(idiom?.text || "");
  const [category, setCategory] = useState(idiom?.category || "idiom");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);

  const isEditing = !!idiom;

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setText(idiom?.text || "");
      setCategory(idiom?.category || "idiom");
      setError(null);
      setDeleteConfirm(false);
    }
  }, [isOpen, idiom, segmentId]);

  const handleSave = async () => {
    if (!text.trim()) {
      setError("请输入表达/短语文本");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await addManualIdiom(timelineId, segmentId, {
        segment_id: segmentId,
        text: text.trim(),
        category,
      });

      if (result.success) {
        onSuccess();
        onClose();
      } else {
        setError(result.message);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "保存失败");
    } finally {
      setLoading(false);
    }
  };

  const handleDelete = async () => {
    if (!idiom) return;

    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await deleteSegmentIdiom(timelineId, segmentId, idiom.text);
      onSuccess();
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除失败");
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
            {isEditing ? "编辑表达" : "添加表达"}
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

        {/* Segment text reference */}
        <div className="mb-4 p-2 bg-gray-700/50 rounded text-sm text-gray-300 max-h-20 overflow-y-auto">
          {segmentText}
        </div>

        {/* Form */}
        <div className="space-y-4">
          {/* Idiom text */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              表达/短语文本 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="例如: break the ice"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-500 focus:border-amber-500 focus:outline-none"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter" && !e.shiftKey) {
                  e.preventDefault();
                  handleSave();
                }
                if (e.key === "Escape") onClose();
              }}
            />
          </div>

          {/* Category select */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              类别
            </label>
            <select
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white focus:border-amber-500 focus:outline-none"
            >
              {CATEGORY_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </div>

          {/* Error message */}
          {error && (
            <div className="p-2 bg-red-500/20 border border-red-500/50 rounded text-sm text-red-400">
              {error}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="flex items-center justify-between mt-6 pt-4 border-t border-gray-700">
          <div>
            {isEditing && (
              <button
                onClick={handleDelete}
                disabled={loading}
                className={`px-3 py-1.5 text-sm rounded transition-colors ${
                  deleteConfirm
                    ? "bg-red-600 hover:bg-red-700 text-white"
                    : "text-red-400 hover:text-red-300 hover:bg-red-500/20"
                }`}
              >
                {deleteConfirm ? "确认删除" : "删除"}
              </button>
            )}
          </div>
          <div className="flex items-center gap-2">
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
              className="px-4 py-1.5 text-sm bg-amber-600 hover:bg-amber-700 disabled:bg-amber-800 text-white rounded transition-colors flex items-center gap-2"
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
    </div>
  );
}

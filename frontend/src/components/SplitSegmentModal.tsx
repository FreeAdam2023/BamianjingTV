"use client";

/**
 * SplitSegmentModal - Modal for splitting a long segment into two
 */

import { useState, useCallback, useMemo } from "react";
import type { EditableSegment } from "@/lib/types";

interface SplitSegmentModalProps {
  segment: EditableSegment;
  onSplit: (enIndex: number, zhIndex: number) => Promise<void>;
  onClose: () => void;
}

export default function SplitSegmentModal({
  segment,
  onSplit,
  onClose,
}: SplitSegmentModalProps) {
  const [enSplitIndex, setEnSplitIndex] = useState(Math.floor(segment.en.length / 2));
  const [zhSplitIndex, setZhSplitIndex] = useState(Math.floor(segment.zh.length / 2));
  const [splitting, setSplitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Preview of split texts
  const preview = useMemo(() => ({
    en1: segment.en.slice(0, enSplitIndex),
    en2: segment.en.slice(enSplitIndex),
    zh1: segment.zh.slice(0, zhSplitIndex),
    zh2: segment.zh.slice(zhSplitIndex),
  }), [segment.en, segment.zh, enSplitIndex, zhSplitIndex]);

  // Calculate time split
  const timePreview = useMemo(() => {
    const ratio = enSplitIndex / segment.en.length;
    const duration = segment.end - segment.start;
    const splitTime = segment.start + duration * ratio;
    return {
      part1: { start: segment.start, end: splitTime },
      part2: { start: splitTime, end: segment.end },
    };
  }, [segment.start, segment.end, segment.en.length, enSplitIndex]);

  const formatTime = (t: number) => {
    const mins = Math.floor(t / 60);
    const secs = (t % 60).toFixed(1);
    return `${mins}:${secs.padStart(4, '0')}`;
  };

  const handleSplit = useCallback(async () => {
    if (enSplitIndex <= 0 || enSplitIndex >= segment.en.length) {
      setError("英文分割位置无效");
      return;
    }
    if (zhSplitIndex <= 0 || zhSplitIndex >= segment.zh.length) {
      setError("中文分割位置无效");
      return;
    }

    setSplitting(true);
    setError(null);
    try {
      await onSplit(enSplitIndex, zhSplitIndex);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "分割失败");
    } finally {
      setSplitting(false);
    }
  }, [enSplitIndex, zhSplitIndex, segment.en.length, segment.zh.length, onSplit, onClose]);

  // Find sentence boundaries for quick split options
  const sentenceBreaks = useMemo(() => {
    const enBreaks: number[] = [];
    const zhBreaks: number[] = [];

    // Find EN sentence endings (., !, ?, ;)
    for (let i = 1; i < segment.en.length - 1; i++) {
      if (/[.!?;]/.test(segment.en[i]) && segment.en[i + 1] === ' ') {
        enBreaks.push(i + 2); // After the space
      }
    }

    // Find ZH sentence endings (。！？；)
    for (let i = 1; i < segment.zh.length - 1; i++) {
      if (/[。！？；，]/.test(segment.zh[i])) {
        zhBreaks.push(i + 1);
      }
    }

    return { en: enBreaks, zh: zhBreaks };
  }, [segment.en, segment.zh]);

  return (
    <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
      <div className="bg-gray-800 rounded-lg max-w-3xl w-full max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-gray-700">
          <h2 className="text-lg font-medium text-white">分割长台词</h2>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* Quick split buttons */}
          {sentenceBreaks.en.length > 0 && (
            <div className="flex flex-wrap gap-2">
              <span className="text-xs text-gray-400">按句子分割:</span>
              {sentenceBreaks.en.slice(0, 5).map((pos, i) => (
                <button
                  key={pos}
                  onClick={() => {
                    setEnSplitIndex(pos);
                    // Try to find matching ZH position
                    if (sentenceBreaks.zh[i]) {
                      setZhSplitIndex(sentenceBreaks.zh[i]);
                    }
                  }}
                  className="px-2 py-1 text-xs bg-gray-700 hover:bg-blue-600 rounded text-gray-300"
                >
                  位置 {i + 1}
                </button>
              ))}
            </div>
          )}

          {/* English text with slider */}
          <div>
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-400">English ({segment.en.length} chars)</label>
              <span className="text-xs text-gray-500">
                {formatTime(timePreview.part1.start)} - {formatTime(timePreview.part1.end)} | {formatTime(timePreview.part2.start)} - {formatTime(timePreview.part2.end)}
              </span>
            </div>
            <input
              type="range"
              min={1}
              max={segment.en.length - 1}
              value={enSplitIndex}
              onChange={(e) => setEnSplitIndex(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-600 rounded-full appearance-none cursor-pointer"
            />
            <div className="mt-2 grid grid-cols-2 gap-2">
              <div className="bg-gray-900 p-2 rounded text-sm text-white">
                <div className="text-xs text-green-400 mb-1">Part 1:</div>
                {preview.en1 || <span className="text-gray-500">(empty)</span>}
              </div>
              <div className="bg-gray-900 p-2 rounded text-sm text-white">
                <div className="text-xs text-blue-400 mb-1">Part 2:</div>
                {preview.en2 || <span className="text-gray-500">(empty)</span>}
              </div>
            </div>
          </div>

          {/* Chinese text with slider */}
          <div>
            <label className="text-sm text-gray-400 block mb-1">Chinese ({segment.zh.length} chars)</label>
            <input
              type="range"
              min={1}
              max={segment.zh.length - 1}
              value={zhSplitIndex}
              onChange={(e) => setZhSplitIndex(parseInt(e.target.value))}
              className="w-full h-2 bg-gray-600 rounded-full appearance-none cursor-pointer"
            />
            <div className="mt-2 grid grid-cols-2 gap-2">
              <div className="bg-gray-900 p-2 rounded text-sm text-yellow-400">
                <div className="text-xs text-green-400 mb-1">Part 1:</div>
                {preview.zh1 || <span className="text-gray-500">(empty)</span>}
              </div>
              <div className="bg-gray-900 p-2 rounded text-sm text-yellow-400">
                <div className="text-xs text-blue-400 mb-1">Part 2:</div>
                {preview.zh2 || <span className="text-gray-500">(empty)</span>}
              </div>
            </div>
          </div>

          {/* Error message */}
          {error && (
            <div className="text-red-400 text-sm bg-red-900/30 px-3 py-2 rounded">
              {error}
            </div>
          )}

          {/* Actions */}
          <div className="flex justify-end gap-2 pt-2">
            <button
              onClick={onClose}
              className="px-4 py-2 text-sm bg-gray-700 text-white rounded hover:bg-gray-600 transition"
              disabled={splitting}
            >
              取消
            </button>
            <button
              onClick={handleSplit}
              disabled={splitting}
              className="px-4 py-2 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 transition disabled:bg-blue-400"
            >
              {splitting ? "分割中..." : "确认分割"}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

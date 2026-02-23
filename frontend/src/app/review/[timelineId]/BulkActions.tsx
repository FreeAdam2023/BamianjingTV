"use client";

/**
 * BulkActions - Buttons for segment operations and video trimming
 */

import { useState, useCallback } from "react";
import type { EditableSegment } from "@/lib/types";
import {
  keepAllSegments,
  dropAllSegments,
  resetAllSegments,
  batchUpdateSegments,
  setVideoTrim,
  resetVideoTrim,
  cleanDisfluenciesWithProgress,
} from "@/lib/api";
import { useToast, useConfirm } from "@/components/ui";

interface BulkActionsProps {
  timelineId: string;
  currentTime?: number; // Current playhead position in seconds
  trimStart?: number; // Current video trim start
  trimEnd?: number | null; // Current video trim end
  sourceDuration?: number; // Total video duration
  segments?: EditableSegment[]; // Segments for time-range operations
  onUpdate?: () => void; // Callback after update
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  // Show one decimal place for sub-second precision
  const secsStr = secs < 10 ? `0${secs.toFixed(1)}` : secs.toFixed(1);
  return `${mins}:${secsStr}`;
}

export default function BulkActions({
  timelineId,
  currentTime = 0,
  trimStart = 0,
  trimEnd = null,
  sourceDuration = 0,
  segments = [],
  onUpdate,
}: BulkActionsProps) {
  const toast = useToast();
  const confirm = useConfirm();

  const [cleaning, setCleaning] = useState(false);
  const [cleanProgress, setCleanProgress] = useState("");

  // Unified range selector
  const [showPanel, setShowPanel] = useState(false);
  const [startInput, setStartInput] = useState("");
  const [endInput, setEndInput] = useState("");

  const hasTrim = trimStart > 0 || trimEnd !== null;
  const effectiveDuration = (trimEnd ?? sourceDuration) - trimStart;

  // Parse "M:SS", "M:SS.d", or "H:MM:SS.d" to seconds (supports decimals)
  const parseTime = (str: string): number | null => {
    const parts = str.trim().split(":");
    const nums = parts.map(Number);
    if (nums.some(isNaN)) return null;
    if (nums.length === 2) return nums[0] * 60 + nums[1];
    if (nums.length === 3) return nums[0] * 3600 + nums[1] * 60 + nums[2];
    return null;
  };

  // Compute overlapping segment count for display
  const overlappingCount = (() => {
    if (!startInput || !endInput) return null;
    const s = parseTime(startInput);
    const e = parseTime(endInput);
    if (s !== null && e !== null && e > s) {
      return segments.filter((seg) => seg.start >= s && seg.start < e).length;
    }
    return null;
  })();

  const handleKeepAll = async () => {
    const confirmed = await confirm({
      title: "全部保留",
      message: "确定要将所有片段标记为保留吗？",
      type: "info",
      confirmText: "全部保留",
    });
    if (confirmed) {
      try {
        const result = await keepAllSegments(timelineId);
        toast.success(`已将 ${result.updated} 个片段标记为保留`);
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
      }
    }
  };

  const handleDropAll = async () => {
    const confirmed = await confirm({
      title: "全部丢弃",
      message: "确定要将所有片段标记为丢弃吗？",
      type: "danger",
      confirmText: "全部丢弃",
    });
    if (confirmed) {
      try {
        const result = await dropAllSegments(timelineId);
        toast.success(`已将 ${result.updated} 个片段标记为丢弃`);
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
      }
    }
  };

  const handleResetAll = async () => {
    const confirmed = await confirm({
      title: "全部重置",
      message: "确定要将所有片段重置为未决定状态吗？",
      type: "warning",
      confirmText: "重置",
    });
    if (confirmed) {
      try {
        const result = await resetAllSegments(timelineId);
        toast.success(`已重置 ${result.updated} 个片段`);
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
      }
    }
  };

  const handleCleanDisfluencies = async () => {
    const confirmed = await confirm({
      title: "清理字幕",
      message: "将自动移除英文字幕中的 um/uh 等填充词和重复语句，并重新翻译中文。",
      type: "info",
      confirmText: "开始清理",
    });
    if (!confirmed) return;

    setCleaning(true);
    setCleanProgress("");
    try {
      const result = await cleanDisfluenciesWithProgress(timelineId, (data) => {
        if (data.type === "phase") {
          setCleanProgress(data.phase === "cleaning" ? "清理中..." : "翻译中...");
        } else if (data.type === "progress") {
          setCleanProgress(
            data.phase === "cleaning"
              ? `清理中... ${data.current}/${data.total}`
              : `翻译中... ${data.current}/${data.total}`
          );
        }
      });
      toast.success(`已清理 ${result.updated_count} 个片段`);
      if (onUpdate) onUpdate();
    } catch (err) {
      toast.error(
        "清理失败: " + (err instanceof Error ? err.message : "Unknown error")
      );
    } finally {
      setCleaning(false);
      setCleanProgress("");
    }
  };

  // Capture playhead to start/end inputs
  const handleCaptureStart = useCallback(() => {
    setStartInput(formatTime(currentTime));
    if (!showPanel) setShowPanel(true);
  }, [currentTime, showPanel]);

  const handleCaptureEnd = useCallback(() => {
    setEndInput(formatTime(currentTime));
    if (!showPanel) setShowPanel(true);
  }, [currentTime, showPanel]);

  // Apply video trim
  const handleApplyTrim = async () => {
    const startVal = startInput ? parseTime(startInput) : null;
    const endVal = endInput ? parseTime(endInput) : null;

    if (startInput && startVal === null) {
      toast.error("起点时间格式无效，请使用 M:SS.d");
      return;
    }
    if (endInput && endVal === null) {
      toast.error("终点时间格式无效，请使用 M:SS.d");
      return;
    }
    if (startVal !== null && endVal !== null && startVal >= endVal) {
      toast.error("起点必须小于终点");
      return;
    }
    if (!startInput && !endInput) {
      toast.error("请至少设置起点或终点");
      return;
    }

    const startStr = startVal !== null ? formatTime(startVal) : "0:00.0";
    const endStr = endVal !== null ? formatTime(endVal) : formatTime(sourceDuration);

    const confirmed = await confirm({
      title: "应用视频裁剪",
      message: `裁剪范围: ${startStr} ~ ${endStr}\n\n范围外的内容将被剪掉。`,
      type: "warning",
      confirmText: "应用裁剪",
    });

    if (confirmed) {
      try {
        await setVideoTrim(
          timelineId,
          startVal !== null ? startVal : undefined,
          endVal !== null ? endVal : undefined,
        );
        toast.success(`裁剪已应用: ${startStr} ~ ${endStr}`);
        setShowPanel(false);
        setStartInput("");
        setEndInput("");
        onUpdate?.();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
    }
  };

  const handleResetTrim = async () => {
    const confirmed = await confirm({
      title: "恢复完整视频",
      message: "确定要恢复显示完整视频吗？这会清除起点和终点的裁剪设置。",
      type: "info",
      confirmText: "恢复",
    });
    if (confirmed) {
      try {
        await resetVideoTrim(timelineId);
        toast.success("已恢复完整视频");
        setStartInput("");
        setEndInput("");
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
      }
    }
  };

  // Drop all segments overlapping the time range
  const handleRangeDrop = async () => {
    const startSec = parseTime(startInput);
    const endSec = parseTime(endInput);
    if (startSec === null || endSec === null) {
      toast.error("时间格式无效，请使用 M:SS.d 或 H:MM:SS.d");
      return;
    }
    if (startSec >= endSec) {
      toast.error("起始时间必须小于结束时间");
      return;
    }

    const overlapping = segments.filter(
      (seg) => seg.start >= startSec && seg.start < endSec
    );

    if (overlapping.length === 0) {
      toast.error("该时间范围内没有片段");
      return;
    }

    const confirmed = await confirm({
      title: "丢弃时间范围",
      message: `将丢弃 ${formatTime(startSec)} ~ ${formatTime(endSec)} 范围内的 ${overlapping.length} 个片段（视频+字幕）。`,
      type: "danger",
      confirmText: `丢弃 ${overlapping.length} 个片段`,
    });

    if (confirmed) {
      try {
        const result = await batchUpdateSegments(timelineId, {
          segment_ids: overlapping.map((s) => s.id),
          state: "drop",
        });
        toast.success(`已丢弃 ${result.updated} 个片段`);
        setShowPanel(false);
        setStartInput("");
        setEndInput("");
        onUpdate?.();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
    }
  };

  // Keep all segments in the time range
  const handleRangeKeep = async () => {
    const startSec = parseTime(startInput);
    const endSec = parseTime(endInput);
    if (startSec === null || endSec === null) {
      toast.error("时间格式无效，请使用 M:SS.d 或 H:MM:SS.d");
      return;
    }
    if (startSec >= endSec) {
      toast.error("起始时间必须小于结束时间");
      return;
    }

    // Permissive: any overlap counts for restore/keep
    const overlapping = segments.filter(
      (seg) => seg.start < endSec && seg.end > startSec
    );

    if (overlapping.length === 0) {
      toast.error("该时间范围内没有片段");
      return;
    }

    try {
      const result = await batchUpdateSegments(timelineId, {
        segment_ids: overlapping.map((s) => s.id),
        state: "keep",
      });
      toast.success(`已保留 ${result.updated} 个片段`);
      setShowPanel(false);
      setStartInput("");
      setEndInput("");
      onUpdate?.();
    } catch (err) {
      toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  };

  const handleClosePanel = () => {
    setShowPanel(false);
    setStartInput("");
    setEndInput("");
  };

  return (
    <div className="p-2 border-b border-gray-700 space-y-2">
      {/* Row 1: Keep All / Drop All / Reset */}
      <div className="flex gap-2">
        <button
          onClick={handleKeepAll}
          className="flex-1 py-1 text-xs bg-green-600 hover:bg-green-700 rounded"
        >
          Keep All
        </button>
        <button
          onClick={handleDropAll}
          className="flex-1 py-1 text-xs bg-red-600 hover:bg-red-700 rounded"
        >
          Drop All
        </button>
        <button
          onClick={handleResetAll}
          className="flex-1 py-1 text-xs bg-gray-600 hover:bg-gray-700 rounded"
        >
          Reset
        </button>
      </div>

      {/* Row 1.5: Clean Disfluencies */}
      <div className="flex gap-2">
        <button
          onClick={handleCleanDisfluencies}
          disabled={cleaning}
          className="flex-1 py-1 text-xs bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 disabled:cursor-not-allowed rounded"
        >
          {cleaning ? cleanProgress || "Cleaning..." : "Clean Subtitles"}
        </button>
      </div>

      {/* Row 2: Toggle button for unified range selector */}
      <div className="flex items-center gap-2">
        <button
          onClick={() => setShowPanel(!showPanel)}
          className="flex-1 py-1 text-xs bg-gray-600 hover:bg-gray-500 rounded flex items-center justify-center gap-1"
        >
          <span>✂️</span>
          <span>时间范围选择</span>
          <span className="text-[10px]">{showPanel ? "▴" : "▾"}</span>
        </button>
        {hasTrim && !showPanel && (
          <span className="text-[10px] text-green-400 shrink-0">已裁剪 ✓</span>
        )}
      </div>

      {/* Row 3: Unified panel */}
      {(showPanel || hasTrim) && (
        <div className="bg-gray-800/50 border border-gray-600/50 rounded p-2 space-y-2">
          {/* Input row */}
          <div className="flex items-center gap-1.5 text-xs">
            <button
              onClick={handleCaptureStart}
              className="w-6 h-6 flex items-center justify-center bg-gray-600 hover:bg-gray-500 rounded text-[10px] shrink-0"
              title={`捕获 ${formatTime(currentTime)} 为起点`}
            >
              ⏱
            </button>
            <input
              type="text"
              value={startInput}
              onChange={(e) => setStartInput(e.target.value)}
              placeholder="起点"
              className="w-[4.5rem] px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs text-center focus:border-blue-500 focus:outline-none"
            />
            <span className="text-gray-400">~</span>
            <button
              onClick={handleCaptureEnd}
              className="w-6 h-6 flex items-center justify-center bg-gray-600 hover:bg-gray-500 rounded text-[10px] shrink-0"
              title={`捕获 ${formatTime(currentTime)} 为终点`}
            >
              ⏱
            </button>
            <input
              type="text"
              value={endInput}
              onChange={(e) => setEndInput(e.target.value)}
              placeholder="终点"
              className="w-[4.5rem] px-1.5 py-0.5 bg-gray-700 border border-gray-600 rounded text-white text-xs text-center focus:border-blue-500 focus:outline-none"
            />
            {overlappingCount !== null && (
              <span className="text-gray-400 text-[10px] shrink-0">
                ({overlappingCount}个片段)
              </span>
            )}
            <span className="ml-auto text-gray-500 text-[10px] shrink-0">
              ⏱ {formatTime(currentTime)}
            </span>
          </div>

          {/* Action row */}
          <div className="flex gap-1.5">
            <button
              onClick={handleRangeDrop}
              className="flex-1 py-1 text-xs bg-red-600 hover:bg-red-700 rounded"
            >
              丢弃片段
            </button>
            <button
              onClick={handleRangeKeep}
              className="flex-1 py-1 text-xs bg-green-600 hover:bg-green-700 rounded"
            >
              保留片段
            </button>
            <button
              onClick={handleApplyTrim}
              className="flex-1 py-1 text-xs bg-purple-600 hover:bg-purple-700 rounded"
            >
              裁剪视频
            </button>
            <button
              onClick={handleClosePanel}
              className="px-2 py-1 text-xs bg-gray-600 hover:bg-gray-500 rounded"
              title="关闭面板"
            >
              ✕
            </button>
          </div>

          {/* Trim status row */}
          {hasTrim && (
            <div className="flex items-center gap-2 text-[10px] text-gray-400 border-t border-gray-600/50 pt-1.5">
              <span>
                已裁剪: {formatTime(trimStart)} ~ {formatTime(trimEnd ?? sourceDuration)} ({formatTime(effectiveDuration)})
              </span>
              <button
                onClick={handleResetTrim}
                className="px-2 py-0.5 text-[10px] bg-gray-600 hover:bg-gray-500 rounded"
              >
                恢复完整
              </button>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

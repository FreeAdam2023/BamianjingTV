"use client";

/**
 * BulkActions - Buttons for segment operations and video trimming
 */

import { useState } from "react";
import {
  keepAllSegments,
  dropAllSegments,
  resetAllSegments,
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
  onUpdate?: () => void; // Callback after update
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, "0")}`;
}

export default function BulkActions({
  timelineId,
  currentTime = 0,
  trimStart = 0,
  trimEnd = null,
  sourceDuration = 0,
  onUpdate,
}: BulkActionsProps) {
  const toast = useToast();
  const confirm = useConfirm();

  const [cleaning, setCleaning] = useState(false);
  const [cleanProgress, setCleanProgress] = useState("");

  const hasTrim = trimStart > 0 || trimEnd !== null;
  const effectiveDuration = (trimEnd ?? sourceDuration) - trimStart;

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

  // Video-level trim operations
  const handleTrimStart = async () => {
    const timeStr = formatTime(currentTime);
    const confirmed = await confirm({
      title: "设置视频起点",
      message: `将视频起点设为 ${timeStr}？\n\n这会剪掉 ${timeStr} 之前的所有内容（包括无字幕部分）。`,
      type: "warning",
      confirmText: `从 ${timeStr} 开始`,
    });
    if (confirmed) {
      try {
        const result = await setVideoTrim(timelineId, currentTime, undefined);
        toast.success(`视频起点已设为 ${timeStr}`);
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
      }
    }
  };

  const handleTrimEnd = async () => {
    const timeStr = formatTime(currentTime);
    const confirmed = await confirm({
      title: "设置视频终点",
      message: `将视频终点设为 ${timeStr}？\n\n这会剪掉 ${timeStr} 之后的所有内容。`,
      type: "warning",
      confirmText: `在 ${timeStr} 结束`,
    });
    if (confirmed) {
      try {
        const result = await setVideoTrim(timelineId, undefined, currentTime);
        toast.success(`视频终点已设为 ${timeStr}`);
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
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
        if (onUpdate) onUpdate();
      } catch (err) {
        toast.error(
          "操作失败: " + (err instanceof Error ? err.message : "Unknown error")
        );
      }
    }
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

      {/* Row 2: Video Trim Controls */}
      <div className="flex gap-2">
        <button
          onClick={handleTrimStart}
          className="flex-1 py-1 text-xs bg-purple-600 hover:bg-purple-700 rounded flex items-center justify-center gap-1"
          title={`设置视频起点为 ${formatTime(currentTime)}`}
        >
          <span>✂️</span>
          <span>Start @ {formatTime(currentTime)}</span>
        </button>
        <button
          onClick={handleTrimEnd}
          className="flex-1 py-1 text-xs bg-purple-600 hover:bg-purple-700 rounded flex items-center justify-center gap-1"
          title={`设置视频终点为 ${formatTime(currentTime)}`}
        >
          <span>End @ {formatTime(currentTime)}</span>
          <span>✂️</span>
        </button>
      </div>

      {/* Row 3: Current Trim Status (if any) */}
      {hasTrim && (
        <div className="flex items-center gap-2 text-xs bg-purple-900/50 rounded p-2">
          <span className="text-purple-300">
            📐 裁剪范围: {formatTime(trimStart)} - {formatTime(trimEnd ?? sourceDuration)}
            <span className="text-gray-400 ml-1">
              ({formatTime(effectiveDuration)})
            </span>
          </span>
          <button
            onClick={handleResetTrim}
            className="ml-auto px-2 py-0.5 bg-gray-600 hover:bg-gray-500 rounded text-white"
          >
            恢复
          </button>
        </div>
      )}
    </div>
  );
}

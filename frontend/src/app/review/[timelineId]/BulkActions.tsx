"use client";

/**
 * BulkActions - Buttons for keep all / drop all / reset all / drop by time
 */

import { keepAllSegments, dropAllSegments, resetAllSegments, dropSegmentsBefore, dropSegmentsAfter } from "@/lib/api";
import { useToast, useConfirm } from "@/components/ui";

interface BulkActionsProps {
  timelineId: string;
  currentTime?: number;  // Current playhead position in seconds
  onUpdate?: () => void; // Callback after update
}

function formatTime(seconds: number): string {
  const mins = Math.floor(seconds / 60);
  const secs = Math.floor(seconds % 60);
  return `${mins}:${secs.toString().padStart(2, '0')}`;
}

export default function BulkActions({ timelineId, currentTime = 0, onUpdate }: BulkActionsProps) {
  const toast = useToast();
  const confirm = useConfirm();

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
        window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
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
        window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
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
        else window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
    }
  };

  const handleDropBefore = async () => {
    const timeStr = formatTime(currentTime);
    const confirmed = await confirm({
      title: "丢弃之前片段",
      message: `确定要丢弃 ${timeStr} 之前的所有片段吗？这通常用于剪掉视频开头的等待时间。`,
      type: "warning",
      confirmText: `丢弃 ${timeStr} 之前`,
    });
    if (confirmed) {
      try {
        const result = await dropSegmentsBefore(timelineId, currentTime);
        toast.success(`已丢弃 ${result.updated} 个片段 (${timeStr} 之前)`);
        if (onUpdate) onUpdate();
        else window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
      }
    }
  };

  const handleDropAfter = async () => {
    const timeStr = formatTime(currentTime);
    const confirmed = await confirm({
      title: "丢弃之后片段",
      message: `确定要丢弃 ${timeStr} 之后的所有片段吗？这通常用于剪掉视频结尾部分。`,
      type: "warning",
      confirmText: `丢弃 ${timeStr} 之后`,
    });
    if (confirmed) {
      try {
        const result = await dropSegmentsAfter(timelineId, currentTime);
        toast.success(`已丢弃 ${result.updated} 个片段 (${timeStr} 之后)`);
        if (onUpdate) onUpdate();
        else window.location.reload();
      } catch (err) {
        toast.error("操作失败: " + (err instanceof Error ? err.message : "Unknown error"));
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
      {/* Row 2: Drop Before / Drop After (based on playhead) */}
      <div className="flex gap-2">
        <button
          onClick={handleDropBefore}
          className="flex-1 py-1 text-xs bg-orange-600 hover:bg-orange-700 rounded flex items-center justify-center gap-1"
          title={`丢弃 ${formatTime(currentTime)} 之前的所有片段`}
        >
          <span>✂️</span>
          <span>Drop Before {formatTime(currentTime)}</span>
        </button>
        <button
          onClick={handleDropAfter}
          className="flex-1 py-1 text-xs bg-orange-600 hover:bg-orange-700 rounded flex items-center justify-center gap-1"
          title={`丢弃 ${formatTime(currentTime)} 之后的所有片段`}
        >
          <span>Drop After {formatTime(currentTime)}</span>
          <span>✂️</span>
        </button>
      </div>
    </div>
  );
}

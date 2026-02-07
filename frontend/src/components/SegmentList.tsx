"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { EditableSegment, SegmentState, SegmentAnnotations, EntityAnnotation, IdiomAnnotation } from "@/lib/types";
import { formatDuration } from "@/lib/api";
import { ClickableSubtitle, EntityBadges, IdiomBadges } from "@/components/Cards";
import SplitSegmentModal from "./SplitSegmentModal";
import type { OpenWordCardOptions } from "@/hooks/useCardPopup";

interface SegmentListProps {
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onSegmentClick: (segmentId: number) => void;
  onStateChange: (segmentId: number, state: SegmentState) => void | Promise<void>;
  onTextChange?: (segmentId: number, en: string, zh: string) => void | Promise<void>;
  onSplitSegment?: (segmentId: number, enIndex: number, zhIndex: number) => Promise<void>;
  // NER annotations for segments (optional)
  segmentAnnotations?: Map<number, SegmentAnnotations>;
  // Force refresh entity recognition for a segment
  onRefreshAnnotations?: (segmentId: number) => Promise<void>;
  // Card handlers (passed from parent to display cards in video area)
  onWordClick?: (word: string, options?: OpenWordCardOptions) => void | Promise<void>;
  onEntityClick?: (entityIdOrText: string, position?: { x: number; y: number }) => void | Promise<void>;
  onIdiomClick?: (idiomText: string, position?: { x: number; y: number }) => void | Promise<void>;
  // Entity editing handlers
  onAddEntity?: (segmentId: number, segmentText: string) => void;
  onEditEntity?: (segmentId: number, segmentText: string, entity: EntityAnnotation) => void;
}

export default function SegmentList({
  segments,
  currentSegmentId,
  onSegmentClick,
  onStateChange,
  onTextChange,
  onSplitSegment,
  segmentAnnotations,
  onRefreshAnnotations,
  onWordClick,
  onEntityClick,
  onIdiomClick,
  onAddEntity,
  onEditEntity,
}: SegmentListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editEn, setEditEn] = useState("");
  const [editZh, setEditZh] = useState("");
  const [saving, setSaving] = useState(false);
  const [splittingSegment, setSplittingSegment] = useState<EditableSegment | null>(null);
  const [refreshingSegmentId, setRefreshingSegmentId] = useState<number | null>(null);

  // Check if segment is long enough to split (at least 50 chars EN or 25 chars ZH)
  const canSplit = (segment: EditableSegment) => {
    return segment.en.length >= 50 || segment.zh.length >= 25;
  };

  // Handle word click in subtitle
  const handleWordClick = useCallback((word: string, position: { x: number; y: number }) => {
    onWordClick?.(word, { position });
  }, [onWordClick]);

  // Handle entity click in badges
  const handleEntityClick = useCallback((entity: EntityAnnotation, position: { x: number; y: number }) => {
    // Use entity_id if available, otherwise search by text
    const entityIdOrText = entity.entity_id || entity.text;
    onEntityClick?.(entityIdOrText, position);
  }, [onEntityClick]);

  // Handle entity edit (right-click on badge)
  const handleEditEntity = useCallback((segmentId: number, segmentText: string, entity: EntityAnnotation) => {
    onEditEntity?.(segmentId, segmentText, entity);
  }, [onEditEntity]);

  // Handle idiom click in badges
  const handleIdiomClick = useCallback((idiom: IdiomAnnotation, position: { x: number; y: number }) => {
    onIdiomClick?.(idiom.text, position);
  }, [onIdiomClick]);

  // Auto-scroll to current segment
  useEffect(() => {
    if (currentSegmentId === null || !listRef.current) return;

    const element = listRef.current.querySelector(
      `[data-segment-id="${currentSegmentId}"]`
    );
    if (element) {
      element.scrollIntoView({
        behavior: "smooth",
        block: "center",
      });
    }
  }, [currentSegmentId]);

  const getStateClass = (state: SegmentState): string => {
    switch (state) {
      case "keep":
        return "segment-keep";
      case "drop":
        return "segment-drop";
      case "undecided":
      default:
        return "segment-undecided";
    }
  };

  const startEditing = (segment: EditableSegment) => {
    setEditingId(segment.id);
    setEditEn(segment.en);
    setEditZh(segment.zh);
  };

  const cancelEditing = () => {
    setEditingId(null);
    setEditEn("");
    setEditZh("");
  };

  const saveEditing = async (segmentId: number) => {
    if (onTextChange) {
      setSaving(true);
      try {
        await onTextChange(segmentId, editEn, editZh);
        setEditingId(null);
      } catch (err) {
        console.error("Failed to save:", err);
      } finally {
        setSaving(false);
      }
    }
  };

  // Handle double-click to edit
  const handleDoubleClick = (segment: EditableSegment, e: React.MouseEvent) => {
    e.stopPropagation();
    if (onTextChange && editingId !== segment.id) {
      startEditing(segment);
    }
  };

  return (
    <>
    <div ref={listRef} className="h-full overflow-y-auto space-y-2 p-2">
      {segments.map((segment) => (
        <div
          key={segment.id}
          data-segment-id={segment.id}
          className={`
            p-3 rounded-lg cursor-pointer transition
            ${getStateClass(segment.state)}
            ${segment.id === currentSegmentId ? "segment-active" : ""}
          `}
          onClick={() => onSegmentClick(segment.id)}
        >
          {/* Time and speaker */}
          <div className="flex justify-between items-center text-xs text-gray-400 mb-1">
            <span>
              {formatDuration(segment.start)} - {formatDuration(segment.end)}
            </span>
            <div className="flex items-center gap-2">
              {segment.speaker && (
                <span className="bg-gray-700 px-2 py-0.5 rounded">
                  {segment.speaker}
                </span>
              )}
              {/* Edit button */}
              {editingId !== segment.id && onTextChange && (
                <button
                  className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded hover:bg-blue-600 hover:text-white transition"
                  onClick={(e) => {
                    e.stopPropagation();
                    startEditing(segment);
                  }}
                  title="编辑字幕（或双击文本）"
                >
                  编辑
                </button>
              )}
              {/* Split button - only show for long segments */}
              {editingId !== segment.id && onSplitSegment && canSplit(segment) && (
                <button
                  className="px-2 py-0.5 text-xs bg-gray-700 text-orange-300 rounded hover:bg-orange-600 hover:text-white transition"
                  onClick={(e) => {
                    e.stopPropagation();
                    setSplittingSegment(segment);
                  }}
                  title="将长段落拆分为两段"
                >
                  拆分
                </button>
              )}
              {/* Refresh entity recognition button - only show on active segment */}
              {editingId !== segment.id && segment.id === currentSegmentId && onRefreshAnnotations && (
                <button
                  className="p-1 text-xs bg-gray-700 text-cyan-300 rounded hover:bg-cyan-600 hover:text-white transition disabled:opacity-50"
                  onClick={async (e) => {
                    e.stopPropagation();
                    setRefreshingSegmentId(segment.id);
                    try {
                      await onRefreshAnnotations(segment.id);
                    } finally {
                      setRefreshingSegmentId(null);
                    }
                  }}
                  disabled={refreshingSegmentId === segment.id}
                  title="刷新实体识别"
                >
                  {refreshingSegmentId === segment.id ? (
                    <svg className="w-3.5 h-3.5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                    </svg>
                  )}
                </button>
              )}
            </div>
          </div>

          {/* Text content - either editing or display mode */}
          {editingId === segment.id ? (
            <div className="space-y-2" onClick={(e) => e.stopPropagation()}>
              {/* English input */}
              <div>
                <label className="text-xs text-gray-500 block mb-1">英文:</label>
                <textarea
                  value={editEn}
                  onChange={(e) => setEditEn(e.target.value)}
                  className="w-full bg-gray-800 text-white text-sm p-2 rounded border border-gray-600 focus:border-blue-500 outline-none resize-none"
                  rows={2}
                  autoFocus
                  onKeyDown={(e) => {
                    if (e.key === "Escape") cancelEditing();
                  }}
                />
              </div>
              {/* Chinese input */}
              <div>
                <label className="text-xs text-gray-500 block mb-1">中文:</label>
                <textarea
                  value={editZh}
                  onChange={(e) => setEditZh(e.target.value)}
                  className="w-full bg-gray-800 text-yellow-400 text-sm p-2 rounded border border-gray-600 focus:border-blue-500 outline-none resize-none"
                  rows={2}
                  onKeyDown={(e) => {
                    if (e.key === "Escape") cancelEditing();
                    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) {
                      saveEditing(segment.id);
                    }
                  }}
                />
              </div>
              {/* Save/Cancel buttons */}
              <div className="flex gap-2 justify-end items-center">
                <span className="text-xs text-gray-500">Ctrl+Enter 保存，Esc 取消</span>
                <button
                  className="px-3 py-1 text-xs bg-gray-600 text-white rounded hover:bg-gray-500 transition"
                  onClick={cancelEditing}
                  disabled={saving}
                >
                  取消
                </button>
                <button
                  className="px-3 py-1 text-xs bg-blue-500 text-white rounded hover:bg-blue-400 transition disabled:bg-blue-400"
                  onClick={() => saveEditing(segment.id)}
                  disabled={saving}
                >
                  {saving ? "保存中..." : "保存"}
                </button>
              </div>
            </div>
          ) : (
            <div
              className="group cursor-text"
              onDoubleClick={(e) => handleDoubleClick(segment, e)}
              title="双击编辑"
            >
              {/* English text - clickable words for dictionary lookup */}
              <div className="text-white text-sm mb-1 group-hover:bg-gray-700/50 rounded px-1 -mx-1 transition">
                <ClickableSubtitle
                  text={segment.en}
                  onWordClick={handleWordClick}
                />
              </div>
              {/* Chinese text */}
              <div className="text-yellow-400 text-sm mb-2 group-hover:bg-gray-700/50 rounded px-1 -mx-1 transition">
                {segment.zh}
              </div>
              {/* Entity badges - show if annotations available */}
              {segmentAnnotations?.get(segment.id)?.entities && (
                <div className="flex items-center gap-1 mt-1">
                  <EntityBadges
                    entities={segmentAnnotations.get(segment.id)!.entities}
                    onEntityClick={handleEntityClick}
                    onEditEntity={onEditEntity ? (entity) => handleEditEntity(segment.id, segment.en, entity) : undefined}
                    className="flex-1"
                  />
                  {onAddEntity && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAddEntity(segment.id, segment.en);
                      }}
                      className="p-1 text-gray-400 hover:text-cyan-400 hover:bg-cyan-500/20 rounded transition-colors"
                      title="添加实体"
                    >
                      <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
              {/* Idiom badges - show if annotations available */}
              {segmentAnnotations?.get(segment.id)?.idioms && (segmentAnnotations.get(segment.id)!.idioms?.length ?? 0) > 0 && (
                <div className="mt-1">
                  <IdiomBadges
                    idioms={segmentAnnotations.get(segment.id)!.idioms!}
                    onIdiomClick={handleIdiomClick}
                  />
                </div>
              )}
              {/* Show add button even when no entities exist */}
              {!segmentAnnotations?.get(segment.id)?.entities && segment.id === currentSegmentId && onAddEntity && (
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    onAddEntity(segment.id, segment.en);
                  }}
                  className="mt-1 px-2 py-0.5 text-xs text-gray-400 hover:text-cyan-400 border border-dashed border-gray-600 hover:border-cyan-500 rounded-full transition-colors flex items-center gap-1"
                  title="添加实体"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <span>添加实体</span>
                </button>
              )}
            </div>
          )}

          {/* State buttons - hide when editing */}
          {editingId !== segment.id && (
            <div className="flex gap-2" onClick={(e) => e.stopPropagation()}>
              <button
                className={`
                  flex-1 py-1 px-2 text-xs rounded transition
                  ${
                    segment.state === "keep"
                      ? "bg-green-500 text-white"
                      : "bg-gray-700 text-gray-300 hover:bg-green-600"
                  }
                `}
                onClick={() => onStateChange(segment.id, "keep")}
                title="Shift+K"
              >
                保留
              </button>
              <button
                className={`
                  flex-1 py-1 px-2 text-xs rounded transition
                  ${
                    segment.state === "drop"
                      ? "bg-red-500 text-white"
                      : "bg-gray-700 text-gray-300 hover:bg-red-600"
                  }
                `}
                onClick={() => onStateChange(segment.id, "drop")}
                title="D"
              >
                丢弃
              </button>
              <button
                className={`
                  flex-1 py-1 px-2 text-xs rounded transition
                  ${
                    segment.state === "undecided"
                      ? "bg-gray-500 text-white"
                      : "bg-gray-700 text-gray-300 hover:bg-gray-500"
                  }
                `}
                onClick={() => onStateChange(segment.id, "undecided")}
                title="U"
              >
                ?
              </button>
            </div>
          )}
        </div>
      ))}
    </div>

    {/* Split segment modal */}
    {splittingSegment && onSplitSegment && (
      <SplitSegmentModal
        segment={splittingSegment}
        onSplit={async (enIndex, zhIndex) => {
          await onSplitSegment(splittingSegment.id, enIndex, zhIndex);
        }}
        onClose={() => setSplittingSegment(null)}
      />
    )}
    </>
  );
}

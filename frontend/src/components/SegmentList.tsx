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
  onTimeChange?: (segmentId: number, start: number, end: number) => void | Promise<void>;
  onSplitSegment?: (segmentId: number, enIndex: number, zhIndex: number) => Promise<void>;
  // NER annotations for segments (optional)
  segmentAnnotations?: Map<number, SegmentAnnotations>;
  // Separate refresh for entities and idioms
  onRefreshEntities?: (segmentId: number) => Promise<void>;
  onRefreshIdioms?: (segmentId: number) => Promise<void>;
  // Card handlers (passed from parent to display cards in video area)
  onWordClick?: (word: string, options?: OpenWordCardOptions) => void | Promise<void>;
  onEntityClick?: (entityIdOrText: string, position?: { x: number; y: number }) => void | Promise<void>;
  onIdiomClick?: (idiomText: string, position?: { x: number; y: number }) => void | Promise<void>;
  // Entity editing handlers
  onAddEntity?: (segmentId: number, segmentText: string) => void;
  onEditEntity?: (segmentId: number, segmentText: string, entity: EntityAnnotation) => void;
  // Idiom editing handlers
  onAddIdiom?: (segmentId: number, segmentText: string) => void;
  onEditIdiom?: (segmentId: number, segmentText: string, idiom: IdiomAnnotation) => void;
  // Bookmark handlers
  onToggleBookmark?: (segmentId: number) => void;
  bookmarkFilter?: boolean | null;  // null = show all, true = bookmarked only
}

export default function SegmentList({
  segments,
  currentSegmentId,
  onSegmentClick,
  onStateChange,
  onTextChange,
  onTimeChange,
  onSplitSegment,
  segmentAnnotations,
  onRefreshEntities,
  onRefreshIdioms,
  onWordClick,
  onEntityClick,
  onIdiomClick,
  onAddEntity,
  onEditEntity,
  onAddIdiom,
  onEditIdiom,
  onToggleBookmark,
  bookmarkFilter,
}: SegmentListProps) {
  const listRef = useRef<HTMLDivElement>(null);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [editEn, setEditEn] = useState("");
  const [editZh, setEditZh] = useState("");
  const [saving, setSaving] = useState(false);
  const [splittingSegment, setSplittingSegment] = useState<EditableSegment | null>(null);
  const [refreshingEntities, setRefreshingEntities] = useState<number | null>(null);
  const [refreshingIdioms, setRefreshingIdioms] = useState<number | null>(null);
  const [editingTimeId, setEditingTimeId] = useState<number | null>(null);
  const [editStart, setEditStart] = useState("");
  const [editEnd, setEditEnd] = useState("");
  const [savingTime, setSavingTime] = useState(false);

  // Filter segments by bookmark status
  const filteredSegments = bookmarkFilter === true
    ? segments.filter((s) => s.bookmarked)
    : segments;

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

  // Handle idiom edit (right-click on badge)
  const handleEditIdiom = useCallback((segmentId: number, segmentText: string, idiom: IdiomAnnotation) => {
    onEditIdiom?.(segmentId, segmentText, idiom);
  }, [onEditIdiom]);

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

  // Parse "H:MM:SS" or "M:SS" or "M:SS.s" back to seconds
  const parseTimeInput = (str: string): number | null => {
    const parts = str.trim().split(":").map(Number);
    if (parts.some(isNaN)) return null;
    if (parts.length === 3) return parts[0] * 3600 + parts[1] * 60 + parts[2];
    if (parts.length === 2) return parts[0] * 60 + parts[1];
    return null;
  };

  const startEditingTime = (segment: EditableSegment) => {
    setEditingTimeId(segment.id);
    setEditStart(formatDuration(segment.start));
    setEditEnd(formatDuration(segment.end));
  };

  const cancelEditingTime = () => {
    setEditingTimeId(null);
  };

  const saveEditingTime = async (segmentId: number) => {
    if (!onTimeChange) return;
    const s = parseTimeInput(editStart);
    const e = parseTimeInput(editEnd);
    if (s === null || e === null || s >= e) return;
    setSavingTime(true);
    try {
      await onTimeChange(segmentId, s, e);
      setEditingTimeId(null);
    } catch (err) {
      console.error("Failed to save time:", err);
    } finally {
      setSavingTime(false);
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
    <div ref={listRef} className="h-full overflow-y-auto divide-y divide-white/5 p-2">
      {filteredSegments.map((segment) => (
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
            {editingTimeId === segment.id ? (
              <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                <input
                  value={editStart}
                  onChange={(e) => setEditStart(e.target.value)}
                  className="w-16 bg-gray-800 text-white text-xs px-1.5 py-0.5 rounded border border-gray-600 focus:border-blue-500 outline-none text-center"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveEditingTime(segment.id);
                    if (e.key === "Escape") cancelEditingTime();
                  }}
                  autoFocus
                />
                <span>-</span>
                <input
                  value={editEnd}
                  onChange={(e) => setEditEnd(e.target.value)}
                  className="w-16 bg-gray-800 text-white text-xs px-1.5 py-0.5 rounded border border-gray-600 focus:border-blue-500 outline-none text-center"
                  onKeyDown={(e) => {
                    if (e.key === "Enter") saveEditingTime(segment.id);
                    if (e.key === "Escape") cancelEditingTime();
                  }}
                />
                <button
                  onClick={() => saveEditingTime(segment.id)}
                  disabled={savingTime}
                  className="px-1.5 py-0.5 text-xs bg-blue-600 text-white rounded hover:bg-blue-700 disabled:opacity-50"
                >
                  ✓
                </button>
                <button
                  onClick={cancelEditingTime}
                  className="px-1.5 py-0.5 text-xs bg-gray-700 text-gray-300 rounded hover:bg-gray-600"
                >
                  ✕
                </button>
              </div>
            ) : (
              <span
                className={onTimeChange ? "cursor-pointer hover:text-blue-400 transition" : ""}
                onClick={(e) => {
                  if (onTimeChange) {
                    e.stopPropagation();
                    startEditingTime(segment);
                  }
                }}
                title={onTimeChange ? "点击编辑时间戳" : undefined}
              >
                {formatDuration(segment.start)} - {formatDuration(segment.end)}
              </span>
            )}
            <div className="flex items-center gap-2">
              {segment.speaker && (
                <span className="bg-gray-700 px-2 py-0.5 rounded">
                  {segment.speaker}
                </span>
              )}
              {/* Bookmark button */}
              {editingId !== segment.id && onToggleBookmark && (
                <button
                  className={`p-1 text-xs rounded transition ${
                    segment.bookmarked
                      ? "text-amber-400 bg-amber-500/20 hover:bg-amber-500/30"
                      : "text-gray-400 bg-gray-700 hover:text-amber-400 hover:bg-amber-500/20"
                  }`}
                  onClick={(e) => {
                    e.stopPropagation();
                    onToggleBookmark(segment.id);
                  }}
                  title={segment.bookmarked ? "取消书签" : "添加书签 (稍後再閱)"}
                >
                  {segment.bookmarked ? (
                    <svg className="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                      <path d="M5 4a2 2 0 012-2h6a2 2 0 012 2v14l-5-2.5L5 18V4z" />
                    </svg>
                  ) : (
                    <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z" />
                    </svg>
                  )}
                </button>
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
              {/* Refresh buttons moved to badge rows */}
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
              {/* Entity row — label + badges + refresh + add */}
              {(segmentAnnotations?.get(segment.id)?.entities || (segment.id === currentSegmentId && onAddEntity)) && (
                <div className="flex items-center gap-1 mt-1">
                  <span className="text-[10px] text-cyan-400/70 font-medium shrink-0">实体</span>
                  {segmentAnnotations?.get(segment.id)?.entities ? (
                    <EntityBadges
                      entities={segmentAnnotations.get(segment.id)!.entities}
                      onEntityClick={handleEntityClick}
                      onEditEntity={onEditEntity ? (entity) => handleEditEntity(segment.id, segment.en, entity) : undefined}
                      className="flex-1"
                    />
                  ) : (
                    <div className="flex-1" />
                  )}
                  {segment.id === currentSegmentId && onRefreshEntities && (
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        setRefreshingEntities(segment.id);
                        try { await onRefreshEntities(segment.id); } finally { setRefreshingEntities(null); }
                      }}
                      disabled={refreshingEntities === segment.id}
                      className="p-0.5 text-cyan-400/60 hover:text-cyan-300 hover:bg-cyan-500/20 rounded transition-colors disabled:opacity-50"
                      title="刷新实体识别"
                    >
                      {refreshingEntities === segment.id ? (
                        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      )}
                    </button>
                  )}
                  {onAddEntity && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAddEntity(segment.id, segment.en);
                      }}
                      className="p-0.5 text-gray-400 hover:text-cyan-400 hover:bg-cyan-500/20 rounded transition-colors"
                      title="添加实体"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
              {/* Idiom row — label + badges + refresh + add */}
              {((segmentAnnotations?.get(segment.id)?.idioms?.length ?? 0) > 0 || (segment.id === currentSegmentId && onAddIdiom)) && (
                <div className="flex items-center gap-1 mt-1">
                  <span className="text-[10px] text-amber-400/70 font-medium shrink-0">俚语</span>
                  {(segmentAnnotations?.get(segment.id)?.idioms?.length ?? 0) > 0 ? (
                    <IdiomBadges
                      idioms={segmentAnnotations!.get(segment.id)!.idioms!}
                      onIdiomClick={handleIdiomClick}
                      onEditIdiom={onEditIdiom ? (idiom) => handleEditIdiom(segment.id, segment.en, idiom) : undefined}
                      className="flex-1"
                    />
                  ) : (
                    <div className="flex-1" />
                  )}
                  {segment.id === currentSegmentId && onRefreshIdioms && (
                    <button
                      onClick={async (e) => {
                        e.stopPropagation();
                        setRefreshingIdioms(segment.id);
                        try { await onRefreshIdioms(segment.id); } finally { setRefreshingIdioms(null); }
                      }}
                      disabled={refreshingIdioms === segment.id}
                      className="p-0.5 text-amber-400/60 hover:text-amber-300 hover:bg-amber-500/20 rounded transition-colors disabled:opacity-50"
                      title="刷新俚语识别"
                    >
                      {refreshingIdioms === segment.id ? (
                        <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                        </svg>
                      ) : (
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                        </svg>
                      )}
                    </button>
                  )}
                  {onAddIdiom && (
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onAddIdiom(segment.id, segment.en);
                      }}
                      className="p-0.5 text-gray-400 hover:text-amber-400 hover:bg-amber-500/20 rounded transition-colors"
                      title="添加俚语"
                    >
                      <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                      </svg>
                    </button>
                  )}
                </div>
              )}
            </div>
          )}

          {/* State toggle - hide when editing */}
          {editingId !== segment.id && (
            <div onClick={(e) => e.stopPropagation()}>
              {segment.state === "drop" ? (
                <button
                  className="w-full py-1 px-3 text-xs rounded transition bg-red-500/20 text-red-400 border border-red-500/30 hover:bg-green-500/20 hover:text-green-400 hover:border-green-500/30"
                  onClick={() => onStateChange(segment.id, "keep")}
                  title="K: 恢复"
                >
                  已丢弃 · 恢复
                </button>
              ) : (
                <button
                  className="w-full py-1 px-3 text-xs rounded transition text-gray-500 border border-white/10 hover:bg-red-500/20 hover:text-red-400 hover:border-red-500/30"
                  onClick={() => onStateChange(segment.id, "drop")}
                  title="D: 丢弃"
                >
                  丢弃
                </button>
              )}
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

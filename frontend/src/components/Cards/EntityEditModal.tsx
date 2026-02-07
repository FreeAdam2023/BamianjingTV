"use client";

/**
 * EntityEditModal - Modal for adding/editing/deleting entities
 */

import { useState, useCallback, useEffect, useRef } from "react";
import type { EntityAnnotation } from "@/lib/types";
import { addManualEntity, deleteSegmentEntity } from "@/lib/api";

/**
 * Extract article title from Wikipedia URL
 * Supports formats:
 * - https://en.wikipedia.org/wiki/Article_Name
 * - https://zh.wikipedia.org/wiki/Article_Name
 * - https://zh.wikipedia.org/zh-cn/Article_Name (Chinese variants)
 * - https://zh.wikipedia.org/zh-tw/Article_Name
 */
function extractWikipediaTitle(url: string): { title: string; lang: string } | null {
  try {
    // Standard wiki path: /wiki/Title
    const wikiMatch = url.match(/(\w+)\.wikipedia\.org\/wiki\/(.+?)(?:\?|#|$)/);
    if (wikiMatch) {
      return {
        lang: wikiMatch[1],
        title: decodeURIComponent(wikiMatch[2].replace(/_/g, " ")),
      };
    }

    // Chinese variant paths: /zh-cn/Title, /zh-tw/Title, etc.
    const zhMatch = url.match(/(\w+)\.wikipedia\.org\/zh-\w+\/(.+?)(?:\?|#|$)/);
    if (zhMatch) {
      return {
        lang: zhMatch[1], // "zh"
        title: decodeURIComponent(zhMatch[2].replace(/_/g, " ")),
      };
    }
  } catch {
    // ignore
  }
  return null;
}

/**
 * Resolve Wikipedia URL to Wikidata QID
 */
async function resolveWikipediaToQID(url: string): Promise<string | null> {
  const parsed = extractWikipediaTitle(url);
  if (!parsed) return null;

  try {
    const response = await fetch(
      `https://www.wikidata.org/w/api.php?` +
        new URLSearchParams({
          action: "wbgetentities",
          sites: `${parsed.lang}wiki`,
          titles: parsed.title,
          format: "json",
          origin: "*",
          props: "labels",
        })
    );

    if (response.ok) {
      const data = await response.json();
      const entities = data.entities || {};
      for (const qid of Object.keys(entities)) {
        if (qid.startsWith("Q") && !entities[qid].missing) {
          return qid;
        }
      }
    }
  } catch (err) {
    console.error("Failed to resolve Wikipedia URL:", err);
  }
  return null;
}

interface EntityEditModalProps {
  isOpen: boolean;
  onClose: () => void;
  timelineId: string;
  segmentId: number;
  segmentText: string;
  /** Existing entity to edit, or null for adding new */
  entity?: EntityAnnotation | null;
  onSuccess: (newEntityId?: string) => void;
}

export default function EntityEditModal({
  isOpen,
  onClose,
  timelineId,
  segmentId,
  segmentText,
  entity,
  onSuccess,
}: EntityEditModalProps) {
  const [text, setText] = useState(entity?.text || "");
  const [wikipediaUrl, setWikipediaUrl] = useState("");
  const [entityId, setEntityId] = useState(entity?.entity_id || "");
  const [loading, setLoading] = useState(false);
  const [resolving, setResolving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const resolveTimeoutRef = useRef<NodeJS.Timeout | null>(null);

  const isEditing = !!entity;

  // Reset form when modal opens with new entity
  useEffect(() => {
    if (isOpen) {
      setText(entity?.text || "");
      setWikipediaUrl("");
      setEntityId(entity?.entity_id || "");
      setError(null);
      setDeleteConfirm(false);
      setResolving(false);
    }
  }, [isOpen, entity, segmentId]);

  // Auto-resolve Wikipedia URL to QID (debounced)
  useEffect(() => {
    // Clear previous timeout
    if (resolveTimeoutRef.current) {
      clearTimeout(resolveTimeoutRef.current);
    }

    // Check if URL looks like a Wikipedia URL
    // Check if URL looks like a Wikipedia URL (including Chinese variants like /zh-cn/)
    if (!wikipediaUrl || !wikipediaUrl.includes("wikipedia.org/")) {
      return;
    }

    setResolving(true);
    resolveTimeoutRef.current = setTimeout(async () => {
      const qid = await resolveWikipediaToQID(wikipediaUrl);
      if (qid) {
        setEntityId(qid);
        setError(null);
      } else {
        setError("无法从该链接解析 Wikidata QID");
      }
      setResolving(false);
    }, 500); // 500ms debounce

    return () => {
      if (resolveTimeoutRef.current) {
        clearTimeout(resolveTimeoutRef.current);
      }
    };
  }, [wikipediaUrl]);

  // Handle save
  const handleSave = async () => {
    if (!text.trim()) {
      setError("请输入实体文本");
      return;
    }

    if (!wikipediaUrl.trim() && !entityId.trim()) {
      setError("请输入 Wikipedia 链接或 Wikidata QID");
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const result = await addManualEntity(timelineId, segmentId, {
        segment_id: segmentId,
        text: text.trim(),
        wikipedia_url: wikipediaUrl.trim() || undefined,
        entity_id: entityId.trim() || undefined,
      });

      if (result.success) {
        onSuccess(result.entity_id);
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

  // Handle delete
  const handleDelete = async () => {
    if (!entity) return;

    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }

    setLoading(true);
    setError(null);

    try {
      await deleteSegmentEntity(timelineId, segmentId, entity.text);
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
            {isEditing ? "编辑实体" : "添加实体"}
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
          {/* Entity text */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              实体文本 <span className="text-red-400">*</span>
            </label>
            <input
              type="text"
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="例如: New York City"
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-gray-500">
              在字幕中显示的文本
            </p>
          </div>

          {/* Wikipedia URL */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Wikipedia 链接
              {resolving && (
                <span className="ml-2 text-cyan-400">
                  <svg className="inline w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  <span className="ml-1">解析中...</span>
                </span>
              )}
            </label>
            <input
              type="url"
              value={wikipediaUrl}
              onChange={(e) => setWikipediaUrl(e.target.value)}
              placeholder="https://en.wikipedia.org/wiki/..."
              className="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none"
            />
            <p className="mt-1 text-xs text-gray-500">
              输入链接后自动解析 Wikidata QID
            </p>
          </div>

          {/* Or divider */}
          <div className="flex items-center gap-2">
            <div className="flex-1 border-t border-gray-600" />
            <span className="text-xs text-gray-500">或</span>
            <div className="flex-1 border-t border-gray-600" />
          </div>

          {/* Wikidata QID */}
          <div>
            <label className="block text-sm text-gray-400 mb-1">
              Wikidata QID
              {wikipediaUrl && entityId && !resolving && (
                <span className="ml-2 text-green-400 text-xs">✓ 已解析</span>
              )}
            </label>
            <input
              type="text"
              value={entityId}
              onChange={(e) => setEntityId(e.target.value)}
              placeholder="例如: Q60"
              className={`w-full px-3 py-2 bg-gray-700 border rounded text-white placeholder-gray-500 focus:border-cyan-500 focus:outline-none ${
                wikipediaUrl && entityId && !resolving
                  ? "border-green-500/50"
                  : "border-gray-600"
              }`}
            />
            <p className="mt-1 text-xs text-gray-500">
              直接输入 Wikidata ID（可在 wikidata.org 查找）
            </p>
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
              className="px-4 py-1.5 text-sm bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-800 text-white rounded transition-colors flex items-center gap-2"
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

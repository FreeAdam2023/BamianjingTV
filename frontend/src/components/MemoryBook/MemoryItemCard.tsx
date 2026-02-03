"use client";

/**
 * MemoryItemCard - Display a single memory item
 */

import { useState } from "react";
import type { MemoryItem, MemoryItemType, WordCard, EntityCard } from "@/lib/types";
import { getMemoryItemTypeIcon, deleteMemoryItem, updateMemoryItem } from "@/lib/api";

interface MemoryItemCardProps {
  item: MemoryItem;
  bookId: string;
  onDelete?: (itemId: string) => void;
  onUpdate?: (item: MemoryItem) => void;
}

export default function MemoryItemCard({
  item,
  bookId,
  onDelete,
  onUpdate,
}: MemoryItemCardProps) {
  const [isDeleting, setIsDeleting] = useState(false);
  const [isEditing, setIsEditing] = useState(false);
  const [notes, setNotes] = useState(item.user_notes);
  const [isSaving, setIsSaving] = useState(false);

  const handleDelete = async () => {
    if (!confirm("Delete this item from your collection?")) return;
    setIsDeleting(true);
    try {
      await deleteMemoryItem(bookId, item.item_id);
      onDelete?.(item.item_id);
    } catch (err) {
      console.error("Failed to delete item:", err);
    } finally {
      setIsDeleting(false);
    }
  };

  const handleSaveNotes = async () => {
    setIsSaving(true);
    try {
      const updated = await updateMemoryItem(bookId, item.item_id, {
        user_notes: notes,
      });
      onUpdate?.(updated);
      setIsEditing(false);
    } catch (err) {
      console.error("Failed to save notes:", err);
    } finally {
      setIsSaving(false);
    }
  };

  const renderWordContent = () => {
    const cardData = item.card_data as unknown as WordCard | null;
    if (!cardData) {
      return <span className="text-xl font-bold">{item.target_id}</span>;
    }

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xl font-bold text-blue-400">{cardData.word}</span>
          {cardData.pronunciations?.[0]?.ipa && (
            <span className="text-sm text-gray-500">{cardData.pronunciations[0].ipa}</span>
          )}
        </div>
        {cardData.senses?.[0] && (
          <div className="text-sm">
            <span className="text-gray-500 italic">{cardData.senses[0].part_of_speech}</span>
            <span className="ml-2 text-gray-300">{cardData.senses[0].definition}</span>
          </div>
        )}
      </div>
    );
  };

  const renderEntityContent = () => {
    const cardData = item.card_data as unknown as EntityCard | null;
    if (!cardData) {
      return <span className="text-xl font-bold">{item.target_id}</span>;
    }

    return (
      <div className="space-y-2">
        <div className="flex items-center gap-2">
          <span className="text-xl font-bold text-green-400">{cardData.name}</span>
          <span className="text-xs text-gray-500 uppercase">{cardData.entity_type}</span>
        </div>
        {cardData.description && (
          <p className="text-sm text-gray-300 line-clamp-2">{cardData.description}</p>
        )}
      </div>
    );
  };

  const renderObservationContent = () => {
    return (
      <div className="space-y-2">
        <span className="text-lg font-medium text-orange-400">Observation</span>
        <p className="text-sm text-gray-300">{item.target_id}</p>
      </div>
    );
  };

  const renderContent = () => {
    switch (item.target_type) {
      case "word":
        return renderWordContent();
      case "entity":
        return renderEntityContent();
      case "observation":
        return renderObservationContent();
      default:
        return <span>{item.target_id}</span>;
    }
  };

  const formatDate = (dateStr: string) => {
    const date = new Date(dateStr);
    return date.toLocaleDateString();
  };

  return (
    <div className="bg-gray-800 rounded-lg p-4 border border-gray-700 hover:border-gray-600 transition-colors">
      {/* Header */}
      <div className="flex items-start justify-between mb-3">
        <div className="flex items-center gap-2">
          <span className="text-lg">{getMemoryItemTypeIcon(item.target_type)}</span>
          <span className="text-xs text-gray-500">{formatDate(item.created_at)}</span>
        </div>
        <button
          onClick={handleDelete}
          disabled={isDeleting}
          className="p-1 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400 transition-colors disabled:opacity-50"
          title="Delete"
        >
          {isDeleting ? (
            <span className="inline-block w-4 h-4 border-2 border-gray-500/30 border-t-gray-500 rounded-full animate-spin" />
          ) : (
            <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                strokeWidth={2}
                d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
              />
            </svg>
          )}
        </button>
      </div>

      {/* Main content */}
      {renderContent()}

      {/* Source context */}
      {item.source_segment_text && (
        <div className="mt-3 p-2 bg-gray-900 rounded text-sm text-gray-400 italic">
          "{item.source_segment_text}"
        </div>
      )}

      {/* Notes */}
      <div className="mt-3 pt-3 border-t border-gray-700">
        {isEditing ? (
          <div className="space-y-2">
            <textarea
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              className="input-sm text-sm"
              rows={2}
              placeholder="Add notes..."
            />
            <div className="flex justify-end gap-2">
              <button
                onClick={() => {
                  setNotes(item.user_notes);
                  setIsEditing(false);
                }}
                className="px-3 py-1 text-sm text-gray-400 hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleSaveNotes}
                disabled={isSaving}
                className="px-3 py-1 text-sm bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50"
              >
                {isSaving ? "Saving..." : "Save"}
              </button>
            </div>
          </div>
        ) : (
          <div
            onClick={() => setIsEditing(true)}
            className="cursor-pointer text-sm text-gray-500 hover:text-gray-300"
          >
            {item.user_notes || "Click to add notes..."}
          </div>
        )}
      </div>

      {/* Tags */}
      {item.tags.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1">
          {item.tags.map((tag) => (
            <span
              key={tag}
              className="px-2 py-0.5 text-xs bg-gray-700 text-gray-300 rounded"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

"use client";

import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import type { CardPopupState } from "@/hooks/useCardPopup";
import WordCard from "./WordCard";
import EntityCard from "./EntityCard";

interface CardPopupContainerProps {
  state: CardPopupState;
  onClose: () => void;
  onAddWordToMemory?: (word: string) => void;
}

/**
 * CardPopupContainer - Renders card popup with smart positioning
 * Uses a portal to render outside the component hierarchy
 */
export default function CardPopupContainer({
  state,
  onClose,
  onAddWordToMemory,
}: CardPopupContainerProps) {
  const popupRef = useRef<HTMLDivElement>(null);
  const [adjustedPosition, setAdjustedPosition] = useState(state.position);
  const [mounted, setMounted] = useState(false);

  // Handle client-side mounting for portal
  useEffect(() => {
    setMounted(true);
  }, []);

  // Adjust position to keep popup in viewport
  useEffect(() => {
    if (!state.isOpen || !popupRef.current) {
      setAdjustedPosition(state.position);
      return;
    }

    const popup = popupRef.current;
    const rect = popup.getBoundingClientRect();
    const padding = 16;

    let { x, y } = state.position;

    // Adjust horizontal position
    if (x + rect.width / 2 > window.innerWidth - padding) {
      x = window.innerWidth - rect.width / 2 - padding;
    }
    if (x - rect.width / 2 < padding) {
      x = rect.width / 2 + padding;
    }

    // Adjust vertical position - flip above if not enough space below
    if (y + rect.height > window.innerHeight - padding) {
      y = state.position.y - rect.height - 8;
    }

    setAdjustedPosition({ x, y });
  }, [state.isOpen, state.position]);

  // Close on escape key
  useEffect(() => {
    if (!state.isOpen) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onClose();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [state.isOpen, onClose]);

  // Close on click outside
  useEffect(() => {
    if (!state.isOpen) return;

    const handleClickOutside = (e: MouseEvent) => {
      if (popupRef.current && !popupRef.current.contains(e.target as Node)) {
        onClose();
      }
    };

    // Delay adding listener to prevent immediate close from the triggering click
    const timer = setTimeout(() => {
      document.addEventListener("mousedown", handleClickOutside);
    }, 100);

    return () => {
      clearTimeout(timer);
      document.removeEventListener("mousedown", handleClickOutside);
    };
  }, [state.isOpen, onClose]);

  if (!mounted || !state.isOpen) return null;

  const content = (
    <div
      ref={popupRef}
      className="fixed z-50 animate-fade-in"
      style={{
        left: adjustedPosition.x,
        top: adjustedPosition.y,
        transform: "translateX(-50%)",
      }}
    >
      {/* Loading state */}
      {state.loading && (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl p-6 w-80">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-500 border-t-transparent" />
            <span className="text-gray-300">Loading...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {state.error && !state.loading && (
        <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl p-4 w-80">
          <div className="flex items-center justify-between">
            <span className="text-red-400 text-sm">{state.error}</span>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white p-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      {/* Word card */}
      {state.type === "word" && state.wordCard && !state.loading && (
        <WordCard
          card={state.wordCard}
          onClose={onClose}
          onAddToMemory={onAddWordToMemory}
        />
      )}

      {/* Entity card */}
      {state.type === "entity" && state.entityCard && !state.loading && (
        <EntityCard
          card={state.entityCard}
          onClose={onClose}
        />
      )}
    </div>
  );

  // Render in portal to escape parent overflow constraints
  return createPortal(content, document.body);
}

// Re-export types for convenience
export type { CardPopupState };

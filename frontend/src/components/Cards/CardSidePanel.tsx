"use client";

/**
 * CardSidePanel - Side panel for displaying cards overlaid on video
 * Slides in from the right side with elegant animation
 */

import { useEffect, useRef } from "react";
import type { CardPopupState } from "@/hooks/useCardPopup";
import type { WordCard, EntityCard } from "@/lib/types";

interface CardSidePanelProps {
  state: CardPopupState;
  onClose: () => void;
  position?: "left" | "right";
  sourceTimelineId?: string;
  sourceTimecode?: number;
  sourceSegmentText?: string;
  /** When true, panel fills its container instead of absolute positioning */
  inline?: boolean;
}

// Inline WordCard component optimized for side panel
function SidePanelWordCard({ card, onClose }: { card: WordCard; onClose: () => void }) {
  const audioRef = useRef<HTMLAudioElement | null>(null);

  const primaryPronunciation = card.pronunciations.find((p) => p.region === "us") || card.pronunciations[0];

  const playPronunciation = () => {
    if (!primaryPronunciation?.audio_url) return;
    if (audioRef.current) audioRef.current.pause();
    audioRef.current = new Audio(primaryPronunciation.audio_url);
    audioRef.current.play().catch(() => {});
  };

  const sensesByPos = card.senses.reduce((acc, sense) => {
    const pos = sense.part_of_speech;
    if (!acc[pos]) acc[pos] = [];
    acc[pos].push(sense);
    return acc;
  }, {} as Record<string, typeof card.senses>);

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="flex items-start justify-between p-4 border-b border-white/10">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-white">{card.word}</h2>
            {card.lemma !== card.word && (
              <span className="text-sm text-white/50">({card.lemma})</span>
            )}
          </div>
          {primaryPronunciation && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-blue-300 font-mono text-sm">{primaryPronunciation.ipa}</span>
              {primaryPronunciation.audio_url && (
                <button
                  onClick={playPronunciation}
                  className="p-1 rounded hover:bg-white/10 text-white/60 hover:text-white transition"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02z" />
                  </svg>
                </button>
              )}
            </div>
          )}
          {card.cefr_level && (
            <span className="inline-block mt-2 px-2 py-0.5 bg-purple-500/30 text-purple-300 text-xs rounded">
              {card.cefr_level}
            </span>
          )}
        </div>
        <button
          onClick={onClose}
          className="p-1.5 text-white/60 hover:text-white hover:bg-white/10 rounded transition"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {Object.entries(sensesByPos).map(([pos, senses]) => (
          <div key={pos}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">{pos}</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <ol className="space-y-3 list-decimal list-inside">
              {senses.slice(0, 3).map((sense, idx) => (
                <li key={idx} className="text-white/90 text-sm">
                  <span>{sense.definition}</span>
                  {sense.definition_zh && (
                    <p className="text-yellow-300/80 text-sm ml-5 mt-0.5">{sense.definition_zh}</p>
                  )}
                  {sense.examples.length > 0 && (
                    <div className="ml-5 mt-1">
                      {sense.examples.slice(0, 1).map((example, exIdx) => (
                        <p key={exIdx} className="text-white/50 text-xs italic">"{example}"</p>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>
    </div>
  );
}

// Inline EntityCard component optimized for side panel
function SidePanelEntityCard({ card, onClose }: { card: EntityCard; onClose: () => void }) {
  const typeColors: Record<string, string> = {
    person: "bg-blue-500/50",
    place: "bg-green-500/50",
    organization: "bg-purple-500/50",
    event: "bg-orange-500/50",
    work: "bg-pink-500/50",
    concept: "bg-cyan-500/50",
    product: "bg-yellow-500/50",
    other: "bg-gray-500/50",
  };

  const zhLocalization = card.localizations?.zh;

  return (
    <div className="h-full flex flex-col">
      {/* Header with image */}
      <div className="relative flex-shrink-0">
        {card.image_url ? (
          <div className="h-32 overflow-hidden">
            <img
              src={card.image_url}
              alt={card.name}
              className="w-full h-full object-cover"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
          </div>
        ) : (
          <div className="h-16 bg-gradient-to-r from-white/5 to-white/10" />
        )}

        <button
          onClick={onClose}
          className="absolute top-2 right-2 p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>

        <span className={`absolute top-2 left-2 px-2 py-0.5 ${typeColors[card.entity_type] || typeColors.other} text-white text-xs font-medium rounded backdrop-blur-sm`}>
          {card.entity_type}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        <h2 className="text-xl font-bold text-white mb-1">{card.name}</h2>
        {zhLocalization?.name && zhLocalization.name !== card.name && (
          <p className="text-yellow-300/80 text-sm mb-3">{zhLocalization.name}</p>
        )}

        <p className="text-white/80 text-sm mb-3">{card.description}</p>
        {zhLocalization?.description && (
          <p className="text-white/60 text-sm mb-4">{zhLocalization.description}</p>
        )}

        {/* Type-specific info */}
        <div className="space-y-1.5 text-sm">
          {card.entity_type === "person" && (
            <>
              {card.birth_date && (
                <div className="flex gap-2">
                  <span className="text-white/40">Born:</span>
                  <span className="text-white/80">{card.birth_date}</span>
                </div>
              )}
              {card.nationality && (
                <div className="flex gap-2">
                  <span className="text-white/40">Nationality:</span>
                  <span className="text-white/80">{card.nationality}</span>
                </div>
              )}
            </>
          )}
          {card.entity_type === "place" && card.location && (
            <div className="flex gap-2">
              <span className="text-white/40">Location:</span>
              <span className="text-white/80">{card.location}</span>
            </div>
          )}
        </div>

        {/* Links */}
        <div className="mt-4 flex flex-wrap gap-2">
          {card.wikipedia_url && (
            <a
              href={card.wikipedia_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 text-white/80 text-xs rounded transition"
            >
              Wikipedia
            </a>
          )}
          {card.official_website && (
            <a
              href={card.official_website}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 text-white/80 text-xs rounded transition"
            >
              Website
            </a>
          )}
        </div>
      </div>
    </div>
  );
}

export default function CardSidePanel({
  state,
  onClose,
  position = "right",
  inline = false,
}: CardSidePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);

  // Close on escape key
  useEffect(() => {
    if (!state.isOpen) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [state.isOpen, onClose]);

  if (!state.isOpen) return null;

  // Inline mode: fill container
  if (inline) {
    return (
      <div
        ref={panelRef}
        className="h-full flex flex-col"
      >
      {/* Loading state */}
      {state.loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-400 border-t-transparent" />
            <span className="text-white/60">Loading...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {state.error && !state.loading && (
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <p className="text-red-400 text-sm text-center mb-3">{state.error}</p>
          <button
            onClick={onClose}
            className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white/80 text-sm rounded transition"
          >
            Close
          </button>
        </div>
      )}

      {/* Word card */}
      {state.type === "word" && state.wordCard && !state.loading && (
        <SidePanelWordCard card={state.wordCard} onClose={onClose} />
      )}

      {/* Entity card */}
      {state.type === "entity" && state.entityCard && !state.loading && (
        <SidePanelEntityCard card={state.entityCard} onClose={onClose} />
      )}
    </div>
    );
  }

  // Absolute position mode (overlay)
  const positionClasses = position === "left"
    ? "left-0 rounded-r-xl"
    : "right-0 rounded-l-xl";

  return (
    <div
      ref={panelRef}
      className={`
        absolute top-0 bottom-0 ${positionClasses}
        w-80 max-w-[40%]
        bg-black/80 backdrop-blur-md
        border-l border-white/10
        shadow-2xl
        z-20
        flex flex-col
      `}
      style={{
        animation: `slideIn${position === "left" ? "Left" : "Right"} 0.2s ease-out`,
      }}
    >
      {/* Loading state */}
      {state.loading && (
        <div className="flex-1 flex items-center justify-center">
          <div className="flex items-center gap-3">
            <div className="animate-spin rounded-full h-5 w-5 border-2 border-blue-400 border-t-transparent" />
            <span className="text-white/60">Loading...</span>
          </div>
        </div>
      )}

      {/* Error state */}
      {state.error && !state.loading && (
        <div className="flex-1 flex flex-col items-center justify-center p-4">
          <p className="text-red-400 text-sm text-center mb-3">{state.error}</p>
          <button
            onClick={onClose}
            className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white/80 text-sm rounded transition"
          >
            Close
          </button>
        </div>
      )}

      {/* Word card */}
      {state.type === "word" && state.wordCard && !state.loading && (
        <SidePanelWordCard card={state.wordCard} onClose={onClose} />
      )}

      {/* Entity card */}
      {state.type === "entity" && state.entityCard && !state.loading && (
        <SidePanelEntityCard card={state.entityCard} onClose={onClose} />
      )}
    </div>
  );
}

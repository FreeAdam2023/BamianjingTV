"use client";

/**
 * CardSidePanel - Side panel for displaying cards overlaid on video
 * Slides in from the right side with elegant animation
 */

import { useEffect, useRef, useState, useCallback } from "react";
import type { CardPopupState } from "@/hooks/useCardPopup";
import type { WordCard, EntityCard, IdiomCard, PinnedCard, PinnedCardType } from "@/lib/types";
import { pinCard, unpinCard, updatePinnedCardNote } from "@/lib/api";

interface CardSidePanelProps {
  state: CardPopupState;
  onClose: () => void;
  position?: "left" | "right";
  sourceTimelineId?: string;
  sourceTimecode?: number;
  sourceSegmentText?: string;
  /** Segment ID for pinning */
  sourceSegmentId?: number;
  /** Callback when pin state changes */
  onPinChange?: (pinned: PinnedCard | null) => void;
  /** When true, panel fills its container instead of absolute positioning */
  inline?: boolean;
  /** Pinned cards list to check pin status locally (avoids API call) */
  pinnedCards?: PinnedCard[];
  /** Callback to refresh card data */
  onRefresh?: () => void;
  /** Whether refresh is in progress */
  refreshing?: boolean;
  /** Callback to edit entity */
  onEditEntity?: (entityId: string) => void;
}

// Pin icon component - thumbtack style
function PinIcon({ filled }: { filled: boolean }) {
  if (filled) {
    // Filled pin (pinned state) - solid thumbtack
    return (
      <svg className="w-4 h-4" viewBox="0 0 24 24" fill="currentColor">
        <path d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
      </svg>
    );
  }
  // Outline pin (unpinned state)
  return (
    <svg className="w-4 h-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M16 9V4h1c.55 0 1-.45 1-1s-.45-1-1-1H7c-.55 0-1 .45-1 1s.45 1 1 1h1v5c0 1.66-1.34 3-3 3v2h5.97v7l1 1 1-1v-7H19v-2c-1.66 0-3-1.34-3-3z" />
    </svg>
  );
}

// Exported for reuse in PinnedCardOverlay
export interface SidePanelWordCardProps {
  card: WordCard;
  onClose: () => void;
  isPinned?: boolean;
  pinLoading?: boolean;
  onTogglePin?: () => void;
  canPin?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  pinnedNote?: string;
  onNoteChange?: (note: string) => void;
}

export function SidePanelWordCard({ card, onClose, isPinned, pinLoading, onTogglePin, canPin, onRefresh, refreshing, pinnedNote, onNoteChange }: SidePanelWordCardProps) {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [imageError, setImageError] = useState(false);

  const pronunciations = card.pronunciations || [];
  const senses = card.senses || [];
  const primaryPronunciation = pronunciations.find((p) => p.region === "us") || pronunciations[0];
  const primaryImage = card.images?.[0];

  const playPronunciation = () => {
    if (!primaryPronunciation?.audio_url) return;
    if (audioRef.current) audioRef.current.pause();
    audioRef.current = new Audio(primaryPronunciation.audio_url);
    audioRef.current.play().catch(() => {});
  };

  const sensesByPos = senses.reduce((acc, sense) => {
    const pos = sense.part_of_speech;
    if (!acc[pos]) acc[pos] = [];
    acc[pos].push(sense);
    return acc;
  }, {} as Record<string, typeof senses>);

  return (
    <div className="h-full flex flex-col">
      {/* Image Header */}
      {primaryImage && !imageError && (
        <div className="relative h-40 flex-shrink-0 overflow-hidden bg-black/30">
          <img
            src={primaryImage}
            alt={card.word}
            className="w-full h-full object-contain"
            onError={() => setImageError(true)}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
        </div>
      )}

      {/* Header */}
      <div className={`flex items-start justify-between p-4 border-b border-white/10 ${primaryImage && !imageError ? '-mt-14 relative z-10' : ''}`}>
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
        <div className="flex items-center gap-1">
          {/* Refresh button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className={`p-1.5 rounded transition text-white/60 hover:text-white hover:bg-white/10 ${refreshing ? "opacity-50 cursor-wait" : ""}`}
              title="刷新卡片"
            >
              {refreshing ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
            </button>
          )}
          {/* Pin button */}
          {canPin && (
            <button
              onClick={onTogglePin}
              disabled={pinLoading}
              className={`p-1.5 rounded transition ${
                isPinned
                  ? "text-purple-400 bg-purple-500/20 hover:bg-purple-500/30"
                  : "text-white/60 hover:text-white hover:bg-white/10"
              } ${pinLoading ? "opacity-50 cursor-wait" : ""}`}
              title={isPinned ? "取消钉住" : "钉住到视频"}
            >
              {pinLoading ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <PinIcon filled={isPinned || false} />
              )}
            </button>
          )}
          {/* Close button */}
          <button
            onClick={onClose}
            className="p-1.5 text-white/60 hover:text-white hover:bg-white/10 rounded transition"
          >
            <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {Object.entries(sensesByPos).map(([pos, senses]) => (
          <div key={pos}>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">{pos}</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <div className="space-y-4">
              {senses.slice(0, 3).map((sense, idx) => (
                <div key={idx} className="space-y-2">
                  {/* Chinese Definition - Primary */}
                  {sense.definition_zh && (
                    <p className="text-base text-white font-medium">
                      {idx + 1}. {sense.definition_zh}
                    </p>
                  )}

                  {/* English Definition - if different */}
                  {sense.definition && sense.definition !== sense.definition_zh && (
                    <p className="text-sm text-white/60 ml-4">{sense.definition}</p>
                  )}

                  {/* Examples with Chinese translations */}
                  {(sense.examples?.length ?? 0) > 0 && (
                    <div className="ml-4 space-y-2">
                      {sense.examples.slice(0, 2).map((example, exIdx) => (
                        <div key={exIdx} className="pl-3 border-l-2 border-white/20">
                          <p className="text-sm text-white/70 italic">"{example}"</p>
                          {sense.examples_zh?.[exIdx] && (
                            <p className="text-sm text-yellow-300/70 mt-0.5">
                              {sense.examples_zh[exIdx]}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Synonyms & Antonyms */}
                  {((sense.synonyms?.length ?? 0) > 0 || (sense.antonyms?.length ?? 0) > 0) && (
                    <div className="flex flex-wrap gap-2 ml-4 pt-1">
                      {(sense.synonyms?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-green-400 text-xs">≈</span>
                          {sense.synonyms!.slice(0, 3).map((syn, synIdx) => (
                            <span
                              key={synIdx}
                              className="text-xs px-1.5 py-0.5 bg-green-900/40 text-green-300 rounded"
                            >
                              {syn}
                            </span>
                          ))}
                        </div>
                      )}
                      {(sense.antonyms?.length ?? 0) > 0 && (
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-red-400 text-xs">≠</span>
                          {sense.antonyms!.slice(0, 2).map((ant, antIdx) => (
                            <span
                              key={antIdx}
                              className="text-xs px-1.5 py-0.5 bg-red-900/40 text-red-300 rounded"
                            >
                              {ant}
                            </span>
                          ))}
                        </div>
                      )}
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        ))}

        {/* Pinned note */}
        {isPinned && onNoteChange && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">备注</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <textarea
              defaultValue={pinnedNote || ""}
              onBlur={(e) => onNoteChange(e.target.value)}
              placeholder="添加备注..."
              rows={2}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white/80 placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30"
            />
          </div>
        )}
      </div>
    </div>
  );
}

export interface SidePanelEntityCardProps {
  card: EntityCard;
  onClose: () => void;
  isPinned?: boolean;
  pinLoading?: boolean;
  onTogglePin?: () => void;
  canPin?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  onEdit?: () => void;
  pinnedNote?: string;
  onNoteChange?: (note: string) => void;
  annotationNote?: string | null;
}

export function SidePanelEntityCard({ card, onClose, isPinned, pinLoading, onTogglePin, canPin, onRefresh, refreshing, onEdit, pinnedNote, onNoteChange, annotationNote }: SidePanelEntityCardProps) {
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

  const entityTypeLabels: Record<string, string> = {
    person: "人物",
    place: "地点",
    organization: "组织",
    event: "事件",
    work: "作品",
    concept: "概念",
    product: "产品",
    other: "其他",
  };

  const zhLocalization = card.localizations?.zh;
  const enLocalization = card.localizations?.en;

  return (
    <div className="h-full flex flex-col">
      {/* Header with image */}
      <div className="relative flex-shrink-0">
        {card.image_url ? (
          <div className="h-40 overflow-hidden bg-black/30">
            <img
              src={card.image_url}
              alt={card.name}
              className="w-full h-full object-contain"
              onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
            />
            <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-black/20 to-transparent" />
          </div>
        ) : (
          <div className="h-16 bg-gradient-to-r from-white/5 to-white/10" />
        )}

        {/* Action buttons */}
        <div className="absolute top-2 right-2 flex items-center gap-1">
          {/* Refresh button */}
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className={`p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition ${refreshing ? "opacity-50 cursor-wait" : ""}`}
              title="刷新卡片"
            >
              {refreshing ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
            </button>
          )}
          {/* Edit button */}
          {onEdit && (
            <button
              onClick={onEdit}
              className="p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition"
              title="编辑实体"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z" />
              </svg>
            </button>
          )}
          {/* Pin button */}
          {canPin && (
            <button
              onClick={onTogglePin}
              disabled={pinLoading}
              className={`p-1.5 rounded-full transition ${
                isPinned
                  ? "bg-purple-500/80 text-white hover:bg-purple-500"
                  : "bg-black/50 text-white hover:bg-black/70"
              } ${pinLoading ? "opacity-50 cursor-wait" : ""}`}
              title={isPinned ? "取消钉住" : "钉住到视频"}
            >
              {pinLoading ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <PinIcon filled={isPinned || false} />
              )}
            </button>
          )}
          {/* Close button */}
          <button
            onClick={onClose}
            className="p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <span className={`absolute top-2 left-2 px-2 py-0.5 ${typeColors[card.entity_type] || typeColors.other} text-white text-xs font-medium rounded backdrop-blur-sm`}>
          {entityTypeLabels[card.entity_type] || card.entity_type}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4">
        {zhLocalization?.name ? (
          <>
            <h2 className="text-xl font-bold text-white mb-1">{zhLocalization.name}</h2>
            {zhLocalization.name !== card.name && (
              <p className="text-white/50 text-sm mb-1">{card.name}</p>
            )}
          </>
        ) : (
          <h2 className="text-xl font-bold text-white mb-1">{card.name}</h2>
        )}

        {zhLocalization?.description ? (
          <p className="text-white/80 text-sm mb-3 mt-2">{zhLocalization.description}</p>
        ) : (
          <p className="text-white/80 text-sm mb-3 mt-2">{card.description}</p>
        )}

        {/* Annotation note (from segment context) */}
        {annotationNote && (
          <div className="mt-3 p-2.5 bg-purple-500/10 border border-purple-500/20 rounded-lg">
            <div className="flex items-center gap-1.5 mb-1">
              <span className="text-[10px] font-medium text-purple-300/60 uppercase tracking-wider">备注</span>
            </div>
            <p className="text-sm text-purple-300/80">{annotationNote}</p>
          </div>
        )}

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
          {card.wikidata_url && (
            <a
              href={card.wikidata_url}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex items-center gap-1 px-2 py-1 bg-white/10 hover:bg-white/20 text-white/80 text-xs rounded transition"
            >
              Wikidata
            </a>
          )}
        </div>

        {/* Pinned note */}
        {isPinned && onNoteChange && (
          <div className="mt-4">
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">备注</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <textarea
              defaultValue={pinnedNote || ""}
              onBlur={(e) => onNoteChange(e.target.value)}
              placeholder="添加备注..."
              rows={2}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white/80 placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30"
            />
          </div>
        )}
      </div>
    </div>
  );
}

export interface SidePanelIdiomCardProps {
  card: IdiomCard;
  onClose: () => void;
  isPinned?: boolean;
  pinLoading?: boolean;
  onTogglePin?: () => void;
  canPin?: boolean;
  onRefresh?: () => void;
  refreshing?: boolean;
  pinnedNote?: string;
  onNoteChange?: (note: string) => void;
}

export function SidePanelIdiomCard({ card, onClose, isPinned, pinLoading, onTogglePin, canPin, onRefresh, refreshing, pinnedNote, onNoteChange }: SidePanelIdiomCardProps) {
  const categoryColors: Record<string, string> = {
    idiom: "bg-amber-500/50",
    phrasal_verb: "bg-amber-600/50",
    slang: "bg-orange-500/50",
    colloquial: "bg-yellow-500/50",
    proverb: "bg-rose-500/50",
    expression: "bg-teal-500/50",
  };

  const categoryLabels: Record<string, string> = {
    idiom: "Idiom",
    phrasal_verb: "Phrasal Verb",
    slang: "Slang",
    colloquial: "Colloquial",
    proverb: "Proverb",
    expression: "Expression",
  };

  return (
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="relative flex-shrink-0">
        <div className="h-16 bg-gradient-to-r from-amber-900/30 to-amber-800/20" />

        {/* Action buttons */}
        <div className="absolute top-2 right-2 flex items-center gap-1">
          {onRefresh && (
            <button
              onClick={onRefresh}
              disabled={refreshing}
              className={`p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition ${refreshing ? "opacity-50 cursor-wait" : ""}`}
              title="刷新卡片"
            >
              {refreshing ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                </svg>
              )}
            </button>
          )}
          {canPin && (
            <button
              onClick={onTogglePin}
              disabled={pinLoading}
              className={`p-1.5 rounded-full transition ${
                isPinned
                  ? "text-purple-400 bg-purple-500/20 hover:bg-purple-500/30"
                  : "bg-black/50 text-white hover:bg-black/70"
              } ${pinLoading ? "opacity-50 cursor-wait" : ""}`}
              title={isPinned ? "取消钉住" : "钉住到视频"}
            >
              {pinLoading ? (
                <div className="w-4 h-4 border-2 border-current border-t-transparent rounded-full animate-spin" />
              ) : (
                <PinIcon filled={isPinned || false} />
              )}
            </button>
          )}
          <button
            onClick={onClose}
            className="p-1.5 bg-black/50 text-white hover:bg-black/70 rounded-full transition"
          >
            <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <span className={`absolute top-2 left-2 px-2 py-0.5 ${categoryColors[card.category] || categoryColors.idiom} text-white text-xs font-medium rounded backdrop-blur-sm`}>
          {categoryLabels[card.category] || card.category}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        <h2 className="text-xl font-bold text-amber-300">{card.text}</h2>

        {/* Meaning */}
        {(card.meaning_original || card.meaning_localized) && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">释义</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            {card.meaning_original && (
              <p className="text-sm text-white/70 mb-1">{card.meaning_original}</p>
            )}
            {card.meaning_localized && (
              <p className="text-sm text-yellow-300/70">{card.meaning_localized}</p>
            )}
          </div>
        )}

        {/* Example */}
        {(card.example_original || card.example_localized) && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">例句</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <div className="pl-3 border-l-2 border-amber-500/30 space-y-1">
              {card.example_original && (
                <p className="text-sm text-white/80">{card.example_original}</p>
              )}
              {card.example_localized && (
                <p className="text-sm text-yellow-300/70">{card.example_localized}</p>
              )}
            </div>
          </div>
        )}

        {/* Origin */}
        {card.origin_localized && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">来源</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <p className="text-sm text-yellow-300/60">{card.origin_localized}</p>
          </div>
        )}

        {/* Usage Notes */}
        {card.usage_note_localized && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">用法</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <p className="text-sm text-yellow-300/60">{card.usage_note_localized}</p>
          </div>
        )}

        {/* Pinned note */}
        {isPinned && onNoteChange && (
          <div>
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-white/40 uppercase tracking-wider">备注</span>
              <div className="flex-1 h-px bg-white/10" />
            </div>
            <textarea
              defaultValue={pinnedNote || ""}
              onBlur={(e) => onNoteChange(e.target.value)}
              placeholder="添加备注..."
              rows={2}
              className="w-full bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm text-white/80 placeholder-white/30 resize-none focus:outline-none focus:border-purple-500/50 focus:ring-1 focus:ring-purple-500/30"
            />
          </div>
        )}
      </div>
    </div>
  );
}

export default function CardSidePanel({
  state,
  onClose,
  position = "right",
  sourceTimelineId,
  sourceTimecode,
  sourceSegmentId,
  onPinChange,
  inline = false,
  pinnedCards = [],
  onRefresh,
  refreshing = false,
  onEditEntity,
}: CardSidePanelProps) {
  const panelRef = useRef<HTMLDivElement>(null);
  const [pinLoading, setPinLoading] = useState(false);
  const [pinError, setPinError] = useState<string | null>(null);

  // Determine if pinning is available
  const canPin = !!(sourceTimelineId && sourceSegmentId !== undefined && sourceTimecode !== undefined);

  // Check if current card is pinned (local check, no API call)
  const getCurrentPinInfo = useCallback((): { isPinned: boolean; pinId: string | null; pinnedNote: string | null } => {
    if (!state.isOpen) return { isPinned: false, pinId: null, pinnedNote: null };

    let cardId: string | null = null;
    let cardType: PinnedCardType | null = null;

    if (state.type === "word" && state.wordCard) {
      cardId = state.wordCard.word;
      cardType = "word";
    } else if (state.type === "entity" && state.entityCard) {
      cardId = state.entityCard.entity_id;
      cardType = "entity";
    } else if (state.type === "idiom" && state.idiomCard) {
      cardId = state.idiomCard.text;
      cardType = "idiom";
    }

    if (!cardId || !cardType) return { isPinned: false, pinId: null, pinnedNote: null };

    const pinned = pinnedCards.find(
      (p) => p.card_type === cardType && p.card_id === cardId && p.segment_id === sourceSegmentId
    );

    return { isPinned: !!pinned, pinId: pinned?.id || null, pinnedNote: pinned?.note || null };
  }, [state, pinnedCards, sourceSegmentId]);

  const { isPinned, pinId, pinnedNote } = getCurrentPinInfo();

  // Get current card info
  const getCardInfo = useCallback((): { cardType: PinnedCardType; cardId: string; cardData: WordCard | EntityCard | IdiomCard } | null => {
    if (state.type === "word" && state.wordCard) {
      return { cardType: "word", cardId: state.wordCard.word, cardData: state.wordCard };
    }
    if (state.type === "entity" && state.entityCard) {
      return { cardType: "entity", cardId: state.entityCard.entity_id, cardData: state.entityCard };
    }
    if (state.type === "idiom" && state.idiomCard) {
      return { cardType: "idiom", cardId: state.idiomCard.text, cardData: state.idiomCard };
    }
    return null;
  }, [state]);

  // Handle note change (save on blur)
  const handleNoteChange = useCallback(async (note: string) => {
    if (!sourceTimelineId || !pinId) return;
    try {
      await updatePinnedCardNote(sourceTimelineId, pinId, note);
      onPinChange?.(null); // trigger refresh of pinned cards
    } catch (err) {
      console.error("Failed to update note:", err);
    }
  }, [sourceTimelineId, pinId, onPinChange]);

  // Note: Pin status is now checked locally via pinnedCards prop instead of API call
  // This avoids unnecessary network requests when opening cards

  // Max pinned cards per segment
  const MAX_PINS_PER_SEGMENT = 2;

  // Handle pin/unpin toggle
  const handleTogglePin = useCallback(async () => {
    if (!canPin || pinLoading) return;
    setPinError(null);

    const cardInfo = getCardInfo();
    if (!cardInfo) return;

    // Pre-check: max 2 cards per segment (only when pinning, not unpinning)
    if (!isPinned) {
      const segmentPinCount = pinnedCards.filter((p) => p.segment_id === sourceSegmentId).length;
      if (segmentPinCount >= MAX_PINS_PER_SEGMENT) {
        setPinError(`每条台词最多钉住 ${MAX_PINS_PER_SEGMENT} 张卡片`);
        setTimeout(() => setPinError(null), 3000);
        return;
      }
    }

    setPinLoading(true);
    try {
      if (isPinned && pinId) {
        // Unpin
        await unpinCard(sourceTimelineId!, pinId);
        onPinChange?.(null);
      } else {
        // Pin
        const pinned = await pinCard(sourceTimelineId!, {
          card_type: cardInfo.cardType,
          card_id: cardInfo.cardId,
          segment_id: sourceSegmentId!,
          timestamp: sourceTimecode!,
          card_data: cardInfo.cardData,
        });
        onPinChange?.(pinned);
      }
    } catch (err: unknown) {
      // Handle 409 from backend (segment limit exceeded)
      const apiErr = err as { response?: { status?: number; data?: { detail?: string } } };
      if (apiErr?.response?.status === 409) {
        setPinError(apiErr.response.data?.detail || `每条台词最多钉住 ${MAX_PINS_PER_SEGMENT} 张卡片`);
        setTimeout(() => setPinError(null), 3000);
      } else {
        console.error("Failed to toggle pin:", err);
      }
    } finally {
      setPinLoading(false);
    }
  }, [canPin, pinLoading, isPinned, pinId, sourceTimelineId, sourceSegmentId, sourceTimecode, getCardInfo, onPinChange, pinnedCards]);

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
          <div className="flex items-center gap-2">
            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={refreshing}
                className={`px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-sm rounded transition ${refreshing ? "opacity-50 cursor-wait" : ""}`}
              >
                {refreshing ? "重试中..." : "强制重试"}
              </button>
            )}
            <button
              onClick={onClose}
              className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white/80 text-sm rounded transition"
            >
              关闭
            </button>
          </div>
        </div>
      )}

      {/* Word card */}
      {state.type === "word" && state.wordCard && !state.loading && (
        <SidePanelWordCard
          card={state.wordCard}
          onClose={onClose}
          isPinned={isPinned}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
          canPin={canPin}
          onRefresh={onRefresh}
          refreshing={refreshing}
          pinnedNote={pinnedNote || undefined}
          onNoteChange={isPinned ? handleNoteChange : undefined}
        />
      )}

      {/* Entity card */}
      {state.type === "entity" && state.entityCard && !state.loading && (
        <SidePanelEntityCard
          card={state.entityCard}
          onClose={onClose}
          isPinned={isPinned}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
          canPin={canPin}
          onRefresh={onRefresh}
          refreshing={refreshing}
          onEdit={onEditEntity ? () => onEditEntity(state.entityCard!.entity_id) : undefined}
          pinnedNote={pinnedNote || undefined}
          onNoteChange={isPinned ? handleNoteChange : undefined}
          annotationNote={state.annotationNote}
        />
      )}

      {/* Idiom card */}
      {state.type === "idiom" && state.idiomCard && !state.loading && (
        <SidePanelIdiomCard
          card={state.idiomCard}
          onClose={onClose}
          isPinned={isPinned}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
          canPin={canPin}
          onRefresh={onRefresh}
          refreshing={refreshing}
          pinnedNote={pinnedNote || undefined}
          onNoteChange={isPinned ? handleNoteChange : undefined}
        />
      )}

      {/* Pin error toast */}
      {pinError && (
        <div className="absolute bottom-3 left-3 right-3 bg-red-500/90 text-white text-xs px-3 py-2 rounded-lg shadow-lg text-center animate-in fade-in slide-in-from-bottom-2 duration-200">
          {pinError}
        </div>
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
          <div className="flex items-center gap-2">
            {onRefresh && (
              <button
                onClick={onRefresh}
                disabled={refreshing}
                className={`px-3 py-1.5 bg-blue-500/20 hover:bg-blue-500/30 text-blue-400 text-sm rounded transition ${refreshing ? "opacity-50 cursor-wait" : ""}`}
              >
                {refreshing ? "重试中..." : "强制重试"}
              </button>
            )}
            <button
              onClick={onClose}
              className="px-3 py-1.5 bg-white/10 hover:bg-white/20 text-white/80 text-sm rounded transition"
            >
              关闭
            </button>
          </div>
        </div>
      )}

      {/* Word card */}
      {state.type === "word" && state.wordCard && !state.loading && (
        <SidePanelWordCard
          card={state.wordCard}
          onClose={onClose}
          isPinned={isPinned}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
          canPin={canPin}
          onRefresh={onRefresh}
          refreshing={refreshing}
          pinnedNote={pinnedNote || undefined}
          onNoteChange={isPinned ? handleNoteChange : undefined}
        />
      )}

      {/* Entity card */}
      {state.type === "entity" && state.entityCard && !state.loading && (
        <SidePanelEntityCard
          card={state.entityCard}
          onClose={onClose}
          isPinned={isPinned}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
          canPin={canPin}
          onRefresh={onRefresh}
          refreshing={refreshing}
          onEdit={onEditEntity ? () => onEditEntity(state.entityCard!.entity_id) : undefined}
          pinnedNote={pinnedNote || undefined}
          onNoteChange={isPinned ? handleNoteChange : undefined}
          annotationNote={state.annotationNote}
        />
      )}

      {/* Idiom card */}
      {state.type === "idiom" && state.idiomCard && !state.loading && (
        <SidePanelIdiomCard
          card={state.idiomCard}
          onClose={onClose}
          isPinned={isPinned}
          pinLoading={pinLoading}
          onTogglePin={handleTogglePin}
          canPin={canPin}
          onRefresh={onRefresh}
          refreshing={refreshing}
          pinnedNote={pinnedNote || undefined}
          onNoteChange={isPinned ? handleNoteChange : undefined}
        />
      )}

      {/* Pin error toast */}
      {pinError && (
        <div className="absolute bottom-3 left-3 right-3 bg-red-500/90 text-white text-xs px-3 py-2 rounded-lg shadow-lg text-center animate-in fade-in slide-in-from-bottom-2 duration-200">
          {pinError}
        </div>
      )}
    </div>
  );
}

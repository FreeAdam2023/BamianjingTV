"use client";

import { useState, useRef } from "react";
import type { WordCard as WordCardType } from "@/lib/types";
import { CollectButton } from "@/components/MemoryBook";

interface WordCardProps {
  card: WordCardType;
  onClose: () => void;
  onAddToMemory?: (word: string) => void;
  sourceTimelineId?: string;
  sourceTimecode?: number;
  sourceSegmentText?: string;
}

export default function WordCard({
  card,
  onClose,
  onAddToMemory,
  sourceTimelineId,
  sourceTimecode,
  sourceSegmentText,
}: WordCardProps) {
  const [playingAudio, setPlayingAudio] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Get primary pronunciation
  const primaryPronunciation = card.pronunciations.find((p) => p.region === "us") || card.pronunciations[0];

  const playPronunciation = () => {
    if (!primaryPronunciation?.audio_url) return;

    if (audioRef.current) {
      audioRef.current.pause();
    }

    audioRef.current = new Audio(primaryPronunciation.audio_url);
    audioRef.current.onplay = () => setPlayingAudio(true);
    audioRef.current.onended = () => setPlayingAudio(false);
    audioRef.current.onerror = () => setPlayingAudio(false);
    audioRef.current.play().catch(() => setPlayingAudio(false));
  };

  // Group senses by part of speech
  const sensesByPos = card.senses.reduce((acc, sense) => {
    const pos = sense.part_of_speech;
    if (!acc[pos]) acc[pos] = [];
    acc[pos].push(sense);
    return acc;
  }, {} as Record<string, typeof card.senses>);

  return (
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl w-96 max-h-[500px] overflow-hidden flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-[var(--border)] flex items-start justify-between">
        <div className="flex-1">
          <div className="flex items-center gap-2">
            <h2 className="text-2xl font-bold text-white">{card.word}</h2>
            {card.lemma !== card.word && (
              <span className="text-sm text-gray-400">({card.lemma})</span>
            )}
          </div>

          {/* Pronunciation */}
          {primaryPronunciation && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-blue-400 font-mono text-sm">{primaryPronunciation.ipa}</span>
              {primaryPronunciation.audio_url && (
                <button
                  onClick={playPronunciation}
                  className={`p-1 rounded hover:bg-gray-700 transition-colors ${
                    playingAudio ? "text-blue-400" : "text-gray-400"
                  }`}
                  title="Play pronunciation"
                >
                  <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                  </svg>
                </button>
              )}
            </div>
          )}

          {/* CEFR level badge */}
          {card.cefr_level && (
            <span className="inline-block mt-1 px-2 py-0.5 bg-purple-600/20 text-purple-400 text-xs rounded">
              {card.cefr_level}
            </span>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1 text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
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
            {/* Part of speech header */}
            <div className="flex items-center gap-2 mb-2">
              <span className="text-xs font-medium text-gray-400 uppercase tracking-wider">
                {pos}
              </span>
              <div className="flex-1 h-px bg-gray-700" />
            </div>

            {/* Definitions */}
            <ol className="space-y-3 list-decimal list-inside">
              {senses.slice(0, 3).map((sense, idx) => (
                <li key={idx} className="text-gray-200 text-sm">
                  <span>{sense.definition}</span>

                  {/* Chinese translation */}
                  {sense.definition_zh && (
                    <p className="text-gray-400 text-sm ml-5 mt-0.5">{sense.definition_zh}</p>
                  )}

                  {/* Examples */}
                  {sense.examples.length > 0 && (
                    <div className="ml-5 mt-1 space-y-1">
                      {sense.examples.slice(0, 2).map((example, exIdx) => (
                        <p key={exIdx} className="text-gray-500 text-xs italic">
                          "{example}"
                          {sense.examples_zh?.[exIdx] && (
                            <span className="text-gray-600 not-italic ml-2">
                              {sense.examples_zh[exIdx]}
                            </span>
                          )}
                        </p>
                      ))}
                    </div>
                  )}

                  {/* Synonyms */}
                  {sense.synonyms.length > 0 && (
                    <div className="ml-5 mt-1 flex flex-wrap gap-1">
                      <span className="text-gray-500 text-xs">Syn:</span>
                      {sense.synonyms.slice(0, 4).map((syn, synIdx) => (
                        <span
                          key={synIdx}
                          className="text-xs px-1.5 py-0.5 bg-gray-700 text-gray-300 rounded"
                        >
                          {syn}
                        </span>
                      ))}
                    </div>
                  )}
                </li>
              ))}
            </ol>
          </div>
        ))}
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-[var(--border)] flex items-center justify-between bg-[var(--card)]">
        <span className="text-xs text-gray-500">
          Source: {card.source}
        </span>

        <div className="flex items-center gap-2">
          <CollectButton
            targetType="word"
            targetId={card.word}
            cardData={card}
            sourceTimelineId={sourceTimelineId}
            sourceTimecode={sourceTimecode}
            sourceSegmentText={sourceSegmentText}
            size="md"
          />
          {onAddToMemory && (
            <button
              onClick={() => onAddToMemory(card.word)}
              className="btn btn-sm btn-primary flex items-center gap-1.5"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
              </svg>
              Add to Memory
            </button>
          )}
        </div>
      </div>
    </div>
  );
}

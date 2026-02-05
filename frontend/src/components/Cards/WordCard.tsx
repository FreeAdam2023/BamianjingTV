"use client";

import { useState, useRef } from "react";
import Image from "next/image";
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
  const [imageError, setImageError] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);

  // Get primary pronunciation
  const primaryPronunciation = card.pronunciations.find((p) => p.region === "us") || card.pronunciations[0];

  // Get first image
  const primaryImage = card.images?.[0];

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
    <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl shadow-2xl w-[420px] max-h-[600px] overflow-hidden flex flex-col">
      {/* Image Header */}
      {primaryImage && !imageError && (
        <div className="relative h-32 w-full overflow-hidden bg-gray-800">
          <img
            src={primaryImage}
            alt={card.word}
            className="w-full h-full object-cover"
            onError={() => setImageError(true)}
          />
          <div className="absolute inset-0 bg-gradient-to-t from-[var(--card)] via-transparent to-transparent" />
        </div>
      )}

      {/* Header */}
      <div className={`p-4 ${primaryImage && !imageError ? '-mt-10 relative z-10' : ''} flex items-start justify-between`}>
        <div className="flex-1">
          <div className="flex items-center gap-3">
            <h2 className="text-2xl font-bold text-white">{card.word}</h2>
            {primaryPronunciation && (
              <button
                onClick={playPronunciation}
                className={`p-2 rounded-full transition-all ${
                  playingAudio
                    ? "bg-blue-500 text-white scale-110"
                    : "bg-gray-700/80 text-gray-300 hover:bg-gray-600"
                }`}
                title="Play pronunciation"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                </svg>
              </button>
            )}
          </div>

          {/* Pronunciation IPA */}
          {primaryPronunciation && (
            <span className="text-blue-400 font-mono text-sm">{primaryPronunciation.ipa}</span>
          )}

          {/* CEFR level badge */}
          {card.cefr_level && (
            <span className="inline-block ml-2 px-2 py-0.5 bg-purple-600/20 text-purple-400 text-xs rounded">
              {card.cefr_level}
            </span>
          )}
        </div>

        <button
          onClick={onClose}
          className="p-1.5 text-gray-400 hover:text-white hover:bg-gray-700 rounded-lg transition-colors"
        >
          <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto px-4 pb-4 space-y-4">
        {Object.entries(sensesByPos).map(([pos, senses]) => (
          <div key={pos}>
            {/* Part of speech header */}
            <div className="flex items-center gap-2 mb-3">
              <span className="px-2 py-0.5 bg-blue-600/20 text-blue-400 text-xs font-medium rounded">
                {pos}
              </span>
              <div className="flex-1 h-px bg-gray-700/50" />
            </div>

            {/* Definitions */}
            <div className="space-y-4">
              {senses.slice(0, 3).map((sense, idx) => (
                <div key={idx} className="space-y-2">
                  {/* Chinese Definition - Primary */}
                  {sense.definition_zh && (
                    <p className="text-lg text-white font-medium">
                      {sense.definition_zh}
                    </p>
                  )}

                  {/* English Definition - if different */}
                  {sense.definition && sense.definition !== sense.definition_zh && (
                    <p className="text-sm text-gray-400">{sense.definition}</p>
                  )}

                  {/* Examples */}
                  {sense.examples.length > 0 && (
                    <div className="pl-3 border-l-2 border-gray-700 space-y-2">
                      {sense.examples.slice(0, 2).map((example, exIdx) => (
                        <div key={exIdx} className="space-y-0.5">
                          <p className="text-sm text-gray-300 italic">"{example}"</p>
                          {sense.examples_zh?.[exIdx] && (
                            <p className="text-sm text-gray-500">
                              {sense.examples_zh[exIdx]}
                            </p>
                          )}
                        </div>
                      ))}
                    </div>
                  )}

                  {/* Synonyms & Antonyms */}
                  {(sense.synonyms.length > 0 || sense.antonyms.length > 0) && (
                    <div className="flex flex-wrap gap-3 pt-1">
                      {sense.synonyms.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-green-500 text-xs font-medium">≈</span>
                          {sense.synonyms.slice(0, 4).map((syn, synIdx) => (
                            <span
                              key={synIdx}
                              className="text-xs px-1.5 py-0.5 bg-green-900/30 text-green-400 rounded"
                            >
                              {syn}
                            </span>
                          ))}
                        </div>
                      )}
                      {sense.antonyms.length > 0 && (
                        <div className="flex flex-wrap items-center gap-1">
                          <span className="text-red-500 text-xs font-medium">≠</span>
                          {sense.antonyms.slice(0, 3).map((ant, antIdx) => (
                            <span
                              key={antIdx}
                              className="text-xs px-1.5 py-0.5 bg-red-900/30 text-red-400 rounded"
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
      </div>

      {/* Footer */}
      <div className="p-3 border-t border-[var(--border)] flex items-center justify-between bg-[var(--card)]">
        <span className="text-xs text-gray-500 flex items-center gap-1">
          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
            <path fillRule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zm-7-4a1 1 0 11-2 0 1 1 0 012 0zM9 9a1 1 0 000 2v3a1 1 0 001 1h1a1 1 0 100-2v-3a1 1 0 00-1-1H9z" clipRule="evenodd" />
          </svg>
          {card.source}
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
        </div>
      </div>
    </div>
  );
}

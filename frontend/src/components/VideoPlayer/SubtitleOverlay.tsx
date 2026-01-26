/**
 * SubtitleOverlay - Bilingual subtitle display area
 */

import { useState } from "react";
import type { EditableSegment } from "@/lib/types";
import { SubtitleStyle } from "./constants";
import SubtitleStylePanel from "./SubtitleStylePanel";

interface SubtitleOverlayProps {
  segment: EditableSegment | null;
  style: SubtitleStyle;
  subtitleHeightRatio: number;
  onStyleChange: (updates: Partial<SubtitleStyle>) => void;
  onStyleReset: () => void;
}

export default function SubtitleOverlay({
  segment,
  style,
  subtitleHeightRatio,
  onStyleChange,
  onStyleReset,
}: SubtitleOverlayProps) {
  const [showStyleSettings, setShowStyleSettings] = useState(false);

  // Calculate font sizes based on subtitle height ratio
  const fontScale = subtitleHeightRatio / 0.5;
  const englishFontSize = Math.max(14, Math.min(48, style.enFontSize * fontScale));
  const chineseFontSize = Math.max(16, Math.min(56, style.zhFontSize * fontScale));

  // Text shadow style for better visibility
  const textShadowStyle = style.textShadow
    ? "2px 2px 4px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.5)"
    : "none";

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center px-8 py-4 min-h-0 relative"
      style={{ backgroundColor: style.backgroundColor }}
    >
      {segment ? (
        <>
          {/* English text */}
          <div
            className="text-center leading-relaxed mb-4"
            style={{
              fontSize: `${englishFontSize}px`,
              fontFamily: style.fontFamily,
              fontWeight: style.fontWeight,
              color: style.enColor,
              textShadow: textShadowStyle,
            }}
          >
            {segment.en}
          </div>
          {/* Chinese text */}
          <div
            className="text-center leading-relaxed"
            style={{
              fontSize: `${chineseFontSize}px`,
              fontFamily: style.fontFamily,
              fontWeight: style.fontWeight,
              color: style.zhColor,
              textShadow: textShadowStyle,
            }}
          >
            {segment.zh}
          </div>
        </>
      ) : (
        <div className="text-gray-500 text-center">
          No subtitle
        </div>
      )}

      {/* Style settings button (floating) */}
      <button
        onClick={() => setShowStyleSettings(!showStyleSettings)}
        className={`absolute top-2 right-2 p-1.5 rounded-full transition-colors ${
          showStyleSettings ? "bg-blue-500 text-white" : "bg-black/30 text-white/70 hover:bg-black/50"
        }`}
        title="Subtitle style settings"
      >
        <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>

      {/* Style settings panel */}
      {showStyleSettings && (
        <SubtitleStylePanel
          style={style}
          onStyleChange={onStyleChange}
          onReset={onStyleReset}
        />
      )}
    </div>
  );
}

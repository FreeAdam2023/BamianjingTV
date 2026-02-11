/**
 * SubtitleOverlay - Bilingual subtitle display area with auto-scaling
 */

import { useState, useMemo } from "react";
import type { EditableSegment } from "@/lib/types";
import { SubtitleStyle } from "./constants";
import SubtitleStylePanel from "./SubtitleStylePanel";

interface SubtitleOverlayProps {
  segment: EditableSegment | null;
  style: SubtitleStyle;
  onStyleChange: (updates: Partial<SubtitleStyle>) => void;
  onStyleReset: () => void;
  overlayMode?: boolean;
}

// Minimum font sizes to maintain readability
const MIN_EN_FONT_SIZE = 18;
const MIN_ZH_FONT_SIZE = 20;

// Character thresholds for scaling (approximate characters per line at base size)
const EN_CHARS_PER_LINE = 60;
const ZH_CHARS_PER_LINE = 30;
const MAX_LINES = 4; // Max lines we want to display

// Fixed subtitle area ratio (33% of screen height, not adjustable)
const SUBTITLE_HEIGHT_RATIO = 0.33;

export default function SubtitleOverlay({
  segment,
  style,
  onStyleChange,
  onStyleReset,
  overlayMode = false,
}: SubtitleOverlayProps) {
  const [showStyleSettings, setShowStyleSettings] = useState(false);

  // Calculate adaptive font sizes based on text length
  const { englishFontSize, chineseFontSize } = useMemo(() => {
    // Base font scale (fixed 30% ratio, only for split mode)
    const fontScale = overlayMode ? 1 : SUBTITLE_HEIGHT_RATIO / 0.5;
    let enSize = Math.max(MIN_EN_FONT_SIZE, Math.min(48, style.enFontSize * fontScale));
    let zhSize = Math.max(MIN_ZH_FONT_SIZE, Math.min(56, style.zhFontSize * fontScale));

    if (!segment) return { englishFontSize: enSize, chineseFontSize: zhSize };

    // Calculate text lengths
    const enText = segment.en || "";
    const zhText = segment.zh || "";
    const enLength = enText.length;
    const zhLength = zhText.length;

    // Estimate how many lines the text would take at current font size
    const enMaxChars = EN_CHARS_PER_LINE * MAX_LINES;
    const zhMaxChars = ZH_CHARS_PER_LINE * MAX_LINES;

    // Scale down if text is too long
    if (enLength > enMaxChars) {
      const enScale = Math.sqrt(enMaxChars / enLength); // Square root for gentler scaling
      enSize = Math.max(MIN_EN_FONT_SIZE, enSize * enScale);
    } else if (enLength > EN_CHARS_PER_LINE * 2) {
      // Moderate scaling for 2-4 lines
      const enScale = Math.sqrt((EN_CHARS_PER_LINE * 2) / enLength);
      enSize = Math.max(MIN_EN_FONT_SIZE, enSize * Math.max(0.8, enScale));
    }

    if (zhLength > zhMaxChars) {
      const zhScale = Math.sqrt(zhMaxChars / zhLength);
      zhSize = Math.max(MIN_ZH_FONT_SIZE, zhSize * zhScale);
    } else if (zhLength > ZH_CHARS_PER_LINE * 2) {
      const zhScale = Math.sqrt((ZH_CHARS_PER_LINE * 2) / zhLength);
      zhSize = Math.max(MIN_ZH_FONT_SIZE, zhSize * Math.max(0.8, zhScale));
    }

    return { englishFontSize: Math.round(enSize), chineseFontSize: Math.round(zhSize) };
  }, [segment, style.enFontSize, style.zhFontSize, overlayMode]);

  // Text shadow style for better visibility (stronger in overlay mode)
  const textShadowStyle = style.textShadow
    ? overlayMode
      ? "2px 2px 6px rgba(0,0,0,0.9), -1px -1px 3px rgba(0,0,0,0.7), 0 0 10px rgba(0,0,0,0.5)"
      : "2px 2px 4px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.5)"
    : "none";

  // Overlay mode: positioned at bottom of video
  if (overlayMode) {
    return (
      <div className="absolute bottom-0 left-0 right-0 px-8 py-6 pointer-events-none">
        {/* Settings button - needs pointer events */}
        <button
          onClick={() => setShowStyleSettings(!showStyleSettings)}
          className={`absolute top-2 right-2 p-1.5 rounded-full transition-colors pointer-events-auto ${
            showStyleSettings ? "bg-blue-500 text-white" : "bg-black/50 text-white/70 hover:bg-black/70"
          }`}
          title="Subtitle style settings"
          aria-label="Toggle subtitle style settings"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </button>

        {/* Style settings panel */}
        {showStyleSettings && (
          <div className="pointer-events-auto relative">
            <SubtitleStylePanel
              style={style}
              onStyleChange={onStyleChange}
              onReset={onStyleReset}
              openUpward
            />
          </div>
        )}

        {segment && style.languageMode !== "none" ? (
          <div className="text-center">
            {/* English text */}
            {(style.languageMode === "both" || style.languageMode === "en") && (
              <div
                className={`leading-relaxed ${style.languageMode === "both" ? "mb-2" : ""}`}
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
            )}
            {/* Chinese text */}
            {(style.languageMode === "both" || style.languageMode === "zh") && (
              <div
                className="leading-relaxed"
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
            )}
          </div>
        ) : null}
      </div>
    );
  }

  // Split mode: separate area below video
  return (
    <div
      className="flex-1 flex flex-col items-center justify-center px-8 py-4 min-h-0 relative"
      style={{ backgroundColor: style.backgroundColor }}
    >
      {segment && style.languageMode !== "none" ? (
        <>
          {/* English text */}
          {(style.languageMode === "both" || style.languageMode === "en") && (
            <div
              className={`text-center leading-relaxed ${style.languageMode === "both" ? "mb-4" : ""}`}
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
          )}
          {/* Chinese text */}
          {(style.languageMode === "both" || style.languageMode === "zh") && (
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
          )}
        </>
      ) : null}

      {/* Style settings button (floating) */}
      <button
        onClick={() => setShowStyleSettings(!showStyleSettings)}
        className={`absolute top-2 right-2 p-1.5 rounded-full transition-colors ${
          showStyleSettings ? "bg-blue-500 text-white" : "bg-black/30 text-white/70 hover:bg-black/50"
        }`}
        title="Subtitle style settings"
        aria-label="Toggle subtitle style settings"
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

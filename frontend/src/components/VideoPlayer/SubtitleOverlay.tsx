/**
 * SubtitleOverlay - Bilingual subtitle display floating on video
 *
 * Positioned at bottom 25% of video with gradient background (transparent → semi-dark).
 */

import { useMemo } from "react";
import type { EditableSegment } from "@/lib/types";
import { SubtitleStyle } from "./constants";

interface SubtitleOverlayProps {
  segment: EditableSegment | null;
  style: SubtitleStyle;
}

// Minimum font sizes to maintain readability
const MIN_EN_FONT_SIZE = 18;
const MIN_ZH_FONT_SIZE = 20;

// Character thresholds for scaling (approximate characters per line at base size)
const EN_CHARS_PER_LINE = 60;
const ZH_CHARS_PER_LINE = 30;
const MAX_LINES = 4; // Max lines we want to display

// Fixed subtitle area ratio (25% of screen height, not adjustable)
const SUBTITLE_HEIGHT_RATIO = 0.25;

export default function SubtitleOverlay({
  segment,
  style,
}: SubtitleOverlayProps) {

  // Calculate adaptive font sizes based on text length
  const { englishFontSize, chineseFontSize } = useMemo(() => {
    const fontScale = SUBTITLE_HEIGHT_RATIO / 0.5;
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
  }, [segment, style.enFontSize, style.zhFontSize]);

  // Text shadow style for better visibility
  const textShadowStyle = style.textShadow
    ? "2px 2px 6px rgba(0,0,0,0.9), -1px -1px 3px rgba(0,0,0,0.7), 0 0 10px rgba(0,0,0,0.5)"
    : "none";

  // Always gradient background (transparent at top, dark at bottom)
  const bgStyle = { background: "linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.4) 40%, rgba(0,0,0,0.7) 100%)" };

  return (
    <div
      className="flex-1 flex flex-col items-center justify-center px-8 py-4 min-h-0 relative"
      style={bgStyle}
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

    </div>
  );
}

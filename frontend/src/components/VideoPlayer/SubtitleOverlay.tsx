/**
 * SubtitleOverlay - Bilingual subtitle display floating on video
 *
 * Positioned at bottom 25% of video with gradient background (transparent → semi-dark).
 * Font size auto-scales to fill the container based on text length and available height.
 */

import { useRef, useMemo, useState, useEffect } from "react";
import type { EditableSegment } from "@/lib/types";
import { SubtitleStyle } from "./constants";

interface SubtitleOverlayProps {
  segment: EditableSegment | null;
  style: SubtitleStyle;
}

// Line height multiplier (matches leading-relaxed ≈ 1.625)
const LINE_HEIGHT = 1.625;
// Gap between EN and ZH lines in px (matches mb-2)
const GAP_PX = 8;
// Minimum font sizes
const MIN_EN_FONT_SIZE = 16;
const MIN_ZH_FONT_SIZE = 18;

export default function SubtitleOverlay({
  segment,
  style,
}: SubtitleOverlayProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerHeight, setContainerHeight] = useState(0);
  const [containerWidth, setContainerWidth] = useState(0);

  // Observe container size
  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;

    const observer = new ResizeObserver((entries) => {
      const entry = entries[0];
      if (entry) {
        setContainerHeight(entry.contentRect.height);
        setContainerWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  // Calculate font sizes to fill the 25% subtitle area
  const { englishFontSize, chineseFontSize } = useMemo(() => {
    if (!containerHeight || !containerWidth) {
      return { englishFontSize: style.enFontSize, chineseFontSize: style.zhFontSize };
    }

    const isBoth = style.languageMode === "both";
    const showEn = style.languageMode === "both" || style.languageMode === "en";
    const showZh = style.languageMode === "both" || style.languageMode === "zh";
    const lineCount = (showEn ? 1 : 0) + (showZh ? 1 : 0);
    if (lineCount === 0) return { englishFontSize: style.enFontSize, chineseFontSize: style.zhFontSize };

    // Available height (subtract vertical padding ~32px and gap)
    const padding = 32;
    const gap = isBoth ? GAP_PX : 0;
    const availableHeight = containerHeight - padding - gap;
    // Available width (subtract horizontal padding ~64px)
    const availableWidth = containerWidth - 64;

    // For bilingual, split available height between EN and ZH (EN ~45%, ZH ~55%)
    const enHeightShare = isBoth ? 0.45 : 1;
    const zhHeightShare = isBoth ? 0.55 : 1;

    let enSize = style.enFontSize;
    let zhSize = style.zhFontSize;

    if (segment && showEn) {
      const enText = segment.en || "";
      const maxHeightForEn = availableHeight * enHeightShare;
      // Max font size that fits in one line height
      const maxByHeight = maxHeightForEn / LINE_HEIGHT;
      // Estimate chars per line at a given font size (avg char width ≈ 0.55 * fontSize for EN)
      const charsPerLine = Math.floor(availableWidth / (maxByHeight * 0.55));
      const lines = charsPerLine > 0 ? Math.ceil(enText.length / charsPerLine) : 1;
      // If multi-line, scale down to fit
      if (lines > 1) {
        enSize = Math.min(maxByHeight, maxByHeight / Math.sqrt(lines * 0.8));
      } else {
        enSize = maxByHeight;
      }
      enSize = Math.max(MIN_EN_FONT_SIZE, Math.min(enSize, maxByHeight));
    }

    if (segment && showZh) {
      const zhText = segment.zh || "";
      const maxHeightForZh = availableHeight * zhHeightShare;
      const maxByHeight = maxHeightForZh / LINE_HEIGHT;
      // Chinese chars are roughly square (width ≈ fontSize)
      const charsPerLine = Math.floor(availableWidth / (maxByHeight * 1.0));
      const lines = charsPerLine > 0 ? Math.ceil(zhText.length / charsPerLine) : 1;
      if (lines > 1) {
        zhSize = Math.min(maxByHeight, maxByHeight / Math.sqrt(lines * 0.8));
      } else {
        zhSize = maxByHeight;
      }
      zhSize = Math.max(MIN_ZH_FONT_SIZE, Math.min(zhSize, maxByHeight));
    }

    return { englishFontSize: Math.round(enSize), chineseFontSize: Math.round(zhSize) };
  }, [segment, style.enFontSize, style.zhFontSize, style.languageMode, containerHeight, containerWidth]);

  // Text shadow style for better visibility
  const textShadowStyle = style.textShadow
    ? "2px 2px 6px rgba(0,0,0,0.9), -1px -1px 3px rgba(0,0,0,0.7), 0 0 10px rgba(0,0,0,0.5)"
    : "none";

  // Always gradient background (transparent at top, dark at bottom)
  const bgStyle = { background: "linear-gradient(to bottom, transparent 0%, rgba(0,0,0,0.4) 40%, rgba(0,0,0,0.7) 100%)" };

  return (
    <div
      ref={containerRef}
      className="h-full flex flex-col items-center justify-center px-8 py-4 relative"
      style={bgStyle}
    >
      {segment && style.languageMode !== "none" ? (
        <>
          {/* English text */}
          {(style.languageMode === "both" || style.languageMode === "en") && (
            <div
              className={`text-center leading-relaxed ${style.languageMode === "both" ? "mb-2" : ""}`}
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

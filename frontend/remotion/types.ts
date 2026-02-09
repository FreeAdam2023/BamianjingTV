/**
 * Remotion-specific types for compositions
 */

export interface SubtitleWord {
  word: string;
  start: number; // seconds
  end: number; // seconds
  startFrame: number;
  endFrame: number;
  confidence?: number;
}

export interface SubtitleSegment {
  id: number;
  startFrame: number;
  endFrame: number;
  en: string;
  zh: string;
  speaker?: string | null;
  words?: SubtitleWord[];
  // For highlight style
  highlightedWords?: string[];
  entityWords?: string[];
}

export interface SubtitleStyleConfig {
  fontFamily: string;
  backgroundColor: string;
  position: "bottom" | "top" | "center";
  enFontSize: number;
  zhFontSize: number;
  enColor: string;
  zhColor: string;
  fontWeight: string;
  lineSpacing: number;
}

export interface AnimationTiming {
  entranceDuration: number; // frames
  exitDuration: number; // frames
}

// ============ LearningVideo Composition Types ============

export interface PinnedCardInput {
  id: string;
  card_type: "word" | "entity" | "idiom" | "insight";
  card_data: Record<string, unknown>;
  display_start: number; // seconds
  display_end: number; // seconds
}

export interface SubtitleInput {
  id: number;
  start: number; // seconds
  end: number; // seconds
  en: string;
  zh: string;
}

export interface LearningVideoProps {
  videoSrc: string;
  durationInFrames: number;
  fps: number;
  pinnedCards: PinnedCardInput[];
  subtitles: SubtitleInput[];
  layout: {
    videoRatio: number; // 0.65
    subtitleRatio: number; // 0.33
    bgColor: string; // "#1a2744"
  };
  subtitleStyle: {
    enColor: string;
    zhColor: string;
    enFontSize: number;
    zhFontSize: number;
  };
}

// ============ SubtitleStill Composition Types ============

export interface SubtitleStillInput {
  id: string; // segment id or dedup hash
  en: string;
  zh: string;
  start: number; // seconds (for FFmpeg timing)
  end: number; // seconds
  languageMode: "both" | "en" | "zh";
}

export interface SubtitleStillProps {
  en: string;
  zh: string;
  style: {
    enColor: string;
    zhColor: string;
    enFontSize: number;
    zhFontSize: number;
  };
  bgColor: string;
  width: number;
  height: number;
  languageMode: "both" | "en" | "zh";
}

// Helper to convert seconds to frames
export function secondsToFrames(seconds: number, fps: number): number {
  return Math.round(seconds * fps);
}

// Helper to convert word timings to frame-based
export function convertWordTimings(
  words: Array<{ word: string; start: number; end: number; confidence?: number }>,
  fps: number
): SubtitleWord[] {
  return words.map((w) => ({
    ...w,
    startFrame: secondsToFrames(w.start, fps),
    endFrame: secondsToFrames(w.end, fps),
  }));
}

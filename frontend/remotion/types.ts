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

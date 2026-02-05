/**
 * Creative Mode Types - Remotion configuration and related types
 */

export type CreativeStyle = "karaoke" | "popup" | "slide" | "typewriter" | "highlight" | "fade" | "custom";
export type EntranceType = "fadeIn" | "slideIn" | "bounce" | "typewriter" | "none";
export type ExitType = "fadeOut" | "slideOut" | "none";
export type EasingType = "linear" | "easeIn" | "easeOut" | "easeInOut" | "spring";
export type SubtitlePosition = "bottom" | "top" | "center";

export interface WordHighlightConfig {
  enabled: boolean;
  color: string;
  scale: number;
  duration: number; // frames
}

export interface EntranceAnimation {
  type: EntranceType;
  duration: number; // frames
  easing: EasingType;
}

export interface ExitAnimation {
  type: ExitType;
  duration: number; // frames
  easing: EasingType;
}

export interface AnimationConfig {
  entrance: EntranceAnimation;
  wordHighlight?: WordHighlightConfig;
  exit: ExitAnimation;
}

export interface GlobalConfig {
  fontFamily: string;
  backgroundColor: string;
  subtitlePosition: SubtitlePosition;
  enFontSize: number;
  zhFontSize: number;
  enColor: string;
  zhColor: string;
  fontWeight: string;
  lineSpacing: number;
}

export interface SegmentOverride {
  id: number;
  overrides?: Partial<AnimationConfig>;
}

export interface RemotionConfig {
  version: "1.0";
  style: CreativeStyle;
  global: GlobalConfig;
  animation: AnimationConfig;
  segments?: SegmentOverride[];
}

// Default configurations for each style preset
export const DEFAULT_GLOBAL_CONFIG: GlobalConfig = {
  fontFamily: "Inter, system-ui, sans-serif",
  backgroundColor: "#1a2744",
  subtitlePosition: "bottom",
  enFontSize: 32,
  zhFontSize: 28,
  enColor: "#ffffff",
  zhColor: "#facc15",
  fontWeight: "600",
  lineSpacing: 8,
};

export const STYLE_PRESETS: Record<CreativeStyle, AnimationConfig> = {
  karaoke: {
    entrance: { type: "fadeIn", duration: 10, easing: "easeOut" },
    wordHighlight: { enabled: true, color: "#facc15", scale: 1.1, duration: 15 },
    exit: { type: "fadeOut", duration: 10, easing: "easeIn" },
  },
  popup: {
    entrance: { type: "bounce", duration: 15, easing: "spring" },
    wordHighlight: { enabled: false, color: "#facc15", scale: 1.0, duration: 0 },
    exit: { type: "fadeOut", duration: 10, easing: "easeIn" },
  },
  slide: {
    entrance: { type: "slideIn", duration: 12, easing: "easeOut" },
    wordHighlight: { enabled: false, color: "#facc15", scale: 1.0, duration: 0 },
    exit: { type: "slideOut", duration: 12, easing: "easeIn" },
  },
  typewriter: {
    entrance: { type: "typewriter", duration: 20, easing: "linear" },
    wordHighlight: { enabled: false, color: "#facc15", scale: 1.0, duration: 0 },
    exit: { type: "fadeOut", duration: 8, easing: "easeIn" },
  },
  highlight: {
    entrance: { type: "fadeIn", duration: 8, easing: "easeOut" },
    wordHighlight: { enabled: true, color: "#facc15", scale: 1.05, duration: 0 },
    exit: { type: "fadeOut", duration: 12, easing: "easeIn" },
  },
  fade: {
    entrance: { type: "fadeIn", duration: 12, easing: "easeOut" },
    wordHighlight: { enabled: false, color: "#facc15", scale: 1.0, duration: 0 },
    exit: { type: "fadeOut", duration: 12, easing: "easeIn" },
  },
  custom: {
    entrance: { type: "fadeIn", duration: 10, easing: "easeOut" },
    wordHighlight: { enabled: false, color: "#facc15", scale: 1.0, duration: 0 },
    exit: { type: "fadeOut", duration: 10, easing: "easeIn" },
  },
};

export function createDefaultConfig(style: CreativeStyle = "karaoke"): RemotionConfig {
  return {
    version: "1.0",
    style,
    global: { ...DEFAULT_GLOBAL_CONFIG },
    animation: { ...STYLE_PRESETS[style] },
    segments: [],
  };
}

export function applyStylePreset(config: RemotionConfig, style: CreativeStyle): RemotionConfig {
  return {
    ...config,
    style,
    animation: { ...STYLE_PRESETS[style] },
  };
}

// Word-level timing from Whisper
export interface WordTiming {
  word: string;
  start: number; // seconds
  end: number; // seconds
  startFrame?: number; // computed from start * fps
  endFrame?: number; // computed from end * fps
  confidence?: number;
}

// Subtitle data structure for Remotion compositions
export interface SubtitleData {
  id: number;
  startFrame: number;
  endFrame: number;
  en: string;
  zh: string;
  speaker?: string | null;
  words?: WordTiming[];
  // For highlight style - words to emphasize
  highlightedWords?: string[];
  entityWords?: string[];
}

// Composition props for Remotion
export interface SubtitleCompositionProps {
  subtitles: SubtitleData[];
  config: RemotionConfig;
  videoSrc?: string;
  fps: number;
  width: number;
  height: number;
}

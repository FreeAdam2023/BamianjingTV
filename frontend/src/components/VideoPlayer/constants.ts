/**
 * VideoPlayer constants - fonts, colors, and default styles
 */

export interface SubtitleStyle {
  fontFamily: string;
  enFontSize: number;
  zhFontSize: number;
  enColor: string;
  zhColor: string;
  fontWeight: string;
  textShadow: boolean;
  backgroundColor: string;
}

export const DEFAULT_SUBTITLE_STYLE: SubtitleStyle = {
  fontFamily: "system-ui",
  enFontSize: 24,
  zhFontSize: 28,
  enColor: "#ffffff",
  zhColor: "#facc15", // yellow-400
  fontWeight: "500",
  textShadow: true,
  backgroundColor: "#1a2744",
};

export const FONT_FAMILIES = [
  { value: "system-ui", label: "System Default" },
  { value: "'Noto Sans SC', sans-serif", label: "Noto Sans SC" },
  { value: "'PingFang SC', sans-serif", label: "PingFang SC" },
  { value: "'Microsoft YaHei', sans-serif", label: "Microsoft YaHei" },
  { value: "serif", label: "Serif" },
  { value: "monospace", label: "Monospace" },
];

export const FONT_WEIGHTS = [
  { value: "400", label: "Normal" },
  { value: "500", label: "Medium" },
  { value: "600", label: "Semi-Bold" },
  { value: "700", label: "Bold" },
];

export const PRESET_COLORS = [
  "#ffffff", "#facc15", "#22c55e", "#3b82f6",
  "#a855f7", "#ef4444", "#f97316", "#14b8a6",
];

export const BACKGROUND_COLORS = [
  "#1a2744", "#000000", "#111827", "#1e3a5f", "#2d1f47"
];

export const STORAGE_KEYS = {
  SUBTITLE_STYLE: "subtitleStyle",
  WATERMARK: "videoWatermark",
} as const;

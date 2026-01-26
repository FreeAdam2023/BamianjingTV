"use client";

import { useRef, useEffect, useState, useCallback, forwardRef, useImperativeHandle } from "react";
import type { EditableSegment } from "@/lib/types";
import { formatDuration } from "@/lib/api";

interface SubtitleStyle {
  fontFamily: string;
  enFontSize: number;
  zhFontSize: number;
  enColor: string;
  zhColor: string;
  fontWeight: string;
  textShadow: boolean;
  backgroundColor: string;
}

const DEFAULT_SUBTITLE_STYLE: SubtitleStyle = {
  fontFamily: "system-ui",
  enFontSize: 24,
  zhFontSize: 28,
  enColor: "#ffffff",
  zhColor: "#facc15", // yellow-400
  fontWeight: "500",
  textShadow: true,
  backgroundColor: "#1a2744",
};

const FONT_FAMILIES = [
  { value: "system-ui", label: "System Default" },
  { value: "'Noto Sans SC', sans-serif", label: "Noto Sans SC" },
  { value: "'PingFang SC', sans-serif", label: "PingFang SC" },
  { value: "'Microsoft YaHei', sans-serif", label: "Microsoft YaHei" },
  { value: "serif", label: "Serif" },
  { value: "monospace", label: "Monospace" },
];

const FONT_WEIGHTS = [
  { value: "400", label: "Normal" },
  { value: "500", label: "Medium" },
  { value: "600", label: "Semi-Bold" },
  { value: "700", label: "Bold" },
];

const PRESET_COLORS = [
  "#ffffff", "#facc15", "#22c55e", "#3b82f6", "#a855f7", "#ef4444", "#f97316", "#14b8a6",
];

interface VideoPlayerProps {
  jobId: string;
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: number) => void;
}

export interface VideoPlayerRef {
  getVideoElement: () => HTMLVideoElement | null;
  play: () => void;
  pause: () => void;
  seekTo: (time: number) => void;
  getCurrentTime: () => number;
}

const VideoPlayer = forwardRef<VideoPlayerRef, VideoPlayerProps>(function VideoPlayer({
  jobId,
  segments,
  currentSegmentId,
  onTimeUpdate,
  onSegmentChange,
}, ref) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const containerRef = useRef<HTMLDivElement>(null);
  const watermarkInputRef = useRef<HTMLInputElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLooping, setIsLooping] = useState(false);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);

  // Subtitle area height ratio (0.3 to 0.7, default 0.5 = 50%)
  const [subtitleHeightRatio, setSubtitleHeightRatio] = useState(0.5);
  const [isDragging, setIsDragging] = useState(false);

  // Watermark
  const [watermarkUrl, setWatermarkUrl] = useState<string | null>(null);

  // Subtitle style settings
  const [subtitleStyle, setSubtitleStyle] = useState<SubtitleStyle>(DEFAULT_SUBTITLE_STYLE);
  const [showStyleSettings, setShowStyleSettings] = useState(false);

  // Expose methods via ref
  useImperativeHandle(ref, () => ({
    getVideoElement: () => videoRef.current,
    play: () => videoRef.current?.play(),
    pause: () => videoRef.current?.pause(),
    seekTo: (time: number) => {
      if (videoRef.current) {
        videoRef.current.currentTime = time;
      }
    },
    getCurrentTime: () => videoRef.current?.currentTime || 0,
  }), []);

  // Load watermark from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("videoWatermark");
    if (saved) {
      setWatermarkUrl(saved);
    }
  }, []);

  // Load subtitle style from localStorage on mount
  useEffect(() => {
    const saved = localStorage.getItem("subtitleStyle");
    if (saved) {
      try {
        const parsed = JSON.parse(saved);
        setSubtitleStyle({ ...DEFAULT_SUBTITLE_STYLE, ...parsed });
      } catch (e) {
        console.error("Failed to parse subtitle style:", e);
      }
    }
  }, []);

  // Save subtitle style to localStorage when it changes
  const updateSubtitleStyle = useCallback((updates: Partial<SubtitleStyle>) => {
    setSubtitleStyle((prev) => {
      const newStyle = { ...prev, ...updates };
      localStorage.setItem("subtitleStyle", JSON.stringify(newStyle));
      return newStyle;
    });
  }, []);

  // Reset subtitle style to defaults
  const resetSubtitleStyle = useCallback(() => {
    setSubtitleStyle(DEFAULT_SUBTITLE_STYLE);
    localStorage.setItem("subtitleStyle", JSON.stringify(DEFAULT_SUBTITLE_STYLE));
  }, []);

  // Handle watermark upload
  const handleWatermarkUpload = useCallback((e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    const reader = new FileReader();
    reader.onload = (event) => {
      const dataUrl = event.target?.result as string;
      setWatermarkUrl(dataUrl);
      localStorage.setItem("videoWatermark", dataUrl);
    };
    reader.readAsDataURL(file);
  }, []);

  // Remove watermark
  const handleRemoveWatermark = useCallback(() => {
    setWatermarkUrl(null);
    localStorage.removeItem("videoWatermark");
    if (watermarkInputRef.current) {
      watermarkInputRef.current.value = "";
    }
  }, []);

  // Find current segment based on time
  const findSegmentAtTime = useCallback(
    (time: number): EditableSegment | null => {
      return (
        segments.find(
          (seg) => time >= seg.start && time < seg.end
        ) || null
      );
    },
    [segments]
  );

  // Handle time update from video
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const handleTimeUpdate = () => {
      const time = video.currentTime;
      setCurrentTime(time);
      onTimeUpdate?.(time);

      // Update current segment
      const segment = findSegmentAtTime(time);
      if (segment && segment.id !== currentSegmentId) {
        onSegmentChange?.(segment.id);
      }

      // Handle looping
      if (isLooping && currentSegmentId !== null) {
        const currentSeg = segments.find((s) => s.id === currentSegmentId);
        if (currentSeg && time >= currentSeg.end) {
          video.currentTime = currentSeg.start;
        }
      }
    };

    const handleDurationChange = () => {
      setDuration(video.duration);
    };

    const handlePlay = () => setIsPlaying(true);
    const handlePause = () => setIsPlaying(false);

    video.addEventListener("timeupdate", handleTimeUpdate);
    video.addEventListener("durationchange", handleDurationChange);
    video.addEventListener("play", handlePlay);
    video.addEventListener("pause", handlePause);

    return () => {
      video.removeEventListener("timeupdate", handleTimeUpdate);
      video.removeEventListener("durationchange", handleDurationChange);
      video.removeEventListener("play", handlePlay);
      video.removeEventListener("pause", handlePause);
    };
  }, [
    currentSegmentId,
    isLooping,
    segments,
    findSegmentAtTime,
    onTimeUpdate,
    onSegmentChange,
  ]);

  // Handle drag to resize subtitle area
  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      const totalHeight = rect.height;
      const mouseY = e.clientY - rect.top;
      // Calculate ratio: video height / total height
      // Subtract controls bar height (~60px)
      const controlsHeight = 60;
      const availableHeight = totalHeight - controlsHeight;
      const videoHeight = mouseY;
      const newSubtitleRatio = 1 - (videoHeight / availableHeight);
      // Clamp between 0.2 and 0.7
      setSubtitleHeightRatio(Math.max(0.2, Math.min(0.7, newSubtitleRatio)));
    };

    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);

    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging]);

  // Public methods via ref
  const play = useCallback(() => videoRef.current?.play(), []);
  const pause = useCallback(() => videoRef.current?.pause(), []);
  const toggle = useCallback(() => {
    if (isPlaying) pause();
    else play();
  }, [isPlaying, play, pause]);

  const seekTo = useCallback((time: number) => {
    if (videoRef.current) {
      videoRef.current.currentTime = time;
    }
  }, []);

  const seekToSegment = useCallback(
    (segmentId: number) => {
      const segment = segments.find((s) => s.id === segmentId);
      if (segment) {
        seekTo(segment.start);
        onSegmentChange?.(segmentId);
      }
    },
    [segments, seekTo, onSegmentChange]
  );

  const playSegment = useCallback(
    (segmentId: number) => {
      seekToSegment(segmentId);
      play();
    },
    [seekToSegment, play]
  );

  const toggleLoop = useCallback(() => {
    setIsLooping((prev) => !prev);
  }, []);

  // Volume controls
  const handleVolumeChange = useCallback((newVolume: number) => {
    setVolume(newVolume);
    if (videoRef.current) {
      videoRef.current.volume = newVolume;
      if (newVolume > 0 && isMuted) {
        setIsMuted(false);
        videoRef.current.muted = false;
      }
    }
  }, [isMuted]);

  const toggleMute = useCallback(() => {
    if (videoRef.current) {
      const newMuted = !isMuted;
      setIsMuted(newMuted);
      videoRef.current.muted = newMuted;
    }
  }, [isMuted]);

  // Keyboard shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      // Ignore if in input field
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      switch (e.key) {
        case " ":
          e.preventDefault();
          toggle();
          break;
        case "l":
        case "L":
          e.preventDefault();
          toggleLoop();
          break;
        case "Enter":
          e.preventDefault();
          if (currentSegmentId !== null) {
            playSegment(currentSegmentId);
          }
          break;
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [toggle, toggleLoop, playSegment, currentSegmentId]);

  // Get current segment for subtitle display
  const currentSegment = currentSegmentId !== null
    ? segments.find((s) => s.id === currentSegmentId)
    : findSegmentAtTime(currentTime);

  // Video source URL (proxied through Next.js rewrite)
  const videoUrl = `/api/jobs/${jobId}/video`;

  // Calculate font sizes based on subtitle height ratio and style settings
  const fontScale = subtitleHeightRatio / 0.5;
  const englishFontSize = Math.max(14, Math.min(48, subtitleStyle.enFontSize * fontScale));
  const chineseFontSize = Math.max(16, Math.min(56, subtitleStyle.zhFontSize * fontScale));

  // Text shadow style for better visibility
  const textShadowStyle = subtitleStyle.textShadow
    ? "2px 2px 4px rgba(0,0,0,0.8), -1px -1px 2px rgba(0,0,0,0.5)"
    : "none";

  return (
    <div
      ref={containerRef}
      className="flex flex-col bg-black rounded-lg overflow-hidden"
      style={{ height: "100%" }}
    >
      {/* Video area */}
      <div
        className="relative flex-shrink-0"
        style={{ height: `${(1 - subtitleHeightRatio) * 100}%` }}
      >
        <video
          ref={videoRef}
          src={videoUrl}
          className="w-full h-full object-contain cursor-pointer bg-black"
          preload="metadata"
          onClick={toggle}
        />
        {/* Watermark overlay */}
        {watermarkUrl && (
          <div className="absolute top-3 left-3 pointer-events-none">
            <img
              src={watermarkUrl}
              alt="Watermark"
              className="max-h-16 max-w-32 object-contain opacity-90"
            />
          </div>
        )}
      </div>

      {/* Drag handle to resize */}
      <div
        className="h-1 bg-gray-600 hover:bg-blue-500 cursor-ns-resize flex-shrink-0 relative group"
        onMouseDown={() => setIsDragging(true)}
      >
        <div className="absolute inset-x-0 -top-2 -bottom-2" />
        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 w-12 h-1 bg-gray-400 rounded group-hover:bg-blue-400" />
      </div>

      {/* Subtitle area */}
      <div
        className="flex-1 flex flex-col items-center justify-center px-8 py-4 min-h-0 relative"
        style={{ backgroundColor: subtitleStyle.backgroundColor }}
      >
        {currentSegment ? (
          <>
            {/* English text */}
            <div
              className="text-center leading-relaxed mb-4"
              style={{
                fontSize: `${englishFontSize}px`,
                fontFamily: subtitleStyle.fontFamily,
                fontWeight: subtitleStyle.fontWeight,
                color: subtitleStyle.enColor,
                textShadow: textShadowStyle,
              }}
            >
              {currentSegment.en}
            </div>
            {/* Chinese text */}
            <div
              className="text-center leading-relaxed"
              style={{
                fontSize: `${chineseFontSize}px`,
                fontFamily: subtitleStyle.fontFamily,
                fontWeight: subtitleStyle.fontWeight,
                color: subtitleStyle.zhColor,
                textShadow: textShadowStyle,
              }}
            >
              {currentSegment.zh}
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
          <div className="absolute top-10 right-2 w-72 bg-gray-800 rounded-lg shadow-xl p-4 z-20 text-sm">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-white font-medium">Subtitle Style</h3>
              <button
                onClick={resetSubtitleStyle}
                className="text-xs text-gray-400 hover:text-white"
              >
                Reset
              </button>
            </div>

            {/* Font family */}
            <div className="mb-3">
              <label className="block text-gray-400 text-xs mb-1">Font Family</label>
              <select
                value={subtitleStyle.fontFamily}
                onChange={(e) => updateSubtitleStyle({ fontFamily: e.target.value })}
                className="w-full bg-gray-700 text-white rounded px-2 py-1.5 text-sm"
              >
                {FONT_FAMILIES.map((f) => (
                  <option key={f.value} value={f.value}>{f.label}</option>
                ))}
              </select>
            </div>

            {/* Font sizes */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-gray-400 text-xs mb-1">EN Size: {subtitleStyle.enFontSize}px</label>
                <input
                  type="range"
                  min="14"
                  max="48"
                  value={subtitleStyle.enFontSize}
                  onChange={(e) => updateSubtitleStyle({ enFontSize: parseInt(e.target.value) })}
                  className="w-full h-1 bg-gray-600 rounded-full appearance-none cursor-pointer"
                />
              </div>
              <div>
                <label className="block text-gray-400 text-xs mb-1">ZH Size: {subtitleStyle.zhFontSize}px</label>
                <input
                  type="range"
                  min="16"
                  max="56"
                  value={subtitleStyle.zhFontSize}
                  onChange={(e) => updateSubtitleStyle({ zhFontSize: parseInt(e.target.value) })}
                  className="w-full h-1 bg-gray-600 rounded-full appearance-none cursor-pointer"
                />
              </div>
            </div>

            {/* Font weight */}
            <div className="mb-3">
              <label className="block text-gray-400 text-xs mb-1">Font Weight</label>
              <div className="flex gap-1">
                {FONT_WEIGHTS.map((w) => (
                  <button
                    key={w.value}
                    onClick={() => updateSubtitleStyle({ fontWeight: w.value })}
                    className={`flex-1 py-1 text-xs rounded ${
                      subtitleStyle.fontWeight === w.value
                        ? "bg-blue-500 text-white"
                        : "bg-gray-700 text-gray-300 hover:bg-gray-600"
                    }`}
                  >
                    {w.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Colors */}
            <div className="grid grid-cols-2 gap-3 mb-3">
              <div>
                <label className="block text-gray-400 text-xs mb-1">EN Color</label>
                <div className="flex flex-wrap gap-1">
                  {PRESET_COLORS.map((color) => (
                    <button
                      key={color}
                      onClick={() => updateSubtitleStyle({ enColor: color })}
                      className={`w-5 h-5 rounded border-2 ${
                        subtitleStyle.enColor === color ? "border-white" : "border-transparent"
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-gray-400 text-xs mb-1">ZH Color</label>
                <div className="flex flex-wrap gap-1">
                  {PRESET_COLORS.map((color) => (
                    <button
                      key={color}
                      onClick={() => updateSubtitleStyle({ zhColor: color })}
                      className={`w-5 h-5 rounded border-2 ${
                        subtitleStyle.zhColor === color ? "border-white" : "border-transparent"
                      }`}
                      style={{ backgroundColor: color }}
                    />
                  ))}
                </div>
              </div>
            </div>

            {/* Text shadow toggle */}
            <div className="flex items-center justify-between mb-3">
              <label className="text-gray-400 text-xs">Text Shadow</label>
              <button
                onClick={() => updateSubtitleStyle({ textShadow: !subtitleStyle.textShadow })}
                className={`w-10 h-5 rounded-full transition-colors ${
                  subtitleStyle.textShadow ? "bg-blue-500" : "bg-gray-600"
                }`}
              >
                <div
                  className={`w-4 h-4 bg-white rounded-full transition-transform ${
                    subtitleStyle.textShadow ? "translate-x-5" : "translate-x-0.5"
                  }`}
                />
              </button>
            </div>

            {/* Background color */}
            <div>
              <label className="block text-gray-400 text-xs mb-1">Background</label>
              <div className="flex gap-1">
                {["#1a2744", "#000000", "#111827", "#1e3a5f", "#2d1f47"].map((color) => (
                  <button
                    key={color}
                    onClick={() => updateSubtitleStyle({ backgroundColor: color })}
                    className={`w-8 h-5 rounded border-2 ${
                      subtitleStyle.backgroundColor === color ? "border-white" : "border-gray-500"
                    }`}
                    style={{ backgroundColor: color }}
                  />
                ))}
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Controls bar */}
      <div className="bg-gray-900 p-3 flex-shrink-0">
        {/* Progress bar */}
        <div
          className="h-1 bg-gray-600 rounded-full mb-3 cursor-pointer"
          onClick={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const ratio = (e.clientX - rect.left) / rect.width;
            seekTo(ratio * duration);
          }}
        >
          <div
            className="h-1 bg-blue-500 rounded-full"
            style={{ width: `${(currentTime / duration) * 100}%` }}
          />
        </div>

        {/* Control buttons */}
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-4">
            {/* Play/Pause */}
            <button
              onClick={toggle}
              className="text-white hover:text-blue-400"
              title="Space to toggle"
            >
              {isPlaying ? (
                <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
                </svg>
              ) : (
                <svg className="w-8 h-8" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M8 5v14l11-7z" />
                </svg>
              )}
            </button>

            {/* Time display */}
            <span className="text-white text-sm">
              {formatDuration(currentTime)} / {formatDuration(duration)}
            </span>

            {/* Volume control */}
            <div className="flex items-center gap-2">
              <button
                onClick={toggleMute}
                className="text-white hover:text-blue-400"
                title={isMuted ? "Unmute" : "Mute"}
              >
                {isMuted || volume === 0 ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
                  </svg>
                ) : volume < 0.5 ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M18.5 12c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM5 9v6h4l5 5V4L9 9H5z" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                  </svg>
                )}
              </button>
              <input
                type="range"
                min="0"
                max="1"
                step="0.05"
                value={isMuted ? 0 : volume}
                onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                className="w-20 h-1 bg-gray-600 rounded-full appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-white"
              />
            </div>
          </div>

          <div className="flex items-center gap-3">
            {/* Watermark upload */}
            <input
              ref={watermarkInputRef}
              type="file"
              accept="image/*"
              onChange={handleWatermarkUpload}
              className="hidden"
              id="watermark-upload"
            />
            {watermarkUrl ? (
              <div className="flex items-center gap-1">
                <img src={watermarkUrl} alt="Logo" className="h-6 w-6 object-contain rounded" />
                <button
                  onClick={handleRemoveWatermark}
                  className="text-xs text-red-400 hover:text-red-300"
                  title="Remove watermark"
                >
                  ✕
                </button>
              </div>
            ) : (
              <button
                onClick={() => watermarkInputRef.current?.click()}
                className="text-sm px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center gap-1"
                title="Upload watermark logo"
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                </svg>
                Logo
              </button>
            )}

            {/* Loop toggle */}
            <button
              onClick={toggleLoop}
              className={`text-sm px-2 py-1 rounded ${
                isLooping
                  ? "bg-blue-500 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
              title="L to toggle loop"
            >
              Loop
            </button>
          </div>
        </div>
      </div>
    </div>
  );
});

export default VideoPlayer;

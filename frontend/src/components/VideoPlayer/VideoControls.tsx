/**
 * VideoControls - Playback controls bar
 */

import { useRef, useCallback, useState, useEffect } from "react";
import { formatDuration } from "@/lib/api";

/** Spinner SVG used across multiple components */
function Spinner({ className = "h-3 w-3" }: { className?: string }) {
  return (
    <svg className={`animate-spin ${className}`} viewBox="0 0 24 24">
      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
    </svg>
  );
}

/** Translation engine options */
const TRANSLATION_ENGINES = [
  { value: "", label: "Azure 翻译 (默认)" },
  { value: "gpt-4o", label: "GPT-4o" },
  { value: "gpt-4o-mini", label: "GPT-4o-mini" },
  { value: "deepseek-chat", label: "DeepSeek" },
] as const;

/** Transcription source (Whisper only) */

/**
 * RetranslateDropdown - Dropdown panel for translation model selection and retranscription
 */
function RetranslateDropdown({
  regenerating,
  regenerateProgress,
  onRegenerateTranslation,
  onRetranscribe,
}: {
  regenerating: boolean;
  regenerateProgress?: { current: number; total: number } | null;
  onRegenerateTranslation: (model?: string) => void;
  onRetranscribe?: (source: "whisper", model?: string) => void;
}) {
  const [isOpen, setIsOpen] = useState(false);
  const [selectedEngine, setSelectedEngine] = useState("");
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on outside click
  useEffect(() => {
    if (!isOpen) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [isOpen]);

  const handleRetranslate = () => {
    onRegenerateTranslation(selectedEngine || undefined);
    setIsOpen(false);
  };

  const handleRetranscribe = () => {
    onRetranscribe?.("whisper", selectedEngine || undefined);
    setIsOpen(false);
  };

  return (
    <div className="relative" ref={dropdownRef}>
      {/* Split button: main action + dropdown arrow */}
      <div className="flex items-center">
        <button
          onClick={() => onRegenerateTranslation(undefined)}
          disabled={regenerating}
          className="px-2 py-1 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded-l disabled:opacity-50 flex items-center gap-1"
          title="使用默认引擎重译中文"
        >
          {regenerating ? (
            <>
              <Spinner />
              {regenerateProgress
                ? `${regenerateProgress.current}/${regenerateProgress.total}`
                : "处理中..."}
            </>
          ) : (
            <>
              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
              </svg>
              重译
            </>
          )}
        </button>
        <button
          onClick={() => setIsOpen(!isOpen)}
          disabled={regenerating}
          className="px-1.5 py-1 text-sm bg-purple-700 hover:bg-purple-800 text-white rounded-r border-l border-purple-500 disabled:opacity-50"
          title="选择翻译引擎"
        >
          <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </button>
      </div>

      {/* Dropdown panel */}
      {isOpen && (
        <div className="absolute bottom-full mb-2 right-0 w-64 bg-gray-800 border border-gray-600 rounded-lg shadow-xl z-50 p-3">
          {/* Translation engine section */}
          <div className="mb-3">
            <div className="text-xs text-gray-400 mb-2 font-medium">翻译引擎</div>
            <div className="space-y-1">
              {TRANSLATION_ENGINES.map((engine) => (
                <label
                  key={engine.value}
                  className="flex items-center gap-2 px-2 py-1 rounded hover:bg-gray-700 cursor-pointer text-sm text-white"
                >
                  <input
                    type="radio"
                    name="engine"
                    value={engine.value}
                    checked={selectedEngine === engine.value}
                    onChange={(e) => setSelectedEngine(e.target.value)}
                    className="accent-purple-500"
                  />
                  {engine.label}
                </label>
              ))}
            </div>
            <button
              onClick={handleRetranslate}
              disabled={regenerating}
              className="w-full mt-2 px-3 py-1.5 text-sm bg-purple-600 hover:bg-purple-700 text-white rounded disabled:opacity-50"
            >
              重译中文
            </button>
          </div>

          {/* Divider */}
          <div className="border-t border-gray-600 my-2" />

          {/* Retranscription section */}
          {onRetranscribe && (
            <div>
              <div className="text-xs text-gray-400 mb-2 font-medium">重新转录 (Whisper large-v3)</div>
              <button
                onClick={handleRetranscribe}
                disabled={regenerating}
                className="w-full px-3 py-1.5 text-sm bg-orange-600 hover:bg-orange-700 text-white rounded disabled:opacity-50"
              >
                重新转录 + 翻译
              </button>
              <p className="text-xs text-amber-400 mt-1.5 flex items-center gap-1">
                <svg className="w-3 h-3 flex-shrink-0" fill="currentColor" viewBox="0 0 20 20">
                  <path fillRule="evenodd" d="M8.257 3.099c.765-1.36 2.722-1.36 3.486 0l5.58 9.92c.75 1.334-.213 2.98-1.742 2.98H4.42c-1.53 0-2.493-1.646-1.743-2.98l5.58-9.92zM11 13a1 1 0 11-2 0 1 1 0 012 0zm-1-8a1 1 0 00-1 1v3a1 1 0 002 0V6a1 1 0 00-1-1z" clipRule="evenodd" />
                </svg>
                英文+中文都会更新
              </p>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

/**
 * Chinese Language Selector - Dropdown with confirm button and regenerate translation
 */
function ChineseLanguageSelector({
  useTraditional,
  converting,
  segmentCount,
  onConvert,
  regenerating,
  regenerateProgress,
  onRegenerateTranslation,
  onRetranscribe,
}: {
  useTraditional: boolean;
  converting: boolean;
  segmentCount: number;
  onConvert: (toTraditional: boolean) => void;
  regenerating?: boolean;
  regenerateProgress?: { current: number; total: number } | null;
  onRegenerateTranslation?: (model?: string) => void;
  onRetranscribe?: (source: "whisper", model?: string) => void;
}) {
  const [selectedValue, setSelectedValue] = useState<string>(
    useTraditional ? "traditional" : "simplified"
  );

  // Check if selection differs from current state
  const needsConversion =
    (selectedValue === "traditional" && !useTraditional) ||
    (selectedValue === "simplified" && useTraditional);

  const handleConfirm = () => {
    if (needsConversion && !converting) {
      onConvert(selectedValue === "traditional");
    }
  };

  return (
    <div className="flex items-center gap-1">
      {/* Current status indicator */}
      <span className="text-xs text-gray-400">
        字幕:
      </span>

      {/* Dropdown */}
      <select
        value={selectedValue}
        onChange={(e) => setSelectedValue(e.target.value)}
        disabled={converting || regenerating}
        className="bg-gray-700 text-white text-sm px-2 py-1 rounded border-none outline-none cursor-pointer disabled:opacity-50"
      >
        <option value="simplified">简体中文</option>
        <option value="traditional">繁体中文</option>
      </select>

      {/* Confirm button - only show when selection differs */}
      {needsConversion && (
        <button
          onClick={handleConfirm}
          disabled={converting || regenerating}
          className="px-2 py-1 text-sm bg-orange-500 hover:bg-orange-600 text-white rounded disabled:opacity-50 flex items-center gap-1"
        >
          {converting ? (
            <>
              <Spinner />
              {segmentCount} 条
            </>
          ) : (
            "应用"
          )}
        </button>
      )}

      {/* Current state indicator when no change needed */}
      {!needsConversion && !converting && !regenerating && (
        <span className="text-xs text-green-400">✓</span>
      )}

      {/* Regenerate Translation Dropdown */}
      {onRegenerateTranslation && (
        <div className="ml-1">
          <RetranslateDropdown
            regenerating={regenerating ?? false}
            regenerateProgress={regenerateProgress}
            onRegenerateTranslation={onRegenerateTranslation}
            onRetranscribe={onRetranscribe}
          />
        </div>
      )}
    </div>
  );
}

interface VideoControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  isLooping: boolean;
  watermarkUrl: string | null;
  coverFrameTime: number | null;
  // Video trim (WYSIWYG)
  trimStart?: number;
  trimEnd?: number | null;
  sourceDuration?: number;
  // Chinese conversion
  useTraditional?: boolean;
  converting?: boolean;
  segmentCount?: number;
  onConvertChinese?: (toTraditional: boolean) => void;
  // Regenerate translation
  regenerating?: boolean;
  regenerateProgress?: { current: number; total: number } | null;
  onRegenerateTranslation?: (model?: string) => void;
  onRetranscribe?: (source: "whisper", model?: string) => void;
  // Export preview
  hasExportFull?: boolean;
  hasExportEssence?: boolean;
  onPreviewExport?: (type: "full" | "essence") => void;
  // Handlers
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onVolumeChange: (volume: number) => void;
  onToggleMute: () => void;
  onToggleLoop: () => void;
  onWatermarkUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onWatermarkRemove: () => void;
  onSetCover?: () => void;
  // Fullscreen
  isFullscreen?: boolean;
  onToggleFullscreen?: () => void;
}

export default function VideoControls({
  isPlaying,
  currentTime,
  duration,
  volume,
  isMuted,
  isLooping,
  watermarkUrl,
  coverFrameTime,
  trimStart = 0,
  trimEnd = null,
  sourceDuration = 0,
  useTraditional,
  converting,
  segmentCount,
  onConvertChinese,
  regenerating,
  regenerateProgress,
  onRegenerateTranslation,
  onRetranscribe,
  hasExportFull = false,
  hasExportEssence = false,
  onPreviewExport,
  onTogglePlay,
  onSeek,
  onVolumeChange,
  onToggleMute,
  onToggleLoop,
  onWatermarkUpload,
  onWatermarkRemove,
  onSetCover,
  isFullscreen = false,
  onToggleFullscreen,
}: VideoControlsProps) {
  const watermarkInputRef = useRef<HTMLInputElement>(null);
  const progressBarRef = useRef<HTMLDivElement>(null);
  const [hoverTime, setHoverTime] = useState<number | null>(null);
  const [hoverX, setHoverX] = useState<number>(0);

  // Calculate effective values for WYSIWYG trim display
  const effectiveSourceDuration = sourceDuration || duration;
  const actualTrimEnd = trimEnd ?? effectiveSourceDuration;
  const effectiveDuration = actualTrimEnd - trimStart;
  const hasTrim = trimStart > 0 || trimEnd !== null;

  // Display time relative to trim start
  const displayTime = currentTime - trimStart;
  const displayDuration = effectiveDuration;

  const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    // Seek to actual video time (trimStart + ratio * effectiveDuration)
    onSeek(trimStart + ratio * effectiveDuration);
  }, [trimStart, effectiveDuration, onSeek]);

  const handleProgressMouseMove = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
    // Show hover time relative to trim (display time)
    setHoverTime(ratio * effectiveDuration);
    setHoverX(e.clientX - rect.left);
  }, [effectiveDuration]);

  const handleProgressMouseLeave = useCallback(() => {
    setHoverTime(null);
  }, []);

  return (
    <div className="bg-gray-900 p-3 flex-shrink-0">
      {/* Progress bar */}
      <div
        ref={progressBarRef}
        className="h-2 bg-gray-600 rounded-full mb-3 cursor-pointer relative group"
        onClick={handleProgressClick}
        onMouseMove={handleProgressMouseMove}
        onMouseLeave={handleProgressMouseLeave}
      >
        {/* Progress fill - based on display time within trimmed range */}
        <div
          className="h-full bg-blue-500 rounded-full pointer-events-none"
          style={{ width: `${effectiveDuration > 0 ? (displayTime / effectiveDuration) * 100 : 0}%` }}
        />
        {/* Hover indicator line */}
        {hoverTime !== null && (
          <div
            className="absolute top-0 h-full w-0.5 bg-white/50 pointer-events-none"
            style={{ left: `${hoverX}px` }}
          />
        )}
        {/* Time tooltip */}
        {hoverTime !== null && (
          <div
            className="absolute -top-8 transform -translate-x-1/2 bg-black/90 text-white text-xs px-2 py-1 rounded whitespace-nowrap pointer-events-none z-10"
            style={{ left: `${hoverX}px` }}
          >
            {formatDuration(hoverTime)}
          </div>
        )}
      </div>

      {/* Control buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Rewind 5s - constrained to trim range */}
          <button
            onClick={() => onSeek(Math.max(trimStart, currentTime - 5))}
            className="text-white hover:text-blue-400 p-1"
            title="后退5秒 (←)"
            aria-label="后退5秒"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
              <text x="12" y="15" textAnchor="middle" fontSize="7" fill="currentColor">5</text>
            </svg>
          </button>

          {/* Play/Pause */}
          <button
            onClick={onTogglePlay}
            className="text-white hover:text-blue-400"
            title="空格键切换"
            aria-label={isPlaying ? "暂停" : "播放"}
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

          {/* Forward 5s - constrained to trim range */}
          <button
            onClick={() => onSeek(Math.min(actualTrimEnd, currentTime + 5))}
            className="text-white hover:text-blue-400 p-1"
            title="前进5秒 (→)"
            aria-label="前进5秒"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
              <text x="12" y="15" textAnchor="middle" fontSize="7" fill="currentColor">5</text>
            </svg>
          </button>

          {/* Time display - shows trimmed time if trim is active */}
          <span className="text-white text-sm ml-2">
            {formatDuration(Math.max(0, displayTime))} / {formatDuration(displayDuration)}
            {hasTrim && (
              <span className="ml-1 text-purple-400 text-xs" title={`Trim range: ${formatDuration(trimStart)} - ${formatDuration(actualTrimEnd)}`}>
                ✂️
              </span>
            )}
          </span>

          {/* Volume control */}
          <div className="flex items-center gap-2">
            <button
              onClick={onToggleMute}
              className="text-white hover:text-blue-400"
              title={isMuted ? "取消静音" : "静音"}
              aria-label={isMuted ? "取消静音" : "静音"}
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
              onChange={(e) => onVolumeChange(parseFloat(e.target.value))}
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
            onChange={onWatermarkUpload}
            className="hidden"
            id="watermark-upload"
          />
          {watermarkUrl ? (
            <div className="flex items-center gap-1">
              <img src={watermarkUrl} alt="Logo" className="h-6 w-6 object-contain rounded" />
              <button
                onClick={onWatermarkRemove}
                className="text-xs text-red-400 hover:text-red-300"
                title="移除水印"
                aria-label="移除水印"
              >
                ✕
              </button>
            </div>
          ) : (
            <button
              onClick={() => watermarkInputRef.current?.click()}
              className="text-sm px-2 py-1 rounded bg-gray-700 text-gray-300 hover:bg-gray-600 flex items-center gap-1"
              title="上传水印标志"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              水印
            </button>
          )}

          {/* Set as Cover */}
          {onSetCover && (
            <button
              onClick={onSetCover}
              className={`text-sm px-2 py-1 rounded flex items-center gap-1 ${
                coverFrameTime !== null
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
              title="将当前帧设为封面"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              {coverFrameTime !== null ? `封面 @${formatDuration(coverFrameTime)}` : "设为封面"}
            </button>
          )}

          {/* Export Preview Buttons */}
          {(hasExportFull || hasExportEssence) && onPreviewExport && (
            <div className="flex items-center gap-1">
              {hasExportFull && (
                <button
                  onClick={() => onPreviewExport("full")}
                  className="text-xs px-2 py-1 rounded bg-green-600 hover:bg-green-700 text-white flex items-center gap-1"
                  title="预览完整导出（带字幕）"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  预览完整
                </button>
              )}
              {hasExportEssence && (
                <button
                  onClick={() => onPreviewExport("essence")}
                  className="text-xs px-2 py-1 rounded bg-purple-600 hover:bg-purple-700 text-white flex items-center gap-1"
                  title="预览精华导出（仅保留片段）"
                >
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  预览精华
                </button>
              )}
            </div>
          )}

          {/* Loop toggle */}
          <button
            onClick={onToggleLoop}
            className={`text-sm px-2 py-1 rounded ${
              isLooping
                ? "bg-blue-500 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            title="L键切换循环"
          >
            循环
          </button>

          {/* Fullscreen toggle */}
          {onToggleFullscreen && (
            <button
              onClick={onToggleFullscreen}
              className="text-white hover:text-blue-400 p-1"
              title={isFullscreen ? "退出全屏 (F)" : "全屏预览 (F)"}
              aria-label={isFullscreen ? "退出全屏" : "全屏预览"}
            >
              {isFullscreen ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 9V4.5M9 9H4.5M9 9L3.75 3.75M9 15v4.5M9 15H4.5M9 15l-5.25 5.25M15 9h4.5M15 9V4.5M15 9l5.25-5.25M15 15h4.5M15 15v4.5m0-4.5l5.25 5.25" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M3.75 3.75v4.5m0-4.5h4.5m-4.5 0L9 9M3.75 20.25v-4.5m0 4.5h4.5m-4.5 0L9 15M20.25 3.75h-4.5m4.5 0v4.5m0-4.5L15 9m5.25 11.25h-4.5m4.5 0v-4.5m0 4.5L15 15" />
                </svg>
              )}
            </button>
          )}

          {/* Chinese Subtitle Language Selector */}
          {onConvertChinese && (
            <ChineseLanguageSelector
              useTraditional={useTraditional ?? true}
              converting={converting ?? false}
              segmentCount={segmentCount ?? 0}
              onConvert={onConvertChinese}
              regenerating={regenerating}
              regenerateProgress={regenerateProgress}
              onRegenerateTranslation={onRegenerateTranslation}
              onRetranscribe={onRetranscribe}
            />
          )}
        </div>
      </div>
    </div>
  );
}

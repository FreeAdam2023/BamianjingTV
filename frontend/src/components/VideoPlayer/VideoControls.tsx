/**
 * VideoControls - Playback controls bar
 */

import { useRef, useCallback } from "react";
import { formatDuration } from "@/lib/api";

interface VideoControlsProps {
  isPlaying: boolean;
  currentTime: number;
  duration: number;
  volume: number;
  isMuted: boolean;
  isLooping: boolean;
  watermarkUrl: string | null;
  coverFrameTime: number | null;
  // Chinese conversion
  useTraditional?: boolean;
  converting?: boolean;
  segmentCount?: number;
  onConvertChinese?: (toTraditional: boolean) => void;
  // Handlers
  onTogglePlay: () => void;
  onSeek: (time: number) => void;
  onVolumeChange: (volume: number) => void;
  onToggleMute: () => void;
  onToggleLoop: () => void;
  onWatermarkUpload: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onWatermarkRemove: () => void;
  onSetCover?: () => void;
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
  useTraditional,
  converting,
  segmentCount,
  onConvertChinese,
  onTogglePlay,
  onSeek,
  onVolumeChange,
  onToggleMute,
  onToggleLoop,
  onWatermarkUpload,
  onWatermarkRemove,
  onSetCover,
}: VideoControlsProps) {
  const watermarkInputRef = useRef<HTMLInputElement>(null);

  const handleProgressClick = useCallback((e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    onSeek(ratio * duration);
  }, [duration, onSeek]);

  return (
    <div className="bg-gray-900 p-3 flex-shrink-0">
      {/* Progress bar */}
      <div
        className="h-1 bg-gray-600 rounded-full mb-3 cursor-pointer"
        onClick={handleProgressClick}
      >
        <div
          className="h-1 bg-blue-500 rounded-full"
          style={{ width: `${(currentTime / duration) * 100}%` }}
        />
      </div>

      {/* Control buttons */}
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          {/* Rewind 5s */}
          <button
            onClick={() => onSeek(Math.max(0, currentTime - 5))}
            className="text-white hover:text-blue-400 p-1"
            title="Rewind 5s (←)"
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

          {/* Forward 5s */}
          <button
            onClick={() => onSeek(Math.min(duration, currentTime + 5))}
            className="text-white hover:text-blue-400 p-1"
            title="Forward 5s (→)"
          >
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
              <text x="12" y="15" textAnchor="middle" fontSize="7" fill="currentColor">5</text>
            </svg>
          </button>

          {/* Time display */}
          <span className="text-white text-sm ml-2">
            {formatDuration(currentTime)} / {formatDuration(duration)}
          </span>

          {/* Volume control */}
          <div className="flex items-center gap-2">
            <button
              onClick={onToggleMute}
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

          {/* Set as Cover */}
          {onSetCover && (
            <button
              onClick={onSetCover}
              className={`text-sm px-2 py-1 rounded flex items-center gap-1 ${
                coverFrameTime !== null
                  ? "bg-purple-600 text-white"
                  : "bg-gray-700 text-gray-300 hover:bg-gray-600"
              }`}
              title="Set current frame as thumbnail cover"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
              </svg>
              {coverFrameTime !== null ? `Cover @${formatDuration(coverFrameTime)}` : "Set Cover"}
            </button>
          )}

          {/* Loop toggle */}
          <button
            onClick={onToggleLoop}
            className={`text-sm px-2 py-1 rounded ${
              isLooping
                ? "bg-blue-500 text-white"
                : "bg-gray-700 text-gray-300 hover:bg-gray-600"
            }`}
            title="L to toggle loop"
          >
            Loop
          </button>

          {/* Chinese 简/繁 Toggle */}
          {onConvertChinese && (
            <div className="flex items-center gap-1">
              {/* Converting status */}
              {converting && segmentCount && (
                <span className="text-xs text-orange-400 animate-pulse">
                  {segmentCount}条...
                </span>
              )}
              <div className="flex items-center bg-gray-700 rounded overflow-hidden">
                <button
                  onClick={() => onConvertChinese(false)}
                  disabled={converting || !useTraditional}
                  className={`px-2 py-1 text-sm transition-colors flex items-center gap-1 ${
                    !useTraditional
                      ? "bg-orange-500 text-white"
                      : "text-gray-400 hover:text-white hover:bg-gray-600"
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                  title="Simplified Chinese"
                >
                  {converting && !useTraditional && (
                    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  简
                </button>
                <button
                  onClick={() => onConvertChinese(true)}
                  disabled={converting || useTraditional}
                  className={`px-2 py-1 text-sm transition-colors flex items-center gap-1 ${
                    useTraditional
                      ? "bg-orange-500 text-white"
                      : "text-gray-400 hover:text-white hover:bg-gray-600"
                  } disabled:opacity-50 disabled:cursor-not-allowed`}
                  title="Traditional Chinese"
                >
                  {converting && useTraditional && (
                    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                  )}
                  繁
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

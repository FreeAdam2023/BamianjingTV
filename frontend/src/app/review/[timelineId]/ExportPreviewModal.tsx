"use client";

/**
 * ExportPreviewModal - Modal for previewing exported videos
 */

import { useEffect, useState, useRef } from "react";
import { formatDuration } from "@/lib/api";

type PreviewType = "full" | "essence";

interface ExportPreviewModalProps {
  jobId: string;
  type: PreviewType;
  onClose: () => void;
}

export default function ExportPreviewModal({
  jobId,
  type,
  onClose,
}: ExportPreviewModalProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  // ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
      if (e.key === " ") {
        e.preventDefault();
        if (videoRef.current) {
          if (videoRef.current.paused) {
            videoRef.current.play();
          } else {
            videoRef.current.pause();
          }
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const getBaseUrl = () => {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8001`;
  };

  const videoUrl = `${getBaseUrl()}/jobs/${jobId}/video/preview/${type}`;
  const downloadUrl = `${getBaseUrl()}/timelines/${jobId}/video/${type}`;

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      setCurrentTime(videoRef.current.currentTime);
    }
  };

  const handleDurationChange = () => {
    if (videoRef.current) {
      setDuration(videoRef.current.duration);
    }
  };

  const handleSeek = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const ratio = (e.clientX - rect.left) / rect.width;
    if (videoRef.current) {
      videoRef.current.currentTime = ratio * duration;
    }
  };

  const togglePlay = () => {
    if (videoRef.current) {
      if (videoRef.current.paused) {
        videoRef.current.play();
      } else {
        videoRef.current.pause();
      }
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/80 flex items-center justify-center z-50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-gray-900 rounded-lg w-[90vw] max-w-[1200px] max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-4 py-3 border-b border-gray-700 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className={`px-2 py-1 rounded text-sm font-medium ${
              type === "full" ? "bg-green-600" : "bg-purple-600"
            }`}>
              {type === "full" ? "完整导出" : "精华导出"}
            </span>
            <span className="text-gray-400 text-sm">
              导出预览
            </span>
          </div>
          <div className="flex items-center gap-2">
            <a
              href={downloadUrl}
              download
              className="px-3 py-1.5 text-sm bg-blue-600 hover:bg-blue-700 rounded flex items-center gap-1"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
              </svg>
              下载
            </a>
            <button
              onClick={onClose}
              className="text-gray-400 hover:text-white p-1"
              title="关闭 (Esc)"
              aria-label="关闭预览"
            >
              <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>

        {/* Video */}
        <div className="flex-1 bg-black flex items-center justify-center min-h-0">
          <video
            ref={videoRef}
            src={videoUrl}
            className="max-w-full max-h-full"
            onClick={togglePlay}
            onTimeUpdate={handleTimeUpdate}
            onDurationChange={handleDurationChange}
            onPlay={() => setIsPlaying(true)}
            onPause={() => setIsPlaying(false)}
            autoPlay
          />
        </div>

        {/* Controls */}
        <div className="px-4 py-3 border-t border-gray-700">
          {/* Progress bar */}
          <div
            className="h-2 bg-gray-700 rounded-full mb-3 cursor-pointer"
            onClick={handleSeek}
          >
            <div
              className="h-full bg-blue-500 rounded-full"
              style={{ width: `${duration ? (currentTime / duration) * 100 : 0}%` }}
            />
          </div>

          {/* Control buttons */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={togglePlay}
                className="text-white hover:text-blue-400"
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
              <span className="text-white text-sm">
                {formatDuration(currentTime)} / {formatDuration(duration)}
              </span>
            </div>

            <div className="text-sm text-gray-400">
              按空格键播放/暂停，Esc 关闭
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

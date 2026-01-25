"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import type { EditableSegment } from "@/lib/types";
import { formatDuration } from "@/lib/api";

interface VideoPlayerProps {
  jobId: string;
  segments: EditableSegment[];
  currentSegmentId: number | null;
  onTimeUpdate?: (time: number) => void;
  onSegmentChange?: (segmentId: number) => void;
}

export default function VideoPlayer({
  jobId,
  segments,
  currentSegmentId,
  onTimeUpdate,
  onSegmentChange,
}: VideoPlayerProps) {
  const videoRef = useRef<HTMLVideoElement>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [isLooping, setIsLooping] = useState(false);

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

  return (
    <div className="relative bg-black rounded-lg overflow-hidden">
      {/* Video element */}
      <video
        ref={videoRef}
        src={videoUrl}
        className="w-full aspect-video"
        preload="metadata"
      />

      {/* Subtitle overlay */}
      {currentSegment && (
        <div className="absolute bottom-16 left-0 right-0 px-4 pointer-events-none">
          {/* English (top) */}
          <div className="text-center mb-2">
            <span className="bg-black/80 text-white px-3 py-1 rounded text-lg">
              {currentSegment.en}
            </span>
          </div>
          {/* Chinese (bottom) */}
          <div className="text-center">
            <span className="bg-black/80 text-yellow-400 px-3 py-1 rounded text-xl">
              {currentSegment.zh}
            </span>
          </div>
        </div>
      )}

      {/* Controls bar */}
      <div className="absolute bottom-0 left-0 right-0 bg-gradient-to-t from-black/80 to-transparent p-4">
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
          </div>

          <div className="flex items-center gap-4">
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
}

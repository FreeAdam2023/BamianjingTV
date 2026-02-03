"use client";

import {
  useRef,
  useState,
  useEffect,
  useCallback,
  forwardRef,
  useImperativeHandle,
} from "react";
import CropSelector from "./CropSelector";
import type { CropRegion } from "@/lib/scenemind-api";
import { formatTimecode } from "@/lib/scenemind-api";

interface WatchPlayerProps {
  videoUrl: string;
  duration: number;
  initialTime?: number;
  onTimeUpdate?: (time: number) => void;
  onCapture?: (timecode: number, cropRegion: CropRegion | null) => void;
}

export interface WatchPlayerRef {
  getVideoElement: () => HTMLVideoElement | null;
  play: () => void;
  pause: () => void;
  seekTo: (time: number) => void;
  getCurrentTime: () => number;
  startCropMode: () => void;
  cancelCropMode: () => void;
}

const WatchPlayer = forwardRef<WatchPlayerRef, WatchPlayerProps>(
  function WatchPlayer(
    { videoUrl, duration, initialTime = 0, onTimeUpdate, onCapture },
    ref
  ) {
    const videoRef = useRef<HTMLVideoElement>(null);
    const containerRef = useRef<HTMLDivElement>(null);

    const [isPlaying, setIsPlaying] = useState(false);
    const [currentTime, setCurrentTime] = useState(initialTime);
    const [volume, setVolume] = useState(1);
    const [isMuted, setIsMuted] = useState(false);
    const [isCropMode, setIsCropMode] = useState(false);
    const [pendingCropRegion, setPendingCropRegion] = useState<CropRegion | null>(null);

    // Expose methods via ref
    useImperativeHandle(
      ref,
      () => ({
        getVideoElement: () => videoRef.current,
        play: () => videoRef.current?.play(),
        pause: () => videoRef.current?.pause(),
        seekTo: (time: number) => {
          if (videoRef.current) {
            videoRef.current.currentTime = time;
          }
        },
        getCurrentTime: () => videoRef.current?.currentTime || 0,
        startCropMode: () => {
          if (videoRef.current) {
            videoRef.current.pause();
            setIsCropMode(true);
          }
        },
        cancelCropMode: () => {
          setIsCropMode(false);
          setPendingCropRegion(null);
        },
      }),
      []
    );

    // Seek to initial time when video loads
    useEffect(() => {
      const video = videoRef.current;
      if (!video || initialTime <= 0) return;

      const handleLoadedMetadata = () => {
        video.currentTime = initialTime;
      };

      if (video.readyState >= 1) {
        video.currentTime = initialTime;
      }

      video.addEventListener("loadedmetadata", handleLoadedMetadata);
      return () => video.removeEventListener("loadedmetadata", handleLoadedMetadata);
    }, [initialTime]);

    // Video event handlers
    useEffect(() => {
      const video = videoRef.current;
      if (!video) return;

      const handleTimeUpdate = () => {
        const time = video.currentTime;
        setCurrentTime(time);
        onTimeUpdate?.(time);
      };

      const handlePlay = () => setIsPlaying(true);
      const handlePause = () => setIsPlaying(false);

      video.addEventListener("timeupdate", handleTimeUpdate);
      video.addEventListener("play", handlePlay);
      video.addEventListener("pause", handlePause);

      return () => {
        video.removeEventListener("timeupdate", handleTimeUpdate);
        video.removeEventListener("play", handlePlay);
        video.removeEventListener("pause", handlePause);
      };
    }, [onTimeUpdate]);

    // Playback controls
    const play = useCallback(() => videoRef.current?.play(), []);
    const pause = useCallback(() => videoRef.current?.pause(), []);
    const toggle = useCallback(() => {
      if (isCropMode) return;
      if (isPlaying) pause();
      else play();
    }, [isPlaying, isCropMode, play, pause]);

    const seekTo = useCallback((time: number) => {
      if (videoRef.current) {
        videoRef.current.currentTime = Math.max(0, Math.min(duration, time));
      }
    }, [duration]);

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

    // Handle capture (screenshot)
    const handleCapture = useCallback(() => {
      if (videoRef.current) {
        videoRef.current.pause();
        setIsCropMode(true);
      }
    }, []);

    // Handle crop selection
    const handleCropSelect = useCallback(
      (region: CropRegion | null) => {
        setIsCropMode(false);
        setPendingCropRegion(region);
        onCapture?.(currentTime, region);
      },
      [currentTime, onCapture]
    );

    const handleCropCancel = useCallback(() => {
      setIsCropMode(false);
      setPendingCropRegion(null);
    }, []);

    // Handle skip capture (no crop)
    const handleSkipCrop = useCallback(() => {
      setIsCropMode(false);
      onCapture?.(currentTime, null);
    }, [currentTime, onCapture]);

    // Keyboard shortcuts
    useEffect(() => {
      const handleKeyDown = (e: KeyboardEvent) => {
        if (
          e.target instanceof HTMLInputElement ||
          e.target instanceof HTMLTextAreaElement
        ) {
          return;
        }

        // Crop mode shortcuts
        if (isCropMode) {
          if (e.key === "Escape") {
            e.preventDefault();
            handleCropCancel();
          } else if (e.key === "Enter") {
            e.preventDefault();
            handleSkipCrop();
          }
          return;
        }

        switch (e.key) {
          case " ":
            e.preventDefault();
            toggle();
            break;
          case "s":
          case "S":
            e.preventDefault();
            handleCapture();
            break;
          case "ArrowLeft":
            e.preventDefault();
            seekTo(currentTime - (e.shiftKey ? 10 : 5));
            break;
          case "ArrowRight":
            e.preventDefault();
            seekTo(currentTime + (e.shiftKey ? 10 : 5));
            break;
          case "j":
          case "J":
            e.preventDefault();
            seekTo(currentTime - 10);
            break;
          case "k":
          case "K":
            e.preventDefault();
            toggle();
            break;
          case "l":
          case "L":
            e.preventDefault();
            seekTo(currentTime + 10);
            break;
          case "m":
          case "M":
            e.preventDefault();
            toggleMute();
            break;
        }
      };

      window.addEventListener("keydown", handleKeyDown);
      return () => window.removeEventListener("keydown", handleKeyDown);
    }, [toggle, seekTo, currentTime, isCropMode, handleCapture, handleCropCancel, handleSkipCrop, toggleMute]);

    // Progress bar seek
    const handleProgressClick = (e: React.MouseEvent<HTMLDivElement>) => {
      const rect = e.currentTarget.getBoundingClientRect();
      const percent = (e.clientX - rect.left) / rect.width;
      seekTo(percent * duration);
    };

    return (
      <div
        ref={containerRef}
        className="flex flex-col bg-black rounded-lg overflow-hidden h-full"
      >
        {/* Video area */}
        <div className="relative flex-1 min-h-0">
          <video
            ref={videoRef}
            src={videoUrl}
            className="w-full h-full object-contain cursor-pointer"
            preload="auto"
            onClick={toggle}
            playsInline
          />

          {/* Crop selector overlay */}
          <CropSelector
            videoElement={videoRef.current}
            active={isCropMode}
            onCropSelect={handleCropSelect}
            onCancel={handleCropCancel}
          />

          {/* Crop mode instructions */}
          {isCropMode && (
            <div className="absolute bottom-4 left-1/2 -translate-x-1/2 bg-black/80 px-4 py-2 rounded-lg text-sm">
              <span className="text-white">
                Drag to select region, or press{" "}
                <kbd className="px-1.5 py-0.5 bg-gray-700 rounded">Enter</kbd>{" "}
                for full frame
              </span>
            </div>
          )}
        </div>

        {/* Controls */}
        <div className="bg-gray-900 px-4 py-3 flex-shrink-0">
          {/* Progress bar */}
          <div
            className="h-1 bg-gray-700 rounded-full cursor-pointer mb-3 group"
            onClick={handleProgressClick}
          >
            <div
              className="h-full bg-blue-500 rounded-full relative group-hover:bg-blue-400"
              style={{ width: `${(currentTime / duration) * 100}%` }}
            >
              <div className="absolute right-0 top-1/2 -translate-y-1/2 w-3 h-3 bg-white rounded-full opacity-0 group-hover:opacity-100 transition-opacity" />
            </div>
          </div>

          {/* Control buttons */}
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              {/* Play/Pause */}
              <button
                onClick={toggle}
                className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
                disabled={isCropMode}
              >
                {isPlaying ? (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                  </svg>
                ) : (
                  <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>

              {/* Volume */}
              <div className="flex items-center gap-2">
                <button
                  onClick={toggleMute}
                  className="p-2 hover:bg-gray-800 rounded-lg transition-colors"
                >
                  {isMuted || volume === 0 ? (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z" />
                    </svg>
                  ) : (
                    <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                      <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z" />
                    </svg>
                  )}
                </button>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.1"
                  value={isMuted ? 0 : volume}
                  onChange={(e) => handleVolumeChange(parseFloat(e.target.value))}
                  className="w-20 accent-blue-500"
                />
              </div>

              {/* Time display */}
              <span className="text-sm text-gray-400 font-mono">
                {formatTimecode(currentTime)} / {formatTimecode(duration)}
              </span>
            </div>

            <div className="flex items-center gap-2">
              {/* Screenshot button */}
              <button
                onClick={handleCapture}
                className="btn btn-primary flex items-center gap-2"
                disabled={isCropMode}
              >
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M3 9a2 2 0 012-2h.93a2 2 0 001.664-.89l.812-1.22A2 2 0 0110.07 4h3.86a2 2 0 011.664.89l.812 1.22A2 2 0 0018.07 7H19a2 2 0 012 2v9a2 2 0 01-2 2H5a2 2 0 01-2-2V9z"
                  />
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M15 13a3 3 0 11-6 0 3 3 0 016 0z"
                  />
                </svg>
                Screenshot
                <kbd className="px-1.5 py-0.5 bg-blue-600 rounded text-xs">S</kbd>
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }
);

export default WatchPlayer;

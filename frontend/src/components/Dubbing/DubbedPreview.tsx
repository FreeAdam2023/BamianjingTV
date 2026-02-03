"use client";

/**
 * DubbedPreview - Preview and play dubbed audio
 */

import { useState, useRef, useEffect } from "react";
import type { DubbingStatus, SeparationStatus } from "@/lib/types";
import { getDubbingAudioUrl, getDubbedVideoUrl } from "@/lib/api";

interface DubbedPreviewProps {
  timelineId: string;
  separationStatus: SeparationStatus;
  dubbingStatus: DubbingStatus;
}

type AudioTrack = "original" | "vocals" | "bgm" | "sfx" | "dubbed" | "mixed";

export default function DubbedPreview({
  timelineId,
  separationStatus,
  dubbingStatus,
}: DubbedPreviewProps) {
  const [activeTrack, setActiveTrack] = useState<AudioTrack>("original");
  const [isPlaying, setIsPlaying] = useState(false);
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);

  const tracks: { id: AudioTrack; label: string; available: boolean }[] = [
    { id: "original", label: "Original", available: true },
    { id: "vocals", label: "Vocals", available: separationStatus.status === "completed" },
    { id: "bgm", label: "BGM", available: separationStatus.status === "completed" },
    { id: "sfx", label: "SFX", available: separationStatus.status === "completed" },
    { id: "dubbed", label: "Dubbed", available: dubbingStatus.status === "completed" },
    { id: "mixed", label: "Final Mix", available: dubbingStatus.status === "completed" },
  ];

  const handleTrackChange = (track: AudioTrack) => {
    setActiveTrack(track);
    setIsPlaying(false);

    if (audioRef.current) {
      audioRef.current.pause();
    }
  };

  const handlePlay = () => {
    if (activeTrack === "original") {
      videoRef.current?.play();
    } else {
      const url = getDubbingAudioUrl(timelineId, activeTrack);
      if (audioRef.current) {
        audioRef.current.src = url;
        audioRef.current.play();
      }
    }
    setIsPlaying(true);
  };

  const handlePause = () => {
    if (activeTrack === "original") {
      videoRef.current?.pause();
    } else {
      audioRef.current?.pause();
    }
    setIsPlaying(false);
  };

  useEffect(() => {
    // Sync video and audio playback
    const video = videoRef.current;
    const audio = audioRef.current;

    if (!video || !audio) return;

    const syncAudio = () => {
      if (activeTrack !== "original" && Math.abs(video.currentTime - audio.currentTime) > 0.1) {
        audio.currentTime = video.currentTime;
      }
    };

    video.addEventListener("timeupdate", syncAudio);
    return () => video.removeEventListener("timeupdate", syncAudio);
  }, [activeTrack]);

  return (
    <div className="space-y-4">
      {/* Video Preview */}
      <div className="bg-black rounded-lg overflow-hidden">
        <video
          ref={videoRef}
          className="w-full aspect-video"
          muted={activeTrack !== "original"}
          onPlay={() => setIsPlaying(true)}
          onPause={() => setIsPlaying(false)}
        >
          <source src={getDubbedVideoUrl(timelineId)} type="video/mp4" />
        </video>
      </div>

      {/* Audio element for non-original tracks */}
      <audio ref={audioRef} className="hidden" />

      {/* Track Selector */}
      <div className="bg-gray-800 rounded-lg p-4">
        <h3 className="text-sm font-medium text-gray-300 mb-3">Audio Track</h3>

        <div className="flex flex-wrap gap-2">
          {tracks.map((track) => (
            <button
              key={track.id}
              onClick={() => handleTrackChange(track.id)}
              disabled={!track.available}
              className={`px-3 py-1.5 rounded text-sm transition-colors ${
                activeTrack === track.id
                  ? "bg-blue-600 text-white"
                  : track.available
                  ? "bg-gray-700 text-gray-300 hover:bg-gray-600"
                  : "bg-gray-800 text-gray-600 cursor-not-allowed"
              }`}
            >
              {track.label}
            </button>
          ))}
        </div>
      </div>

      {/* Playback Controls */}
      <div className="flex items-center justify-center gap-4">
        <button
          onClick={isPlaying ? handlePause : handlePlay}
          className="p-3 bg-blue-600 hover:bg-blue-500 rounded-full text-white transition-colors"
        >
          {isPlaying ? (
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M6 4h4v16H6V4zm8 0h4v16h-4V4z" />
            </svg>
          ) : (
            <svg className="w-6 h-6" fill="currentColor" viewBox="0 0 24 24">
              <path d="M8 5v14l11-7z" />
            </svg>
          )}
        </button>
      </div>

      {/* Status Info */}
      {dubbingStatus.status === "completed" && (
        <div className="bg-green-500/10 border border-green-500/30 rounded-lg p-4">
          <div className="flex items-center gap-2 text-green-400">
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            <span className="font-medium">Dubbing Complete</span>
          </div>
          <p className="text-sm text-gray-400 mt-1">
            {dubbingStatus.dubbed_segments} of {dubbingStatus.total_segments} segments dubbed
          </p>
        </div>
      )}

      {/* Download Button */}
      {dubbingStatus.status === "completed" && (
        <a
          href={getDubbedVideoUrl(timelineId)}
          download
          className="block w-full px-4 py-3 bg-green-600 hover:bg-green-500 text-white text-center rounded-lg transition-colors"
        >
          Download Dubbed Video
        </a>
      )}
    </div>
  );
}

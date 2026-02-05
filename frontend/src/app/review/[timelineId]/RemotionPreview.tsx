"use client";

import React, { useMemo, useCallback, useRef, useEffect, useState } from "react";
import { Player, PlayerRef } from "@remotion/player";
import { SubtitleComposition, SubtitleCompositionProps } from "@remotion/compositions/SubtitleComposition";
import type { SubtitleSegment } from "@remotion/types";
import type { RemotionConfig } from "@/lib/creative-types";
import type { EditableSegment } from "@/lib/types";

interface RemotionPreviewProps {
  jobId: string;
  segments: EditableSegment[];
  config: RemotionConfig;
  fps?: number;
  width?: number;
  height?: number;
  currentTime?: number;
  onTimeUpdate?: (time: number) => void;
}

// Convert timeline segments to Remotion frame-based segments
function convertSegments(
  segments: EditableSegment[],
  fps: number
): SubtitleSegment[] {
  return segments
    .filter((seg) => seg.state === "keep")
    .map((seg) => ({
      id: seg.id,
      startFrame: Math.round(seg.start * fps),
      endFrame: Math.round(seg.end * fps),
      en: seg.en,
      zh: seg.zh,
      speaker: seg.speaker,
    }));
}

export default function RemotionPreview({
  jobId,
  segments,
  config,
  fps = 30,
  width = 1920,
  height = 1080,
  currentTime = 0,
  onTimeUpdate,
}: RemotionPreviewProps) {
  const playerRef = useRef<PlayerRef>(null);
  const [isPlaying, setIsPlaying] = useState(false);

  // Convert segments to Remotion format
  const remotionSegments = useMemo(
    () => convertSegments(segments, fps),
    [segments, fps]
  );

  // Calculate duration based on segments
  const durationInFrames = useMemo(() => {
    if (remotionSegments.length === 0) return fps * 10; // Default 10 seconds
    const lastSegment = remotionSegments[remotionSegments.length - 1];
    return lastSegment.endFrame + fps; // Add 1 second buffer
  }, [remotionSegments, fps]);

  // Video source URL
  const videoSrc = useMemo(() => {
    if (typeof window === "undefined") return "";
    return `${window.location.protocol}//${window.location.hostname}:8000/jobs/${jobId}/video`;
  }, [jobId]);

  // Sync external time changes
  useEffect(() => {
    if (playerRef.current && !isPlaying) {
      const frame = Math.round(currentTime * fps);
      playerRef.current.seekTo(frame);
    }
  }, [currentTime, fps, isPlaying]);

  // Handle frame updates
  const handleFrameUpdate = useCallback(
    (e: { detail: { frame: number } }) => {
      const time = e.detail.frame / fps;
      onTimeUpdate?.(time);
    },
    [fps, onTimeUpdate]
  );

  // Attach frame update listener
  useEffect(() => {
    const player = playerRef.current;
    if (!player) return;

    // @remotion/player uses custom events
    const container = (player as any)?.container;
    if (container) {
      container.addEventListener("frameupdate", handleFrameUpdate);
      return () => container.removeEventListener("frameupdate", handleFrameUpdate);
    }
  }, [handleFrameUpdate]);

  return (
    <div className="relative w-full h-full bg-gray-900 rounded-lg overflow-hidden">
      {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
      <Player
        ref={playerRef}
        component={SubtitleComposition as any}
        inputProps={{
          segments: remotionSegments,
          config,
          videoSrc,
        }}
        durationInFrames={durationInFrames}
        fps={fps}
        compositionWidth={width}
        compositionHeight={height}
        style={{
          width: "100%",
          height: "100%",
        }}
        controls
        autoPlay={false}
        loop={false}
        clickToPlay
        spaceKeyToPlayOrPause
      />

      {/* Style indicator badge */}
      <div className="absolute top-3 left-3 px-2 py-1 bg-black/60 rounded text-xs text-white font-medium">
        Creative: {config.style}
      </div>
    </div>
  );
}

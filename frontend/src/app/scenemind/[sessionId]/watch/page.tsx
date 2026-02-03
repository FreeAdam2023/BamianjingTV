"use client";

import { use, useRef, useState, useCallback, useEffect } from "react";
import Link from "next/link";
import { useSceneMindSession } from "@/hooks/useSceneMindSession";
import WatchPlayer, { type WatchPlayerRef } from "@/components/scenemind/WatchPlayer";
import ObservationPanel from "@/components/scenemind/ObservationPanel";
import ObservationList from "@/components/scenemind/ObservationList";
import {
  getVideoUrl,
  getFrameUrlFromPath,
  formatEpisode,
  formatTimecode,
} from "@/lib/scenemind-api";
import type { CropRegion, ObservationType } from "@/lib/scenemind-api";

interface PageProps {
  params: Promise<{ sessionId: string }>;
}

export default function WatchPage({ params }: PageProps) {
  const { sessionId } = use(params);
  const playerRef = useRef<WatchPlayerRef>(null);

  const {
    session,
    observations,
    loading,
    error,
    saving,
    createObservation,
    removeObservation,
    saveCurrentTime,
    markCompleted,
  } = useSceneMindSession(sessionId);

  // Capture state
  const [captureMode, setCaptureMode] = useState<"idle" | "cropping" | "editing">("idle");
  const [captureTimecode, setCaptureTimecode] = useState(0);
  const [captureCropRegion, setCaptureCropRegion] = useState<CropRegion | null>(null);
  const [tempFrameUrl, setTempFrameUrl] = useState<string | null>(null);
  const [tempCropUrl, setTempCropUrl] = useState<string | null>(null);

  // Save time periodically
  const lastSavedTimeRef = useRef(0);
  const handleTimeUpdate = useCallback(
    (time: number) => {
      // Save every 10 seconds
      if (Math.abs(time - lastSavedTimeRef.current) >= 10) {
        saveCurrentTime(time);
        lastSavedTimeRef.current = time;
      }
    },
    [saveCurrentTime]
  );

  // Handle capture trigger from player
  const handleCapture = useCallback(
    (timecode: number, cropRegion: CropRegion | null) => {
      setCaptureTimecode(timecode);
      setCaptureCropRegion(cropRegion);
      setCaptureMode("editing");

      // In a real implementation, we'd show a preview of the captured frame
      // For now, we'll just proceed to the editing panel
      // The actual frame capture happens when we save the observation
    },
    []
  );

  // Save observation
  const handleSaveObservation = useCallback(
    async (note: string, tag: ObservationType) => {
      try {
        const observation = await createObservation(
          captureTimecode,
          note,
          tag,
          captureCropRegion || undefined
        );

        // Reset capture state
        setCaptureMode("idle");
        setCaptureTimecode(0);
        setCaptureCropRegion(null);
        setTempFrameUrl(null);
        setTempCropUrl(null);

        return observation;
      } catch (err) {
        console.error("Failed to save observation:", err);
        alert("Failed to save observation");
      }
    },
    [captureTimecode, captureCropRegion, createObservation]
  );

  // Cancel capture
  const handleCancelCapture = useCallback(() => {
    setCaptureMode("idle");
    setCaptureTimecode(0);
    setCaptureCropRegion(null);
    setTempFrameUrl(null);
    setTempCropUrl(null);
  }, []);

  // Seek to observation time
  const handleSeekToObservation = useCallback((timecode: number) => {
    playerRef.current?.seekTo(timecode);
  }, []);

  // Handle keyboard shortcuts at page level
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement
      ) {
        return;
      }

      if (e.key === "c" || e.key === "C") {
        e.preventDefault();
        markCompleted();
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [markCompleted]);

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="spinner mx-auto mb-4" />
          <p className="text-gray-400">Loading session...</p>
        </div>
      </main>
    );
  }

  if (error || !session) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="text-5xl mb-4">😵</div>
          <h2 className="text-xl font-bold mb-2">Session Not Found</h2>
          <p className="text-gray-400 mb-4">{error || "Could not load session"}</p>
          <Link href="/scenemind" className="btn btn-primary">
            Back to Sessions
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]/50 backdrop-blur-sm flex-shrink-0">
        <div className="max-w-full mx-auto px-4 py-3 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link
              href="/scenemind"
              className="p-2 text-gray-400 hover:text-white hover:bg-gray-800 rounded-lg transition-colors"
            >
              <svg
                className="w-5 h-5"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
            <div>
              <div className="flex items-center gap-2">
                <h1 className="text-lg font-bold">{session.show_name}</h1>
                <span className="text-gray-500 font-mono text-sm">
                  {formatEpisode(session.season, session.episode)}
                </span>
              </div>
              <p className="text-xs text-gray-500">{session.title}</p>
            </div>
          </div>

          <div className="flex items-center gap-4">
            {/* Observation count */}
            <div className="text-sm text-gray-400">
              <span className="font-bold text-purple-400">
                {observations.length}
              </span>{" "}
              observations
            </div>

            {/* Mark complete button */}
            {session.status !== "completed" && (
              <button
                onClick={() => markCompleted()}
                className="btn btn-secondary flex items-center gap-2"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  stroke="currentColor"
                  viewBox="0 0 24 24"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M5 13l4 4L19 7"
                  />
                </svg>
                Mark Complete
                <kbd className="px-1.5 py-0.5 bg-gray-700 rounded text-xs">C</kbd>
              </button>
            )}
          </div>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Video player (2/3 width) */}
        <div className="flex-1 p-4 min-w-0">
          <WatchPlayer
            ref={playerRef}
            videoUrl={getVideoUrl(sessionId)}
            duration={session.duration}
            initialTime={session.current_time}
            onTimeUpdate={handleTimeUpdate}
            onCapture={handleCapture}
          />
        </div>

        {/* Sidebar (1/3 width) */}
        <div className="w-96 border-l border-[var(--border)] flex flex-col overflow-hidden">
          {/* Observation Panel (when capturing) */}
          {captureMode === "editing" && (
            <div className="p-4 border-b border-[var(--border)]">
              <ObservationPanel
                frameUrl={tempFrameUrl}
                cropUrl={tempCropUrl}
                timecode={captureTimecode}
                cropRegion={captureCropRegion}
                onSave={handleSaveObservation}
                onCancel={handleCancelCapture}
                saving={saving}
              />
            </div>
          )}

          {/* Observations List */}
          <div className="flex-1 overflow-y-auto p-4">
            <h3 className="text-sm font-medium text-gray-400 mb-3">
              Observations ({observations.length})
            </h3>
            <ObservationList
              sessionId={sessionId}
              observations={observations}
              onDelete={removeObservation}
              onSeek={handleSeekToObservation}
            />
          </div>

          {/* Keyboard shortcuts help */}
          <div className="p-4 border-t border-[var(--border)] bg-[var(--card)]/50">
            <h4 className="text-xs font-medium text-gray-500 mb-2">
              Keyboard Shortcuts
            </h4>
            <div className="grid grid-cols-2 gap-1 text-xs text-gray-400">
              <div>
                <kbd className="px-1 bg-gray-700 rounded">Space</kbd> Play/Pause
              </div>
              <div>
                <kbd className="px-1 bg-gray-700 rounded">S</kbd> Screenshot
              </div>
              <div>
                <kbd className="px-1 bg-gray-700 rounded">J/L</kbd> -10s/+10s
              </div>
              <div>
                <kbd className="px-1 bg-gray-700 rounded">←/→</kbd> -5s/+5s
              </div>
              <div>
                <kbd className="px-1 bg-gray-700 rounded">M</kbd> Mute
              </div>
              <div>
                <kbd className="px-1 bg-gray-700 rounded">C</kbd> Mark Complete
              </div>
            </div>
          </div>
        </div>
      </div>
    </main>
  );
}

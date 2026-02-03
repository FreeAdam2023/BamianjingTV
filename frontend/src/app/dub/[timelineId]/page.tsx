"use client";

/**
 * Dubbing Page - Configure and generate dubbed video
 */

import { useState, useEffect, useCallback } from "react";
import { useParams } from "next/navigation";
import Link from "next/link";
import type {
  Timeline,
  DubbingConfig,
  SpeakerVoiceConfig,
  SeparationStatus,
  DubbingStatus,
} from "@/lib/types";
import {
  getTimeline,
  getDubbingConfig,
  getDubbingSpeakers,
  getSeparationStatus,
  getDubbingStatus,
  triggerSeparation,
  generateDubbing,
} from "@/lib/api";
import { VoiceConfig, DubbedPreview } from "@/components/Dubbing";

export default function DubbingPage() {
  const params = useParams();
  const timelineId = params.timelineId as string;

  const [timeline, setTimeline] = useState<Timeline | null>(null);
  const [config, setConfig] = useState<DubbingConfig | null>(null);
  const [speakers, setSpeakers] = useState<SpeakerVoiceConfig[]>([]);
  const [separationStatus, setSeparationStatus] = useState<SeparationStatus | null>(null);
  const [dubbingStatus, setDubbingStatus] = useState<DubbingStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Load initial data
  useEffect(() => {
    const loadData = async () => {
      try {
        setLoading(true);
        const [tl, cfg, spk, sep, dub] = await Promise.all([
          getTimeline(timelineId),
          getDubbingConfig(timelineId),
          getDubbingSpeakers(timelineId),
          getSeparationStatus(timelineId),
          getDubbingStatus(timelineId),
        ]);
        setTimeline(tl);
        setConfig(cfg);
        setSpeakers(spk);
        setSeparationStatus(sep);
        setDubbingStatus(dub);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load data");
      } finally {
        setLoading(false);
      }
    };

    loadData();
  }, [timelineId]);

  // Poll for status updates when processing
  useEffect(() => {
    const isProcessing =
      separationStatus?.status === "processing" ||
      ["separating", "extracting_samples", "synthesizing", "mixing"].includes(
        dubbingStatus?.status || ""
      );

    if (!isProcessing) return;

    const interval = setInterval(async () => {
      try {
        const [sep, dub] = await Promise.all([
          getSeparationStatus(timelineId),
          getDubbingStatus(timelineId),
        ]);
        setSeparationStatus(sep);
        setDubbingStatus(dub);

        // Refresh speakers after samples are extracted
        if (dub.status === "synthesizing" || dub.status === "completed") {
          const spk = await getDubbingSpeakers(timelineId);
          setSpeakers(spk);
        }
      } catch (err) {
        console.error("Failed to poll status:", err);
      }
    }, 2000);

    return () => clearInterval(interval);
  }, [timelineId, separationStatus?.status, dubbingStatus?.status]);

  const handleSeparate = async () => {
    try {
      await triggerSeparation(timelineId);
      setSeparationStatus({ ...separationStatus!, status: "processing" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start separation");
    }
  };

  const handleGenerate = async () => {
    try {
      await generateDubbing(timelineId);
      setDubbingStatus({ ...dubbingStatus!, status: "separating" });
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to start dubbing");
    }
  };

  const handleSpeakerChange = (updated: SpeakerVoiceConfig) => {
    setSpeakers((prev) =>
      prev.map((s) => (s.speaker_id === updated.speaker_id ? updated : s))
    );
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500" />
      </div>
    );
  }

  if (error || !timeline || !config || !separationStatus || !dubbingStatus) {
    return (
      <div className="min-h-screen bg-gray-900 flex items-center justify-center">
        <div className="text-center">
          <h1 className="text-xl font-semibold text-red-400 mb-2">Error</h1>
          <p className="text-gray-400">{error || "Timeline not found"}</p>
          <Link href="/" className="text-blue-400 hover:text-blue-300 mt-4 inline-block">
            Go back
          </Link>
        </div>
      </div>
    );
  }

  const isProcessing =
    separationStatus.status === "processing" ||
    ["separating", "extracting_samples", "synthesizing", "mixing"].includes(dubbingStatus.status);

  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/95 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href={`/review/${timelineId}`}
              className="text-gray-500 hover:text-gray-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <div>
              <h1 className="text-xl font-semibold text-gray-100">Dubbing Mode</h1>
              <p className="text-sm text-gray-500 truncate max-w-md">{timeline.source_title}</p>
            </div>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column - Configuration */}
          <div className="lg:col-span-1 space-y-6">
            <VoiceConfig
              timelineId={timelineId}
              config={config}
              speakers={speakers}
              onConfigChange={setConfig}
              onSpeakerChange={handleSpeakerChange}
            />

            {/* Action Buttons */}
            <div className="space-y-3">
              {/* Separate Audio */}
              {separationStatus.status !== "completed" && (
                <button
                  onClick={handleSeparate}
                  disabled={separationStatus.status === "processing"}
                  className="w-full px-4 py-3 bg-purple-600 hover:bg-purple-500 disabled:bg-purple-600/50 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
                >
                  {separationStatus.status === "processing" ? (
                    <>
                      <span className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white" />
                      Separating Audio...
                    </>
                  ) : (
                    <>
                      <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
                      </svg>
                      Separate Audio
                    </>
                  )}
                </button>
              )}

              {/* Generate Dubbing */}
              <button
                onClick={handleGenerate}
                disabled={isProcessing || dubbingStatus.status === "completed"}
                className="w-full px-4 py-3 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-600/50 text-white rounded-lg transition-colors flex items-center justify-center gap-2"
              >
                {isProcessing ? (
                  <>
                    <span className="animate-spin rounded-full h-4 w-4 border-t-2 border-b-2 border-white" />
                    {dubbingStatus.current_step || "Processing..."}
                  </>
                ) : dubbingStatus.status === "completed" ? (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                    </svg>
                    Dubbing Complete
                  </>
                ) : (
                  <>
                    <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                    </svg>
                    Generate Dubbed Video
                  </>
                )}
              </button>
            </div>

            {/* Progress */}
            {isProcessing && (
              <div className="bg-gray-800 rounded-lg p-4">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-sm text-gray-300">{dubbingStatus.current_step}</span>
                  <span className="text-sm text-gray-500">{dubbingStatus.progress}%</span>
                </div>
                <div className="h-2 bg-gray-700 rounded-full overflow-hidden">
                  <div
                    className="h-full bg-blue-500 transition-all duration-300"
                    style={{ width: `${dubbingStatus.progress}%` }}
                  />
                </div>
              </div>
            )}

            {/* Error */}
            {(separationStatus.error || dubbingStatus.error) && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-4 text-red-400 text-sm">
                {separationStatus.error || dubbingStatus.error}
              </div>
            )}
          </div>

          {/* Right column - Preview */}
          <div className="lg:col-span-2">
            <DubbedPreview
              timelineId={timelineId}
              separationStatus={separationStatus}
              dubbingStatus={dubbingStatus}
            />
          </div>
        </div>
      </main>
    </div>
  );
}

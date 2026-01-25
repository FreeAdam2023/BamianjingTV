"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import VideoPlayer from "@/components/VideoPlayer";
import SegmentList from "@/components/SegmentList";
import { useTimeline } from "@/hooks/useTimeline";
import { useKeyboardNavigation } from "@/hooks/useKeyboardNavigation";
import { formatDuration, keepAllSegments, dropAllSegments, resetAllSegments } from "@/lib/api";
import type { SegmentState, ExportProfile, ExportRequest } from "@/lib/types";

export default function ReviewPage() {
  const params = useParams();
  const timelineId = params.timelineId as string;

  const {
    timeline,
    loading,
    error,
    saving,
    stats,
    setSegmentState,
    markReviewed,
    startExport,
  } = useTimeline(timelineId);

  const [currentSegmentId, setCurrentSegmentId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [showExportPanel, setShowExportPanel] = useState(false);
  const [exportProfile, setExportProfile] = useState<ExportProfile>("full");
  const [useTraditional, setUseTraditional] = useState(true);
  const [exporting, setExporting] = useState(false);

  // YouTube upload options
  const [uploadToYouTube, setUploadToYouTube] = useState(false);
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeDescription, setYoutubeDescription] = useState("");
  const [youtubeTags, setYoutubeTags] = useState("");
  const [youtubePrivacy, setYoutubePrivacy] = useState<"private" | "unlisted" | "public">("private");

  const videoRef = useRef<HTMLVideoElement | null>(null);

  // Video control handlers
  const handlePlayToggle = useCallback(() => {
    setIsPlaying((prev) => !prev);
  }, []);

  const handleLoopToggle = useCallback(() => {
    setIsLooping((prev) => !prev);
  }, []);

  const handlePlaySegment = useCallback((segmentId: number) => {
    if (timeline) {
      const segment = timeline.segments.find((s) => s.id === segmentId);
      if (segment && videoRef.current) {
        videoRef.current.currentTime = segment.start;
        videoRef.current.play();
      }
    }
  }, [timeline]);

  // Keyboard navigation
  useKeyboardNavigation({
    segmentCount: timeline?.segments.length || 0,
    currentSegmentId,
    onSegmentChange: setCurrentSegmentId,
    onStateChange: setSegmentState,
    onPlayToggle: handlePlayToggle,
    onLoopToggle: handleLoopToggle,
    onPlaySegment: handlePlaySegment,
  });

  // Handle segment click
  const handleSegmentClick = useCallback((segmentId: number) => {
    setCurrentSegmentId(segmentId);
    if (timeline) {
      const segment = timeline.segments.find((s) => s.id === segmentId);
      if (segment && videoRef.current) {
        videoRef.current.currentTime = segment.start;
      }
    }
  }, [timeline]);

  // Handle export
  const handleExport = async () => {
    setExporting(true);
    try {
      const request: ExportRequest = {
        profile: exportProfile,
        use_traditional_chinese: useTraditional,
        upload_to_youtube: uploadToYouTube,
      };

      if (uploadToYouTube) {
        if (youtubeTitle) request.youtube_title = youtubeTitle;
        if (youtubeDescription) request.youtube_description = youtubeDescription;
        if (youtubeTags) request.youtube_tags = youtubeTags.split(",").map(t => t.trim()).filter(Boolean);
        request.youtube_privacy = youtubePrivacy;
      }

      await startExport(request);
      const message = uploadToYouTube
        ? "Export started with YouTube upload! Check back later."
        : "Export started! Check back later for the output files.";
      alert(message);
      setShowExportPanel(false);
    } catch (err) {
      alert("Export failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setExporting(false);
    }
  };

  // Handle bulk operations
  const handleKeepAll = async () => {
    if (confirm("Mark all segments as KEEP?")) {
      await keepAllSegments(timelineId);
      window.location.reload();
    }
  };

  const handleDropAll = async () => {
    if (confirm("Mark all segments as DROP?")) {
      await dropAllSegments(timelineId);
      window.location.reload();
    }
  };

  const handleResetAll = async () => {
    if (confirm("Reset all segments to UNDECIDED?")) {
      await resetAllSegments(timelineId);
      window.location.reload();
    }
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-white mx-auto mb-4" />
          <p>Loading timeline...</p>
        </div>
      </main>
    );
  }

  if (error || !timeline) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <p className="text-red-400 mb-4">{error || "Timeline not found"}</p>
          <Link href="/" className="text-blue-400 hover:underline">
            Back to Dashboard
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="h-screen flex flex-col">
      {/* Header */}
      <header className="bg-gray-800 px-4 py-3 flex items-center justify-between">
        <div className="flex items-center gap-4">
          <Link href="/" className="text-gray-400 hover:text-white">
            &larr; Back
          </Link>
          <h1 className="text-lg font-medium truncate max-w-md">
            {timeline.source_title}
          </h1>
          {saving && <span className="text-yellow-400 text-sm">Saving...</span>}
        </div>

        <div className="flex items-center gap-4">
          {/* Stats */}
          {stats && (
            <div className="text-sm">
              <span className="text-green-400">{stats.keep} keep</span>
              {" / "}
              <span className="text-red-400">{stats.drop} drop</span>
              {" / "}
              <span className="text-gray-400">{stats.undecided} pending</span>
              {" | "}
              <span className="text-blue-400">{Math.round(stats.progress)}%</span>
            </div>
          )}

          {/* Export button */}
          <button
            onClick={() => setShowExportPanel(true)}
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
          >
            Export
          </button>
        </div>
      </header>

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Video panel */}
        <div className="flex-1 flex flex-col p-4">
          <VideoPlayer
            jobId={timeline.job_id}
            segments={timeline.segments}
            currentSegmentId={currentSegmentId}
            onSegmentChange={setCurrentSegmentId}
          />

          {/* Keyboard shortcuts help */}
          <div className="mt-4 text-xs text-gray-500 flex flex-wrap gap-4">
            <span><kbd className="kbd">Space</kbd> Play/Pause</span>
            <span><kbd className="kbd">j</kbd>/<kbd className="kbd">k</kbd> Next/Prev</span>
            <span><kbd className="kbd">Shift+K</kbd> Keep</span>
            <span><kbd className="kbd">D</kbd> Drop</span>
            <span><kbd className="kbd">U</kbd> Undecided</span>
            <span><kbd className="kbd">L</kbd> Loop</span>
            <span><kbd className="kbd">Enter</kbd> Play segment</span>
          </div>
        </div>

        {/* Segment list panel */}
        <div className="w-96 border-l border-gray-700 flex flex-col">
          {/* Bulk actions */}
          <div className="p-2 border-b border-gray-700 flex gap-2">
            <button
              onClick={handleKeepAll}
              className="flex-1 py-1 text-xs bg-green-600 hover:bg-green-700 rounded"
            >
              Keep All
            </button>
            <button
              onClick={handleDropAll}
              className="flex-1 py-1 text-xs bg-red-600 hover:bg-red-700 rounded"
            >
              Drop All
            </button>
            <button
              onClick={handleResetAll}
              className="flex-1 py-1 text-xs bg-gray-600 hover:bg-gray-700 rounded"
            >
              Reset
            </button>
          </div>

          {/* Segment list */}
          <SegmentList
            segments={timeline.segments}
            currentSegmentId={currentSegmentId}
            onSegmentClick={handleSegmentClick}
            onStateChange={setSegmentState}
          />
        </div>
      </div>

      {/* Export Panel Modal */}
      {showExportPanel && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 w-[480px] max-h-[90vh] overflow-y-auto">
            <h2 className="text-xl font-bold mb-4">Export Video</h2>

            {/* Export profile */}
            <div className="mb-4">
              <label className="block text-sm text-gray-400 mb-2">
                Export Profile
              </label>
              <div className="space-y-2">
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="profile"
                    value="full"
                    checked={exportProfile === "full"}
                    onChange={() => setExportProfile("full")}
                  />
                  <span>Full Video (with subtitles)</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="profile"
                    value="essence"
                    checked={exportProfile === "essence"}
                    onChange={() => setExportProfile("essence")}
                  />
                  <span>Essence Only (KEEP segments)</span>
                </label>
                <label className="flex items-center gap-2">
                  <input
                    type="radio"
                    name="profile"
                    value="both"
                    checked={exportProfile === "both"}
                    onChange={() => setExportProfile("both")}
                  />
                  <span>Both versions</span>
                </label>
              </div>
            </div>

            {/* Traditional Chinese toggle */}
            <div className="mb-4">
              <label className="flex items-center gap-2">
                <input
                  type="checkbox"
                  checked={useTraditional}
                  onChange={(e) => setUseTraditional(e.target.checked)}
                />
                <span>Use Traditional Chinese (繁體)</span>
              </label>
            </div>

            {/* YouTube Upload Section */}
            <div className="border-t border-gray-700 pt-4 mt-4">
              <label className="flex items-center gap-2 mb-4">
                <input
                  type="checkbox"
                  checked={uploadToYouTube}
                  onChange={(e) => setUploadToYouTube(e.target.checked)}
                />
                <span className="font-medium">Upload to YouTube</span>
              </label>

              {uploadToYouTube && (
                <div className="space-y-4 ml-6">
                  {/* Title */}
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">
                      Title (optional, defaults to source title)
                    </label>
                    <input
                      type="text"
                      value={youtubeTitle}
                      onChange={(e) => setYoutubeTitle(e.target.value)}
                      placeholder={timeline?.source_title}
                      className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Description */}
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">
                      Description (optional)
                    </label>
                    <textarea
                      value={youtubeDescription}
                      onChange={(e) => setYoutubeDescription(e.target.value)}
                      placeholder={`Original: ${timeline?.source_url}`}
                      rows={3}
                      className="w-full bg-gray-700 rounded px-3 py-2 text-sm resize-none"
                    />
                  </div>

                  {/* Tags */}
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">
                      Tags (comma-separated)
                    </label>
                    <input
                      type="text"
                      value={youtubeTags}
                      onChange={(e) => setYoutubeTags(e.target.value)}
                      placeholder="learning, english, chinese"
                      className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
                    />
                  </div>

                  {/* Privacy */}
                  <div>
                    <label className="block text-sm text-gray-400 mb-1">
                      Privacy
                    </label>
                    <select
                      value={youtubePrivacy}
                      onChange={(e) => setYoutubePrivacy(e.target.value as "private" | "unlisted" | "public")}
                      className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
                    >
                      <option value="private">Private</option>
                      <option value="unlisted">Unlisted</option>
                      <option value="public">Public</option>
                    </select>
                  </div>
                </div>
              )}
            </div>

            {/* Buttons */}
            <div className="flex gap-4 mt-6">
              <button
                onClick={() => setShowExportPanel(false)}
                className="flex-1 py-2 bg-gray-600 hover:bg-gray-700 rounded"
              >
                Cancel
              </button>
              <button
                onClick={handleExport}
                disabled={exporting}
                className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded"
              >
                {exporting ? "Exporting..." : uploadToYouTube ? "Export & Upload" : "Start Export"}
              </button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

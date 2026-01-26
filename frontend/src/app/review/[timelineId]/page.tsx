"use client";

import { useState, useRef, useCallback } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import VideoPlayer, { VideoPlayerRef } from "@/components/VideoPlayer";
import SegmentList from "@/components/SegmentList";
import { TimelineEditor } from "@/components/timeline";
import { useTimeline } from "@/hooks/useTimeline";
import { useKeyboardNavigation } from "@/hooks/useKeyboardNavigation";
import { useTimelineKeyboard } from "@/hooks/useTimelineKeyboard";
import { useMultiTrackWaveform, TrackType } from "@/hooks/useMultiTrackWaveform";
import { formatDuration, keepAllSegments, dropAllSegments, resetAllSegments, generateThumbnail } from "@/lib/api";
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
    setSegmentText,
    setSegmentTrim,
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

  // Thumbnail generation
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [generatingThumbnail, setGeneratingThumbnail] = useState(false);

  // Video time tracking for timeline sync
  const [currentVideoTime, setCurrentVideoTime] = useState(0);

  // Waveform data for timeline (multi-track support)
  const { tracks: waveformTracks, generateTrack: generateWaveform } = useMultiTrackWaveform(timelineId);

  // Convert track waveforms to the format expected by TimelineEditor
  const waveformData = {
    original: waveformTracks.original.waveform,
    dubbing: waveformTracks.dubbing.waveform,
    bgm: waveformTracks.bgm.waveform,
  };

  const videoPlayerRef = useRef<VideoPlayerRef>(null);

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
      if (segment && videoPlayerRef.current) {
        videoPlayerRef.current.seekTo(segment.start);
        videoPlayerRef.current.play();
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
      if (segment && videoPlayerRef.current) {
        videoPlayerRef.current.seekTo(segment.start);
      }
    }
  }, [timeline]);

  // Handle video time update (for timeline sync)
  const handleVideoTimeUpdate = useCallback((time: number) => {
    setCurrentVideoTime(time);
  }, []);

  // Handle timeline seek (when user clicks on timeline)
  const handleTimelineSeek = useCallback((time: number) => {
    if (videoPlayerRef.current) {
      videoPlayerRef.current.seekTo(time);
    }
    setCurrentVideoTime(time);
  }, []);

  // Timeline keyboard shortcuts (frame stepping, boundary jumping)
  useTimelineKeyboard({
    fps: 30,
    duration: timeline?.source_duration || 0,
    currentTime: currentVideoTime,
    isPlaying,
    onSeek: handleTimelineSeek,
    onPlayToggle: handlePlayToggle,
    segments: timeline?.segments.map((s) => ({ start: s.start, end: s.end })),
  });

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

  // Handle thumbnail generation
  const handleGenerateThumbnail = async () => {
    setGeneratingThumbnail(true);
    try {
      const result = await generateThumbnail(timelineId);
      // Build full URL for the thumbnail
      const { protocol, hostname } = window.location;
      const baseUrl = `${protocol}//${hostname}:8000`;
      setThumbnailUrl(`${baseUrl}${result.thumbnail_url}`);
    } catch (err) {
      alert("Thumbnail generation failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setGeneratingThumbnail(false);
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
        <div className="flex-1 flex flex-col p-4 min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 h-0">
            <VideoPlayer
              ref={videoPlayerRef}
              jobId={timeline.job_id}
              segments={timeline.segments}
              currentSegmentId={currentSegmentId}
              onTimeUpdate={handleVideoTimeUpdate}
              onSegmentChange={setCurrentSegmentId}
            />
          </div>

          {/* Timeline Editor */}
          <div className="mt-4 flex-shrink-0">
            <TimelineEditor
              segments={timeline.segments}
              duration={timeline.source_duration}
              jobId={timeline.job_id}
              currentTime={currentVideoTime}
              onTimeChange={handleTimelineSeek}
              onSegmentClick={handleSegmentClick}
              onSegmentSelect={setCurrentSegmentId}
              onStateChange={setSegmentState}
              onTrimChange={setSegmentTrim}
              waveformData={waveformData}
              onGenerateWaveform={(trackType: TrackType) => generateWaveform(trackType)}
            />
          </div>

          {/* Keyboard shortcuts help */}
          <div className="mt-4 text-xs text-gray-500 flex flex-wrap gap-4 flex-shrink-0">
            <span><kbd className="kbd">Space</kbd> Play/Pause</span>
            <span><kbd className="kbd">j</kbd>/<kbd className="kbd">k</kbd> Next/Prev</span>
            <span><kbd className="kbd">Shift+K</kbd> Keep</span>
            <span><kbd className="kbd">D</kbd> Drop</span>
            <span><kbd className="kbd">U</kbd> Undecided</span>
            <span><kbd className="kbd">L</kbd> Loop</span>
            <span><kbd className="kbd">,</kbd>/<kbd className="kbd">.</kbd> Frame ±1</span>
            <span><kbd className="kbd">[</kbd>/<kbd className="kbd">]</kbd> Prev/Next boundary</span>
          </div>
        </div>

        {/* Segment list panel - always visible */}
        <div className="w-[480px] flex-shrink-0 border-l border-gray-700 flex flex-col">
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
            onTextChange={setSegmentText}
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
                <span>Use Traditional Chinese</span>
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

            {/* Thumbnail Generation Section */}
            <div className="border-t border-gray-700 pt-4 mt-4">
              <div className="flex items-center justify-between mb-3">
                <span className="font-medium">Video Thumbnail</span>
                <button
                  onClick={handleGenerateThumbnail}
                  disabled={generatingThumbnail}
                  className="px-3 py-1 text-sm bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded flex items-center gap-2"
                >
                  {generatingThumbnail ? (
                    <>
                      <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                      </svg>
                      Generating...
                    </>
                  ) : thumbnailUrl ? (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15" />
                      </svg>
                      Regenerate
                    </>
                  ) : (
                    <>
                      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                      </svg>
                      Generate Thumbnail
                    </>
                  )}
                </button>
              </div>
              <p className="text-xs text-gray-500 mb-3">
                AI-generated YouTube-style thumbnail based on video content
              </p>
              {thumbnailUrl && (
                <div className="relative rounded-lg overflow-hidden bg-gray-900">
                  <img
                    src={thumbnailUrl}
                    alt="Generated thumbnail"
                    className="w-full aspect-video object-cover"
                  />
                  <a
                    href={thumbnailUrl}
                    download="thumbnail.png"
                    target="_blank"
                    rel="noopener noreferrer"
                    className="absolute bottom-2 right-2 px-2 py-1 text-xs bg-black/70 hover:bg-black/90 rounded"
                  >
                    Download
                  </a>
                </div>
              )}
              {!thumbnailUrl && !generatingThumbnail && (
                <div className="border-2 border-dashed border-gray-600 rounded-lg aspect-video flex items-center justify-center text-gray-500">
                  <span>Click "Generate Thumbnail" to create</span>
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

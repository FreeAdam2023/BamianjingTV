"use client";

/**
 * ReviewPage - Timeline review page with video player, timeline editor, and segment list
 */

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
import { captureCoverFrame, getCoverFrameUrl, convertChineseSubtitles } from "@/lib/api";
import ReviewHeader from "./ReviewHeader";
import ExportPanel from "./ExportPanel";
import KeyboardHelp from "./KeyboardHelp";
import BulkActions from "./BulkActions";

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
    refresh,
  } = useTimeline(timelineId);

  const [converting, setConverting] = useState(false);

  const [currentSegmentId, setCurrentSegmentId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [showExportPanel, setShowExportPanel] = useState(false);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const [coverFrameTime, setCoverFrameTime] = useState<number | null>(null);
  const [coverFrameUrl, setCoverFrameUrl] = useState<string | null>(null);

  // Waveform data for timeline
  const { tracks: waveformTracks, generateTrack: generateWaveform } = useMultiTrackWaveform(timelineId);

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

  // Handle video time update
  const handleVideoTimeUpdate = useCallback((time: number) => {
    setCurrentVideoTime(time);
  }, []);

  // Handle set cover frame
  const handleSetCover = useCallback(async (timestamp: number) => {
    if (!timeline) return;
    try {
      const result = await captureCoverFrame(timeline.timeline_id, timestamp);
      setCoverFrameTime(timestamp);
      // Add cache buster to force reload
      setCoverFrameUrl(`${getCoverFrameUrl(timeline.job_id)}?t=${Date.now()}`);
    } catch (err) {
      console.error("Failed to capture cover frame:", err);
      alert("Failed to capture cover frame: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  }, [timeline]);

  // Handle Chinese conversion
  const handleConvertChinese = useCallback(async (toTraditional: boolean) => {
    if (!timeline) return;
    setConverting(true);
    try {
      const result = await convertChineseSubtitles(timeline.timeline_id, toTraditional);
      // Refresh timeline to get updated subtitles
      await refresh();
      alert(`Converted ${result.converted_count} subtitles to ${result.target} Chinese`);
    } catch (err) {
      console.error("Failed to convert Chinese:", err);
      alert("Failed to convert: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setConverting(false);
    }
  }, [timeline, refresh]);

  // Handle timeline seek
  const handleTimelineSeek = useCallback((time: number) => {
    if (videoPlayerRef.current) {
      videoPlayerRef.current.seekTo(time);
    }
    setCurrentVideoTime(time);
  }, []);

  // Timeline keyboard shortcuts
  useTimelineKeyboard({
    fps: 30,
    duration: timeline?.source_duration || 0,
    currentTime: currentVideoTime,
    isPlaying,
    onSeek: handleTimelineSeek,
    onPlayToggle: handlePlayToggle,
    segments: timeline?.segments.map((s) => ({ start: s.start, end: s.end })),
  });

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
      <ReviewHeader
        title={timeline.source_title}
        saving={saving}
        stats={stats}
        useTraditional={timeline.use_traditional_chinese}
        converting={converting}
        onExportClick={() => setShowExportPanel(true)}
        onConvertChinese={handleConvertChinese}
      />

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
              coverFrameTime={coverFrameTime}
              onSetCover={handleSetCover}
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

          <KeyboardHelp />
        </div>

        {/* Segment list panel */}
        <div className="w-[480px] flex-shrink-0 border-l border-gray-700 flex flex-col">
          <BulkActions timelineId={timelineId} />
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
        <ExportPanel
          timeline={timeline}
          coverFrameUrl={coverFrameUrl}
          coverFrameTime={coverFrameTime}
          onClose={() => setShowExportPanel(false)}
          onExport={startExport}
        />
      )}
    </main>
  );
}

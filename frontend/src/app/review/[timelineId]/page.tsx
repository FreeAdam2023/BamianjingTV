"use client";

/**
 * ReviewPage - Timeline review page with video player, timeline editor, and segment list
 */

import { useState, useRef, useCallback, useEffect } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import VideoPlayer, { VideoPlayerRef } from "@/components/VideoPlayer";
import SegmentList from "@/components/SegmentList";
import { TimelineEditor } from "@/components/timeline";
import { useTimeline } from "@/hooks/useTimeline";
import { useKeyboardNavigation } from "@/hooks/useKeyboardNavigation";
import { useTimelineKeyboard } from "@/hooks/useTimelineKeyboard";
import { useMultiTrackWaveform, TrackType } from "@/hooks/useMultiTrackWaveform";
import { captureCoverFrame, getCoverFrameUrl, convertChineseSubtitles, deleteJob, regenerateTranslationWithProgress, setSubtitleAreaRatio } from "@/lib/api";
import type { ExportStatusResponse } from "@/lib/types";
import { useToast, useConfirm } from "@/components/ui";
import ReviewHeader from "./ReviewHeader";
import ExportPanel from "./ExportPanel";
import PreviewUploadPanel from "./PreviewUploadPanel";
import ExportPreviewModal from "./ExportPreviewModal";
import KeyboardHelp from "./KeyboardHelp";
import BulkActions from "./BulkActions";

export default function ReviewPage() {
  const params = useParams();
  const router = useRouter();
  const timelineId = params.timelineId as string;
  const toast = useToast();
  const confirm = useConfirm();

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
  const [regenerating, setRegenerating] = useState(false);
  const [regenerateProgress, setRegenerateProgress] = useState<{ current: number; total: number } | null>(null);

  const [currentSegmentId, setCurrentSegmentId] = useState<number | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [isLooping, setIsLooping] = useState(false);
  const [showExportPanel, setShowExportPanel] = useState(false);
  const [showPreviewPanel, setShowPreviewPanel] = useState(false);
  const [exportStatusForPreview, setExportStatusForPreview] = useState<ExportStatusResponse | null>(null);
  const [exportJustStarted, setExportJustStarted] = useState(false);
  const [currentVideoTime, setCurrentVideoTime] = useState(0);
  const [coverFrameTime, setCoverFrameTime] = useState<number | null>(null);
  const [coverFrameUrl, setCoverFrameUrl] = useState<string | null>(null);
  const [exportPreviewType, setExportPreviewType] = useState<"full" | "essence" | null>(null);

  // Waveform data for timeline
  const { tracks: waveformTracks, generateTrack: generateWaveform } = useMultiTrackWaveform(timelineId);

  // Initialize cover frame from timeline data
  useEffect(() => {
    if (timeline?.cover_frame_time !== undefined && timeline?.cover_frame_time !== null) {
      setCoverFrameTime(timeline.cover_frame_time);
      setCoverFrameUrl(`${getCoverFrameUrl(timeline.job_id)}?t=${timeline.cover_frame_time}`);
    }
  }, [timeline?.cover_frame_time, timeline?.job_id]);

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
      toast.success("封面已设置");
    } catch (err) {
      console.error("Failed to capture cover frame:", err);
      toast.error("封面设置失败: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  }, [timeline, toast]);

  // Handle subtitle area ratio change (save to backend)
  const handleSubtitleAreaRatioChange = useCallback(async (ratio: number) => {
    if (!timeline) return;
    try {
      await setSubtitleAreaRatio(timeline.timeline_id, ratio);
      console.log("[ReviewPage] Subtitle ratio saved:", ratio);
    } catch (err) {
      console.error("[ReviewPage] Failed to save subtitle ratio:", err);
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
      toast.success(`已转换 ${result.converted_count} 条字幕为${result.target === "traditional" ? "繁体" : "简体"}中文`);
    } catch (err) {
      console.error("Failed to convert Chinese:", err);
      toast.error("转换失败: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setConverting(false);
    }
  }, [timeline, refresh, toast]);

  // Handle delete job
  const handleDelete = useCallback(async () => {
    if (!timeline) return;
    const confirmed = await confirm({
      title: "删除 Job",
      message: "确定要删除这个 Job 吗？此操作不可撤销。",
      type: "danger",
      confirmText: "删除",
      cancelText: "取消",
    });
    if (!confirmed) return;
    try {
      await deleteJob(timeline.job_id);
      toast.success("Job 已删除");
      router.push("/");
    } catch (err) {
      console.error("Failed to delete job:", err);
      toast.error("删除失败: " + (err instanceof Error ? err.message : "Unknown error"));
    }
  }, [timeline, router, confirm, toast]);

  // Handle regenerate translation
  const handleRegenerateTranslation = useCallback(async () => {
    if (!timeline) return;
    const confirmed = await confirm({
      title: "重新翻译",
      message: "确定要重新生成翻译吗？这将覆盖现有的中文字幕。",
      type: "warning",
      confirmText: "重新翻译",
      cancelText: "取消",
    });
    if (!confirmed) return;
    setRegenerating(true);
    setRegenerateProgress({ current: 0, total: timeline.segments.length });
    try {
      const result = await regenerateTranslationWithProgress(
        timeline.timeline_id,
        (progress) => {
          if (progress.type === "progress" && progress.current !== undefined && progress.total !== undefined) {
            setRegenerateProgress({ current: progress.current, total: progress.total });
          }
        }
      );
      await refresh();
      toast.success(`翻译完成：更新了 ${result.updated_count} 条字幕`);
    } catch (err) {
      console.error("Failed to regenerate translation:", err);
      toast.error("翻译失败: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setRegenerating(false);
      setRegenerateProgress(null);
    }
  }, [timeline, refresh, confirm, toast]);

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
        timelineId={timeline.timeline_id}
        jobId={timeline.job_id}
        exportStatus={timeline.export_status}
        onExportClick={() => setShowExportPanel(true)}
        onDelete={handleDelete}
        onShowPreview={(status) => {
          setExportStatusForPreview(status);
          setShowPreviewPanel(true);
        }}
        forcePolling={exportJustStarted}
        onExportStatusChange={(status) => {
          // Reset forcePolling when export completes or fails
          if (status.status === "completed" || status.status === "failed" || status.status === "idle") {
            setExportJustStarted(false);
          }
        }}
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
              useTraditional={timeline.use_traditional_chinese}
              converting={converting}
              onConvertChinese={handleConvertChinese}
              regenerating={regenerating}
              regenerateProgress={regenerateProgress}
              onRegenerateTranslation={handleRegenerateTranslation}
              hasExportFull={!!timeline.output_full_path}
              hasExportEssence={!!timeline.output_essence_path}
              onPreviewExport={setExportPreviewType}
              subtitleAreaRatio={timeline.subtitle_area_ratio}
              onSubtitleAreaRatioChange={handleSubtitleAreaRatioChange}
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
          onExportStarted={() => {
            setShowExportPanel(false);
            setExportJustStarted(true); // Force polling to start
            refresh(); // Refresh to update export_status
          }}
        />
      )}

      {/* Preview & Upload Panel */}
      {showPreviewPanel && exportStatusForPreview && (
        <PreviewUploadPanel
          timeline={timeline}
          exportStatus={exportStatusForPreview}
          onClose={() => {
            setShowPreviewPanel(false);
            setExportStatusForPreview(null);
          }}
          onUploadStarted={() => {
            refresh(); // Refresh to update export_status
          }}
        />
      )}

      {/* Export Preview Modal */}
      {exportPreviewType && (
        <ExportPreviewModal
          jobId={timeline.job_id}
          type={exportPreviewType}
          onClose={() => setExportPreviewType(null)}
        />
      )}
    </main>
  );
}

"use client";

/**
 * ReviewPage - Timeline review page with video player, timeline editor, and segment list
 */

import { useState, useRef, useCallback, useEffect, useMemo, lazy, Suspense } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import VideoPlayer, { VideoPlayerRef } from "@/components/VideoPlayer";
import SegmentList from "@/components/SegmentList";
import { TimelineEditor } from "@/components/timeline";
import { useTimeline } from "@/hooks/useTimeline";
import { useKeyboardNavigation } from "@/hooks/useKeyboardNavigation";
import { useTimelineKeyboard } from "@/hooks/useTimelineKeyboard";
import { useMultiTrackWaveform, TrackType } from "@/hooks/useMultiTrackWaveform";
import { useCardPopup } from "@/hooks/useCardPopup";
import { useCreativeConfig } from "@/hooks/useCreativeConfig";
import { useCreativeKeyboard } from "@/hooks/useCreativeKeyboard";
import { captureCoverFrame, getCoverFrameUrl, convertChineseSubtitles, deleteJob, regenerateTranslationWithProgress, setSubtitleAreaRatio, splitSegment, getSegmentAnnotations, setSubtitleLanguageMode, unpinCard, analyzeTimelineEntities } from "@/lib/api";
import type { ExportStatusResponse, SubtitleStyleOptions, SegmentAnnotations, PinnedCard } from "@/lib/types";
import type { CreativeStyle } from "@/lib/creative-types";
import { useToast, useConfirm } from "@/components/ui";
import ReviewHeader from "./ReviewHeader";
import ExportPanel from "./ExportPanel";
import PreviewUploadPanel from "./PreviewUploadPanel";
import ExportPreviewModal from "./ExportPreviewModal";
import KeyboardHelp from "./KeyboardHelp";
import BulkActions from "./BulkActions";
import SpeakerEditor from "./SpeakerEditor";
import ObservationCapture from "./ObservationCapture";
import ObservationList from "./ObservationList";
import AIChatPanel from "./AIChatPanel";
import StyleSelector from "./StyleSelector";
import CreativeConfigPanel from "./CreativeConfigPanel";
import CreativeAIChat from "./CreativeAIChat";
import RemotionExportPanel from "./RemotionExportPanel";
import PinnedCardsList from "./PinnedCardsList";
import type { Observation, EntityAnnotation } from "@/lib/types";
import type { RemotionConfig } from "@/lib/creative-types";
import { EntityEditModal } from "@/components/Cards";

// Lazy load RemotionPreview to avoid SSR issues with Remotion
const RemotionPreview = lazy(() => import("./RemotionPreview"));

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

  // Observation capture state (for WATCHING mode)
  const [showObservationCapture, setShowObservationCapture] = useState(false);
  const [observations, setObservations] = useState<Observation[]>([]);

  // NER annotations state - populated on-demand when segments are clicked
  const [segmentAnnotations, setSegmentAnnotations] = useState<Map<number, SegmentAnnotations> | undefined>();
  const [analyzingEntities, setAnalyzingEntities] = useState(false);

  // Entity editing modal state
  const [entityEditModal, setEntityEditModal] = useState<{
    isOpen: boolean;
    segmentId: number;
    segmentText: string;
    entity: EntityAnnotation | null;
  } | null>(null);

  // Card popup state (shared between video and segment list)
  const { state: cardState, openWordCard, openEntityCard, close: closeCard, refresh: refreshCard, refreshing: cardRefreshing } = useCardPopup();

  // Creative mode state
  const [isCreativeMode, setIsCreativeMode] = useState(false);
  const { config: creativeConfig, style: creativeStyle, setConfig: setCreativeConfig, setStyle: setCreativeStyle } = useCreativeConfig();

  // Creative mode keyboard shortcuts
  useCreativeKeyboard({
    enabled: isCreativeMode,
    config: creativeConfig,
    onStyleChange: setCreativeStyle,
    onConfigChange: setCreativeConfig,
  });

  // Initialize observations from timeline
  useEffect(() => {
    if (timeline?.observations) {
      setObservations(timeline.observations);
    }
  }, [timeline?.observations]);

  // Initialize segment annotations from timeline (cached annotations)
  useEffect(() => {
    if (timeline?.segment_annotations && Object.keys(timeline.segment_annotations).length > 0) {
      const annotationsMap = new Map<number, SegmentAnnotations>();
      for (const [segIdStr, annotation] of Object.entries(timeline.segment_annotations)) {
        annotationsMap.set(Number(segIdStr), annotation as SegmentAnnotations);
      }
      setSegmentAnnotations(annotationsMap);
    }
  }, [timeline?.segment_annotations]);

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

  // Get subtitle style from localStorage for export
  const getSubtitleStyleForExport = useCallback((): SubtitleStyleOptions | undefined => {
    if (typeof window === "undefined") return undefined;
    try {
      const saved = localStorage.getItem("subtitleStyle");
      if (saved) {
        const style = JSON.parse(saved);
        return {
          en_font_size: style.enFontSize,
          zh_font_size: style.zhFontSize,
          en_color: style.enColor,
          zh_color: style.zhColor,
          font_weight: style.fontWeight,
          background_color: style.backgroundColor,
        };
      }
    } catch (e) {
      console.error("Failed to parse subtitle style:", e);
    }
    return undefined;
  }, []);

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

  // Observation keyboard shortcut (S to capture - only for WATCHING mode)
  useEffect(() => {
    if (timeline?.mode !== "watching") return;

    const handleKeyDown = (e: KeyboardEvent) => {
      // Don't capture if in input field or modal is open
      if (
        e.target instanceof HTMLInputElement ||
        e.target instanceof HTMLTextAreaElement ||
        showObservationCapture ||
        showExportPanel ||
        showPreviewPanel
      ) {
        return;
      }

      if (e.key === "s" || e.key === "S") {
        e.preventDefault();
        setShowObservationCapture(true);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [timeline?.mode, showObservationCapture, showExportPanel, showPreviewPanel]);

  // Handle observation save
  const handleObservationSave = useCallback((observation: Observation) => {
    setObservations((prev) => [...prev, observation]);
    setShowObservationCapture(false);
    toast.success("Observation saved");
  }, [toast]);

  // Handle observation delete
  const handleObservationDelete = useCallback((observationId: string) => {
    setObservations((prev) => prev.filter((o) => o.id !== observationId));
    toast.success("Observation deleted");
  }, [toast]);

  // Handle observation click - seek to timecode
  const handleObservationClick = useCallback((observation: Observation) => {
    if (videoPlayerRef.current) {
      videoPlayerRef.current.seekTo(observation.timecode);
    }
  }, []);

  // Handle pinned card click - seek to timestamp and show card
  const handlePinnedCardClick = useCallback((card: PinnedCard) => {
    if (videoPlayerRef.current) {
      videoPlayerRef.current.seekTo(card.timestamp);
    }
    // Open the card popup
    if (card.card_type === "word" && card.card_data) {
      openWordCard((card.card_data as { word: string }).word);
    } else if (card.card_type === "entity" && card.card_data) {
      openEntityCard((card.card_data as { entity_id: string }).entity_id);
    }
  }, [openWordCard, openEntityCard]);

  // Handle pinned card unpin
  const handlePinnedCardUnpin = useCallback(async (cardId: string) => {
    if (!timeline) return;
    try {
      await unpinCard(timeline.timeline_id, cardId);
      await refresh();
      toast.success("卡片已取消钉住");
    } catch (err) {
      console.error("Failed to unpin card:", err);
      toast.error("取消钉住失败");
    }
  }, [timeline, refresh, toast]);

  // Handle segment click - also triggers entity analysis for that segment
  const handleSegmentClick = useCallback(async (segmentId: number) => {
    setCurrentSegmentId(segmentId);
    if (timeline) {
      const segment = timeline.segments.find((s) => s.id === segmentId);
      if (segment && videoPlayerRef.current) {
        videoPlayerRef.current.seekTo(segment.start);
      }

      // Auto-analyze entities for this segment if not already done
      if (segment && !segmentAnnotations?.has(segmentId)) {
        try {
          const annotation = await getSegmentAnnotations(segment.en, {
            timelineId: timeline.timeline_id,
            segmentId: segmentId,
          });
          setSegmentAnnotations((prev) => {
            const newMap = new Map(prev || []);
            newMap.set(segmentId, annotation);
            return newMap;
          });
        } catch (err) {
          console.error("Failed to analyze segment entities:", err);
        }
      }
    }
  }, [timeline, segmentAnnotations]);

  // Handle force refresh entity recognition for a segment
  const handleRefreshAnnotations = useCallback(async (segmentId: number) => {
    if (!timeline) return;
    const segment = timeline.segments.find((s) => s.id === segmentId);
    if (!segment) return;

    try {
      const annotation = await getSegmentAnnotations(segment.en, {
        timelineId: timeline.timeline_id,
        segmentId: segmentId,
        forceRefresh: true,
      });
      setSegmentAnnotations((prev) => {
        const newMap = new Map(prev || []);
        newMap.set(segmentId, annotation);
        return newMap;
      });
      toast.success("实体识别已刷新");
    } catch (err) {
      console.error("Failed to refresh segment entities:", err);
      toast.error("刷新失败");
    }
  }, [timeline, toast]);

  // Handle add entity (open modal for adding new entity)
  const handleAddEntity = useCallback((segmentId: number, segmentText: string) => {
    setEntityEditModal({
      isOpen: true,
      segmentId,
      segmentText,
      entity: null,
    });
  }, []);

  // Handle edit entity (open modal for editing existing entity)
  const handleEditEntity = useCallback((segmentId: number, segmentText: string, entity: EntityAnnotation) => {
    setEntityEditModal({
      isOpen: true,
      segmentId,
      segmentText,
      entity,
    });
  }, []);

  // Handle edit entity from card (only has entityId)
  const handleEditEntityFromCard = useCallback((entityId: string) => {
    if (!currentSegmentId || !timeline || !segmentAnnotations) return;

    const segment = timeline.segments.find((s) => s.id === currentSegmentId);
    if (!segment) return;

    const annotations = segmentAnnotations.get(currentSegmentId);
    const entity = annotations?.entities?.find((e) => e.entity_id === entityId);
    if (!entity) return;

    setEntityEditModal({
      isOpen: true,
      segmentId: currentSegmentId,
      segmentText: segment.en,
      entity,
    });
  }, [currentSegmentId, timeline, segmentAnnotations]);

  // Handle entity edit success
  const handleEntityEditSuccess = useCallback(async () => {
    // Refresh the segment annotations after edit
    if (entityEditModal && timeline) {
      const segment = timeline.segments.find((s) => s.id === entityEditModal.segmentId);
      if (segment) {
        const annotation = await getSegmentAnnotations(segment.en, {
          timelineId: timeline.timeline_id,
          segmentId: entityEditModal.segmentId,
          forceRefresh: true,
        });
        setSegmentAnnotations((prev) => {
          const newMap = new Map(prev || []);
          newMap.set(entityEditModal.segmentId, annotation);
          return newMap;
        });
      }
    }
    toast.success("实体已更新");
  }, [entityEditModal, timeline, toast]);

  // Handle full-text entity analysis
  const handleAnalyzeAllEntities = useCallback(async () => {
    if (!timeline || analyzingEntities) return;
    setAnalyzingEntities(true);
    try {
      const result = await analyzeTimelineEntities(timeline.timeline_id, {
        forceRefresh: true,
      });
      // Refresh timeline to get updated annotations
      await refresh();
      // Clear local cache and reload from timeline
      setSegmentAnnotations(undefined);
      toast.success(`识别完成: ${result.unique_entities} 个实体`);
    } catch (err) {
      console.error("Failed to analyze entities:", err);
      toast.error("实体识别失败");
    } finally {
      setAnalyzingEntities(false);
    }
  }, [timeline, analyzingEntities, refresh, toast]);

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

  // Handle subtitle language mode change (save to backend)
  const handleSubtitleLanguageModeChange = useCallback(async (mode: "both" | "en" | "zh" | "none") => {
    if (!timeline) return;
    try {
      await setSubtitleLanguageMode(timeline.timeline_id, mode);
      console.log("[ReviewPage] Subtitle language mode saved:", mode);
    } catch (err) {
      console.error("[ReviewPage] Failed to save subtitle language mode:", err);
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

  // Handle segment split
  const handleSplitSegment = useCallback(async (segmentId: number, enIndex: number, zhIndex: number) => {
    if (!timeline) return;
    try {
      await splitSegment(timeline.timeline_id, segmentId, enIndex, zhIndex);
      await refresh();
      toast.success("段落已分割");
    } catch (err) {
      console.error("Failed to split segment:", err);
      toast.error("分割失败: " + (err instanceof Error ? err.message : "Unknown error"));
      throw err;
    }
  }, [timeline, refresh, toast]);

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
        isCreativeMode={isCreativeMode}
        onModeChange={setIsCreativeMode}
      />

      {/* Main content */}
      <div className="flex-1 flex overflow-hidden">
        {/* Video panel */}
        <div className="flex-1 flex flex-col p-4 min-h-0 overflow-hidden">
          <div className="flex-1 min-h-0 h-0">
            {isCreativeMode ? (
              <Suspense
                fallback={
                  <div className="w-full h-full flex items-center justify-center bg-gray-900 rounded-lg">
                    <div className="text-center">
                      <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-purple-500 mx-auto mb-2" />
                      <p className="text-sm text-gray-400">加载动效预览...</p>
                    </div>
                  </div>
                }
              >
                <RemotionPreview
                  jobId={timeline.job_id}
                  segments={timeline.segments}
                  config={creativeConfig}
                  currentTime={currentVideoTime}
                  onTimeUpdate={handleVideoTimeUpdate}
                />
              </Suspense>
            ) : (
              <VideoPlayer
              ref={videoPlayerRef}
              jobId={timeline.job_id}
              segments={timeline.segments}
              currentSegmentId={currentSegmentId}
              onTimeUpdate={handleVideoTimeUpdate}
              onSegmentChange={setCurrentSegmentId}
              coverFrameTime={coverFrameTime}
              onSetCover={handleSetCover}
              trimStart={timeline.video_trim_start}
              trimEnd={timeline.video_trim_end}
              sourceDuration={timeline.source_duration}
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
              subtitleLanguageMode={timeline.subtitle_language_mode}
              onSubtitleLanguageModeChange={handleSubtitleLanguageModeChange}
              cardState={cardState}
              onCardClose={closeCard}
              timelineId={timeline.timeline_id}
              pinnedCards={timeline.pinned_cards || []}
              onCardPinChange={() => refresh()}
              onCardRefresh={refreshCard}
              cardRefreshing={cardRefreshing}
              onEditEntity={handleEditEntityFromCard}
            />
            )}
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
              trimStart={timeline.video_trim_start}
              trimEnd={timeline.video_trim_end}
              pinnedCards={timeline.pinned_cards || []}
              onPinnedCardClick={handlePinnedCardClick}
              onPinnedCardUnpin={handlePinnedCardUnpin}
            />
          </div>

          <KeyboardHelp isCreativeMode={isCreativeMode} />
        </div>

        {/* Segment list panel */}
        <div className="w-[480px] flex-shrink-0 border-l border-gray-700 flex flex-col">
          {/* Style selector (for CREATIVE mode) */}
          {isCreativeMode && (
            <>
              <StyleSelector
                currentStyle={creativeStyle}
                onStyleChange={setCreativeStyle}
              />
              <CreativeConfigPanel
                config={creativeConfig}
                onConfigChange={setCreativeConfig}
              />
            </>
          )}

          <BulkActions
            timelineId={timelineId}
            currentTime={currentVideoTime}
            trimStart={timeline.video_trim_start ?? 0}
            trimEnd={timeline.video_trim_end ?? null}
            sourceDuration={timeline.source_duration}
            onUpdate={() => refresh()}
          />
          <SpeakerEditor timelineId={timelineId} onSpeakerNamesChange={() => refresh()} />

          {/* Pinned cards list */}
          {(timeline.pinned_cards?.length ?? 0) > 0 && (
            <PinnedCardsList
              timelineId={timeline.timeline_id}
              pinnedCards={timeline.pinned_cards || []}
              onCardClick={handlePinnedCardClick}
              onRefresh={() => refresh()}
            />
          )}

          {/* Entity analysis section */}
          <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700 bg-gray-800/50">
            <div className="flex items-center gap-2">
              <svg className="w-4 h-4 text-cyan-400" fill="currentColor" viewBox="0 0 20 20">
                <path fillRule="evenodd" d="M17.707 9.293a1 1 0 010 1.414l-7 7a1 1 0 01-1.414 0l-7-7A.997.997 0 012 10V5a3 3 0 013-3h5c.256 0 .512.098.707.293l7 7zM5 6a1 1 0 100-2 1 1 0 000 2z" clipRule="evenodd" />
              </svg>
              <span className="text-sm text-gray-400">实体识别</span>
              {Object.keys(timeline.segment_annotations || {}).length > 0 && (
                <span className="px-1.5 py-0.5 text-xs bg-cyan-500/20 text-cyan-400 rounded">
                  {Object.keys(timeline.segment_annotations || {}).length} 段
                </span>
              )}
            </div>
            <button
              onClick={handleAnalyzeAllEntities}
              disabled={analyzingEntities}
              className="px-2 py-1 text-xs bg-cyan-600 hover:bg-cyan-700 disabled:bg-cyan-800 disabled:cursor-wait text-white rounded flex items-center gap-1.5 transition-colors"
              title="使用完整上下文一次性识别所有实体（更准确）"
            >
              {analyzingEntities ? (
                <>
                  <svg className="w-3 h-3 animate-spin" fill="none" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  分析中...
                </>
              ) : (
                <>
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                  </svg>
                  全文识别
                </>
              )}
            </button>
          </div>

          {/* Segment list - scrollable */}
          <SegmentList
            segments={timeline.segments}
            currentSegmentId={currentSegmentId}
            onSegmentClick={handleSegmentClick}
            onStateChange={setSegmentState}
            onTextChange={setSegmentText}
            onSplitSegment={handleSplitSegment}
            segmentAnnotations={segmentAnnotations}
            onRefreshAnnotations={handleRefreshAnnotations}
            onWordClick={openWordCard}
            onEntityClick={openEntityCard}
            onAddEntity={handleAddEntity}
            onEditEntity={handleEditEntity}
          />

          {/* Observations section (for WATCHING mode) - below segment list */}
          {timeline.mode === "watching" && (
            <div className="border-t border-gray-700 flex-shrink-0">
              <div className="flex items-center justify-between px-4 py-2 bg-gray-800/50">
                <div className="flex items-center gap-2">
                  <svg className="w-4 h-4 text-yellow-500" fill="currentColor" viewBox="0 0 20 20">
                    <path fillRule="evenodd" d="M4 5a2 2 0 00-2 2v8a2 2 0 002 2h12a2 2 0 002-2V7a2 2 0 00-2-2h-1.586a1 1 0 01-.707-.293l-1.121-1.121A2 2 0 0011.172 3H8.828a2 2 0 00-1.414.586L6.293 4.707A1 1 0 015.586 5H4zm6 9a3 3 0 100-6 3 3 0 000 6z" clipRule="evenodd" />
                  </svg>
                  <span className="text-sm font-medium">Observations</span>
                  <span className="px-1.5 py-0.5 text-xs bg-yellow-500/20 text-yellow-400 rounded">
                    {observations.length}
                  </span>
                </div>
                <button
                  onClick={() => setShowObservationCapture(true)}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  + Add (S)
                </button>
              </div>
              <div className="max-h-32 overflow-y-auto">
                <ObservationList
                  timelineId={timelineId}
                  observations={observations}
                  onObservationClick={handleObservationClick}
                  onDelete={handleObservationDelete}
                />
              </div>
            </div>
          )}

          {/* AI Chat Panel - at the bottom */}
          {isCreativeMode ? (
            <>
              <CreativeAIChat
                timelineId={timelineId}
                currentConfig={creativeConfig}
                onConfigChange={setCreativeConfig}
              />
              <RemotionExportPanel
                timelineId={timelineId}
                jobId={timeline.job_id}
                config={creativeConfig}
              />
            </>
          ) : (
            <AIChatPanel
              timelineId={timelineId}
              videoTitle={timeline.source_title}
              currentTime={currentVideoTime}
              observations={observations}
            />
          )}
        </div>
      </div>

      {/* Export Panel Modal */}
      {showExportPanel && (
        <ExportPanel
          timeline={timeline}
          coverFrameUrl={coverFrameUrl}
          coverFrameTime={coverFrameTime}
          subtitleStyle={getSubtitleStyleForExport()}
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

      {/* Observation Capture Modal (for WATCHING mode) */}
      {showObservationCapture && timeline.mode === "watching" && (
        <ObservationCapture
          timelineId={timelineId}
          timecode={currentVideoTime}
          onSave={handleObservationSave}
          onCancel={() => setShowObservationCapture(false)}
        />
      )}

      {/* Entity Edit Modal */}
      {entityEditModal && (
        <EntityEditModal
          isOpen={entityEditModal.isOpen}
          onClose={() => setEntityEditModal(null)}
          timelineId={timeline.timeline_id}
          segmentId={entityEditModal.segmentId}
          segmentText={entityEditModal.segmentText}
          entity={entityEditModal.entity}
          onSuccess={handleEntityEditSuccess}
        />
      )}
    </main>
  );
}

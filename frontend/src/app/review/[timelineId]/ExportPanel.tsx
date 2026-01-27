"use client";

/**
 * ExportPanel - Modal for export settings and thumbnail generation
 */

import { useState, useEffect, useRef, useCallback } from "react";
import type { ExportProfile, ExportRequest, Timeline, TitleCandidate, MetadataDraft } from "@/lib/types";
import { generateThumbnail, generateUnifiedMetadata, getMetadataDraft, saveMetadataDraft, formatDuration } from "@/lib/api";
import { useToast } from "@/components/ui";

interface ExportPanelProps {
  timeline: Timeline;
  coverFrameUrl: string | null;
  coverFrameTime: number | null;
  onClose: () => void;
  onExport: (request: ExportRequest) => Promise<unknown>;
  onExportStarted?: () => void;
}

export default function ExportPanel({
  timeline,
  coverFrameUrl,
  coverFrameTime,
  onClose,
  onExport,
  onExportStarted,
}: ExportPanelProps) {
  const toast = useToast();
  const [exportProfile, setExportProfile] = useState<ExportProfile>("full");
  const [useTraditional, setUseTraditional] = useState(true);
  const [exporting, setExporting] = useState(false);

  // YouTube metadata (for draft saving, upload happens in PreviewUploadPanel)
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeDescription, setYoutubeDescription] = useState("");
  const [youtubeTags, setYoutubeTags] = useState("");

  // Title candidates (thumbnail)
  const [titleCandidates, setTitleCandidates] = useState<TitleCandidate[]>([]);
  const [selectedTitle, setSelectedTitle] = useState<TitleCandidate | null>(null);

  // Shared AI instruction for both YouTube metadata and thumbnail titles
  const [aiInstruction, setAiInstruction] = useState("");
  const [generatingAll, setGeneratingAll] = useState(false);
  const [loadingDraft, setLoadingDraft] = useState(true);

  // Draft auto-save
  const [savingDraft, setSavingDraft] = useState(false);
  const [draftSavedAt, setDraftSavedAt] = useState<Date | null>(null);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const initialLoadRef = useRef(true);

  // Thumbnail generation (moved up so saveDraft can use it)
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [generatingThumbnail, setGeneratingThumbnail] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  // Auto-save draft function
  const saveDraft = useCallback(async () => {
    // Don't save during initial load or if nothing to save
    if (loadingDraft || initialLoadRef.current) return;
    if (!youtubeTitle && !youtubeDescription && !youtubeTags && titleCandidates.length === 0 && !selectedTitle && !thumbnailUrl) return;

    setSavingDraft(true);
    try {
      const draft: MetadataDraft = {
        youtube_title: youtubeTitle || null,
        youtube_description: youtubeDescription || null,
        youtube_tags: youtubeTags ? youtubeTags.split(",").map(t => t.trim()).filter(Boolean) : null,
        thumbnail_candidates: titleCandidates.length > 0 ? titleCandidates : null,
        instruction: aiInstruction || null,
        selected_title: selectedTitle || null,
        thumbnail_url: thumbnailUrl || null,
      };
      await saveMetadataDraft(timeline.timeline_id, draft);
      setDraftSavedAt(new Date());
      console.log("[ExportPanel] Draft saved successfully");
    } catch (err) {
      console.error("[ExportPanel] Failed to save draft:", err);
    } finally {
      setSavingDraft(false);
    }
  }, [timeline.timeline_id, youtubeTitle, youtubeDescription, youtubeTags, titleCandidates, aiInstruction, selectedTitle, thumbnailUrl, loadingDraft]);

  // Debounced auto-save when any metadata changes
  useEffect(() => {
    // Skip during initial load
    if (loadingDraft) return;

    // Mark initial load complete after first render
    if (initialLoadRef.current) {
      initialLoadRef.current = false;
      return;
    }

    // Clear existing timeout
    if (saveTimeoutRef.current) {
      clearTimeout(saveTimeoutRef.current);
    }

    // Set new timeout for debounced save (1.5 seconds after last change)
    saveTimeoutRef.current = setTimeout(() => {
      saveDraft();
    }, 1500);

    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [youtubeTitle, youtubeDescription, youtubeTags, titleCandidates, aiInstruction, selectedTitle, thumbnailUrl, loadingDraft, saveDraft]);

  // Load saved draft on mount
  useEffect(() => {
    async function loadDraft() {
      console.log("[ExportPanel] Loading metadata draft for timeline:", timeline.timeline_id);
      try {
        const result = await getMetadataDraft(timeline.timeline_id);
        console.log("[ExportPanel] Draft response:", { has_draft: result.has_draft, message: result.message });
        if (result.has_draft) {
          const { draft } = result;
          console.log("[ExportPanel] Restoring draft:", {
            youtube_title: draft.youtube_title?.slice(0, 30),
            candidates_count: draft.thumbnail_candidates?.length,
            instruction: draft.instruction,
            selected_title: draft.selected_title?.main,
          });
          if (draft.youtube_title) setYoutubeTitle(draft.youtube_title);
          if (draft.youtube_description) setYoutubeDescription(draft.youtube_description);
          if (draft.youtube_tags) setYoutubeTags(draft.youtube_tags.join(", "));
          if (draft.thumbnail_candidates) setTitleCandidates(draft.thumbnail_candidates);
          if (draft.instruction) setAiInstruction(draft.instruction);
          if (draft.selected_title) setSelectedTitle(draft.selected_title);
          if (draft.thumbnail_url) setThumbnailUrl(draft.thumbnail_url);
        }
      } catch (err) {
        console.error("[ExportPanel] Failed to load metadata draft:", err);
      } finally {
        setLoadingDraft(false);
      }
    }
    loadDraft();
  }, [timeline.timeline_id]);

  // ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

  const handleExport = async () => {
    console.log("[ExportPanel] Starting export...", { profile: exportProfile });
    setExporting(true);
    try {
      const request: ExportRequest = {
        profile: exportProfile,
        use_traditional_chinese: useTraditional,
        upload_to_youtube: false, // Don't upload yet, user will preview first
      };

      console.log("[ExportPanel] Export request:", request);
      await onExport(request);
      console.log("[ExportPanel] Export started");
      toast.success("开始导出视频，进度显示在顶部...");

      // Close modal and let header show progress
      onExportStarted?.();
    } catch (err) {
      console.error("[ExportPanel] Export failed:", err);
      toast.error("导出失败: " + (err instanceof Error ? err.message : "Unknown error"));
      setExporting(false);
    }
  };

  const getBaseUrl = () => {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  };

  // Unified generation: YouTube metadata + thumbnail titles together
  const handleGenerateAll = async () => {
    console.log("[ExportPanel] Starting unified metadata generation...", {
      timeline_id: timeline.timeline_id,
      instruction: aiInstruction || "(none)",
    });
    setGeneratingAll(true);
    try {
      const result = await generateUnifiedMetadata(
        timeline.timeline_id,
        {
          instruction: aiInstruction || undefined,
          num_title_candidates: 5,
        }
      );

      console.log("[ExportPanel] Generated unified metadata:", {
        youtube_title: result.youtube_title?.slice(0, 50),
        candidates_count: result.thumbnail_candidates?.length,
        message: result.message,
      });

      // Set YouTube metadata
      setYoutubeTitle(result.youtube_title);
      setYoutubeDescription(result.youtube_description);
      setYoutubeTags(result.youtube_tags.join(", "));

      // Set thumbnail title candidates
      setTitleCandidates(result.thumbnail_candidates);
      setSelectedTitle(null);
    } catch (err) {
      console.error("[ExportPanel] Failed to generate metadata:", err);
      toast.error("元数据生成失败: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setGeneratingAll(false);
    }
  };

  const handleGenerateThumbnail = async () => {
    setGeneratingThumbnail(true);
    try {
      const request: { use_cover_frame?: boolean; main_title?: string; sub_title?: string } = {};

      if (coverFrameUrl) {
        request.use_cover_frame = true;
      }

      if (selectedTitle) {
        request.main_title = selectedTitle.main;
        request.sub_title = selectedTitle.sub;
      }

      const result = await generateThumbnail(
        timeline.timeline_id,
        Object.keys(request).length > 0 ? request : undefined
      );
      setThumbnailUrl(`${getBaseUrl()}${result.thumbnail_url}`);
      setShowOriginal(false);
    } catch (err) {
      toast.error("封面生成失败: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setGeneratingThumbnail(false);
    }
  };

  return (
    <div
      className="fixed inset-0 bg-black/50 flex items-center justify-center z-50"
      onClick={(e) => {
        // Close when clicking backdrop
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-gray-800 rounded-lg p-6 w-[520px] max-h-[90vh] overflow-y-auto relative">
        {/* Close button */}
        <button
          onClick={onClose}
          className="absolute top-4 right-4 text-gray-400 hover:text-white"
          title="Close (Esc)"
        >
          <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
        <h2 className="text-xl font-bold mb-4">Export Video</h2>

        {/* Export profile */}
        <div className="mb-4">
          <label className="block text-sm text-gray-400 mb-2">Export Profile</label>
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

        {/* AI Generate Section - Unified for YouTube metadata + Thumbnail titles */}
        <div className="border-t border-gray-700 pt-4 mt-4">
          <div className="mb-4 p-4 bg-gradient-to-r from-purple-900/30 to-indigo-900/30 rounded-lg border border-purple-700/50">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <svg className="w-5 h-5 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
                </svg>
                <span className="font-medium text-purple-300">AI 一键生成</span>
              </div>
              {/* Draft status indicator */}
              {loadingDraft ? (
                <span className="text-xs text-gray-500 flex items-center gap-1">
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  加载草稿...
                </span>
              ) : savingDraft ? (
                <span className="text-xs text-yellow-400 flex items-center gap-1">
                  <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                  </svg>
                  保存中...
                </span>
              ) : (youtubeTitle || titleCandidates.length > 0) ? (
                <span className="text-xs text-green-400 flex items-center gap-1">
                  <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  草稿已保存
                </span>
              ) : null}
            </div>

            {/* Shared instruction input */}
            <div className="mb-3">
              <input
                type="text"
                value={aiInstruction}
                onChange={(e) => setAiInstruction(e.target.value)}
                placeholder="创作指导（如：'突出冲突'、'更戏剧化'、'专注经济话题'）..."
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm placeholder-gray-500"
              />
            </div>

            <button
              onClick={handleGenerateAll}
              disabled={generatingAll || loadingDraft}
              className="w-full px-3 py-2 text-sm bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-700 hover:to-indigo-700 disabled:from-gray-600 disabled:to-gray-600 rounded flex items-center justify-center gap-2"
            >
              {generatingAll ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  AI 生成中...
                </>
              ) : (youtubeTitle || titleCandidates.length > 0) ? (
                "重新生成 YouTube 元数据 + 封面标题"
              ) : (
                "一键生成 YouTube 元数据 + 封面标题"
              )}
            </button>
            <p className="text-xs text-gray-500 text-center mt-2">
              {(youtubeTitle || titleCandidates.length > 0)
                ? "修改会自动保存，下次打开无需重新生成"
                : "YouTube 标题和封面标题将协调一致，共享相同的创作指导"}
            </p>
          </div>
        </div>

        {/* YouTube Metadata Section */}
        <div className="border-t border-gray-700 pt-4 mt-4">
          <div className="flex items-center justify-between mb-4">
            <span className="font-medium flex items-center gap-2">
              <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
              </svg>
              YouTube 元数据
            </span>
            {youtubeTitle && (
              <span className="text-xs text-green-400">元数据已就绪</span>
            )}
          </div>
          <p className="text-xs text-gray-500 mb-3">
            导出完成后可预览视频，确认后再上传到 YouTube
          </p>

          {/* Title with copy button */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-400">标题</label>
              {youtubeTitle && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(youtubeTitle);
                    toast.success("标题已复制");
                  }}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  复制
                </button>
              )}
            </div>
            <input
              type="text"
              value={youtubeTitle}
              onChange={(e) => setYoutubeTitle(e.target.value)}
              placeholder={timeline?.source_title}
              className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
            />
          </div>

          {/* Description with copy button */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-400">描述</label>
              {youtubeDescription && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(youtubeDescription);
                    toast.success("描述已复制");
                  }}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  复制
                </button>
              )}
            </div>
            <textarea
              value={youtubeDescription}
              onChange={(e) => setYoutubeDescription(e.target.value)}
              placeholder={`Original: ${timeline?.source_url}`}
              rows={4}
              className="w-full bg-gray-700 rounded px-3 py-2 text-sm resize-none"
            />
          </div>

          {/* Tags with copy button */}
          <div className="mb-3">
            <div className="flex items-center justify-between mb-1">
              <label className="text-sm text-gray-400">标签</label>
              {youtubeTags && (
                <button
                  onClick={() => {
                    navigator.clipboard.writeText(youtubeTags);
                    toast.success("标签已复制");
                  }}
                  className="text-xs text-blue-400 hover:text-blue-300"
                >
                  复制
                </button>
              )}
            </div>
            <input
              type="text"
              value={youtubeTags}
              onChange={(e) => setYoutubeTags(e.target.value)}
              placeholder="learning, english, chinese"
              className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
            />
          </div>

          {/* Copy all button */}
          <div className="mt-3">
            <button
              onClick={() => {
                const text = `标题:\n${youtubeTitle || timeline?.source_title}\n\n描述:\n${youtubeDescription || ""}\n\n标签:\n${youtubeTags || ""}`;
                navigator.clipboard.writeText(text);
                toast.success("全部信息已复制到剪贴板");
              }}
              className="w-full px-3 py-2 text-sm bg-gray-700 hover:bg-gray-600 rounded flex items-center justify-center gap-2"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              复制全部元数据
            </button>
          </div>
        </div>

        {/* Thumbnail Generation Section */}
        <div className="border-t border-gray-700 pt-4 mt-4">
          <div className="flex items-center justify-between mb-3">
            <span className="font-medium">Video Thumbnail</span>
            {coverFrameTime !== null && (
              <span className="text-sm text-purple-400">
                Cover @ {formatDuration(coverFrameTime)}
              </span>
            )}
          </div>

          {/* Thumbnail Title Candidates (generated by unified AI call above) */}
          <div className="mb-4 p-3 bg-gray-900 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-300">
                封面标题候选 {titleCandidates.length > 0 && <span className="text-green-400 text-xs ml-1">(AI Generated)</span>}
              </span>
            </div>

            {/* Title Candidates */}
            {titleCandidates.length > 0 && (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {titleCandidates.map((candidate) => (
                  <button
                    key={candidate.index}
                    onClick={() => setSelectedTitle({ ...candidate })}
                    className={`w-full text-left p-2 rounded border-2 transition-colors ${
                      selectedTitle?.index === candidate.index
                        ? "border-purple-500 bg-purple-500/20"
                        : "border-transparent bg-gray-800 hover:bg-gray-750"
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <span className={`text-xs px-1.5 py-0.5 rounded ${
                        selectedTitle?.index === candidate.index
                          ? "bg-purple-500 text-white"
                          : "bg-gray-700 text-gray-400"
                      }`}>
                        {candidate.index + 1}
                      </span>
                      <div className="flex-1 min-w-0">
                        <div className="text-yellow-400 font-bold truncate">{candidate.main}</div>
                        <div className="text-white text-sm truncate">{candidate.sub}</div>
                        {candidate.style && (
                          <div className="text-xs text-gray-500 mt-0.5">{candidate.style}</div>
                        )}
                      </div>
                    </div>
                  </button>
                ))}
              </div>
            )}

            {titleCandidates.length === 0 && (
              <p className="text-xs text-gray-500 text-center py-2">
                点击上方「一键生成」获取 AI 封面标题建议
              </p>
            )}

            {/* Editable selected title */}
            {selectedTitle && (
              <div className="mt-3 p-3 bg-purple-900/30 rounded-lg border border-purple-700/50">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-xs text-purple-400 font-medium">已选标题（可编辑）</span>
                  <button
                    onClick={() => setSelectedTitle(null)}
                    className="text-xs text-gray-500 hover:text-gray-300"
                  >
                    取消选择
                  </button>
                </div>
                <div className="space-y-2">
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">主标题（黄色大字）</label>
                    <input
                      type="text"
                      value={selectedTitle.main}
                      onChange={(e) => setSelectedTitle({ ...selectedTitle, main: e.target.value })}
                      className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-yellow-400 font-bold"
                      placeholder="主标题"
                    />
                  </div>
                  <div>
                    <label className="text-xs text-gray-500 block mb-1">副标题（白色字）</label>
                    <input
                      type="text"
                      value={selectedTitle.sub}
                      onChange={(e) => setSelectedTitle({ ...selectedTitle, sub: e.target.value })}
                      className="w-full bg-gray-800 border border-gray-600 rounded px-2 py-1.5 text-sm text-white"
                      placeholder="副标题"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Custom title option when no candidates or want to add custom */}
            {!selectedTitle && (
              <button
                onClick={() => setSelectedTitle({ index: -1, main: "", sub: "", style: "自定义" })}
                className="mt-2 w-full text-left p-2 rounded border-2 border-dashed border-gray-600 hover:border-gray-500 bg-gray-800/50 hover:bg-gray-800 transition-colors"
              >
                <div className="flex items-center gap-2 text-gray-400">
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                  </svg>
                  <span className="text-sm">自定义封面标题</span>
                </div>
              </button>
            )}
          </div>

          {/* Cover Frame Preview / Generated Thumbnail */}
          <div className="relative rounded-lg overflow-hidden bg-gray-900 aspect-video mb-3">
            {thumbnailUrl ? (
              <>
                <img
                  src={showOriginal && coverFrameUrl ? coverFrameUrl : thumbnailUrl}
                  alt={showOriginal ? "Original cover frame" : "Generated thumbnail"}
                  className="w-full h-full object-cover"
                />
                {coverFrameUrl && (
                  <div className="absolute top-2 left-2 flex gap-1">
                    <button
                      onClick={() => setShowOriginal(false)}
                      className={`px-2 py-1 text-xs rounded ${
                        !showOriginal
                          ? "bg-purple-600 text-white"
                          : "bg-black/70 text-gray-300 hover:bg-black/90"
                      }`}
                    >
                      AI Generated
                    </button>
                    <button
                      onClick={() => setShowOriginal(true)}
                      className={`px-2 py-1 text-xs rounded ${
                        showOriginal
                          ? "bg-purple-600 text-white"
                          : "bg-black/70 text-gray-300 hover:bg-black/90"
                      }`}
                    >
                      Original
                    </button>
                  </div>
                )}
                <a
                  href={thumbnailUrl}
                  download="thumbnail.png"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="absolute bottom-2 right-2 px-2 py-1 text-xs bg-black/70 hover:bg-black/90 rounded"
                >
                  Download
                </a>
              </>
            ) : coverFrameUrl ? (
              <>
                <img
                  src={coverFrameUrl}
                  alt="Cover frame"
                  className="w-full h-full object-cover"
                />
                <div className="absolute bottom-2 left-2 px-2 py-1 text-xs bg-black/70 rounded">
                  Cover Frame Preview
                </div>
              </>
            ) : (
              <div className="w-full h-full flex items-center justify-center text-gray-500 text-sm">
                <div className="text-center">
                  <svg className="w-12 h-12 mx-auto mb-2 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M4 16l4.586-4.586a2 2 0 012.828 0L16 16m-2-2l1.586-1.586a2 2 0 012.828 0L20 14m-6-6h.01M6 20h12a2 2 0 002-2V6a2 2 0 00-2-2H6a2 2 0 00-2 2v12a2 2 0 002 2z" />
                  </svg>
                  <p>No cover frame selected</p>
                  <p className="text-xs mt-1">Use "Set Cover" button in video player</p>
                </div>
              </div>
            )}
          </div>

          {/* Generate Thumbnail Button */}
          <button
            onClick={handleGenerateThumbnail}
            disabled={generatingThumbnail}
            className="w-full px-3 py-2 text-sm bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded flex items-center justify-center gap-2"
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
              "Regenerate Thumbnail"
            ) : (
              "Generate Thumbnail"
            )}
          </button>

          <p className="text-xs text-gray-500 mt-2 text-center">
            {selectedTitle
              ? "使用编辑后的标题生成封面"
              : "将自动生成封面标题（或先选择/自定义标题）"}
          </p>
        </div>

        {/* Buttons */}
        <div className="flex gap-4 mt-6">
          <button
            onClick={onClose}
            className="flex-1 py-2 bg-gray-600 hover:bg-gray-700 rounded"
          >
            取消
          </button>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="flex-1 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded flex items-center justify-center gap-2"
          >
            {exporting ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                正在开始...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-8l-4-4m0 0L8 8m4-4v12" />
                </svg>
                开始导出
              </>
            )}
          </button>
        </div>
        <p className="text-xs text-gray-500 text-center mt-2">
          导出完成后可预览视频，确认后再上传到 YouTube
        </p>
      </div>
    </div>
  );
}

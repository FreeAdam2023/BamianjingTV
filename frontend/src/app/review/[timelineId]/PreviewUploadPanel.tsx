"use client";

/**
 * PreviewUploadPanel - Modal for previewing exported video and confirming YouTube upload
 */

import { useState, useEffect } from "react";
import type { ExportStatusResponse, Timeline } from "@/lib/types";
import { getMetadataDraft, triggerExport } from "@/lib/api";
import { useToast } from "@/components/ui";

interface PreviewUploadPanelProps {
  timeline: Timeline;
  exportStatus: ExportStatusResponse;
  onClose: () => void;
  onUploadStarted: () => void;
}

export default function PreviewUploadPanel({
  timeline,
  exportStatus,
  onClose,
  onUploadStarted,
}: PreviewUploadPanelProps) {
  const toast = useToast();
  const [uploading, setUploading] = useState(false);

  // YouTube metadata from draft
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeDescription, setYoutubeDescription] = useState("");
  const [youtubeTags, setYoutubeTags] = useState("");
  const [youtubePrivacy, setYoutubePrivacy] = useState<"private" | "unlisted" | "public">("unlisted");
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [loadingDraft, setLoadingDraft] = useState(true);

  // Load saved draft on mount
  useEffect(() => {
    async function loadDraft() {
      try {
        const result = await getMetadataDraft(timeline.timeline_id);
        if (result.has_draft) {
          const { draft } = result;
          if (draft.youtube_title) setYoutubeTitle(draft.youtube_title);
          if (draft.youtube_description) setYoutubeDescription(draft.youtube_description);
          if (draft.youtube_tags) setYoutubeTags(draft.youtube_tags.join(", "));
          if (draft.thumbnail_url) setThumbnailUrl(draft.thumbnail_url);
        }
      } catch (err) {
        console.error("[PreviewUploadPanel] Failed to load draft:", err);
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

  const getBaseUrl = () => {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8001`;
  };

  const handleUpload = async () => {
    setUploading(true);
    try {
      // Trigger export with YouTube upload (video already exported, this will just upload)
      await triggerExport(timeline.timeline_id, {
        profile: timeline.export_profile || "full",
        use_traditional_chinese: timeline.use_traditional_chinese,
        upload_to_youtube: true,
        youtube_title: youtubeTitle || undefined,
        youtube_description: youtubeDescription || undefined,
        youtube_tags: youtubeTags ? youtubeTags.split(",").map(t => t.trim()).filter(Boolean) : undefined,
        youtube_privacy: youtubePrivacy,
      });
      toast.success("开始上传到 YouTube...");
      onUploadStarted();
      onClose();
    } catch (err) {
      console.error("[PreviewUploadPanel] Upload failed:", err);
      toast.error("上传失败: " + (err instanceof Error ? err.message : "Unknown error"));
      setUploading(false);
    }
  };

  const videoUrl = exportStatus.full_video_path
    ? `${getBaseUrl()}/timelines/${timeline.timeline_id}/video/full`
    : null;

  return (
    <div
      className="fixed inset-0 bg-black/70 flex items-center justify-center z-50"
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div className="bg-gray-800 rounded-lg w-[800px] max-h-[90vh] overflow-hidden flex flex-col">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
          <div>
            <h2 className="text-xl font-bold">导出完成 - 预览 & 上传</h2>
            <p className="text-sm text-gray-400 mt-1">预览导出视频，确认后上传到 YouTube</p>
          </div>
          <button
            onClick={onClose}
            className="text-gray-400 hover:text-white p-1"
            title="关闭 (Esc)"
            aria-label="关闭预览"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-6">
          {/* Video Preview */}
          <div className="mb-6">
            <h3 className="text-sm font-medium text-gray-300 mb-2">视频预览</h3>
            {videoUrl ? (
              <video
                src={videoUrl}
                controls
                className="w-full rounded-lg bg-black"
                style={{ maxHeight: "360px" }}
              >
                您的浏览器不支持视频标签。
              </video>
            ) : (
              <div className="w-full h-48 bg-gray-900 rounded-lg flex items-center justify-center text-gray-500">
                视频文件不可用
              </div>
            )}
            {/* Download button */}
            {videoUrl && (
              <div className="mt-2 flex justify-end">
                <a
                  href={videoUrl}
                  download
                  className="text-sm text-blue-400 hover:text-blue-300 flex items-center gap-1"
                >
                  <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  下载视频
                </a>
              </div>
            )}
          </div>

          {/* Thumbnail Preview */}
          {thumbnailUrl && (
            <div className="mb-6">
              <h3 className="text-sm font-medium text-gray-300 mb-2">封面预览</h3>
              <div className="relative rounded-lg overflow-hidden bg-gray-900 aspect-video" style={{ maxHeight: "200px" }}>
                <img
                  src={thumbnailUrl.startsWith('http') ? thumbnailUrl : `${getBaseUrl()}${thumbnailUrl}`}
                  alt="Generated thumbnail"
                  className="w-full h-full object-contain"
                />
                <a
                  href={thumbnailUrl.startsWith('http') ? thumbnailUrl : `${getBaseUrl()}${thumbnailUrl}`}
                  download="thumbnail.png"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="absolute bottom-2 right-2 px-2 py-1 text-xs bg-black/70 hover:bg-black/90 rounded"
                >
                  下载封面
                </a>
              </div>
            </div>
          )}

          {/* YouTube Metadata */}
          <div className="border-t border-gray-700 pt-4">
            <h3 className="text-sm font-medium text-gray-300 mb-3 flex items-center gap-2">
              <svg className="w-4 h-4 text-red-500" fill="currentColor" viewBox="0 0 24 24">
                <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
              </svg>
              YouTube 上传设置
            </h3>

            {loadingDraft ? (
              <div className="text-center py-4 text-gray-500">加载元数据...</div>
            ) : (
              <div className="space-y-3">
                {/* Title */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">标题</label>
                  <input
                    type="text"
                    value={youtubeTitle}
                    onChange={(e) => setYoutubeTitle(e.target.value)}
                    placeholder={timeline.source_title}
                    className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">描述</label>
                  <textarea
                    value={youtubeDescription}
                    onChange={(e) => setYoutubeDescription(e.target.value)}
                    placeholder="视频描述..."
                    rows={3}
                    className="w-full bg-gray-700 rounded px-3 py-2 text-sm resize-none"
                  />
                </div>

                {/* Tags */}
                <div>
                  <label className="text-xs text-gray-500 block mb-1">标签（逗号分隔）</label>
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
                  <label className="text-xs text-gray-500 block mb-1">隐私设置</label>
                  <select
                    value={youtubePrivacy}
                    onChange={(e) => setYoutubePrivacy(e.target.value as "private" | "unlisted" | "public")}
                    className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
                  >
                    <option value="private">私享 (Private)</option>
                    <option value="unlisted">不公开 (Unlisted)</option>
                    <option value="public">公开 (Public)</option>
                  </select>
                </div>
              </div>
            )}
          </div>
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-gray-700 flex gap-3">
          <button
            onClick={onClose}
            className="flex-1 py-2 bg-gray-600 hover:bg-gray-700 rounded"
          >
            稍后上传
          </button>
          <button
            onClick={() => window.open("https://studio.youtube.com/channel/UC/videos/upload?d=ud", "_blank")}
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded text-sm"
          >
            手动上传
          </button>
          <button
            onClick={handleUpload}
            disabled={uploading || loadingDraft}
            className="flex-1 py-2 bg-red-600 hover:bg-red-700 disabled:bg-gray-600 rounded flex items-center justify-center gap-2"
          >
            {uploading ? (
              <>
                <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                </svg>
                上传中...
              </>
            ) : (
              <>
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z"/>
                </svg>
                上传到 YouTube
              </>
            )}
          </button>
        </div>
      </div>
    </div>
  );
}

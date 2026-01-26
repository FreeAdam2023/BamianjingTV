"use client";

/**
 * ExportPanel - Modal for export settings and thumbnail generation
 */

import { useState, useEffect } from "react";
import type { ExportProfile, ExportRequest, Timeline, TitleCandidate } from "@/lib/types";
import { generateThumbnail, generateTitleCandidates, formatDuration } from "@/lib/api";

interface ExportPanelProps {
  timeline: Timeline;
  coverFrameUrl: string | null;
  coverFrameTime: number | null;
  onClose: () => void;
  onExport: (request: ExportRequest) => Promise<unknown>;
}

export default function ExportPanel({
  timeline,
  coverFrameUrl,
  coverFrameTime,
  onClose,
  onExport,
}: ExportPanelProps) {
  const [exportProfile, setExportProfile] = useState<ExportProfile>("full");
  const [useTraditional, setUseTraditional] = useState(true);
  const [exporting, setExporting] = useState(false);

  // YouTube upload options
  const [uploadToYouTube, setUploadToYouTube] = useState(false);
  const [youtubeTitle, setYoutubeTitle] = useState("");
  const [youtubeDescription, setYoutubeDescription] = useState("");
  const [youtubeTags, setYoutubeTags] = useState("");
  const [youtubePrivacy, setYoutubePrivacy] = useState<"private" | "unlisted" | "public">("private");

  // Title candidates
  const [titleCandidates, setTitleCandidates] = useState<TitleCandidate[]>([]);
  const [selectedTitle, setSelectedTitle] = useState<TitleCandidate | null>(null);
  const [loadingTitles, setLoadingTitles] = useState(false);
  const [titleInstruction, setTitleInstruction] = useState("");

  // Thumbnail generation
  const [thumbnailUrl, setThumbnailUrl] = useState<string | null>(null);
  const [generatingThumbnail, setGeneratingThumbnail] = useState(false);
  const [showOriginal, setShowOriginal] = useState(false);

  // ESC key to close
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [onClose]);

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

      await onExport(request);
      const message = uploadToYouTube
        ? "Export started with YouTube upload! Check back later."
        : "Export started! Check back later for the output files.";
      alert(message);
      onClose();
    } catch (err) {
      alert("Export failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setExporting(false);
    }
  };

  const getBaseUrl = () => {
    const { protocol, hostname } = window.location;
    return `${protocol}//${hostname}:8000`;
  };

  const handleGenerateTitles = async () => {
    setLoadingTitles(true);
    try {
      const result = await generateTitleCandidates(
        timeline.timeline_id,
        titleInstruction || undefined,
        5
      );
      setTitleCandidates(result.candidates);
      setSelectedTitle(null);
    } catch (err) {
      alert("Failed to generate titles: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setLoadingTitles(false);
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
      alert("Thumbnail generation failed: " + (err instanceof Error ? err.message : "Unknown error"));
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

              <div>
                <label className="block text-sm text-gray-400 mb-1">Description (optional)</label>
                <textarea
                  value={youtubeDescription}
                  onChange={(e) => setYoutubeDescription(e.target.value)}
                  placeholder={`Original: ${timeline?.source_url}`}
                  rows={3}
                  className="w-full bg-gray-700 rounded px-3 py-2 text-sm resize-none"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Tags (comma-separated)</label>
                <input
                  type="text"
                  value={youtubeTags}
                  onChange={(e) => setYoutubeTags(e.target.value)}
                  placeholder="learning, english, chinese"
                  className="w-full bg-gray-700 rounded px-3 py-2 text-sm"
                />
              </div>

              <div>
                <label className="block text-sm text-gray-400 mb-1">Privacy</label>
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
            {coverFrameTime !== null && (
              <span className="text-sm text-purple-400">
                Cover @ {formatDuration(coverFrameTime)}
              </span>
            )}
          </div>

          {/* Title Generation Section */}
          <div className="mb-4 p-3 bg-gray-900 rounded-lg">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-gray-300">Thumbnail Titles</span>
              <button
                onClick={handleGenerateTitles}
                disabled={loadingTitles}
                className="px-3 py-1 text-xs bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 rounded flex items-center gap-1"
              >
                {loadingTitles ? (
                  <>
                    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                    </svg>
                    Generating...
                  </>
                ) : titleCandidates.length > 0 ? (
                  "Regenerate"
                ) : (
                  "Generate 5 Titles"
                )}
              </button>
            </div>

            {/* Instruction Input */}
            <div className="mb-3">
              <input
                type="text"
                value={titleInstruction}
                onChange={(e) => setTitleInstruction(e.target.value)}
                placeholder="Tell AI how to generate titles (e.g., 'focus on conflict', 'more dramatic')..."
                className="w-full bg-gray-800 border border-gray-700 rounded px-3 py-2 text-sm placeholder-gray-500"
              />
            </div>

            {/* Title Candidates */}
            {titleCandidates.length > 0 && (
              <div className="space-y-2 max-h-48 overflow-y-auto">
                {titleCandidates.map((candidate) => (
                  <button
                    key={candidate.index}
                    onClick={() => setSelectedTitle(candidate)}
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

            {titleCandidates.length === 0 && !loadingTitles && (
              <p className="text-xs text-gray-500 text-center py-2">
                Click "Generate 5 Titles" to get AI suggestions
              </p>
            )}

            {selectedTitle && (
              <div className="mt-2 p-2 bg-purple-900/30 rounded text-sm">
                <span className="text-purple-400">Selected:</span>
                <span className="text-yellow-400 ml-2">{selectedTitle.main}</span>
                <span className="text-gray-400 mx-1">/</span>
                <span className="text-white">{selectedTitle.sub}</span>
              </div>
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
              ? "Using selected title"
              : "AI will generate title automatically"}
          </p>
        </div>

        {/* Buttons */}
        <div className="flex gap-4 mt-6">
          <button
            onClick={onClose}
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
  );
}

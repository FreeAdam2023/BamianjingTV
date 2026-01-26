"use client";

/**
 * ExportPanel - Modal for export settings and thumbnail generation
 */

import { useState } from "react";
import type { ExportProfile, ExportRequest, Timeline, ThumbnailCandidate } from "@/lib/types";
import { generateThumbnail, generateThumbnailCandidates } from "@/lib/api";

interface ExportPanelProps {
  timeline: Timeline;
  onClose: () => void;
  onExport: (request: ExportRequest) => Promise<unknown>;
}

export default function ExportPanel({ timeline, onClose, onExport }: ExportPanelProps) {
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

  // Candidate screenshots
  const [candidates, setCandidates] = useState<ThumbnailCandidate[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState(false);
  const [selectedCandidateIndex, setSelectedCandidateIndex] = useState<number | null>(null);
  const [customTimestamp, setCustomTimestamp] = useState<string>("");

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

  const handleLoadCandidates = async () => {
    setLoadingCandidates(true);
    try {
      const result = await generateThumbnailCandidates(timeline.timeline_id);
      setCandidates(result.candidates);
      setSelectedCandidateIndex(null);
      setCustomTimestamp("");
    } catch (err) {
      alert("Failed to load candidates: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setLoadingCandidates(false);
    }
  };

  const handleGenerateThumbnail = async () => {
    setGeneratingThumbnail(true);
    try {
      // Determine request parameters
      const request: { timestamp?: number; candidate_index?: number } = {};

      if (selectedCandidateIndex !== null) {
        request.candidate_index = selectedCandidateIndex;
      } else if (customTimestamp) {
        const ts = parseFloat(customTimestamp);
        if (!isNaN(ts) && ts >= 0 && ts <= timeline.source_duration) {
          request.timestamp = ts;
        }
      }
      // If nothing selected, backend will auto-analyze

      const result = await generateThumbnail(timeline.timeline_id, Object.keys(request).length > 0 ? request : undefined);
      setThumbnailUrl(`${getBaseUrl()}${result.thumbnail_url}`);
    } catch (err) {
      alert("Thumbnail generation failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setGeneratingThumbnail(false);
    }
  };

  const formatTime = (seconds: number) => {
    const m = Math.floor(seconds / 60);
    const s = Math.floor(seconds % 60);
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-[480px] max-h-[90vh] overflow-y-auto">
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
            <button
              onClick={handleLoadCandidates}
              disabled={loadingCandidates}
              className="px-3 py-1 text-sm bg-indigo-600 hover:bg-indigo-700 disabled:bg-gray-600 rounded flex items-center gap-2"
            >
              {loadingCandidates ? (
                <>
                  <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                    <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                    <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                  </svg>
                  Loading...
                </>
              ) : candidates.length > 0 ? (
                "Refresh Candidates"
              ) : (
                "Load Screenshot Candidates"
              )}
            </button>
          </div>

          {/* Candidate Grid */}
          {candidates.length > 0 && (
            <div className="mb-4">
              <p className="text-xs text-gray-400 mb-2">Select a screenshot as base:</p>
              <div className="grid grid-cols-3 gap-2">
                {candidates.map((c) => (
                  <button
                    key={c.index}
                    onClick={() => {
                      setSelectedCandidateIndex(c.index);
                      setCustomTimestamp("");
                    }}
                    className={`relative rounded overflow-hidden border-2 transition-colors ${
                      selectedCandidateIndex === c.index
                        ? "border-purple-500"
                        : "border-transparent hover:border-gray-500"
                    }`}
                  >
                    <img
                      src={`${getBaseUrl()}${c.url}`}
                      alt={`Candidate ${c.index}`}
                      className="w-full aspect-video object-cover"
                    />
                    <span className="absolute bottom-0 left-0 right-0 bg-black/70 text-xs text-center py-0.5">
                      {formatTime(c.timestamp)}
                    </span>
                    {selectedCandidateIndex === c.index && (
                      <div className="absolute inset-0 bg-purple-500/20 flex items-center justify-center">
                        <svg className="w-8 h-8 text-purple-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                        </svg>
                      </div>
                    )}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Custom Timestamp Input */}
          <div className="mb-4">
            <label className="block text-xs text-gray-400 mb-1">
              Or enter custom timestamp (seconds):
            </label>
            <div className="flex gap-2">
              <input
                type="number"
                value={customTimestamp}
                onChange={(e) => {
                  setCustomTimestamp(e.target.value);
                  setSelectedCandidateIndex(null);
                }}
                placeholder={`0 - ${Math.floor(timeline.source_duration)}`}
                min={0}
                max={timeline.source_duration}
                step={0.1}
                className="flex-1 bg-gray-700 rounded px-3 py-2 text-sm"
              />
              <span className="text-xs text-gray-500 self-center">
                / {formatTime(timeline.source_duration)}
              </span>
            </div>
          </div>

          {/* Generate Button */}
          <div className="flex items-center gap-2 mb-3">
            <button
              onClick={handleGenerateThumbnail}
              disabled={generatingThumbnail}
              className="flex-1 px-3 py-2 text-sm bg-purple-600 hover:bg-purple-700 disabled:bg-gray-600 rounded flex items-center justify-center gap-2"
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
                "Regenerate with Selection"
              ) : (
                "Generate Thumbnail"
              )}
            </button>
            {selectedCandidateIndex !== null && (
              <span className="text-xs text-purple-400">Using candidate #{selectedCandidateIndex}</span>
            )}
            {customTimestamp && !selectedCandidateIndex && (
              <span className="text-xs text-purple-400">Using {customTimestamp}s</span>
            )}
            {!selectedCandidateIndex && !customTimestamp && (
              <span className="text-xs text-gray-500">AI auto-select</span>
            )}
          </div>

          <p className="text-xs text-gray-500 mb-3">
            Large Chinese text overlay added automatically
          </p>

          {/* Generated Thumbnail Preview */}
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
            <div className="border-2 border-dashed border-gray-600 rounded-lg aspect-video flex items-center justify-center text-gray-500 text-sm">
              {candidates.length > 0
                ? "Select a candidate or enter timestamp, then click Generate"
                : "Load candidates or click Generate for AI auto-selection"}
            </div>
          )}
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

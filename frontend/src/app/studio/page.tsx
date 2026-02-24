"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import PageHeader from "@/components/ui/PageHeader";
import {
  createLofiSession,
  listLofiSessions,
  getLofiSession,
  updateLofiSession,
  deleteLofiSession,
  startLofiGeneration,
  publishLofiSession,
  regenerateLofiMetadata,
  getLofiAudioUrl,
  getLofiVideoUrl,
  getLofiThumbnailUrl,
  listLofiThemes,
  listLofiImages,
} from "@/lib/api";
import type {
  LofiSession,
  LofiSessionStatus,
  LofiTheme,
  LofiThemeInfo,
  LofiImageInfo,
} from "@/lib/types";

const THEME_LABELS: Record<LofiTheme, string> = {
  lofi_hip_hop: "Lofi Hip Hop",
  jazz: "Jazz",
  ambient: "Ambient",
  chillhop: "Chillhop",
  study: "Study",
  sleep: "Sleep",
  coffee_shop: "Coffee Shop",
  rain: "Rainy Day",
  night: "Late Night",
  piano: "Piano",
  guitar: "Guitar",
};

const STATUS_CONFIG: Record<
  LofiSessionStatus,
  { label: string; color: string; bg: string }
> = {
  pending: { label: "Pending", color: "text-gray-400", bg: "bg-gray-500/20" },
  generating_music: { label: "Generating Music...", color: "text-blue-400", bg: "bg-blue-500/20" },
  mixing_audio: { label: "Mixing Audio...", color: "text-blue-400", bg: "bg-blue-500/20" },
  generating_visuals: { label: "Generating Video...", color: "text-purple-400", bg: "bg-purple-500/20" },
  compositing: { label: "Compositing...", color: "text-purple-400", bg: "bg-purple-500/20" },
  generating_thumbnail: { label: "Generating Thumbnail...", color: "text-cyan-400", bg: "bg-cyan-500/20" },
  generating_metadata: { label: "Generating Metadata...", color: "text-cyan-400", bg: "bg-cyan-500/20" },
  awaiting_review: { label: "Ready for Review", color: "text-yellow-400", bg: "bg-yellow-500/20" },
  publishing: { label: "Publishing...", color: "text-orange-400", bg: "bg-orange-500/20" },
  published: { label: "Published", color: "text-green-400", bg: "bg-green-500/20" },
  failed: { label: "Failed", color: "text-red-400", bg: "bg-red-500/20" },
  cancelled: { label: "Cancelled", color: "text-gray-400", bg: "bg-gray-500/20" },
};

const AMBIENT_OPTIONS = [
  { value: "rain", label: "Rain" },
  { value: "fireplace", label: "Fireplace" },
  { value: "birds", label: "Birds" },
  { value: "thunder", label: "Thunder" },
  { value: "wind", label: "Wind" },
  { value: "ocean", label: "Ocean" },
  { value: "cafe", label: "Cafe" },
  { value: "vinyl_crackle", label: "Vinyl Crackle" },
];

type FilterStatus = "all" | "generating" | "awaiting_review" | "published";

function formatDuration(seconds: number): string {
  const h = Math.floor(seconds / 3600);
  const m = Math.floor((seconds % 3600) / 60);
  if (h > 0) return `${h}h ${m > 0 ? `${m}m` : ""}`.trim();
  return `${m}m`;
}

function isGenerating(status: LofiSessionStatus): boolean {
  return [
    "generating_music",
    "mixing_audio",
    "generating_visuals",
    "compositing",
    "generating_thumbnail",
    "generating_metadata",
    "publishing",
  ].includes(status);
}

export default function StudioPage() {
  const [sessions, setSessions] = useState<LofiSession[]>([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterStatus>("all");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [themes, setThemes] = useState<LofiThemeInfo[]>([]);
  const [images, setImages] = useState<LofiImageInfo[]>([]);

  // Create form state
  const [createTheme, setCreateTheme] = useState<LofiTheme>("lofi_hip_hop");
  const [createDuration, setCreateDuration] = useState(3600);
  const [createModelSize, setCreateModelSize] = useState("medium");
  const [createAmbient, setCreateAmbient] = useState<string[]>([]);
  const [createImage, setCreateImage] = useState<string>("");
  const [creating, setCreating] = useState(false);

  // Review form state
  const [editTitle, setEditTitle] = useState("");
  const [editDescription, setEditDescription] = useState("");
  const [editTags, setEditTags] = useState<string[]>([]);
  const [editPrivacy, setEditPrivacy] = useState("private");
  const [newTag, setNewTag] = useState("");
  const [saving, setSaving] = useState(false);

  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Auto-dismiss error
  useEffect(() => {
    if (!error) return;
    const t = setTimeout(() => setError(null), 5000);
    return () => clearTimeout(t);
  }, [error]);

  const loadSessions = useCallback(async () => {
    try {
      const data = await listLofiSessions();
      setSessions(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load sessions");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadSessions();
    listLofiThemes().then(setThemes).catch(() => {});
    listLofiImages().then(setImages).catch(() => {});
  }, [loadSessions]);

  // Poll for updates when any session is generating
  useEffect(() => {
    const hasGenerating = sessions.some((s) => isGenerating(s.status));
    if (hasGenerating) {
      if (!pollRef.current) {
        pollRef.current = setInterval(loadSessions, 5000);
      }
    } else {
      if (pollRef.current) {
        clearInterval(pollRef.current);
        pollRef.current = null;
      }
    }
    return () => {
      if (pollRef.current) clearInterval(pollRef.current);
    };
  }, [sessions, loadSessions]);

  const selected = sessions.find((s) => s.id === selectedId) || null;

  // Sync review form when selection changes
  useEffect(() => {
    if (selected) {
      setEditTitle(selected.metadata.title);
      setEditDescription(selected.metadata.description);
      setEditTags([...selected.metadata.tags]);
      setEditPrivacy(selected.metadata.privacy_status);
    }
  }, [selected]);

  const filteredSessions = sessions.filter((s) => {
    if (filter === "all") return true;
    if (filter === "generating") return isGenerating(s.status);
    if (filter === "awaiting_review") return s.status === "awaiting_review";
    if (filter === "published") return s.status === "published";
    return true;
  });

  async function handleCreate() {
    setCreating(true);
    try {
      const session = await createLofiSession({
        target_duration: createDuration,
        theme: createTheme,
        model_size: createModelSize,
        ambient_sounds: createAmbient,
        image_path: createImage || undefined,
      });
      // Auto-start generation
      await startLofiGeneration(session.id);
      setShowCreate(false);
      await loadSessions();
      setSelectedId(session.id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to create session");
    } finally {
      setCreating(false);
    }
  }

  async function handleSaveMetadata() {
    if (!selectedId) return;
    setSaving(true);
    try {
      await updateLofiSession(selectedId, {
        title: editTitle,
        description: editDescription,
        tags: editTags,
        privacy_status: editPrivacy,
      });
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save");
    } finally {
      setSaving(false);
    }
  }

  async function handlePublish() {
    if (!selectedId) return;
    await handleSaveMetadata();
    try {
      await publishLofiSession(selectedId);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to publish");
    }
  }

  async function handleRegenerate() {
    if (!selectedId) return;
    try {
      await regenerateLofiMetadata(selectedId);
      // Wait a moment for the background task to complete
      setTimeout(async () => {
        const updated = await getLofiSession(selectedId);
        setSessions((prev) =>
          prev.map((s) => (s.id === updated.id ? updated : s))
        );
        setEditTitle(updated.metadata.title);
        setEditDescription(updated.metadata.description);
        setEditTags([...updated.metadata.tags]);
      }, 3000);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to regenerate");
    }
  }

  async function handleDelete(id: string) {
    try {
      await deleteLofiSession(id);
      if (selectedId === id) setSelectedId(null);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to delete");
    }
  }

  async function handleRetry(id: string) {
    try {
      await startLofiGeneration(id);
      await loadSessions();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to restart");
    }
  }

  function addTag() {
    const tag = newTag.trim();
    if (tag && !editTags.includes(tag)) {
      setEditTags([...editTags, tag]);
      setNewTag("");
    }
  }

  function removeTag(tag: string) {
    setEditTags(editTags.filter((t) => t !== tag));
  }

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="spinner mx-auto mb-4" />
          <p className="text-gray-400">Loading...</p>
        </div>
      </main>
    );
  }

  return (
    <div className="min-h-screen bg-[var(--background)]">
      <PageHeader
        title="Lofi Studio"
        subtitle="AI-powered lofi video factory"
        icon="🎵"
        iconGradient="from-purple-500 to-pink-600"
        backHref="/"
        actions={
          <button
            onClick={() => setShowCreate(true)}
            className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-500 transition-colors"
          >
            + New Session
          </button>
        }
      >
        {/* Filter tabs */}
        <div className="flex gap-2 mt-2">
          {(
            [
              ["all", "All"],
              ["generating", "Generating"],
              ["awaiting_review", "Review"],
              ["published", "Published"],
            ] as [FilterStatus, string][]
          ).map(([key, label]) => (
            <button
              key={key}
              onClick={() => setFilter(key)}
              className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                filter === key
                  ? "bg-purple-600 text-white"
                  : "bg-gray-800 text-gray-400 hover:bg-gray-700"
              }`}
            >
              {label}
              {key === "all" && ` (${sessions.length})`}
              {key === "generating" &&
                ` (${sessions.filter((s) => isGenerating(s.status)).length})`}
              {key === "awaiting_review" &&
                ` (${sessions.filter((s) => s.status === "awaiting_review").length})`}
              {key === "published" &&
                ` (${sessions.filter((s) => s.status === "published").length})`}
            </button>
          ))}
        </div>
      </PageHeader>

      {/* Error banner */}
      {error && (
        <div className="max-w-6xl mx-auto px-6 mt-4">
          <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex justify-between items-center">
            <p className="text-red-400 text-sm">{error}</p>
            <button
              onClick={() => setError(null)}
              className="text-red-400 hover:text-red-300"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        </div>
      )}

      <div className="max-w-6xl mx-auto px-6 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Session Grid */}
          <div className="lg:col-span-2">
            {filteredSessions.length === 0 ? (
              <div className="card text-center py-12">
                <p className="text-gray-500 mb-4">No sessions yet</p>
                <button
                  onClick={() => setShowCreate(true)}
                  className="px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-500"
                >
                  Create your first lofi session
                </button>
              </div>
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {filteredSessions.map((session) => (
                  <SessionCard
                    key={session.id}
                    session={session}
                    isSelected={session.id === selectedId}
                    onClick={() => setSelectedId(session.id)}
                    onDelete={() => handleDelete(session.id)}
                    onRetry={() => handleRetry(session.id)}
                  />
                ))}
              </div>
            )}
          </div>

          {/* Review Panel */}
          <div className="space-y-4">
            {selected ? (
              <>
                {/* Preview */}
                <div className="card">
                  <h3 className="text-sm font-semibold text-gray-400 mb-3">Preview</h3>
                  {selected.final_video_path ? (
                    <video
                      src={getLofiVideoUrl(selected.id)}
                      controls
                      className="w-full rounded-lg"
                    />
                  ) : selected.final_audio_path ? (
                    <audio
                      src={getLofiAudioUrl(selected.id)}
                      controls
                      className="w-full"
                    />
                  ) : (
                    <div className="aspect-video bg-gray-900 rounded-lg flex items-center justify-center">
                      <p className="text-gray-500 text-sm">
                        {isGenerating(selected.status)
                          ? `${STATUS_CONFIG[selected.status].label} (${Math.round(selected.progress)}%)`
                          : "No preview available"}
                      </p>
                    </div>
                  )}

                  {/* Progress bar */}
                  {isGenerating(selected.status) && (
                    <div className="mt-3">
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>{STATUS_CONFIG[selected.status].label}</span>
                        <span>{Math.round(selected.progress)}%</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div
                          className="bg-purple-500 h-2 rounded-full transition-all duration-500"
                          style={{ width: `${selected.progress}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>

                {/* Metadata Editor */}
                {(selected.status === "awaiting_review" ||
                  selected.status === "published") && (
                  <div className="card space-y-3">
                    <h3 className="text-sm font-semibold text-gray-400">Metadata</h3>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Title</label>
                      <input
                        type="text"
                        value={editTitle}
                        onChange={(e) => setEditTitle(e.target.value)}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:border-purple-500 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Description</label>
                      <textarea
                        value={editDescription}
                        onChange={(e) => setEditDescription(e.target.value)}
                        rows={4}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:border-purple-500 focus:outline-none resize-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Tags</label>
                      <div className="flex flex-wrap gap-1 mb-2">
                        {editTags.map((tag) => (
                          <span
                            key={tag}
                            className="inline-flex items-center gap-1 px-2 py-0.5 bg-purple-500/20 text-purple-300 rounded text-xs"
                          >
                            {tag}
                            <button
                              onClick={() => removeTag(tag)}
                              className="hover:text-white"
                            >
                              x
                            </button>
                          </span>
                        ))}
                      </div>
                      <div className="flex gap-1">
                        <input
                          type="text"
                          value={newTag}
                          onChange={(e) => setNewTag(e.target.value)}
                          onKeyDown={(e) => e.key === "Enter" && (e.preventDefault(), addTag())}
                          placeholder="Add tag..."
                          className="flex-1 px-2 py-1 bg-gray-800 border border-gray-700 rounded text-xs text-gray-200 focus:border-purple-500 focus:outline-none"
                        />
                        <button
                          onClick={addTag}
                          className="px-2 py-1 bg-gray-700 text-gray-300 rounded text-xs hover:bg-gray-600"
                        >
                          +
                        </button>
                      </div>
                    </div>
                    <div>
                      <label className="block text-xs text-gray-500 mb-1">Privacy</label>
                      <select
                        value={editPrivacy}
                        onChange={(e) => setEditPrivacy(e.target.value)}
                        className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:border-purple-500 focus:outline-none"
                      >
                        <option value="private">Private</option>
                        <option value="unlisted">Unlisted</option>
                        <option value="public">Public</option>
                      </select>
                    </div>
                    <div className="flex gap-2 pt-2">
                      <button
                        onClick={handleRegenerate}
                        className="flex-1 px-3 py-2 bg-gray-700 text-gray-300 rounded-lg text-xs font-medium hover:bg-gray-600 transition-colors"
                      >
                        Regenerate Metadata
                      </button>
                      <button
                        onClick={handleSaveMetadata}
                        disabled={saving}
                        className="flex-1 px-3 py-2 bg-purple-600 text-white rounded-lg text-xs font-medium hover:bg-purple-500 disabled:opacity-50 transition-colors"
                      >
                        {saving ? "Saving..." : "Save"}
                      </button>
                    </div>
                    {selected.status === "awaiting_review" && (
                      <button
                        onClick={handlePublish}
                        className="w-full px-3 py-2 bg-green-600 text-white rounded-lg text-sm font-medium hover:bg-green-500 transition-colors"
                      >
                        Publish to YouTube
                      </button>
                    )}
                    {selected.youtube_url && (
                      <a
                        href={selected.youtube_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-center text-sm text-blue-400 hover:text-blue-300"
                      >
                        View on YouTube
                      </a>
                    )}
                  </div>
                )}

                {/* Session Info */}
                <div className="card">
                  <h3 className="text-sm font-semibold text-gray-400 mb-3">Session Info</h3>
                  <div className="space-y-2 text-xs">
                    <InfoRow label="ID" value={selected.id} />
                    <InfoRow label="Theme" value={THEME_LABELS[selected.music_config.theme]} />
                    <InfoRow label="Duration" value={formatDuration(selected.target_duration)} />
                    <InfoRow label="Model" value={selected.music_config.model_size} />
                    <InfoRow label="Segments" value={`${selected.music_segments.length}`} />
                    <InfoRow label="Triggered by" value={selected.triggered_by} />
                    {selected.error && (
                      <div className="mt-2 p-2 bg-red-500/10 rounded text-red-400 text-xs">
                        {selected.error}
                      </div>
                    )}
                    {Object.keys(selected.step_timings).length > 0 && (
                      <>
                        <div className="border-t border-gray-700 my-2" />
                        <p className="text-gray-500 font-medium">Timing</p>
                        {Object.entries(selected.step_timings).map(([step, time]) => (
                          <InfoRow key={step} label={step.replace(/_/g, " ")} value={`${time}s`} />
                        ))}
                      </>
                    )}
                  </div>
                </div>
              </>
            ) : (
              <div className="card text-center py-8">
                <p className="text-gray-500 text-sm">Select a session to review</p>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Create Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm">
          <div className="bg-[var(--card)] border border-[var(--border)] rounded-xl w-full max-w-md mx-4 p-6 space-y-4">
            <h2 className="text-lg font-bold">New Lofi Session</h2>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Theme</label>
              <select
                value={createTheme}
                onChange={(e) => setCreateTheme(e.target.value as LofiTheme)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:border-purple-500 focus:outline-none"
              >
                {(themes.length > 0
                  ? themes.map((t) => (
                      <option key={t.value} value={t.value}>
                        {t.label}
                      </option>
                    ))
                  : Object.entries(THEME_LABELS).map(([val, label]) => (
                      <option key={val} value={val}>
                        {label}
                      </option>
                    ))
                )}
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">
                Duration: {formatDuration(createDuration)}
              </label>
              <input
                type="range"
                min={300}
                max={10800}
                step={300}
                value={createDuration}
                onChange={(e) => setCreateDuration(Number(e.target.value))}
                className="w-full accent-purple-500"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>5m</span>
                <span>1h</span>
                <span>2h</span>
                <span>3h</span>
              </div>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Model Size</label>
              <select
                value={createModelSize}
                onChange={(e) => setCreateModelSize(e.target.value)}
                className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:border-purple-500 focus:outline-none"
              >
                <option value="small">Small (faster)</option>
                <option value="medium">Medium (balanced)</option>
                <option value="large">Large (best quality)</option>
              </select>
            </div>

            <div>
              <label className="block text-xs text-gray-500 mb-1">Ambient Sounds</label>
              <div className="flex flex-wrap gap-2">
                {AMBIENT_OPTIONS.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() =>
                      setCreateAmbient((prev) =>
                        prev.includes(opt.value)
                          ? prev.filter((a) => a !== opt.value)
                          : [...prev, opt.value]
                      )
                    }
                    className={`px-3 py-1 rounded-full text-xs font-medium transition-colors ${
                      createAmbient.includes(opt.value)
                        ? "bg-purple-600 text-white"
                        : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {images.length > 0 && (
              <div>
                <label className="block text-xs text-gray-500 mb-1">Background Image</label>
                <select
                  value={createImage}
                  onChange={(e) => setCreateImage(e.target.value)}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg text-sm text-gray-200 focus:border-purple-500 focus:outline-none"
                >
                  <option value="">Default</option>
                  {images.map((img) => (
                    <option key={img.name} value={img.path}>
                      {img.name}
                    </option>
                  ))}
                </select>
              </div>
            )}

            <div className="flex gap-2 pt-2">
              <button
                onClick={() => setShowCreate(false)}
                className="flex-1 px-4 py-2 bg-gray-700 text-gray-300 rounded-lg text-sm font-medium hover:bg-gray-600 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={handleCreate}
                disabled={creating}
                className="flex-1 px-4 py-2 bg-purple-600 text-white rounded-lg text-sm font-medium hover:bg-purple-500 disabled:opacity-50 transition-colors"
              >
                {creating ? "Creating..." : "Generate"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function SessionCard({
  session,
  isSelected,
  onClick,
  onDelete,
  onRetry,
}: {
  session: LofiSession;
  isSelected: boolean;
  onClick: () => void;
  onDelete: () => void;
  onRetry: () => void;
}) {
  const config = STATUS_CONFIG[session.status];

  return (
    <div
      onClick={onClick}
      className={`card cursor-pointer transition-all hover:border-purple-500/50 ${
        isSelected ? "border-purple-500 ring-1 ring-purple-500/30" : ""
      }`}
    >
      {/* Thumbnail or placeholder */}
      <div className="aspect-video bg-gray-900 rounded-lg mb-3 overflow-hidden flex items-center justify-center relative">
        {session.thumbnail_path ? (
          <img
            src={getLofiThumbnailUrl(session.id)}
            alt={session.metadata.title || "Lofi session"}
            className="w-full h-full object-cover"
          />
        ) : (
          <span className="text-4xl">🎵</span>
        )}
        {/* Progress overlay for generating sessions */}
        {isGenerating(session.status) && (
          <div className="absolute bottom-0 left-0 right-0 bg-black/60 px-2 py-1">
            <div className="w-full bg-gray-700 rounded-full h-1.5">
              <div
                className="bg-purple-500 h-1.5 rounded-full transition-all duration-500"
                style={{ width: `${session.progress}%` }}
              />
            </div>
          </div>
        )}
      </div>

      {/* Info */}
      <div className="space-y-1">
        <p className="text-sm font-medium truncate">
          {session.metadata.title || `${THEME_LABELS[session.music_config.theme]} Session`}
        </p>
        <div className="flex items-center justify-between">
          <span
            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${config.bg} ${config.color}`}
          >
            {config.label}
          </span>
          <span className="text-xs text-gray-500">
            {formatDuration(session.target_duration)}
          </span>
        </div>
        <p className="text-xs text-gray-500">
          {THEME_LABELS[session.music_config.theme]}
          {session.music_config.ambient_sounds.length > 0 &&
            ` + ${session.music_config.ambient_sounds.join(", ")}`}
        </p>
      </div>

      {/* Actions */}
      <div className="flex gap-1 mt-2" onClick={(e) => e.stopPropagation()}>
        {session.status === "failed" && (
          <button
            onClick={onRetry}
            className="px-2 py-1 bg-yellow-600/20 text-yellow-400 rounded text-xs hover:bg-yellow-600/30"
          >
            Retry
          </button>
        )}
        <button
          onClick={onDelete}
          className="px-2 py-1 bg-red-600/20 text-red-400 rounded text-xs hover:bg-red-600/30 ml-auto"
        >
          Delete
        </button>
      </div>
    </div>
  );
}

function InfoRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between">
      <span className="text-gray-500">{label}</span>
      <span className="text-gray-300">{value}</span>
    </div>
  );
}

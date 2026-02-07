"use client";

import Link from "next/link";
import { useEffect, useState, useCallback, useRef } from "react";
import {
  generateMusic,
  listMusicTracks,
  getMusicAudioUrl,
  deleteMusicTrack,
} from "@/lib/api";
import type { MusicTrack, MusicModelSize, MusicGenerateRequest } from "@/lib/types";

export default function MusicPage() {
  const [tracks, setTracks] = useState<MusicTrack[]>([]);
  const [loading, setLoading] = useState(true);
  const [generating, setGenerating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Form state
  const [prompt, setPrompt] = useState("");
  const [duration, setDuration] = useState(30);
  const [modelSize, setModelSize] = useState<MusicModelSize>("medium");
  const [title, setTitle] = useState("");

  // Delete confirmation
  const [deleteId, setDeleteId] = useState<string | null>(null);

  // Audio player ref
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [playingId, setPlayingId] = useState<string | null>(null);

  const loadTracks = useCallback(async () => {
    try {
      const data = await listMusicTracks();
      setTracks(data);
    } catch (err) {
      console.error("Failed to load tracks:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadTracks();
  }, [loadTracks]);

  // Auto-refresh while any track is generating
  useEffect(() => {
    const hasGenerating = tracks.some((t) => t.status === "generating");
    if (!hasGenerating) return;

    const interval = setInterval(loadTracks, 5000);
    return () => clearInterval(interval);
  }, [tracks, loadTracks]);

  async function handleGenerate(e: React.FormEvent) {
    e.preventDefault();
    if (!prompt.trim()) return;

    setGenerating(true);
    setError(null);

    try {
      const request: MusicGenerateRequest = {
        prompt: prompt.trim(),
        duration_seconds: duration,
        model_size: modelSize,
        title: title.trim() || undefined,
      };
      await generateMusic(request);
      setPrompt("");
      setTitle("");
      await loadTracks();
    } catch (err) {
      const message = err instanceof Error ? err.message : "Generation failed";
      setError(message);
    } finally {
      setGenerating(false);
    }
  }

  async function handleDelete(trackId: string) {
    try {
      await deleteMusicTrack(trackId);
      if (playingId === trackId) {
        audioRef.current?.pause();
        setPlayingId(null);
      }
      setDeleteId(null);
      await loadTracks();
    } catch (err) {
      console.error("Failed to delete track:", err);
    }
  }

  function handlePlay(trackId: string) {
    if (playingId === trackId) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const audio = new Audio(getMusicAudioUrl(trackId));
    audio.onended = () => setPlayingId(null);
    audio.play();
    audioRef.current = audio;
    setPlayingId(trackId);
  }

  function formatFileSize(bytes: number | null): string {
    if (!bytes) return "-";
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function formatDate(dateStr: string): string {
    return new Date(dateStr).toLocaleString();
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
      {/* Header */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-gray-500 hover:text-gray-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <h1 className="text-xl font-semibold text-gray-100">AI Music</h1>
          </div>
          <div className="text-sm text-gray-500">
            MusicGen - Background music generation
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Generate Section */}
        <div className="card mb-8">
          <h2 className="text-lg font-semibold mb-4">Generate Music</h2>
          <form onSubmit={handleGenerate}>
            <div className="space-y-4">
              {/* Title (optional) */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Title (optional)</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="My background track"
                  className="input"
                  disabled={generating}
                />
              </div>

              {/* Prompt */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">Prompt</label>
                <textarea
                  value={prompt}
                  onChange={(e) => setPrompt(e.target.value)}
                  placeholder="Describe the music you want... e.g. 'upbeat electronic lo-fi hip hop with warm pads and soft drums'"
                  className="input min-h-[80px] resize-y"
                  disabled={generating}
                  rows={3}
                />
              </div>

              {/* Duration + Model Size */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm text-gray-400 mb-1">
                    Duration: {duration}s
                  </label>
                  <input
                    type="range"
                    min={5}
                    max={300}
                    step={5}
                    value={duration}
                    onChange={(e) => setDuration(Number(e.target.value))}
                    className="w-full accent-purple-500"
                    disabled={generating}
                  />
                  <div className="flex justify-between text-xs text-gray-500 mt-1">
                    <span>5s</span>
                    <span>150s</span>
                    <span>300s</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">Model Size</label>
                  <div className="flex gap-2">
                    {(["small", "medium", "large"] as MusicModelSize[]).map((size) => (
                      <button
                        key={size}
                        type="button"
                        onClick={() => setModelSize(size)}
                        disabled={generating}
                        className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                          modelSize === size
                            ? "bg-purple-600 text-white"
                            : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                        }`}
                      >
                        {size.charAt(0).toUpperCase() + size.slice(1)}
                      </button>
                    ))}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {modelSize === "small" && "300M params - Fastest"}
                    {modelSize === "medium" && "1.5B params - Balanced"}
                    {modelSize === "large" && "3.3B params - Best quality"}
                  </div>
                </div>
              </div>

              {/* Error */}
              {error && (
                <div className="p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}

              {/* Submit */}
              <button
                type="submit"
                disabled={generating || !prompt.trim()}
                className="btn btn-primary w-full"
              >
                {generating ? (
                  <span className="flex items-center justify-center gap-2">
                    <span className="spinner" />
                    Starting generation...
                  </span>
                ) : (
                  "Generate Music"
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Track List */}
        <h2 className="text-lg font-semibold mb-4">
          Tracks ({tracks.length})
        </h2>

        {tracks.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">🎵</div>
            <h3 className="text-xl font-medium mb-2">No tracks yet</h3>
            <p className="text-gray-400">Generate your first AI music track above</p>
          </div>
        ) : (
          <div className="space-y-4">
            {tracks.map((track) => (
              <div key={track.id} className="card">
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="font-semibold truncate">
                        {track.title || track.prompt.slice(0, 60)}
                      </h3>
                      {/* Status badge */}
                      {track.status === "generating" && (
                        <span className="badge badge-info animate-pulse flex items-center gap-1">
                          <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24">
                            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                          </svg>
                          Generating
                        </span>
                      )}
                      {track.status === "ready" && (
                        <span className="badge bg-green-600 text-white">Ready</span>
                      )}
                      {track.status === "failed" && (
                        <span className="badge badge-danger" title={track.error || ""}>
                          Failed
                        </span>
                      )}
                      <span className="badge bg-gray-700 text-gray-300 text-xs">
                        {track.model_size}
                      </span>
                    </div>
                    <p className="text-gray-400 text-sm truncate">{track.prompt}</p>
                    <div className="flex items-center gap-4 mt-2 text-xs text-gray-500">
                      <span>{track.duration_seconds}s</span>
                      <span>{formatFileSize(track.file_size_bytes)}</span>
                      <span>{formatDate(track.created_at)}</span>
                    </div>

                    {/* Error message */}
                    {track.status === "failed" && track.error && (
                      <p className="text-red-400 text-xs mt-2">{track.error}</p>
                    )}

                    {/* Audio player */}
                    {track.status === "ready" && (
                      <div className="mt-3">
                        <audio
                          controls
                          src={getMusicAudioUrl(track.id)}
                          className="w-full h-8"
                          preload="none"
                        />
                      </div>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col items-end gap-2 flex-shrink-0">
                    {track.status === "ready" && (
                      <button
                        onClick={() => handlePlay(track.id)}
                        className="btn btn-secondary text-sm py-1.5"
                      >
                        {playingId === track.id ? "Stop" : "Play"}
                      </button>
                    )}
                    {deleteId === track.id ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleDelete(track.id)}
                          className="btn bg-red-600 hover:bg-red-700 text-white text-sm py-1.5 px-3"
                        >
                          Confirm
                        </button>
                        <button
                          onClick={() => setDeleteId(null)}
                          className="btn btn-secondary text-sm py-1.5 px-3"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteId(track.id)}
                        className="text-gray-500 hover:text-red-400 transition-colors"
                        title="Delete track"
                      >
                        <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                        </svg>
                      </button>
                    )}
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

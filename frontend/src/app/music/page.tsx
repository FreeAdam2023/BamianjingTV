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

/** Estimate generation time in seconds based on model size and audio duration. */
function estimateGenerationSeconds(durationSec: number, modelSize: MusicModelSize): number {
  const multiplier = { small: 1.0, medium: 2.5, large: 5.0 }[modelSize];
  const modelLoadOverhead = 15; // first-run model loading
  return Math.round(durationSec * multiplier + modelLoadOverhead);
}

function formatDuration(seconds: number): string {
  if (seconds < 60) return `${seconds}秒`;
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return s > 0 ? `${m}分${s}秒` : `${m}分`;
}

/** Live progress indicator for tracks being generated. */
function GeneratingProgress({
  durationSeconds,
  modelSize,
  createdAt,
}: {
  durationSeconds: number;
  modelSize: MusicModelSize;
  createdAt: string;
}) {
  const estimated = estimateGenerationSeconds(durationSeconds, modelSize);
  const startMs = useRef(new Date(createdAt).getTime()).current;
  const [elapsed, setElapsed] = useState(() =>
    Math.max(0, Math.floor((Date.now() - startMs) / 1000))
  );

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.max(0, Math.floor((Date.now() - startMs) / 1000)));
    }, 1000);
    return () => clearInterval(interval);
  }, [startMs]);

  const progress = Math.min(95, (elapsed / estimated) * 100); // cap at 95%
  const remaining = Math.max(0, estimated - elapsed);

  return (
    <div className="mt-2">
      {/* Progress bar */}
      <div className="w-full h-1.5 bg-gray-700 rounded-full overflow-hidden">
        <div
          className="h-full bg-blue-500 rounded-full transition-all duration-1000"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="flex justify-between text-xs text-gray-500 mt-1">
        <span>已用时 {formatDuration(elapsed)}</span>
        <span>
          {remaining > 0
            ? `预计剩余 ${formatDuration(remaining)}`
            : "即将完成..."}
        </span>
      </div>
    </div>
  );
}

const MUSIC_PRESETS: { category: string; tags: { label: string; prompt: string }[] }[] = [
  {
    category: "风格",
    tags: [
      { label: "Lo-fi", prompt: "lo-fi hip hop" },
      { label: "Electronic", prompt: "electronic" },
      { label: "Jazz", prompt: "jazz" },
      { label: "Classical", prompt: "classical orchestral" },
      { label: "Ambient", prompt: "ambient" },
      { label: "Rock", prompt: "rock" },
      { label: "Pop", prompt: "pop" },
      { label: "Cinematic", prompt: "cinematic film score" },
    ],
  },
  {
    category: "情绪",
    tags: [
      { label: "Upbeat", prompt: "upbeat energetic" },
      { label: "Relaxing", prompt: "relaxing calm" },
      { label: "Melancholy", prompt: "melancholy emotional" },
      { label: "Epic", prompt: "epic dramatic" },
      { label: "Cheerful", prompt: "cheerful happy" },
      { label: "Dark", prompt: "dark mysterious" },
    ],
  },
  {
    category: "乐器",
    tags: [
      { label: "Piano", prompt: "piano" },
      { label: "Guitar", prompt: "acoustic guitar" },
      { label: "Synth", prompt: "synthesizer pads" },
      { label: "Strings", prompt: "string ensemble" },
      { label: "Drums", prompt: "soft drums" },
    ],
  },
  {
    category: "场景",
    tags: [
      { label: "Study", prompt: "study music background" },
      { label: "Travel", prompt: "travel adventure" },
      { label: "Night", prompt: "late night chill" },
      { label: "Workout", prompt: "workout high energy" },
    ],
  },
  {
    category: "自然声音",
    tags: [
      { label: "Rain", prompt: "rain falling gentle rainfall" },
      { label: "Thunder", prompt: "thunderstorm distant thunder rain" },
      { label: "Ocean", prompt: "ocean waves crashing on shore" },
      { label: "Stream", prompt: "flowing stream babbling brook water" },
      { label: "Wind", prompt: "wind blowing through trees" },
      { label: "Birds", prompt: "birds singing birdsong morning" },
      { label: "Cicadas", prompt: "cicadas buzzing summer night" },
      { label: "Crickets", prompt: "crickets chirping night" },
      { label: "Frogs", prompt: "frogs croaking pond night" },
      { label: "Fireplace", prompt: "crackling fireplace warm fire" },
      { label: "Snow", prompt: "gentle snowfall winter wind quiet" },
      { label: "Forest", prompt: "forest ambience birds leaves rustling" },
      { label: "Waterfall", prompt: "waterfall cascading water" },
      { label: "Waves", prompt: "gentle waves lapping beach shore" },
      { label: "Whale", prompt: "whale sounds deep ocean" },
    ],
  },
];

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

  // Playlist controls
  const [shuffle, setShuffle] = useState(false);
  const [loopMode, setLoopMode] = useState<"off" | "one" | "all">("off");

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

  // Refs for shuffle/loop so onended callback always sees latest values
  const shuffleRef = useRef(shuffle);
  shuffleRef.current = shuffle;
  const loopModeRef = useRef(loopMode);
  loopModeRef.current = loopMode;
  const tracksRef = useRef(tracks);
  tracksRef.current = tracks;

  const playTrack = useCallback((trackId: string) => {
    if (audioRef.current) {
      audioRef.current.pause();
    }
    const audio = new Audio(getMusicAudioUrl(trackId));
    audio.onended = () => {
      const readyTracks = tracksRef.current.filter((t) => t.status === "ready");
      const currentIdx = readyTracks.findIndex((t) => t.id === trackId);

      // Loop one: replay same track
      if (loopModeRef.current === "one") {
        audio.currentTime = 0;
        audio.play();
        return;
      }

      // Determine next track
      let nextTrack: MusicTrack | undefined;
      if (shuffleRef.current) {
        const others = readyTracks.filter((t) => t.id !== trackId);
        if (others.length > 0) {
          nextTrack = others[Math.floor(Math.random() * others.length)];
        } else if (loopModeRef.current === "all") {
          nextTrack = readyTracks[0]; // only one track, replay it
        }
      } else {
        const nextIdx = currentIdx + 1;
        if (nextIdx < readyTracks.length) {
          nextTrack = readyTracks[nextIdx];
        } else if (loopModeRef.current === "all" && readyTracks.length > 0) {
          nextTrack = readyTracks[0]; // wrap around
        }
      }

      if (nextTrack) {
        playTrack(nextTrack.id);
      } else {
        setPlayingId(null);
      }
    };
    audio.play();
    audioRef.current = audio;
    setPlayingId(trackId);
  }, []);

  function handlePlay(trackId: string) {
    if (playingId === trackId) {
      audioRef.current?.pause();
      setPlayingId(null);
      return;
    }
    playTrack(trackId);
  }

  function handlePrev() {
    const readyTracks = tracks.filter((t) => t.status === "ready");
    if (readyTracks.length === 0) return;
    const currentIdx = readyTracks.findIndex((t) => t.id === playingId);
    const prevIdx = currentIdx <= 0 ? readyTracks.length - 1 : currentIdx - 1;
    playTrack(readyTracks[prevIdx].id);
  }

  function handleNext() {
    const readyTracks = tracks.filter((t) => t.status === "ready");
    if (readyTracks.length === 0) return;
    const currentIdx = readyTracks.findIndex((t) => t.id === playingId);
    if (shuffle) {
      const others = readyTracks.filter((t) => t.id !== playingId);
      if (others.length > 0) {
        playTrack(others[Math.floor(Math.random() * others.length)].id);
      }
    } else {
      const nextIdx = (currentIdx + 1) % readyTracks.length;
      playTrack(readyTracks[nextIdx].id);
    }
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
          <p className="text-gray-400">加载中...</p>
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
            <h1 className="text-xl font-semibold text-gray-100">AI 音乐</h1>
          </div>
          <div className="text-sm text-gray-500">
            MusicGen · AI 背景音乐生成
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Generate Section */}
        <div className="card mb-8">
          <h2 className="text-lg font-semibold mb-4">生成音乐</h2>
          <form onSubmit={handleGenerate}>
            <div className="space-y-4">
              {/* Title (optional) */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">标题（可选）</label>
                <input
                  type="text"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                  placeholder="我的背景音乐"
                  className="input"
                  disabled={generating}
                />
              </div>

              {/* Prompt */}
              <div>
                <label className="block text-sm text-gray-400 mb-1">提示词 <span className="text-gray-600">（英文效果更佳，点击标签快速插入）</span></label>
                {/* Preset tags */}
                <div className="flex flex-wrap gap-3 mb-2">
                  {MUSIC_PRESETS.map((group) => (
                    <div key={group.category} className="flex items-center gap-1.5 flex-wrap">
                      <span className="text-xs text-gray-500 mr-0.5">{group.category}</span>
                      {group.tags.map((tag) => (
                        <button
                          key={tag.label}
                          type="button"
                          onClick={() => {
                            setPrompt((prev) =>
                              prev ? `${prev}, ${tag.prompt}` : tag.prompt
                            );
                          }}
                          disabled={generating}
                          className="px-2.5 py-1 text-xs rounded-full bg-purple-500/15 text-purple-300
                                     hover:bg-purple-500/30 border border-purple-500/20
                                     transition-colors disabled:opacity-50"
                        >
                          {tag.label}
                        </button>
                      ))}
                    </div>
                  ))}
                </div>
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
                    时长：{duration}秒
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
                    <span>5秒</span>
                    <span>150秒</span>
                    <span>300秒</span>
                  </div>
                </div>

                <div>
                  <label className="block text-sm text-gray-400 mb-1">模型大小</label>
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
                        {{ small: "小", medium: "中", large: "大" }[size]}
                      </button>
                    ))}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">
                    {modelSize === "small" && "3亿参数 · 最快"}
                    {modelSize === "medium" && "15亿参数 · 均衡"}
                    {modelSize === "large" && "33亿参数 · 最佳音质"}
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
                    正在提交...
                  </span>
                ) : (
                  `生成音乐（预计 ${formatDuration(estimateGenerationSeconds(duration, modelSize))}）`
                )}
              </button>
            </div>
          </form>
        </div>

        {/* Track List Header + Playlist Controls */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">
            曲目列表（{tracks.length}）
          </h2>
          {tracks.some((t) => t.status === "ready") && (
            <div className="flex items-center gap-1">
              {/* Prev */}
              <button
                onClick={handlePrev}
                disabled={!playingId}
                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors disabled:opacity-30"
                title="上一曲"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 6h2v12H6zm3.5 6l8.5 6V6z" />
                </svg>
              </button>
              {/* Play/Pause current */}
              <button
                onClick={() => {
                  if (playingId) {
                    audioRef.current?.pause();
                    setPlayingId(null);
                  } else {
                    const first = tracks.find((t) => t.status === "ready");
                    if (first) playTrack(first.id);
                  }
                }}
                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors"
                title={playingId ? "暂停" : "播放"}
              >
                {playingId ? (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z" />
                  </svg>
                ) : (
                  <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
                    <path d="M8 5v14l11-7z" />
                  </svg>
                )}
              </button>
              {/* Next */}
              <button
                onClick={handleNext}
                disabled={!playingId}
                className="p-2 rounded-lg text-gray-400 hover:text-white hover:bg-gray-800 transition-colors disabled:opacity-30"
                title="下一曲"
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M6 18l8.5-6L6 6v12zM16 6v12h2V6h-2z" />
                </svg>
              </button>

              <div className="w-px h-5 bg-gray-700 mx-1" />

              {/* Shuffle */}
              <button
                onClick={() => setShuffle((s) => !s)}
                className={`p-2 rounded-lg transition-colors ${
                  shuffle
                    ? "text-purple-400 bg-purple-500/15"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
                title={shuffle ? "随机播放：开" : "随机播放：关"}
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M10.59 9.17L5.41 4 4 5.41l5.17 5.17 1.42-1.41zM14.5 4l2.04 2.04L4 18.59 5.41 20 17.96 7.46 20 9.5V4h-5.5zm.33 9.41l-1.41 1.41 3.13 3.13L14.5 20H20v-5.5l-2.04 2.04-3.13-3.13z" />
                </svg>
              </button>
              {/* Loop */}
              <button
                onClick={() =>
                  setLoopMode((m) =>
                    m === "off" ? "all" : m === "all" ? "one" : "off"
                  )
                }
                className={`p-2 rounded-lg transition-colors relative ${
                  loopMode !== "off"
                    ? "text-purple-400 bg-purple-500/15"
                    : "text-gray-400 hover:text-white hover:bg-gray-800"
                }`}
                title={
                  loopMode === "off"
                    ? "循环：关"
                    : loopMode === "all"
                    ? "循环：全部"
                    : "循环：单曲"
                }
              >
                <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                  <path d="M7 7h10v3l4-4-4-4v3H5v6h2V7zm10 10H7v-3l-4 4 4 4v-3h12v-6h-2v4z" />
                </svg>
                {loopMode === "one" && (
                  <span className="absolute -top-0.5 -right-0.5 text-[9px] font-bold text-purple-400">
                    1
                  </span>
                )}
              </button>
            </div>
          )}
        </div>

        {tracks.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">🎵</div>
            <h3 className="text-xl font-medium mb-2">暂无曲目</h3>
            <p className="text-gray-400">在上方生成你的第一首 AI 音乐</p>
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
                          生成中
                        </span>
                      )}
                      {track.status === "ready" && (
                        <span className="badge bg-green-600 text-white">就绪</span>
                      )}
                      {track.status === "failed" && (
                        <span className="badge badge-danger" title={track.error || ""}>
                          失败
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

                    {/* Generation progress */}
                    {track.status === "generating" && (
                      <GeneratingProgress
                        durationSeconds={track.duration_seconds}
                        modelSize={track.model_size}
                        createdAt={track.created_at}
                      />
                    )}

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
                        {playingId === track.id ? "停止" : "播放"}
                      </button>
                    )}
                    {deleteId === track.id ? (
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleDelete(track.id)}
                          className="btn bg-red-600 hover:bg-red-700 text-white text-sm py-1.5 px-3"
                        >
                          确认删除
                        </button>
                        <button
                          onClick={() => setDeleteId(null)}
                          className="btn btn-secondary text-sm py-1.5 px-3"
                        >
                          取消
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteId(track.id)}
                        className="text-gray-500 hover:text-red-400 transition-colors"
                        title="删除曲目"
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

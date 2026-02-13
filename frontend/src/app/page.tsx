"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { listTimelines, listJobs, getStats, formatDuration, createJob, createJobWithUpload, updateTimelineTitle } from "@/lib/api";
import type { TimelineSummary, Job, JobCreate, WhisperModel } from "@/lib/types";
import type { UploadProgress } from "@/lib/api";

type VideoMode = "watching" | "dubbing";

const SOURCE_LANGUAGES = [
  { value: "en", label: "English" },
  { value: "zh", label: "中文" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
] as const;

const TARGET_LANGUAGES = [
  { value: "zh-CN", label: "简体中文" },
  { value: "zh-TW", label: "繁體中文" },
  { value: "en", label: "English" },
  { value: "ja", label: "日本語" },
  { value: "ko", label: "한국어" },
  { value: "es", label: "Español" },
  { value: "fr", label: "Français" },
  { value: "de", label: "Deutsch" },
] as const;

export default function Home() {
  const [timelines, setTimelines] = useState<TimelineSummary[]>([]);
  const [processingJobs, setProcessingJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  // Add Video Modal state
  const [showModal, setShowModal] = useState(false);
  const [videoMode, setVideoMode] = useState<VideoMode>("watching");
  const [inputMode, setInputMode] = useState<"url" | "upload">("url");
  const [newUrl, setNewUrl] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sourceLanguage, setSourceLanguage] = useState("en");
  const [targetLanguage, setTargetLanguage] = useState("zh-CN");
  const [enableDiarization, setEnableDiarization] = useState(false);
  const [whisperModel, setWhisperModel] = useState<WhisperModel>("large-v3");

  const loadData = useCallback(async () => {
    try {
      const [timelinesData, statsData, jobsData] = await Promise.all([
        listTimelines(false, true, 10),
        getStats(),
        listJobs(undefined, 50),
      ]);
      setTimelines(timelinesData);
      setStats(statsData);

      // Filter jobs that are currently processing
      const processingStatuses = ['pending', 'downloading', 'transcribing', 'diarizing', 'translating', 'exporting'];
      const processing = jobsData.filter(job => processingStatuses.includes(job.status));
      setProcessingJobs(processing);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

  function openModal() {
    setVideoMode("watching");
    setInputMode("url");
    setNewUrl("");
    setUploadFile(null);
    setUploadProgress(null);
    setError(null);
    setSourceLanguage("en");
    setTargetLanguage("zh-CN");
    setEnableDiarization(false);
    setWhisperModel("large-v3");
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setNewUrl("");
    setUploadFile(null);
    setUploadProgress(null);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    if (inputMode === "url" && !newUrl.trim()) return;
    if (inputMode === "upload" && !uploadFile) return;

    setSubmitting(true);
    setError(null);
    setUploadProgress(null);

    try {
      const effectiveTargetLang = videoMode === "dubbing" ? targetLanguage : "zh-CN";

      const jobOptions: Partial<JobCreate> = {
        mode: videoMode,
        target_language: effectiveTargetLang,
        skip_diarization: !enableDiarization,
        whisper_model: whisperModel,
      };

      if (inputMode === "url") {
        await createJob({
          url: newUrl.trim(),
          ...jobOptions,
        } as JobCreate);
      } else {
        await createJobWithUpload(
          {
            file: uploadFile!,
            mode: videoMode,
            target_language: effectiveTargetLang,
            skip_diarization: !enableDiarization,
            whisper_model: whisperModel,
          },
          (progress) => setUploadProgress(progress)
        );
      }
      closeModal();
      loadData();
    } catch (err) {
      console.error("Failed to create job:", err);
      const message = err instanceof Error ? err.message : "Failed to create job";
      setError(message);
    } finally {
      setSubmitting(false);
      setUploadProgress(null);
    }
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "downloading":
        return <span className="badge badge-info animate-pulse">Downloading...</span>;
      case "transcribing":
        return <span className="badge badge-info animate-pulse">Transcribing...</span>;
      case "diarizing":
        return <span className="badge badge-info animate-pulse">Diarizing...</span>;
      case "translating":
        return <span className="badge badge-info animate-pulse">Translating...</span>;
      case "exporting":
        return <span className="badge badge-info animate-pulse">Exporting...</span>;
      case "pending":
        return <span className="badge badge-warning">Pending</span>;
      default:
        return <span className="badge badge-info">{status}</span>;
    }
  }

  function getModeBadge(mode: string | undefined) {
    switch (mode) {
      case "watching":
        return <span className="badge bg-purple-600 text-white text-xs">Watch</span>;
      case "dubbing":
        return <span className="badge bg-orange-600 text-white text-xs">Dub</span>;
      default:
        return <span className="badge bg-purple-600 text-white text-xs">Watch</span>;
    }
  }

  function getExportStatusBadge(timeline: TimelineSummary) {
    switch (timeline.export_status) {
      case "exporting":
        return (
          <span className="badge badge-info animate-pulse flex items-center gap-1">
            <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Exporting {Math.round(timeline.export_progress)}%
          </span>
        );
      case "uploading":
        return (
          <span className="badge bg-purple-600 text-white animate-pulse flex items-center gap-1">
            <svg className="w-3 h-3 animate-spin" viewBox="0 0 24 24">
              <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
              <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
            </svg>
            Uploading {Math.round(timeline.export_progress)}%
          </span>
        );
      case "completed":
        return (
          <span className="badge bg-green-600 text-white flex items-center gap-1">
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
            </svg>
            Exported
          </span>
        );
      case "failed":
        return (
          <span className="badge badge-danger flex items-center gap-1" title={timeline.export_message || ""}>
            <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
            Export Failed
          </span>
        );
      default:
        return null;
    }
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
    <main className="min-h-screen">
      {/* Header */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center text-xl">
              🧠
            </div>
            <div>
              <h1 className="text-xl font-bold">SceneMind</h1>
              <p className="text-xs text-gray-500">Watch & Learn</p>
            </div>
          </div>
          <div className="flex items-center gap-3">
            <Link
              href="/channels"
              className="btn btn-secondary flex items-center gap-2"
              title="Manage publishing channels"
            >
              <svg className="w-4 h-4" fill="currentColor" viewBox="0 0 24 24">
                <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z" />
              </svg>
              Channels
            </Link>
            <Link
              href="/music"
              className="btn btn-secondary flex items-center gap-2"
              title="AI Music Generation"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3" />
              </svg>
              AI Music
            </Link>
            <Link
              href="/studio"
              className="btn btn-secondary flex items-center gap-2"
              title="Virtual Studio"
            >
              <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 10l4.553-2.276A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14M5 18h8a2 2 0 002-2V8a2 2 0 00-2-2H5a2 2 0 00-2 2v8a2 2 0 002 2z" />
              </svg>
              Studio
            </Link>
            <Link
              href="/jobs"
              className="btn btn-secondary"
              title="View all jobs"
            >
              Jobs
            </Link>
            <button onClick={openModal} className="btn btn-primary">
              + Add Video
            </button>
          </div>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8 animate-fade-in">
            <div className="stat-card">
              <div className="stat-value">
                {(stats.timelines as Record<string, number>)?.pending || 0}
              </div>
              <div className="stat-label">Pending Review</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-green-400">
                {(stats.timelines as Record<string, number>)?.reviewed || 0}
              </div>
              <div className="stat-label">Reviewed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-purple-400">
                {timelines.filter(t => t.export_status === "completed").length}
              </div>
              <div className="stat-label">Exported</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-blue-400 animate-pulse-soft">
                {processingJobs.length + timelines.filter(t => t.export_status === "exporting" || t.export_status === "uploading").length}
              </div>
              <div className="stat-label">Processing</div>
            </div>
          </div>
        )}

        {/* Processing Jobs */}
        {processingJobs.length > 0 && (
          <div className="mb-8">
            <div className="mb-4 flex items-center justify-between">
              <h2 className="text-2xl font-bold">Processing</h2>
              <Link href="/jobs" className="text-blue-400 hover:text-blue-300 text-sm">
                View all jobs
              </Link>
            </div>
            <div className="space-y-4 animate-fade-in">
              {processingJobs.map((job, index) => (
                <div
                  key={job.id}
                  className="card"
                  style={{ animationDelay: `${index * 50}ms` }}
                >
                  <div className="flex justify-between items-start gap-4">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-3 mb-1">
                        <h3 className="text-lg font-semibold truncate">
                          {job.title || "Loading video info..."}
                        </h3>
                        {getModeBadge(job.mode)}
                        {getStatusBadge(job.status)}
                      </div>
                      <p className="text-gray-400 text-sm">
                        {job.channel && <span>{job.channel} · </span>}
                        {job.duration ? formatDuration(job.duration) : ""}
                      </p>
                      <p className="text-gray-500 text-xs mt-1 truncate font-mono">
                        {job.url?.startsWith("file://") ? "本地上传" : job.url}
                      </p>
                    </div>
                    <div className="flex flex-col items-end gap-2">
                      {job.progress > 0 && (
                        <span className="text-2xl font-bold text-blue-400">
                          {Math.round(job.progress * 100)}%
                        </span>
                      )}
                      <Link
                        href="/jobs"
                        className="btn btn-secondary text-sm py-1.5"
                      >
                        View Details
                      </Link>
                    </div>
                  </div>
                  {job.progress > 0 && (
                    <div className="progress-bar mt-4">
                      <div
                        className="progress-fill progress-fill-info"
                        style={{ width: `${job.progress * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Ready to Review */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Ready to Review</h2>
          <Link href="/jobs" className="text-blue-400 hover:text-blue-300 text-sm">
            View all jobs
          </Link>
        </div>

        {timelines.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">🎬</div>
            <h3 className="text-xl font-medium mb-2">No videos yet</h3>
            <p className="text-gray-400 mb-6">Add a video to start watching with bilingual subtitles</p>
            <button onClick={openModal} className="btn btn-primary inline-flex">
              + Add Video
            </button>
          </div>
        ) : (
          <div className="space-y-4 animate-fade-in">
            {timelines.map((timeline, index) => (
              <div
                key={timeline.timeline_id}
                className="card card-hover"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3
                        className="text-lg font-semibold truncate cursor-text hover:bg-gray-700/50 rounded px-1 -mx-1 outline-none focus:ring-1 focus:ring-blue-500"
                        contentEditable
                        suppressContentEditableWarning
                        spellCheck={false}
                        onBlur={(e) => {
                          const newTitle = e.currentTarget.textContent?.trim();
                          if (newTitle && newTitle !== timeline.source_title) {
                            updateTimelineTitle(timeline.timeline_id, newTitle).then(() => {
                              setTimelines((prev) =>
                                prev.map((t) =>
                                  t.timeline_id === timeline.timeline_id
                                    ? { ...t, source_title: newTitle }
                                    : t
                                )
                              );
                            }).catch(() => {
                              e.currentTarget.textContent = timeline.source_title;
                            });
                          }
                        }}
                        onKeyDown={(e) => {
                          if (e.key === "Enter") {
                            e.preventDefault();
                            e.currentTarget.blur();
                          }
                          if (e.key === "Escape") {
                            e.currentTarget.textContent = timeline.source_title;
                            e.currentTarget.blur();
                          }
                        }}
                      >
                        {timeline.source_title}
                      </h3>
                      {getModeBadge(timeline.mode)}
                      {getExportStatusBadge(timeline)}
                    </div>
                    <p className="text-gray-400 text-sm">
                      {formatDuration(timeline.source_duration)} · {timeline.total_segments} segments
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0 flex flex-col items-end gap-2">
                    <div className="flex gap-2 mb-1">
                      <span className="badge badge-success">{timeline.keep_count} keep</span>
                      <span className="badge badge-danger">{timeline.drop_count} drop</span>
                      <span className="badge bg-gray-700 text-gray-300">{timeline.undecided_count} pending</span>
                    </div>
                    <Link
                      href={`/review/${timeline.timeline_id}`}
                      className="btn btn-primary text-sm py-1.5"
                    >
                      Review
                    </Link>
                  </div>
                </div>
                <div className="progress-bar mt-4">
                  <div
                    className="progress-fill progress-fill-success"
                    style={{ width: `${timeline.review_progress}%` }}
                  />
                </div>
                {(timeline.export_status === "exporting" || timeline.export_status === "uploading") && (
                  <div className="progress-bar mt-2">
                    <div
                      className={`progress-fill ${
                        timeline.export_status === "uploading"
                          ? "progress-fill-upload"
                          : "progress-fill-info"
                      }`}
                      style={{ width: `${timeline.export_progress}%` }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Video Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeModal}
          />

          <div className="relative bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6">
            <h2 className="text-xl font-bold mb-6">添加视频</h2>

            <form onSubmit={handleSubmit}>
              {/* Mode Selection */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-300 mb-3">
                  模式
                </label>
                <div className="grid grid-cols-2 gap-3">
                  <label
                    className={`flex flex-col items-center p-4 rounded-lg border cursor-pointer transition-all ${
                      videoMode === "watching"
                        ? "border-purple-500 bg-purple-500/10"
                        : "border-gray-600 bg-gray-800/50 hover:border-gray-500"
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      value="watching"
                      checked={videoMode === "watching"}
                      onChange={() => setVideoMode("watching")}
                      className="sr-only"
                    />
                    <span className="text-3xl mb-2">🎬</span>
                    <span className="font-medium">观看学习</span>
                    <span className="text-xs text-gray-400 text-center mt-1">
                      双语字幕 + 笔记 + AI
                    </span>
                  </label>
                  <label
                    className={`flex flex-col items-center p-4 rounded-lg border cursor-pointer transition-all ${
                      videoMode === "dubbing"
                        ? "border-orange-500 bg-orange-500/10"
                        : "border-gray-600 bg-gray-800/50 hover:border-gray-500"
                    }`}
                  >
                    <input
                      type="radio"
                      name="mode"
                      value="dubbing"
                      checked={videoMode === "dubbing"}
                      onChange={() => setVideoMode("dubbing")}
                      className="sr-only"
                    />
                    <span className="text-3xl mb-2">🎙️</span>
                    <span className="font-medium">AI 配音</span>
                    <span className="text-xs text-gray-400 text-center mt-1">
                      声音克隆 + 口型同步
                    </span>
                  </label>
                </div>
              </div>

              {/* Language Selection (Dubbing mode only) */}
              {videoMode === "dubbing" && (
                <div className="mb-6">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1.5">
                        原视频语言
                      </label>
                      <select
                        value={sourceLanguage}
                        onChange={(e) => setSourceLanguage(e.target.value)}
                        className="w-full bg-gray-800 text-white text-sm px-3 py-2 rounded-lg border border-gray-600 outline-none focus:border-orange-500 transition-colors"
                      >
                        {SOURCE_LANGUAGES.map((lang) => (
                          <option key={lang.value} value={lang.value}>
                            {lang.label}
                          </option>
                        ))}
                      </select>
                    </div>
                    <div>
                      <label className="block text-sm font-medium text-gray-300 mb-1.5">
                        目标语言
                      </label>
                      <select
                        value={targetLanguage}
                        onChange={(e) => setTargetLanguage(e.target.value)}
                        className="w-full bg-gray-800 text-white text-sm px-3 py-2 rounded-lg border border-gray-600 outline-none focus:border-orange-500 transition-colors"
                      >
                        {TARGET_LANGUAGES.filter((l) => l.value !== sourceLanguage && !(sourceLanguage === "zh" && l.value.startsWith("zh"))).map((lang) => (
                          <option key={lang.value} value={lang.value}>
                            {lang.label}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                </div>
              )}

              {/* Whisper Model Size */}
              <div className="mb-4">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  转录模型
                </label>
                <div className="flex gap-2">
                  {([
                    { value: "small", label: "Small", desc: "快速" },
                    { value: "medium", label: "Medium", desc: "均衡" },
                    { value: "large-v3", label: "Large v3", desc: "最准确" },
                  ] as const).map((m) => (
                    <button
                      key={m.value}
                      type="button"
                      onClick={() => setWhisperModel(m.value)}
                      disabled={submitting}
                      className={`flex-1 px-3 py-2 rounded-lg text-sm font-medium transition-colors ${
                        whisperModel === m.value
                          ? "bg-blue-600 text-white"
                          : "bg-gray-800 text-gray-400 hover:bg-gray-700"
                      }`}
                    >
                      {m.label}
                      <span className="block text-[10px] opacity-70 font-normal">{m.desc}</span>
                    </button>
                  ))}
                </div>
              </div>

              {/* Speaker Diarization */}
              <div className="mb-4">
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={enableDiarization}
                    onChange={(e) => setEnableDiarization(e.target.checked)}
                    className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    disabled={submitting}
                  />
                  <div>
                    <span className="text-sm text-white">说话人识别</span>
                    <p className="text-xs text-gray-500">自动区分不同说话人，适合多人对话视频</p>
                  </div>
                </label>
              </div>

              {/* Input Mode Tabs */}
              <div className="flex mb-4 border-b border-gray-700">
                <button
                  type="button"
                  onClick={() => setInputMode("url")}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    inputMode === "url"
                      ? "text-blue-400 border-b-2 border-blue-400"
                      : "text-gray-400 hover:text-gray-300"
                  }`}
                >
                  🔗 URL
                </button>
                <button
                  type="button"
                  onClick={() => setInputMode("upload")}
                  className={`px-4 py-2 text-sm font-medium transition-colors ${
                    inputMode === "upload"
                      ? "text-blue-400 border-b-2 border-blue-400"
                      : "text-gray-400 hover:text-gray-300"
                  }`}
                >
                  📁 上传
                </button>
              </div>

              {/* URL Input */}
              {inputMode === "url" && (
                <div className="mb-6">
                  <input
                    type="url"
                    value={newUrl}
                    onChange={(e) => setNewUrl(e.target.value)}
                    placeholder="粘贴 YouTube 或视频链接..."
                    className="input"
                    disabled={submitting}
                    autoFocus
                  />
                </div>
              )}

              {/* File Upload */}
              {inputMode === "upload" && (
                <div className="mb-6">
                  <div className="relative">
                    <input
                      type="file"
                      accept="video/*,.mp4,.mkv,.avi,.mov,.webm,.m4v"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        setUploadFile(file || null);
                      }}
                      className="hidden"
                      id="home-video-upload"
                      disabled={submitting}
                    />
                    <label
                      htmlFor="home-video-upload"
                      className="flex items-center justify-center w-full px-4 py-4 border-2 border-dashed border-gray-600 rounded-lg cursor-pointer hover:border-gray-500 transition-colors"
                    >
                      {uploadFile ? (
                        <div className="text-center">
                          <div className="text-sm font-medium text-white truncate max-w-[350px]">
                            {uploadFile.name}
                          </div>
                          <div className="text-xs text-gray-400 mt-1">
                            {(uploadFile.size / 1024 / 1024).toFixed(1)} MB
                          </div>
                        </div>
                      ) : (
                        <div className="text-center">
                          <svg className="w-10 h-10 mx-auto mb-2 text-gray-500" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12" />
                          </svg>
                          <span className="text-sm text-gray-400">
                            点击选择视频文件
                          </span>
                          <p className="text-xs text-gray-500 mt-1">
                            MP4, MKV, AVI, MOV, WebM (max 4GB)
                          </p>
                        </div>
                      )}
                    </label>
                  </div>
                  {uploadProgress && (
                    <div className="mt-3">
                      <div className="flex justify-between text-xs text-gray-400 mb-1">
                        <span>上传中...</span>
                        <span>{uploadProgress.percentage}%</span>
                      </div>
                      <div className="w-full bg-gray-700 rounded-full h-2">
                        <div
                          className="bg-blue-500 h-2 rounded-full transition-all duration-300"
                          style={{ width: `${uploadProgress.percentage}%` }}
                        />
                      </div>
                    </div>
                  )}
                </div>
              )}

              {/* Error */}
              {error && (
                <div className="mb-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                  <p className="text-red-400 text-sm">{error}</p>
                </div>
              )}

              {/* Buttons */}
              <div className="flex gap-3 justify-end">
                <button
                  type="button"
                  onClick={closeModal}
                  className="btn btn-secondary"
                  disabled={submitting}
                >
                  取消
                </button>
                <button
                  type="submit"
                  disabled={submitting || (inputMode === "url" ? !newUrl.trim() : !uploadFile)}
                  className="btn btn-primary"
                >
                  {submitting ? (
                    <>
                      <span className="spinner mr-2" />
                      {uploadProgress ? `上传中 ${uploadProgress.percentage}%` : "处理中..."}
                    </>
                  ) : (
                    "开始处理"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

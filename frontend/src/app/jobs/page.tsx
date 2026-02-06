"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { listJobs, createJob, createJobWithUpload, deleteJob, cancelJob, formatDuration, getVideoUrl, getExportVideoUrl } from "@/lib/api";
import type { UploadProgress } from "@/lib/api";
import { useToast, useConfirm } from "@/components/ui";
import type { Job, JobCreate, JobMode } from "@/lib/types";

export default function JobsPage() {
  const toast = useToast();
  const confirm = useConfirm();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [initialLoading, setInitialLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<string | null>(null);

  // Modal state
  const [showModal, setShowModal] = useState(false);
  const [inputMode, setInputMode] = useState<"url" | "upload">("url");
  const [newUrl, setNewUrl] = useState("");
  const [uploadFile, setUploadFile] = useState<File | null>(null);
  const [uploadProgress, setUploadProgress] = useState<UploadProgress | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [jobOptions, setJobOptions] = useState<Partial<JobCreate>>({
    mode: "learning",          // Default to Learning mode
    target_language: "zh-CN",  // Default to Simplified Chinese
    skip_diarization: true,    // Default: skip diarization (single speaker)
  });

  // Mode options
  const JOB_MODES: { value: JobMode; label: string; description: string }[] = [
    { value: "learning", label: "Learning Mode", description: "Original audio + Bilingual subtitles + Word cards" },
    { value: "watching", label: "Watching Mode", description: "Original audio + Transparent subtitles + Scene capture" },
    { value: "dubbing", label: "Dubbing Mode", description: "Voice cloning + Lip sync (experimental)" },
  ];

  // Supported target languages (Chinese variants merged into dropdown)
  const SUPPORTED_LANGUAGES = [
    { code: "zh-CN", name: "Chinese (Simplified)" },
    { code: "zh-TW", name: "Chinese (Traditional)" },
    { code: "ja", name: "Japanese" },
    { code: "ko", name: "한국어 (Korean)" },
    { code: "es", name: "Español (Spanish)" },
    { code: "fr", name: "Français (French)" },
    { code: "de", name: "Deutsch (German)" },
  ];

  const loadJobs = useCallback(async (isInitial = false) => {
    if (isInitial) {
      setInitialLoading(true);
    } else {
      setRefreshing(true);
    }

    try {
      const data = await listJobs(undefined, 50);
      setJobs(data);
    } catch (error) {
      console.error("Failed to load jobs:", error);
      if (isInitial) {
        setError("Failed to load jobs");
      }
    } finally {
      setInitialLoading(false);
      setRefreshing(false);
    }
  }, []);

  useEffect(() => {
    loadJobs(true);
    const interval = setInterval(() => loadJobs(false), 5000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  function openModal() {
    setInputMode("url");
    setNewUrl("");
    setUploadFile(null);
    setUploadProgress(null);
    setJobOptions({
      mode: "learning",          // Default to Learning mode
      target_language: "zh-CN",  // Default to Simplified Chinese
      skip_diarization: true,    // Default: skip diarization (single speaker)
    });
    setError(null);
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setInputMode("url");
    setNewUrl("");
    setUploadFile(null);
    setUploadProgress(null);
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    // Validate input based on mode
    if (inputMode === "url" && !newUrl.trim()) return;
    if (inputMode === "upload" && !uploadFile) return;

    setSubmitting(true);
    setError(null);
    setUploadProgress(null);

    try {
      if (inputMode === "url") {
        await createJob({
          url: newUrl.trim(),
          ...jobOptions,
        });
      } else {
        await createJobWithUpload(
          {
            file: uploadFile!,
            mode: jobOptions.mode,
            target_language: jobOptions.target_language,
            skip_diarization: jobOptions.skip_diarization,
          },
          (progress) => setUploadProgress(progress)
        );
      }
      closeModal();
      loadJobs(false);
    } catch (err) {
      console.error("Failed to create job:", err);
      const message = err instanceof Error ? err.message : "Failed to create job";
      setError(message);
    } finally {
      setSubmitting(false);
      setUploadProgress(null);
    }
  }

  async function handleDelete(jobId: string, title: string) {
    const confirmed = await confirm({
      title: "Delete Job",
      message: `Are you sure you want to delete "${title || jobId}"? This will remove all related files.`,
      type: "danger",
      confirmText: "Delete",
    });
    if (!confirmed) return;

    setDeletingId(jobId);
    try {
      await deleteJob(jobId);
      toast.success("Job deleted");
      loadJobs(false);
    } catch (err) {
      console.error("Failed to delete job:", err);
      toast.error("Delete failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setDeletingId(null);
    }
  }

  async function handleCancel(jobId: string, title: string) {
    const confirmed = await confirm({
      title: "Cancel Job",
      message: `Are you sure you want to cancel "${title || jobId}"? The job will stop after completing the current stage.`,
      type: "warning",
      confirmText: "Cancel Job",
    });
    if (!confirmed) return;

    setCancellingId(jobId);
    try {
      await cancelJob(jobId);
      toast.success("Job cancelled");
      loadJobs(false);
    } catch (err) {
      console.error("Failed to cancel job:", err);
      toast.error("Cancel failed: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setCancellingId(null);
    }
  }

  function canCancel(status: string): boolean {
    return ["pending", "downloading", "transcribing", "diarizing", "translating"].includes(status);
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "completed":
        return <span className="badge badge-success">Completed</span>;
      case "failed":
        return <span className="badge badge-danger">Failed</span>;
      case "awaiting_review":
        return <span className="badge badge-warning">Awaiting Review</span>;
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
        return <span className="badge badge-info">Pending</span>;
      case "cancelled":
        return <span className="badge badge-secondary">Cancelled</span>;
      default:
        return <span className="badge badge-info">{status}</span>;
    }
  }

  function getModeBadge(mode: JobMode | undefined) {
    switch (mode) {
      case "learning":
        return <span className="badge bg-blue-600 text-white text-xs">Learn</span>;
      case "watching":
        return <span className="badge bg-purple-600 text-white text-xs">Watch</span>;
      case "dubbing":
        return <span className="badge bg-orange-600 text-white text-xs">Dub</span>;
      default:
        return <span className="badge bg-blue-600 text-white text-xs">Learn</span>;
    }
  }

  // Only show full-page loading on initial load
  if (initialLoading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="spinner mx-auto mb-4" />
          <p className="text-gray-400">Loading jobs...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <PageHeader
        title="Job Queue"
        subtitle="SceneMind Processing Tasks"
        icon="🧠"
        iconGradient="from-purple-500 to-pink-600"
        backHref="/"
        actions={
          <>
            {refreshing && (
              <span className="text-gray-500 text-sm flex items-center gap-2">
                <span className="spinner w-4 h-4" />
                Refreshing...
              </span>
            )}
            <button onClick={openModal} className="btn btn-primary">
              + Add Job
            </button>
            <Link href="/" className="btn btn-secondary">
              ← Home
            </Link>
          </>
        }
      />

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Global Error */}
        {error && !showModal && (
          <div className="mb-6 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center justify-between">
            <p className="text-red-400 text-sm">{error}</p>
            <button onClick={() => setError(null)} className="text-red-400 hover:text-red-300 ml-4">
              ✕
            </button>
          </div>
        )}

        {/* Jobs List */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold">All Jobs</h2>
          <span className="text-gray-400 text-sm">{jobs.length} job(s)</span>
        </div>

        {jobs.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">📽️</div>
            <h3 className="text-xl font-medium mb-2">No Jobs Yet</h3>
            <p className="text-gray-400 mb-4">Click the button above to add a video for processing</p>
            <button onClick={openModal} className="btn btn-primary">
              + Add First Job
            </button>
          </div>
        ) : (
          <div className="space-y-4">
            {jobs.map((job, index) => (
              <div
                key={job.id}
                className="card animate-fade-in"
                style={{ animationDelay: `${index * 30}ms` }}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 mb-1">
                      <h3 className="text-lg font-semibold truncate">
                        {job.title || "Processing..."}
                      </h3>
                      {getModeBadge(job.mode)}
                      {getStatusBadge(job.status)}
                    </div>
                    <p className="text-gray-400 text-sm">
                      {job.channel && (
                        <span className="text-gray-300">{job.channel}</span>
                      )}
                      {job.channel && job.duration && " · "}
                      {job.duration ? formatDuration(job.duration) : ""}
                    </p>
                    <p className="text-gray-500 text-xs mt-1 truncate font-mono">
                      {job.url}
                    </p>
                  </div>
                  <div className="flex flex-col items-end gap-2">
                    {job.progress > 0 && job.progress < 1 && (
                      <span className="text-2xl font-bold text-blue-400">
                        {Math.round(job.progress * 100)}%
                      </span>
                    )}
                    <div className="flex items-center gap-2">
                      {job.timeline_id && (
                        <Link
                          href={`/review/${job.timeline_id}`}
                          className="btn btn-success text-sm py-1.5"
                        >
                          Review →
                        </Link>
                      )}
                      {canCancel(job.status) && (
                        <button
                          onClick={() => handleCancel(job.id, job.title || "")}
                          disabled={cancellingId === job.id}
                          className="btn btn-warning text-sm py-1.5"
                          title="Cancel Job"
                          aria-label="Cancel job"
                        >
                          {cancellingId === job.id ? (
                            <span className="spinner" />
                          ) : (
                            "⏹"
                          )}
                        </button>
                      )}
                      <button
                        onClick={() => handleDelete(job.id, job.title || "")}
                        disabled={deletingId === job.id}
                        className="btn btn-danger text-sm py-1.5"
                        title="Delete Job"
                        aria-label="Delete job"
                      >
                        {deletingId === job.id ? (
                          <span className="spinner" />
                        ) : (
                          "🗑️"
                        )}
                      </button>
                    </div>
                  </div>
                </div>

                {/* Progress bar */}
                {job.progress > 0 && job.progress < 1 && (
                  <div className="progress-bar mt-4">
                    <div
                      className="progress-fill bg-gradient-to-r from-blue-500 to-cyan-400"
                      style={{ width: `${job.progress * 100}%` }}
                    />
                  </div>
                )}

                {/* Download buttons */}
                {(job.source_video || job.output_video) && (
                  <div className="mt-4 flex items-center gap-3">
                    <span className="text-gray-500 text-sm">Download:</span>
                    {job.source_video && (
                      <a
                        href={getVideoUrl(job.id)}
                        className="btn btn-secondary text-sm py-1.5"
                        download
                      >
                        📥 Original
                      </a>
                    )}
                    {job.output_video && (
                      <a
                        href={getExportVideoUrl(job.id)}
                        className="btn btn-primary text-sm py-1.5"
                        download
                      >
                        📥 Bilingual
                      </a>
                    )}
                  </div>
                )}

                {/* Processing Stats */}
                {(job.step_timings && Object.keys(job.step_timings).length > 0) || (job.total_cost_usd && job.total_cost_usd > 0) ? (
                  <div className="mt-4 p-3 bg-gray-800/50 border border-gray-700 rounded-lg">
                    <div className="flex items-center gap-4 text-sm">
                      {/* Total time */}
                      {job.total_processing_seconds && job.total_processing_seconds > 0 && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-gray-400">⏱️</span>
                          <span className="text-gray-300">
                            {formatDuration(job.total_processing_seconds)}
                          </span>
                        </div>
                      )}
                      {/* Total cost */}
                      {job.total_cost_usd && job.total_cost_usd > 0 && (
                        <div className="flex items-center gap-1.5">
                          <span className="text-gray-400">💰</span>
                          <span className="text-green-400">
                            ${job.total_cost_usd.toFixed(4)}
                          </span>
                        </div>
                      )}
                      {/* Step timings */}
                      {job.step_timings && Object.keys(job.step_timings).length > 0 && (
                        <div className="flex-1 flex items-center gap-2 text-xs text-gray-500">
                          <span className="text-gray-600">|</span>
                          {Object.entries(job.step_timings).map(([step, timing]) => (
                            timing.duration_seconds != null && (
                              <span key={step} className="whitespace-nowrap">
                                {step}: {timing.duration_seconds < 60
                                  ? `${Math.round(timing.duration_seconds)}s`
                                  : `${Math.floor(timing.duration_seconds / 60)}m${Math.round(timing.duration_seconds % 60)}s`
                                }
                              </span>
                            )
                          ))}
                        </div>
                      )}
                    </div>
                    {/* API cost breakdown */}
                    {job.api_costs && job.api_costs.length > 0 && (
                      <div className="mt-2 text-xs text-gray-500">
                        {job.api_costs.map((cost, i) => (
                          <span key={i} className="mr-3">
                            {cost.service} ({cost.model}): ${cost.cost_usd.toFixed(4)}
                            {cost.tokens_in > 0 && ` • ${(cost.tokens_in / 1000).toFixed(1)}k in`}
                            {cost.tokens_out > 0 && ` / ${(cost.tokens_out / 1000).toFixed(1)}k out`}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ) : null}

                {/* Error message */}
                {job.error && (
                  <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 text-sm">
                      <span className="font-medium">Error:</span> {job.error}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Job Modal */}
      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={closeModal}
          />

          {/* Modal */}
          <div className="relative bg-[var(--card)] border border-[var(--border)] rounded-2xl shadow-2xl w-full max-w-lg mx-4 p-6">
            <h2 className="text-xl font-bold mb-6">Add New Job</h2>

            <form onSubmit={handleSubmit}>
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
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    视频链接
                  </label>
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
                  <label className="block text-sm font-medium text-gray-300 mb-2">
                    视频文件
                  </label>
                  <div className="relative">
                    <input
                      type="file"
                      accept="video/*,.mp4,.mkv,.avi,.mov,.webm,.m4v"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        setUploadFile(file || null);
                      }}
                      className="hidden"
                      id="job-video-upload"
                      disabled={submitting}
                    />
                    <label
                      htmlFor="job-video-upload"
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

              {/* Mode Selection */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-300 mb-3">
                  处理模式
                </label>
                <div className="grid grid-cols-1 gap-2">
                  {JOB_MODES.map((mode) => (
                    <label
                      key={mode.value}
                      className={`flex items-center gap-3 p-3 rounded-lg border cursor-pointer transition-all ${
                        jobOptions.mode === mode.value
                          ? "border-blue-500 bg-blue-500/10"
                          : "border-gray-600 bg-gray-800/50 hover:border-gray-500"
                      }`}
                    >
                      <input
                        type="radio"
                        name="mode"
                        value={mode.value}
                        checked={jobOptions.mode === mode.value}
                        onChange={(e) =>
                          setJobOptions({ ...jobOptions, mode: e.target.value as JobMode })
                        }
                        className="w-4 h-4 text-blue-500 border-gray-600 bg-gray-700 focus:ring-blue-500"
                        disabled={submitting}
                      />
                      <div>
                        <span className="text-white font-medium">{mode.label}</span>
                        <p className="text-gray-500 text-xs">{mode.description}</p>
                      </div>
                    </label>
                  ))}
                </div>
              </div>

              {/* Options */}
              <div className="mb-6 space-y-4">
                <label className="block text-sm font-medium text-gray-300 mb-3">
                  Processing Options
                </label>

                {/* Target Language */}
                <div>
                  <label className="block text-sm text-gray-400 mb-2">
                    Target Language
                  </label>
                  <select
                    value={jobOptions.target_language || "zh-CN"}
                    onChange={(e) =>
                      setJobOptions({
                        ...jobOptions,
                        target_language: e.target.value,
                      })
                    }
                    className="w-full bg-gray-700 border border-gray-600 rounded-lg px-3 py-2 text-white focus:border-blue-500 focus:ring-1 focus:ring-blue-500"
                    disabled={submitting}
                  >
                    {SUPPORTED_LANGUAGES.map((lang) => (
                      <option key={lang.code} value={lang.code}>
                        {lang.name}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Enable Speaker Diarization */}
                <label className="flex items-center gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={!jobOptions.skip_diarization}
                    onChange={(e) =>
                      setJobOptions({ ...jobOptions, skip_diarization: !e.target.checked })
                    }
                    className="w-5 h-5 rounded border-gray-600 bg-gray-700 text-blue-500 focus:ring-blue-500"
                    disabled={submitting}
                  />
                  <div>
                    <span className="text-white">Enable Speaker Diarization</span>
                    <p className="text-gray-500 text-xs">Automatically distinguish different speakers in multi-person conversations, names can be labeled later</p>
                  </div>
                </label>
              </div>

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
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting || (inputMode === "url" ? !newUrl.trim() : !uploadFile)}
                  className="btn btn-primary"
                >
                  {submitting ? (
                    <>
                      <span className="spinner mr-2" />
                      {uploadProgress ? `Uploading ${uploadProgress.percentage}%` : "Processing..."}
                    </>
                  ) : (
                    inputMode === "url" ? "Add Job" : "Upload & Process"
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

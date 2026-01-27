"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { listJobs, createJob, deleteJob, cancelJob, formatDuration, getVideoUrl, getExportVideoUrl } from "@/lib/api";
import { useToast, useConfirm } from "@/components/ui";
import type { Job, JobCreate } from "@/lib/types";

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
  const [newUrl, setNewUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [jobOptions, setJobOptions] = useState<Partial<JobCreate>>({
    target_language: "zh-TW",  // Default to Traditional Chinese
    skip_diarization: true,    // Default: skip diarization (single speaker)
  });

  // Supported target languages (Chinese variants merged into dropdown)
  const SUPPORTED_LANGUAGES = [
    { code: "zh-TW", name: "中文 (繁體)" },
    { code: "zh-CN", name: "中文 (简体)" },
    { code: "ja", name: "日本語 (Japanese)" },
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
    setNewUrl("");
    setJobOptions({
      target_language: "zh-TW",  // Default to Traditional Chinese
      skip_diarization: true,    // Default: skip diarization (single speaker)
    });
    setError(null);
    setShowModal(true);
  }

  function closeModal() {
    setShowModal(false);
    setNewUrl("");
    setError(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!newUrl.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      await createJob({
        url: newUrl.trim(),
        ...jobOptions,
      });
      closeModal();
      loadJobs(false);
    } catch (err) {
      console.error("Failed to create job:", err);
      const message = err instanceof Error ? err.message : "Failed to create job";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(jobId: string, title: string) {
    const confirmed = await confirm({
      title: "删除 Job",
      message: `确定要删除 "${title || jobId}" 吗？这将删除所有相关文件。`,
      type: "danger",
      confirmText: "删除",
    });
    if (!confirmed) return;

    setDeletingId(jobId);
    try {
      await deleteJob(jobId);
      toast.success("Job 已删除");
      loadJobs(false);
    } catch (err) {
      console.error("Failed to delete job:", err);
      toast.error("删除失败: " + (err instanceof Error ? err.message : "Unknown error"));
    } finally {
      setDeletingId(null);
    }
  }

  async function handleCancel(jobId: string, title: string) {
    const confirmed = await confirm({
      title: "取消 Job",
      message: `确定要取消 "${title || jobId}" 吗？Job 将在当前阶段完成后停止。`,
      type: "warning",
      confirmText: "取消 Job",
    });
    if (!confirmed) return;

    setCancellingId(jobId);
    try {
      await cancelJob(jobId);
      toast.success("Job 已取消");
      loadJobs(false);
    } catch (err) {
      console.error("Failed to cancel job:", err);
      toast.error("取消失败: " + (err instanceof Error ? err.message : "Unknown error"));
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
      {/* Header */}
      <header className="border-b border-[var(--border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-50">
        <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link href="/" className="flex items-center gap-3 hover:opacity-80 transition">
              <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xl">
                🎬
              </div>
              <div>
                <h1 className="text-xl font-bold">Job Queue</h1>
                <p className="text-xs text-gray-500">Video Processing Tasks</p>
              </div>
            </Link>
          </div>
          <div className="flex items-center gap-3">
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
          </div>
        </div>
      </header>

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
              {/* URL Input */}
              <div className="mb-6">
                <label className="block text-sm font-medium text-gray-300 mb-2">
                  Video URL
                </label>
                <input
                  type="url"
                  value={newUrl}
                  onChange={(e) => setNewUrl(e.target.value)}
                  placeholder="Paste YouTube video URL..."
                  className="input"
                  disabled={submitting}
                  autoFocus
                />
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
                    value={jobOptions.target_language || "zh-TW"}
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
                    <span className="text-white">识别说话人</span>
                    <p className="text-gray-500 text-xs">多人对话时自动区分不同说话人，可在后续标注姓名</p>
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
                  disabled={submitting || !newUrl.trim()}
                  className="btn btn-primary"
                >
                  {submitting ? (
                    <>
                      <span className="spinner mr-2" />
                      Adding...
                    </>
                  ) : (
                    "Add Job"
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

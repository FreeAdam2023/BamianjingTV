"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { listJobs, createJob, deleteJob, formatDuration } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUrl, setNewUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [deletingId, setDeletingId] = useState<string | null>(null);

  const loadJobs = useCallback(async () => {
    try {
      const data = await listJobs(undefined, 50);
      setJobs(data);
    } catch (error) {
      console.error("Failed to load jobs:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadJobs();
    // Auto-refresh every 5 seconds
    const interval = setInterval(loadJobs, 5000);
    return () => clearInterval(interval);
  }, [loadJobs]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!newUrl.trim()) return;

    setSubmitting(true);
    setError(null);
    try {
      await createJob({ url: newUrl.trim() });
      setNewUrl("");
      loadJobs();
    } catch (err) {
      console.error("Failed to create job:", err);
      const message = err instanceof Error ? err.message : "创建任务失败";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete(jobId: string, title: string) {
    if (!confirm(`确定要删除任务 "${title || jobId}" 吗？\n\n这将删除所有相关文件。`)) {
      return;
    }

    setDeletingId(jobId);
    try {
      await deleteJob(jobId);
      loadJobs();
    } catch (err) {
      console.error("Failed to delete job:", err);
      const message = err instanceof Error ? err.message : "删除任务失败";
      setError(message);
    } finally {
      setDeletingId(null);
    }
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "completed":
        return <span className="badge badge-success">✓ 已完成</span>;
      case "failed":
        return <span className="badge badge-danger">✕ 失败</span>;
      case "awaiting_review":
        return <span className="badge badge-warning">⏸ 待审阅</span>;
      case "downloading":
        return <span className="badge badge-info">↓ 下载中</span>;
      case "transcribing":
        return <span className="badge badge-info">🎤 转录中</span>;
      case "diarizing":
        return <span className="badge badge-info">👥 说话人识别</span>;
      case "translating":
        return <span className="badge badge-info">🌐 翻译中</span>;
      case "exporting":
        return <span className="badge badge-info">📤 导出中</span>;
      case "pending":
        return <span className="badge badge-info">⏳ 等待中</span>;
      default:
        return <span className="badge badge-info">{status}</span>;
    }
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
                <h1 className="text-xl font-bold">任务队列</h1>
                <p className="text-xs text-gray-500">视频处理任务</p>
              </div>
            </Link>
          </div>
          <Link href="/" className="btn btn-secondary">
            ← 返回首页
          </Link>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* New Job Form */}
        <form onSubmit={handleSubmit} className="card mb-8">
          <h2 className="text-lg font-semibold mb-4">添加新视频</h2>
          <div className="flex gap-4">
            <input
              type="url"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder="粘贴 YouTube 视频链接..."
              className="input flex-1"
              disabled={submitting}
            />
            <button
              type="submit"
              disabled={submitting || !newUrl.trim()}
              className="btn btn-primary whitespace-nowrap"
            >
              {submitting ? (
                <>
                  <span className="spinner mr-2" />
                  添加中...
                </>
              ) : (
                "+ 添加任务"
              )}
            </button>
          </div>
          {error && (
            <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg flex items-center justify-between">
              <p className="text-red-400 text-sm">{error}</p>
              <button
                onClick={() => setError(null)}
                className="text-red-400 hover:text-red-300 ml-4"
              >
                ✕
              </button>
            </div>
          )}
        </form>

        {/* Jobs List */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold">所有任务</h2>
          <span className="text-gray-400 text-sm">共 {jobs.length} 个任务</span>
        </div>

        {jobs.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">📽️</div>
            <h3 className="text-xl font-medium mb-2">暂无任务</h3>
            <p className="text-gray-400">在上方添加视频链接开始处理</p>
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
                        {job.title || "处理中..."}
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
                          去审阅 →
                        </Link>
                      )}
                      <button
                        onClick={() => handleDelete(job.id, job.title || "")}
                        disabled={deletingId === job.id}
                        className="btn btn-danger text-sm py-1.5"
                        title="删除任务"
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

                {/* Error message */}
                {job.error && (
                  <div className="mt-4 p-3 bg-red-500/10 border border-red-500/30 rounded-lg">
                    <p className="text-red-400 text-sm">
                      <span className="font-medium">错误：</span> {job.error}
                    </p>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

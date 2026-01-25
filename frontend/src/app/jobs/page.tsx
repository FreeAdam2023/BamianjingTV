"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { listJobs, createJob, formatDuration } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUrl, setNewUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

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
    try {
      await createJob({ url: newUrl.trim() });
      setNewUrl("");
      loadJobs();
    } catch (error) {
      console.error("Failed to create job:", error);
      alert("Failed to create job");
    } finally {
      setSubmitting(false);
    }
  }

  function getStatusBadge(status: string) {
    switch (status) {
      case "completed":
        return <span className="badge badge-success">✓ Completed</span>;
      case "failed":
        return <span className="badge badge-danger">✕ Failed</span>;
      case "awaiting_review":
        return <span className="badge badge-warning">⏸ Awaiting Review</span>;
      case "downloading":
        return <span className="badge badge-info">↓ Downloading</span>;
      case "transcribing":
        return <span className="badge badge-info">🎤 Transcribing</span>;
      case "diarizing":
        return <span className="badge badge-info">👥 Diarizing</span>;
      case "translating":
        return <span className="badge badge-info">🌐 Translating</span>;
      case "exporting":
        return <span className="badge badge-info">📤 Exporting</span>;
      default:
        return <span className="badge badge-info">{status}</span>;
    }
  }

  if (loading) {
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
                <h1 className="text-xl font-bold">Jobs</h1>
                <p className="text-xs text-gray-500">Video Processing Queue</p>
              </div>
            </Link>
          </div>
          <Link href="/" className="btn btn-secondary">
            ← Dashboard
          </Link>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* New Job Form */}
        <form onSubmit={handleSubmit} className="card mb-8">
          <h2 className="text-lg font-semibold mb-4">Add New Video</h2>
          <div className="flex gap-4">
            <input
              type="url"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder="Paste YouTube URL here..."
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
                  Adding...
                </>
              ) : (
                "+ Add Job"
              )}
            </button>
          </div>
        </form>

        {/* Jobs List */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold">All Jobs</h2>
          <span className="text-gray-400 text-sm">{jobs.length} jobs</span>
        </div>

        {jobs.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">📽️</div>
            <h3 className="text-xl font-medium mb-2">No jobs yet</h3>
            <p className="text-gray-400">Add a video URL above to get started</p>
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
                    {job.timeline_id && (
                      <Link
                        href={`/review/${job.timeline_id}`}
                        className="btn btn-success text-sm py-1.5"
                      >
                        Review →
                      </Link>
                    )}
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
                      <span className="font-medium">Error:</span> {job.error}
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

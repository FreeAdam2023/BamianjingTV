"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import { listTimelines, listJobs, getStats, formatDuration } from "@/lib/api";
import type { TimelineSummary, Job } from "@/lib/types";

export default function Home() {
  const [timelines, setTimelines] = useState<TimelineSummary[]>([]);
  const [processingJobs, setProcessingJobs] = useState<Job[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      const [timelinesData, statsData, jobsData] = await Promise.all([
        listTimelines(false, true, 10),
        getStats(),
        listJobs(undefined, 50),
      ]);
      setTimelines(timelinesData);
      setStats(statsData);

      // Filter jobs that are currently processing (not completed, failed, cancelled, or awaiting review)
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
    // Auto-refresh every 5 seconds to show progress updates
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, [loadData]);

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
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xl">
              🎬
            </div>
            <div>
              <h1 className="text-xl font-bold">Hardcore Player</h1>
              <p className="text-xs text-gray-500">Learning Video Factory</p>
            </div>
          </div>
          <Link href="/jobs" className="btn btn-primary">
            + Add Video
          </Link>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8 animate-fade-in">
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
              <div className="stat-value text-blue-400 animate-pulse-soft">
                {processingJobs.length}
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
                View all jobs →
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
                        {getStatusBadge(job.status)}
                      </div>
                      <p className="text-gray-400 text-sm">
                        {job.channel && <span>{job.channel} · </span>}
                        {job.duration ? formatDuration(job.duration) : ""}
                      </p>
                      <p className="text-gray-500 text-xs mt-1 truncate font-mono">
                        {job.url}
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
                  {/* Progress bar */}
                  {job.progress > 0 && (
                    <div className="progress-bar mt-4">
                      <div
                        className="progress-fill bg-gradient-to-r from-blue-500 to-cyan-400"
                        style={{ width: `${job.progress * 100}%` }}
                      />
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Pending Reviews */}
        <div className="mb-6 flex items-center justify-between">
          <h2 className="text-2xl font-bold">Pending Reviews</h2>
          <Link href="/jobs" className="text-blue-400 hover:text-blue-300 text-sm">
            View all jobs →
          </Link>
        </div>

        {timelines.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">📭</div>
            <h3 className="text-xl font-medium mb-2">No videos pending review</h3>
            <p className="text-gray-400 mb-6">Add a video URL to get started</p>
            <Link href="/jobs" className="btn btn-primary inline-flex">
              + Add Video
            </Link>
          </div>
        ) : (
          <div className="space-y-4 animate-fade-in">
            {timelines.map((timeline, index) => (
              <Link
                key={timeline.timeline_id}
                href={`/review/${timeline.timeline_id}`}
                className="card card-hover block"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <h3 className="text-lg font-semibold truncate mb-1">
                      {timeline.source_title}
                    </h3>
                    <p className="text-gray-400 text-sm">
                      {formatDuration(timeline.source_duration)} · {timeline.total_segments} segments
                    </p>
                  </div>
                  <div className="text-right flex-shrink-0">
                    <div className="flex gap-2 mb-1">
                      <span className="badge badge-success">{timeline.keep_count} keep</span>
                      <span className="badge badge-danger">{timeline.drop_count} drop</span>
                      <span className="badge bg-gray-700 text-gray-300">{timeline.undecided_count} pending</span>
                    </div>
                    <div className="text-gray-400 text-sm">
                      {Math.round(timeline.review_progress)}% reviewed
                    </div>
                  </div>
                </div>
                <div className="progress-bar mt-4">
                  <div
                    className="progress-fill bg-gradient-to-r from-green-500 to-emerald-400"
                    style={{ width: `${timeline.review_progress}%` }}
                  />
                </div>
              </Link>
            ))}
          </div>
        )}
      </div>
    </main>
  );
}

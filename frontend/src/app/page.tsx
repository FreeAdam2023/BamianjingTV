"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listTimelines, getStats, formatDuration } from "@/lib/api";
import type { TimelineSummary } from "@/lib/types";

export default function Home() {
  const [timelines, setTimelines] = useState<TimelineSummary[]>([]);
  const [stats, setStats] = useState<Record<string, unknown> | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadData() {
      try {
        const [timelinesData, statsData] = await Promise.all([
          listTimelines(false, true, 10),
          getStats(),
        ]);
        setTimelines(timelinesData);
        setStats(statsData);
      } catch (error) {
        console.error("Failed to load data:", error);
      } finally {
        setLoading(false);
      }
    }
    loadData();
  }, []);

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
                {(stats.queue as Record<string, number>)?.active || 0}
              </div>
              <div className="stat-label">Processing</div>
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

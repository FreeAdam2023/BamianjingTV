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
          listTimelines(false, true, 10), // Unreviewed timelines
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
      <main className="min-h-screen p-8">
        <div className="text-center">Loading...</div>
      </main>
    );
  }

  return (
    <main className="min-h-screen p-8">
      <div className="max-w-6xl mx-auto">
        <h1 className="text-4xl font-bold mb-2">Hardcore Player</h1>
        <p className="text-gray-400 mb-8">Learning video factory with bilingual subtitles</p>

        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-3 gap-4 mb-8">
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold">
                {(stats.timelines as Record<string, number>)?.pending || 0}
              </div>
              <div className="text-gray-400">Pending Review</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold">
                {(stats.timelines as Record<string, number>)?.reviewed || 0}
              </div>
              <div className="text-gray-400">Reviewed</div>
            </div>
            <div className="bg-gray-800 rounded-lg p-4">
              <div className="text-3xl font-bold">
                {(stats.queue as Record<string, number>)?.active || 0}
              </div>
              <div className="text-gray-400">Processing</div>
            </div>
          </div>
        )}

        {/* Navigation */}
        <div className="flex gap-4 mb-8">
          <Link
            href="/jobs"
            className="px-4 py-2 bg-blue-600 hover:bg-blue-700 rounded-lg"
          >
            View All Jobs
          </Link>
        </div>

        {/* Pending Reviews */}
        <h2 className="text-2xl font-bold mb-4">Pending Reviews</h2>
        {timelines.length === 0 ? (
          <div className="text-gray-400">No videos pending review</div>
        ) : (
          <div className="space-y-4">
            {timelines.map((timeline) => (
              <Link
                key={timeline.timeline_id}
                href={`/review/${timeline.timeline_id}`}
                className="block bg-gray-800 hover:bg-gray-700 rounded-lg p-4 transition"
              >
                <div className="flex justify-between items-start">
                  <div>
                    <h3 className="text-lg font-medium">{timeline.source_title}</h3>
                    <p className="text-gray-400 text-sm">
                      {formatDuration(timeline.source_duration)} &bull;{" "}
                      {timeline.total_segments} segments
                    </p>
                  </div>
                  <div className="text-right">
                    <div className="text-sm">
                      <span className="text-green-400">{timeline.keep_count} keep</span>
                      {" / "}
                      <span className="text-red-400">{timeline.drop_count} drop</span>
                      {" / "}
                      <span className="text-gray-400">{timeline.undecided_count} pending</span>
                    </div>
                    <div className="text-gray-400 text-sm">
                      {Math.round(timeline.review_progress)}% reviewed
                    </div>
                  </div>
                </div>
                <div className="mt-2 bg-gray-700 rounded-full h-2">
                  <div
                    className="bg-green-500 h-2 rounded-full"
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

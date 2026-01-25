"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { listJobs, createJob, formatDuration } from "@/lib/api";
import type { Job } from "@/lib/types";

export default function JobsPage() {
  const [jobs, setJobs] = useState<Job[]>([]);
  const [loading, setLoading] = useState(true);
  const [newUrl, setNewUrl] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    loadJobs();
  }, []);

  async function loadJobs() {
    try {
      const data = await listJobs(undefined, 50);
      setJobs(data);
    } catch (error) {
      console.error("Failed to load jobs:", error);
    } finally {
      setLoading(false);
    }
  }

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

  function getStatusColor(status: string): string {
    switch (status) {
      case "completed":
        return "text-green-400";
      case "failed":
        return "text-red-400";
      case "awaiting_review":
        return "text-yellow-400";
      default:
        return "text-blue-400";
    }
  }

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
        <div className="flex items-center justify-between mb-8">
          <div>
            <h1 className="text-4xl font-bold">Jobs</h1>
            <p className="text-gray-400">Video processing queue</p>
          </div>
          <Link
            href="/"
            className="px-4 py-2 bg-gray-700 hover:bg-gray-600 rounded-lg"
          >
            Back to Dashboard
          </Link>
        </div>

        {/* New Job Form */}
        <form onSubmit={handleSubmit} className="mb-8">
          <div className="flex gap-4">
            <input
              type="url"
              value={newUrl}
              onChange={(e) => setNewUrl(e.target.value)}
              placeholder="Enter video URL (YouTube, etc.)"
              className="flex-1 px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:outline-none focus:border-blue-500"
              disabled={submitting}
            />
            <button
              type="submit"
              disabled={submitting || !newUrl.trim()}
              className="px-6 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-gray-600 rounded-lg"
            >
              {submitting ? "Adding..." : "Add Job"}
            </button>
          </div>
        </form>

        {/* Jobs List */}
        {jobs.length === 0 ? (
          <div className="text-gray-400">No jobs yet. Add a video URL to get started.</div>
        ) : (
          <div className="space-y-4">
            {jobs.map((job) => (
              <div
                key={job.id}
                className="bg-gray-800 rounded-lg p-4"
              >
                <div className="flex justify-between items-start">
                  <div className="flex-1">
                    <h3 className="text-lg font-medium">
                      {job.title || job.url}
                    </h3>
                    <p className="text-gray-400 text-sm">
                      {job.channel && `${job.channel} \u2022 `}
                      {job.duration ? formatDuration(job.duration) : "Processing..."}
                    </p>
                    <p className="text-gray-500 text-xs mt-1 truncate">
                      {job.url}
                    </p>
                  </div>
                  <div className="text-right ml-4">
                    <div className={`font-medium ${getStatusColor(job.status)}`}>
                      {job.status.replace(/_/g, " ")}
                    </div>
                    {job.progress > 0 && job.progress < 1 && (
                      <div className="text-gray-400 text-sm">
                        {Math.round(job.progress * 100)}%
                      </div>
                    )}
                    {job.timeline_id && (
                      <Link
                        href={`/review/${job.timeline_id}`}
                        className="text-blue-400 hover:text-blue-300 text-sm"
                      >
                        Review &rarr;
                      </Link>
                    )}
                  </div>
                </div>
                {job.progress > 0 && job.progress < 1 && (
                  <div className="mt-2 bg-gray-700 rounded-full h-2">
                    <div
                      className="bg-blue-500 h-2 rounded-full transition-all"
                      style={{ width: `${job.progress * 100}%` }}
                    />
                  </div>
                )}
                {job.error && (
                  <div className="mt-2 text-red-400 text-sm">
                    Error: {job.error}
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

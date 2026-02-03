"use client";

import Link from "next/link";
import { useEffect, useState, useCallback } from "react";
import {
  listSessions,
  createSession,
  deleteSession,
  getSceneMindStats,
  formatTimecode,
  formatEpisode,
} from "@/lib/scenemind-api";
import type { SessionSummary, SessionCreate, SceneMindStats } from "@/lib/scenemind-api";
import { useToast } from "@/components/ui/Toast";
import { useConfirm } from "@/components/ui/ConfirmDialog";

export default function SceneMindPage() {
  const [sessions, setSessions] = useState<SessionSummary[]>([]);
  const [stats, setStats] = useState<SceneMindStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [creating, setCreating] = useState(false);
  const toast = useToast();
  const confirm = useConfirm();

  // Form state
  const [formData, setFormData] = useState<SessionCreate>({
    show_name: "That '70s Show",
    season: 1,
    episode: 1,
    title: "",
    video_path: "",
    duration: 0,
  });

  const loadData = useCallback(async () => {
    try {
      const [sessionsData, statsData] = await Promise.all([
        listSessions(),
        getSceneMindStats(),
      ]);
      setSessions(sessionsData);
      setStats(statsData);
    } catch (error) {
      console.error("Failed to load data:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!formData.video_path) return;

    setCreating(true);
    try {
      const session = await createSession(formData);
      setSessions((prev) => [
        {
          ...session,
          session_id: session.session_id,
          show_name: session.show_name,
          season: session.season,
          episode: session.episode,
          title: session.title,
          duration: session.duration,
          status: session.status,
          current_time: session.current_time,
          observation_count: session.observation_count,
          created_at: session.created_at,
          updated_at: session.updated_at,
        },
        ...prev,
      ]);
      setShowCreateModal(false);
      setFormData({
        show_name: "That '70s Show",
        season: 1,
        episode: 1,
        title: "",
        video_path: "",
        duration: 0,
      });
      toast.success("Session created successfully");
    } catch (error) {
      console.error("Failed to create session:", error);
      toast.error("Failed to create session: " + (error instanceof Error ? error.message : "Unknown error"));
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (sessionId: string) => {
    const confirmed = await confirm({
      title: "Delete Session",
      message: "Delete this session and all its observations? This action cannot be undone.",
      confirmText: "Delete",
      cancelText: "Cancel",
      type: "danger",
    });

    if (!confirmed) return;

    try {
      await deleteSession(sessionId);
      setSessions((prev) => prev.filter((s) => s.session_id !== sessionId));
      toast.success("Session deleted successfully");
    } catch (error) {
      console.error("Failed to delete session:", error);
      toast.error("Failed to delete session");
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "watching":
        return <span className="badge badge-info">Watching</span>;
      case "paused":
        return <span className="badge badge-warning">Paused</span>;
      case "completed":
        return <span className="badge badge-success">Completed</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

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
            <Link href="/" className="text-gray-400 hover:text-white">
              <svg
                className="w-6 h-6"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
            <div className="w-10 h-10 rounded-xl bg-gradient-to-br from-purple-500 to-pink-600 flex items-center justify-center text-xl">
              🧠
            </div>
            <div>
              <h1 className="text-xl font-bold">SceneMind</h1>
              <p className="text-xs text-gray-500">Watch & Learn</p>
            </div>
          </div>
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary"
          >
            + New Session
          </button>
        </div>
      </header>

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* Stats */}
        {stats && (
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4 mb-8 animate-fade-in">
            <div className="stat-card">
              <div className="stat-value">{stats.total}</div>
              <div className="stat-label">Total Sessions</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-blue-400">{stats.watching}</div>
              <div className="stat-label">In Progress</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-green-400">{stats.completed}</div>
              <div className="stat-label">Completed</div>
            </div>
            <div className="stat-card">
              <div className="stat-value text-purple-400">
                {stats.total_observations}
              </div>
              <div className="stat-label">Observations</div>
            </div>
          </div>
        )}

        {/* Sessions List */}
        <div className="mb-6">
          <h2 className="text-2xl font-bold mb-4">Watching Sessions</h2>
        </div>

        {sessions.length === 0 ? (
          <div className="card text-center py-12">
            <div className="text-5xl mb-4">📺</div>
            <h3 className="text-xl font-medium mb-2">No watching sessions</h3>
            <p className="text-gray-400 mb-6">
              Start a new session to begin capturing observations
            </p>
            <button
              onClick={() => setShowCreateModal(true)}
              className="btn btn-primary inline-flex"
            >
              + New Session
            </button>
          </div>
        ) : (
          <div className="space-y-4 animate-fade-in">
            {sessions.map((session, index) => (
              <div
                key={session.session_id}
                className="card"
                style={{ animationDelay: `${index * 50}ms` }}
              >
                <div className="flex justify-between items-start gap-4">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-lg font-semibold">
                        {session.show_name}
                      </h3>
                      <span className="text-gray-500 font-mono text-sm">
                        {formatEpisode(session.season, session.episode)}
                      </span>
                      {getStatusBadge(session.status)}
                    </div>
                    <p className="text-gray-400 text-sm mb-1">{session.title}</p>
                    <p className="text-gray-500 text-xs">
                      {formatTimecode(session.current_time)} /{" "}
                      {formatTimecode(session.duration)} ·{" "}
                      {session.observation_count} observations
                    </p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Link
                      href={`/scenemind/${session.session_id}/watch`}
                      className="btn btn-primary"
                    >
                      {session.status === "watching" ? "Continue" : "Watch"}
                    </Link>
                    <button
                      onClick={() => handleDelete(session.session_id)}
                      className="btn btn-secondary text-red-400 hover:text-red-300"
                    >
                      <svg
                        className="w-4 h-4"
                        fill="none"
                        stroke="currentColor"
                        viewBox="0 0 24 24"
                      >
                        <path
                          strokeLinecap="round"
                          strokeLinejoin="round"
                          strokeWidth={2}
                          d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16"
                        />
                      </svg>
                    </button>
                  </div>
                </div>
                {/* Progress bar */}
                {session.duration > 0 && (
                  <div className="progress-bar mt-4">
                    <div
                      className="progress-fill bg-gradient-to-r from-purple-500 to-pink-400"
                      style={{
                        width: `${(session.current_time / session.duration) * 100}%`,
                      }}
                    />
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Create Session Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-[var(--card)] rounded-lg p-6 w-full max-w-md shadow-xl">
            <h2 className="text-xl font-bold mb-4">New Watching Session</h2>
            <form onSubmit={handleCreate}>
              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">
                    Show Name
                  </label>
                  <input
                    type="text"
                    value={formData.show_name}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, show_name: e.target.value }))
                    }
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg"
                    placeholder="e.g., That '70s Show"
                    required
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Season
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={formData.season}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          season: parseInt(e.target.value) || 1,
                        }))
                      }
                      className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg"
                      required
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">
                      Episode
                    </label>
                    <input
                      type="number"
                      min="1"
                      value={formData.episode}
                      onChange={(e) =>
                        setFormData((prev) => ({
                          ...prev,
                          episode: parseInt(e.target.value) || 1,
                        }))
                      }
                      className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg"
                      required
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Episode Title
                  </label>
                  <input
                    type="text"
                    value={formData.title}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, title: e.target.value }))
                    }
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg"
                    placeholder="e.g., That '70s Pilot"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1">
                    Video Path
                  </label>
                  <input
                    type="text"
                    value={formData.video_path}
                    onChange={(e) =>
                      setFormData((prev) => ({ ...prev, video_path: e.target.value }))
                    }
                    className="w-full px-3 py-2 bg-[var(--background)] border border-[var(--border)] rounded-lg font-mono text-sm"
                    placeholder="/path/to/video.mp4"
                    required
                  />
                  <p className="text-xs text-gray-500 mt-1">
                    Full path to the video file on the server
                  </p>
                </div>
              </div>

              <div className="flex justify-end gap-2 mt-6">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn btn-secondary"
                  disabled={creating}
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  className="btn btn-primary"
                  disabled={creating || !formData.video_path}
                >
                  {creating ? (
                    <>
                      <span className="spinner w-4 h-4 mr-2" />
                      Creating...
                    </>
                  ) : (
                    "Create Session"
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

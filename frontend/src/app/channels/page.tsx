"use client";

/**
 * Channel Management Page
 * Manage publishing channels (YouTube, etc.) and view publication history
 */

import Link from "next/link";
import { useEffect, useState, useCallback, Suspense } from "react";
import PageHeader from "@/components/ui/PageHeader";
import { useSearchParams } from "next/navigation";
import {
  listChannels,
  createChannel,
  deleteChannel,
  getChannelPublications,
  getChannel,
  startChannelOAuth,
  revokeChannelOAuth,
} from "@/lib/api";
import { useToast, useConfirm } from "@/components/ui";
import type {
  ChannelSummary,
  ChannelCreate,
  ChannelType,
  PublicationSummary,
  Channel,
} from "@/lib/types";

function ChannelsPageContent() {
  const searchParams = useSearchParams();
  const toast = useToast();
  const confirm = useConfirm();
  const [channels, setChannels] = useState<ChannelSummary[]>([]);
  const [channelDetails, setChannelDetails] = useState<Record<string, Channel>>({});
  const [selectedChannel, setSelectedChannel] = useState<string | null>(null);
  const [publications, setPublications] = useState<PublicationSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [publicationsLoading, setPublicationsLoading] = useState(false);
  const [showCreateModal, setShowCreateModal] = useState(false);
  const [createForm, setCreateForm] = useState<ChannelCreate>({
    name: "",
    type: "youtube",
    default_privacy: "private",
    default_tags: [],
  });
  const [creating, setCreating] = useState(false);
  const [tagsInput, setTagsInput] = useState("");
  const [authorizingChannel, setAuthorizingChannel] = useState<string | null>(null);
  const [oauthMessage, setOauthMessage] = useState<{ type: "success" | "error"; text: string } | null>(null);

  const loadChannels = useCallback(async () => {
    try {
      const data = await listChannels();
      console.log("[ChannelsPage] Loaded channels:", data.length);
      setChannels(data);

      // Load full details for each channel to get authorization status
      const details: Record<string, Channel> = {};
      for (const ch of data) {
        try {
          const full = await getChannel(ch.channel_id);
          details[ch.channel_id] = full;
        } catch (err) {
          console.error(`[ChannelsPage] Failed to load channel ${ch.channel_id}:`, err);
        }
      }
      setChannelDetails(details);
    } catch (error) {
      console.error("[ChannelsPage] Failed to load channels:", error);
    } finally {
      setLoading(false);
    }
  }, []);

  // Handle OAuth callback query params
  useEffect(() => {
    const oauth = searchParams.get("oauth");
    const channelId = searchParams.get("channel");
    const message = searchParams.get("message");

    if (oauth === "success") {
      setOauthMessage({ type: "success", text: `Channel authorized successfully!` });
      // Refresh channels to get updated status
      loadChannels();
      // Clear message after 5 seconds
      setTimeout(() => setOauthMessage(null), 5000);
    } else if (oauth === "error") {
      setOauthMessage({ type: "error", text: message || "Authorization failed" });
      setTimeout(() => setOauthMessage(null), 10000);
    }
  }, [searchParams, loadChannels]);

  const handleAuthorizeChannel = async (channelId: string) => {
    setAuthorizingChannel(channelId);
    try {
      console.log("[ChannelsPage] Starting OAuth for channel:", channelId);
      const result = await startChannelOAuth(channelId);
      console.log("[ChannelsPage] Redirecting to:", result.auth_url);
      // Redirect to Google OAuth
      window.location.href = result.auth_url;
    } catch (error) {
      console.error("[ChannelsPage] Failed to start OAuth:", error);
      toast.error("Authorization failed: " + (error as Error).message);
      setAuthorizingChannel(null);
    }
  };

  const handleRevokeAuth = async (channelId: string, channelName: string) => {
    const confirmed = await confirm({
      title: "Revoke Authorization",
      message: `Are you sure you want to revoke authorization for "${channelName}"? You'll need to re-authorize to publish.`,
      type: "warning",
      confirmText: "Revoke",
    });
    if (!confirmed) return;

    try {
      console.log("[ChannelsPage] Revoking OAuth for channel:", channelId);
      await revokeChannelOAuth(channelId);
      toast.success("Authorization revoked");
      loadChannels();
    } catch (error) {
      console.error("[ChannelsPage] Failed to revoke OAuth:", error);
      toast.error("Revoke failed: " + (error as Error).message);
    }
  };

  const loadPublications = useCallback(async (channelId: string) => {
    setPublicationsLoading(true);
    try {
      const data = await getChannelPublications(channelId);
      console.log("[ChannelsPage] Loaded publications for channel:", channelId, data.length);
      setPublications(data);
    } catch (error) {
      console.error("[ChannelsPage] Failed to load publications:", error);
      setPublications([]);
    } finally {
      setPublicationsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadChannels();
  }, [loadChannels]);

  useEffect(() => {
    if (selectedChannel) {
      loadPublications(selectedChannel);
    } else {
      setPublications([]);
    }
  }, [selectedChannel, loadPublications]);

  const handleCreateChannel = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);

    try {
      const channelData: ChannelCreate = {
        ...createForm,
        default_tags: tagsInput
          .split(",")
          .map((t) => t.trim())
          .filter(Boolean),
      };
      console.log("[ChannelsPage] Creating channel:", channelData);
      await createChannel(channelData);
      setShowCreateModal(false);
      setCreateForm({
        name: "",
        type: "youtube",
        default_privacy: "private",
        default_tags: [],
      });
      setTagsInput("");
      loadChannels();
    } catch (error) {
      console.error("[ChannelsPage] Failed to create channel:", error);
      toast.error("Failed to create channel: " + (error as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteChannel = async (channelId: string, channelName: string) => {
    const confirmed = await confirm({
      title: "Delete Channel",
      message: `Are you sure you want to delete "${channelName}"? This action cannot be undone.`,
      type: "danger",
      confirmText: "Delete",
    });
    if (!confirmed) return;

    try {
      console.log("[ChannelsPage] Deleting channel:", channelId);
      await deleteChannel(channelId);
      if (selectedChannel === channelId) {
        setSelectedChannel(null);
      }
      toast.success("Channel deleted");
      loadChannels();
    } catch (error) {
      console.error("[ChannelsPage] Failed to delete channel:", error);
      toast.error("Delete failed: " + (error as Error).message);
    }
  };

  const getChannelTypeIcon = (type: ChannelType) => {
    switch (type) {
      case "youtube":
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z" />
          </svg>
        );
      case "telegram":
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M11.944 0A12 12 0 0 0 0 12a12 12 0 0 0 12 12 12 12 0 0 0 12-12A12 12 0 0 0 12 0a12 12 0 0 0-.056 0zm4.962 7.224c.1-.002.321.023.465.14a.506.506 0 0 1 .171.325c.016.093.036.306.02.472-.18 1.898-.962 6.502-1.36 8.627-.168.9-.499 1.201-.82 1.23-.696.065-1.225-.46-1.9-.902-1.056-.693-1.653-1.124-2.678-1.8-1.185-.78-.417-1.21.258-1.91.177-.184 3.247-2.977 3.307-3.23.007-.032.014-.15-.056-.212s-.174-.041-.249-.024c-.106.024-1.793 1.14-5.061 3.345-.48.33-.913.49-1.302.48-.428-.008-1.252-.241-1.865-.44-.752-.245-1.349-.374-1.297-.789.027-.216.325-.437.893-.663 3.498-1.524 5.83-2.529 6.998-3.014 3.332-1.386 4.025-1.627 4.476-1.635z" />
          </svg>
        );
      case "bilibili":
        return (
          <svg className="w-5 h-5" fill="currentColor" viewBox="0 0 24 24">
            <path d="M17.813 4.653h.854c1.51.054 2.769.578 3.773 1.574 1.004.995 1.524 2.249 1.56 3.76v7.36c-.036 1.51-.556 2.769-1.56 3.773s-2.262 1.524-3.773 1.56H5.333c-1.51-.036-2.769-.556-3.773-1.56S.036 18.858 0 17.347v-7.36c.036-1.511.556-2.765 1.56-3.76 1.004-.996 2.262-1.52 3.773-1.574h.774l-1.174-1.12a1.234 1.234 0 0 1-.373-.906c0-.356.124-.658.373-.907l.027-.027c.267-.249.573-.373.907-.373.355 0 .657.124.906.373L8.96 4.653h6.08l2.174-2.187c.249-.249.551-.373.906-.373.355 0 .658.124.907.373.248.249.373.551.373.907 0 .355-.125.657-.373.906L17.813 4.653zM5.333 7.24c-.746.018-1.373.276-1.88.773-.506.498-.769 1.13-.786 1.894v7.52c.017.764.28 1.395.786 1.893.507.498 1.134.756 1.88.773h13.334c.746-.017 1.373-.275 1.88-.773.506-.498.769-1.129.786-1.893v-7.52c-.017-.765-.28-1.396-.786-1.894-.507-.497-1.134-.755-1.88-.773H5.333zm4 5.867c-.355 0-.658-.124-.907-.373-.248-.249-.373-.551-.373-.907s.125-.658.373-.907c.249-.248.552-.373.907-.373s.657.125.906.373c.249.249.373.552.373.907s-.124.658-.373.907c-.249.249-.551.373-.906.373zm5.333 0c-.355 0-.658-.124-.907-.373-.248-.249-.373-.551-.373-.907s.125-.658.373-.907c.249-.248.552-.373.907-.373s.657.125.906.373c.249.249.373.552.373.907s-.124.658-.373.907c-.249.249-.551.373-.906.373z" />
          </svg>
        );
      default:
        return null;
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "active":
        return <span className="badge badge-success">Active</span>;
      case "disconnected":
        return <span className="badge badge-warning">Disconnected</span>;
      case "error":
        return <span className="badge badge-danger">Error</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  const getPublicationStatusBadge = (status: string) => {
    switch (status) {
      case "published":
        return <span className="badge badge-success">Published</span>;
      case "publishing":
        return <span className="badge badge-info animate-pulse">Publishing</span>;
      case "draft":
        return <span className="badge bg-gray-600">Draft</span>;
      case "failed":
        return <span className="badge badge-danger">Failed</span>;
      default:
        return <span className="badge">{status}</span>;
    }
  };

  const formatDate = (dateStr: string | null) => {
    if (!dateStr) return "-";
    return new Date(dateStr).toLocaleDateString("zh-CN", {
      year: "numeric",
      month: "short",
      day: "numeric",
    });
  };

  if (loading) {
    return (
      <main className="min-h-screen flex items-center justify-center">
        <div className="text-center">
          <div className="spinner mx-auto mb-4" />
          <p className="text-gray-400">Loading channels...</p>
        </div>
      </main>
    );
  }

  return (
    <main className="min-h-screen">
      <PageHeader
        title="Publishing Channels"
        subtitle="Manage YouTube channels and publication history"
        backHref="/"
        actions={
          <button
            onClick={() => setShowCreateModal(true)}
            className="btn btn-primary"
          >
            + Add Channel
          </button>
        }
      />

      <div className="max-w-6xl mx-auto px-6 py-8">
        {/* OAuth Status Message */}
        {oauthMessage && (
          <div
            className={`mb-6 p-4 rounded-lg flex items-center justify-between ${
              oauthMessage.type === "success"
                ? "bg-green-900/50 border border-green-700 text-green-300"
                : "bg-red-900/50 border border-red-700 text-red-300"
            }`}
          >
            <div className="flex items-center gap-3">
              {oauthMessage.type === "success" ? (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                </svg>
              ) : (
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              <span>{oauthMessage.text}</span>
            </div>
            <button
              onClick={() => setOauthMessage(null)}
              className="text-gray-400 hover:text-white"
            >
              <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          </div>
        )}

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Channels List */}
          <div className="lg:col-span-1">
            <h2 className="text-lg font-semibold mb-4">Channels</h2>
            {channels.length === 0 ? (
              <div className="card text-center py-8">
                <div className="text-4xl mb-3">📺</div>
                <p className="text-gray-400 mb-4">No channels configured</p>
                <button
                  onClick={() => setShowCreateModal(true)}
                  className="btn btn-primary"
                >
                  Add Your First Channel
                </button>
              </div>
            ) : (
              <div className="space-y-3">
                {channels.map((channel) => {
                  const details = channelDetails[channel.channel_id];
                  const isAuthorized = details?.is_authorized ?? false;

                  return (
                    <div
                      key={channel.channel_id}
                      className={`card card-hover cursor-pointer transition-all ${
                        selectedChannel === channel.channel_id
                          ? "ring-2 ring-blue-500"
                          : ""
                      }`}
                      onClick={() => setSelectedChannel(channel.channel_id)}
                    >
                      <div className="flex items-start justify-between">
                        <div className="flex items-center gap-3">
                          <div
                            className={`w-10 h-10 rounded-lg flex items-center justify-center ${
                              channel.type === "youtube"
                                ? "bg-red-500/20 text-red-400"
                                : channel.type === "telegram"
                                ? "bg-blue-500/20 text-blue-400"
                                : "bg-pink-500/20 text-pink-400"
                            }`}
                          >
                            {getChannelTypeIcon(channel.type)}
                          </div>
                          <div>
                            <h3 className="font-medium">{channel.name}</h3>
                            <p className="text-xs text-gray-500">
                              {channel.youtube_channel_name || channel.type}
                            </p>
                          </div>
                        </div>
                        <div className="flex items-center gap-2">
                          {isAuthorized ? (
                            <span className="badge badge-success flex items-center gap-1">
                              <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              Authorized
                            </span>
                          ) : (
                            <span className="badge bg-yellow-600 text-yellow-100">
                              Not Authorized
                            </span>
                          )}
                          <button
                            onClick={(e) => {
                              e.stopPropagation();
                              handleDeleteChannel(channel.channel_id, channel.name);
                            }}
                            className="p-1 text-gray-500 hover:text-red-400 transition-colors"
                            title="Delete channel"
                            aria-label="Delete channel"
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

                      {/* Authorization actions */}
                      <div className="mt-3 pt-3 border-t border-gray-700 flex items-center justify-between">
                        <span className="text-sm text-gray-500">
                          {channel.total_publications} publications
                        </span>
                        <div className="flex items-center gap-2">
                          {channel.type === "youtube" && (
                            isAuthorized ? (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleRevokeAuth(channel.channel_id, channel.name);
                                }}
                                className="text-xs px-2 py-1 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded"
                              >
                                Revoke
                              </button>
                            ) : (
                              <button
                                onClick={(e) => {
                                  e.stopPropagation();
                                  handleAuthorizeChannel(channel.channel_id);
                                }}
                                disabled={authorizingChannel === channel.channel_id}
                                className="text-xs px-2 py-1 bg-red-600 hover:bg-red-700 text-white rounded flex items-center gap-1 disabled:opacity-50"
                              >
                                {authorizingChannel === channel.channel_id ? (
                                  <>
                                    <svg className="animate-spin h-3 w-3" viewBox="0 0 24 24">
                                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                                    </svg>
                                    Redirecting...
                                  </>
                                ) : (
                                  <>
                                    <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 24 24">
                                      <path d="M19.615 3.184c-3.604-.246-11.631-.245-15.23 0-3.897.266-4.356 2.62-4.385 8.816.029 6.185.484 8.549 4.385 8.816 3.6.245 11.626.246 15.23 0 3.897-.266 4.356-2.62 4.385-8.816-.029-6.185-.484-8.549-4.385-8.816zm-10.615 12.816v-8l8 3.993-8 4.007z" />
                                    </svg>
                                    Authorize YouTube
                                  </>
                                )}
                              </button>
                            )
                          )}
                          {channel.last_published_at && (
                            <span className="text-xs text-gray-500">
                              Last: {formatDate(channel.last_published_at)}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* Publications List */}
          <div className="lg:col-span-2">
            <h2 className="text-lg font-semibold mb-4">
              {selectedChannel ? "Publication History" : "Select a Channel"}
            </h2>
            {!selectedChannel ? (
              <div className="card text-center py-12">
                <div className="text-5xl mb-4">👈</div>
                <p className="text-gray-400">
                  Select a channel to view its publication history
                </p>
              </div>
            ) : publicationsLoading ? (
              <div className="card text-center py-12">
                <div className="spinner mx-auto mb-4" />
                <p className="text-gray-400">Loading publications...</p>
              </div>
            ) : publications.length === 0 ? (
              <div className="card text-center py-12">
                <div className="text-5xl mb-4">📭</div>
                <p className="text-gray-400">No publications for this channel yet</p>
              </div>
            ) : (
              <div className="space-y-3">
                {publications.map((pub) => (
                  <div key={pub.publication_id} className="card">
                    <div className="flex items-start justify-between gap-4">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1">
                          <h3 className="font-medium truncate">{pub.title}</h3>
                          {getPublicationStatusBadge(pub.status)}
                        </div>
                        <p className="text-sm text-gray-500">
                          Created: {formatDate(pub.created_at)}
                          {pub.published_at && ` · Published: ${formatDate(pub.published_at)}`}
                        </p>
                      </div>
                      <div className="flex items-center gap-4">
                        {pub.platform_views > 0 && (
                          <span className="text-sm text-gray-400">
                            {pub.platform_views.toLocaleString()} views
                          </span>
                        )}
                        {pub.platform_url && (
                          <a
                            href={pub.platform_url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="text-blue-400 hover:text-blue-300"
                          >
                            <svg
                              className="w-5 h-5"
                              fill="none"
                              stroke="currentColor"
                              viewBox="0 0 24 24"
                            >
                              <path
                                strokeLinecap="round"
                                strokeLinejoin="round"
                                strokeWidth={2}
                                d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"
                              />
                            </svg>
                          </a>
                        )}
                        <Link
                          href={`/review/${pub.timeline_id}`}
                          className="text-gray-400 hover:text-white"
                          title="View timeline"
                          aria-label="View timeline"
                        >
                          <svg
                            className="w-5 h-5"
                            fill="none"
                            stroke="currentColor"
                            viewBox="0 0 24 24"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"
                            />
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              strokeWidth={2}
                              d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"
                            />
                          </svg>
                        </Link>
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Create Channel Modal */}
      {showCreateModal && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="card max-w-md w-full mx-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-xl font-bold">Add Channel</h2>
              <button
                onClick={() => setShowCreateModal(false)}
                className="text-gray-400 hover:text-white"
              >
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
                    d="M6 18L18 6M6 6l12 12"
                  />
                </svg>
              </button>
            </div>

            <form onSubmit={handleCreateChannel} className="space-y-4">
              <div>
                <label className="block text-sm font-medium mb-1">
                  Channel Name
                </label>
                <input
                  type="text"
                  value={createForm.name}
                  onChange={(e) =>
                    setCreateForm({ ...createForm, name: e.target.value })
                  }
                  placeholder="e.g., Main Channel, English Learning"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">Type</label>
                <select
                  value={createForm.type}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      type: e.target.value as ChannelType,
                    })
                  }
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="youtube">YouTube</option>
                  <option value="telegram" disabled>
                    Telegram (Coming Soon)
                  </option>
                  <option value="bilibili" disabled>
                    Bilibili (Coming Soon)
                  </option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  YouTube Channel ID (Optional)
                </label>
                <input
                  type="text"
                  value={createForm.youtube_channel_id || ""}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      youtube_channel_id: e.target.value || undefined,
                    })
                  }
                  placeholder="UC..."
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
                <p className="text-xs text-gray-500 mt-1">
                  Leave empty to use default authenticated channel
                </p>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Default Privacy
                </label>
                <select
                  value={createForm.default_privacy}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      default_privacy: e.target.value,
                    })
                  }
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                >
                  <option value="private">Private</option>
                  <option value="unlisted">Unlisted</option>
                  <option value="public">Public</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Default Tags (comma separated)
                </label>
                <input
                  type="text"
                  value={tagsInput}
                  onChange={(e) => setTagsInput(e.target.value)}
                  placeholder="english learning, podcast, interview"
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div>
                <label className="block text-sm font-medium mb-1">
                  Description Template (Optional)
                </label>
                <textarea
                  value={createForm.description_template || ""}
                  onChange={(e) =>
                    setCreateForm({
                      ...createForm,
                      description_template: e.target.value || undefined,
                    })
                  }
                  placeholder="Use {description} for generated description, {title} for title, {source_url} for source"
                  rows={3}
                  className="w-full px-3 py-2 bg-gray-800 border border-gray-700 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
                />
              </div>

              <div className="flex justify-end gap-3 pt-4">
                <button
                  type="button"
                  onClick={() => setShowCreateModal(false)}
                  className="btn btn-secondary"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating || !createForm.name}
                  className="btn btn-primary"
                >
                  {creating ? "Creating..." : "Create Channel"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </main>
  );
}

export default function ChannelsPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen flex items-center justify-center">
          <div className="text-center">
            <div className="spinner mx-auto mb-4" />
            <p className="text-gray-400">Loading channels...</p>
          </div>
        </main>
      }
    >
      <ChannelsPageContent />
    </Suspense>
  );
}

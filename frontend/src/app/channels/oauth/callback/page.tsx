"use client";

/**
 * OAuth Callback Page
 * Handles redirect from Google OAuth and passes data back to backend
 */

import { useEffect, useState, Suspense } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";

function OAuthCallbackContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const [status, setStatus] = useState<"processing" | "success" | "error">("processing");
  const [message, setMessage] = useState("");

  useEffect(() => {
    const code = searchParams.get("code");
    const state = searchParams.get("state");
    const error = searchParams.get("error");

    if (error) {
      setStatus("error");
      setMessage(`Authorization denied: ${error}`);
      return;
    }

    if (!code || !state) {
      setStatus("error");
      setMessage("Missing authorization code or state");
      return;
    }

    // Send code to backend to exchange for tokens
    const exchangeCode = async () => {
      try {
        const { protocol, hostname } = window.location;

        // If we're on localhost (OAuth redirect), try multiple backend URLs
        // Google OAuth redirects to localhost, but backend may be on LAN IP
        const backendUrls = hostname === "localhost" || hostname === "127.0.0.1"
          ? [
              `${protocol}//192.168.2.64:8001`,  // LAN backend
              `${protocol}//${hostname}:8001`,   // Local backend
            ]
          : [`${protocol}//${hostname}:8001`];

        let response: Response | null = null;
        let lastError: Error | null = null;

        for (const apiBase of backendUrls) {
          try {
            console.log(`[OAuth] Trying backend at ${apiBase}`);
            response = await fetch(
              `${apiBase}/channels/oauth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
              { redirect: "manual" }
            );
            if (response.ok || response.status === 302) {
              console.log(`[OAuth] Success with ${apiBase}`);
              break;
            }
          } catch (e) {
            console.warn(`[OAuth] Failed to reach ${apiBase}:`, e);
            lastError = e instanceof Error ? e : new Error(String(e));
          }
        }

        if (!response) {
          throw lastError || new Error("Could not reach backend");
        }

        // The backend will redirect, so we follow it manually
        if (response.type === "opaqueredirect" || response.status === 302) {
          const redirectUrl = response.headers.get("Location");
          if (redirectUrl) {
            window.location.href = redirectUrl;
            return;
          }
        }

        // If we got a direct response, check for success/error
        if (response.ok) {
          setStatus("success");
          setMessage("Authorization successful!");
          // Redirect to channels page after a short delay
          // If on localhost, redirect to actual frontend
          setTimeout(() => {
            if (hostname === "localhost" || hostname === "127.0.0.1") {
              window.location.href = "http://192.168.2.64:3001/channels?oauth=success";
            } else {
              router.push("/channels?oauth=success");
            }
          }, 1500);
        } else {
          const data = await response.json().catch(() => ({}));
          setStatus("error");
          setMessage(data.detail || "Authorization failed");
        }
      } catch (err) {
        console.error("OAuth callback error:", err);
        setStatus("error");
        setMessage(err instanceof Error ? err.message : "Unknown error");
      }
    };

    exchangeCode();
  }, [searchParams, router]);

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="card max-w-md text-center">
        {status === "processing" && (
          <>
            <div className="spinner mx-auto mb-4" />
            <h1 className="text-xl font-bold mb-2">Completing Authorization...</h1>
            <p className="text-gray-400">Please wait while we set up your channel.</p>
          </>
        )}

        {status === "success" && (
          <>
            <div className="text-5xl mb-4">✓</div>
            <h1 className="text-xl font-bold text-green-400 mb-2">Authorization Successful!</h1>
            <p className="text-gray-400 mb-4">{message}</p>
            <p className="text-gray-500 text-sm">Redirecting to channels...</p>
          </>
        )}

        {status === "error" && (
          <>
            <div className="text-5xl mb-4">✕</div>
            <h1 className="text-xl font-bold text-red-400 mb-2">Authorization Failed</h1>
            <p className="text-gray-400 mb-4">{message}</p>
            <a
              href={
                typeof window !== "undefined" &&
                (window.location.hostname === "localhost" || window.location.hostname === "127.0.0.1")
                  ? "http://192.168.2.64:3001/channels"
                  : "/channels"
              }
              className="btn btn-primary inline-block"
            >
              Back to Channels
            </a>
          </>
        )}
      </div>
    </main>
  );
}

export default function OAuthCallbackPage() {
  return (
    <Suspense
      fallback={
        <main className="min-h-screen flex items-center justify-center">
          <div className="card max-w-md text-center">
            <div className="spinner mx-auto mb-4" />
            <h1 className="text-xl font-bold mb-2">Loading...</h1>
          </div>
        </main>
      }
    >
      <OAuthCallbackContent />
    </Suspense>
  );
}

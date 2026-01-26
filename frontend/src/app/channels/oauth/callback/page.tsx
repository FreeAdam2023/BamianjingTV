"use client";

/**
 * OAuth Callback Page
 * Handles redirect from Google OAuth and passes data back to backend
 */

import { useEffect, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import Link from "next/link";

export default function OAuthCallbackPage() {
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
        const apiBase = `${protocol}//${hostname}:8000`;

        const response = await fetch(
          `${apiBase}/channels/oauth/callback?code=${encodeURIComponent(code)}&state=${encodeURIComponent(state)}`,
          { redirect: "manual" }
        );

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
          setTimeout(() => {
            router.push("/channels?oauth=success");
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
            <Link href="/channels" className="btn btn-primary">
              Back to Channels
            </Link>
          </>
        )}
      </div>
    </main>
  );
}

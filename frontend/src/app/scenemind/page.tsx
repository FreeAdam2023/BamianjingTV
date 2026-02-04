"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";

export default function SceneMindRedirect() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/");
  }, [router]);

  return (
    <main className="min-h-screen flex items-center justify-center">
      <div className="text-center">
        <div className="spinner mx-auto mb-4" />
        <p className="text-gray-400">Redirecting...</p>
      </div>
    </main>
  );
}

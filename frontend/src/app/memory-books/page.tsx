"use client";

/**
 * Memory Books Page - View and manage word/entity collections
 */

import Link from "next/link";
import { MemoryBookList } from "@/components/MemoryBook";

export default function MemoryBooksPage() {
  return (
    <div className="min-h-screen bg-gray-900">
      {/* Header */}
      <header className="border-b border-gray-800 bg-gray-900/95 backdrop-blur sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div className="flex items-center gap-4">
            <Link
              href="/"
              className="text-gray-500 hover:text-gray-300 transition-colors"
            >
              <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 19l-7-7m0 0l7-7m-7 7h18" />
              </svg>
            </Link>
            <h1 className="text-xl font-semibold text-gray-100">Memory Books</h1>
          </div>
          <div className="flex items-center gap-2 text-sm text-gray-500">
            <span>Collect words and entities while learning</span>
          </div>
        </div>
      </header>

      {/* Main content */}
      <main className="h-[calc(100vh-65px)]">
        <MemoryBookList />
      </main>
    </div>
  );
}

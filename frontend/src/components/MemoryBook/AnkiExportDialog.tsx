"use client";

/**
 * AnkiExportDialog - Dialog for exporting memory book to Anki
 */

import { useState } from "react";
import type { MemoryBook } from "@/lib/types";
import { exportMemoryBookToAnki } from "@/lib/api";

interface AnkiExportDialogProps {
  book: MemoryBook;
  onClose: () => void;
}

export default function AnkiExportDialog({ book, onClose }: AnkiExportDialogProps) {
  const [isExporting, setIsExporting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const wordCount = book.items.filter((i) => i.target_type === "word").length;
  const entityCount = book.items.filter((i) => i.target_type === "entity").length;

  const handleExport = async () => {
    setIsExporting(true);
    setError(null);

    try {
      const blob = await exportMemoryBookToAnki(book.book_id);

      // Create download link
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${book.name.replace(/\s+/g, "_")}.apkg`;
      document.body.appendChild(link);
      link.click();
      document.body.removeChild(link);
      URL.revokeObjectURL(url);

      setSuccess(true);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Export failed");
    } finally {
      setIsExporting(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
      <div className="bg-gray-800 rounded-lg p-6 w-[480px] border border-gray-700">
        {/* Header */}
        <div className="flex items-center justify-between mb-6">
          <h3 className="text-lg font-semibold text-gray-100">Export to Anki</h3>
          <button
            onClick={onClose}
            className="text-gray-500 hover:text-gray-300"
          >
            <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {success ? (
          /* Success state */
          <div className="text-center py-8">
            <div className="w-16 h-16 mx-auto bg-green-500/20 rounded-full flex items-center justify-center mb-4">
              <svg className="w-8 h-8 text-green-500" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
              </svg>
            </div>
            <h4 className="text-lg font-medium text-gray-100 mb-2">Export Complete!</h4>
            <p className="text-sm text-gray-400 mb-6">
              Your Anki deck has been downloaded. Import it into Anki to start studying.
            </p>
            <button
              onClick={onClose}
              className="px-6 py-2 bg-blue-600 text-white rounded hover:bg-blue-500"
            >
              Done
            </button>
          </div>
        ) : (
          /* Export form */
          <>
            {/* Collection info */}
            <div className="bg-gray-900 rounded-lg p-4 mb-6">
              <h4 className="font-medium text-gray-200 mb-3">{book.name}</h4>
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div className="flex items-center gap-2">
                  <span className="text-blue-400">Words:</span>
                  <span className="text-gray-300">{wordCount}</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="text-green-400">Entities:</span>
                  <span className="text-gray-300">{entityCount}</span>
                </div>
              </div>
            </div>

            {/* Info */}
            <div className="bg-blue-500/10 border border-blue-500/30 rounded-lg p-4 mb-6">
              <div className="flex gap-3">
                <svg className="w-5 h-5 text-blue-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <div className="text-sm text-gray-300">
                  <p className="mb-2">This will create an Anki deck with:</p>
                  <ul className="list-disc list-inside space-y-1 text-gray-400">
                    <li><strong>Words:</strong> Recognition and recall cards with pronunciation, definition, and examples</li>
                    <li><strong>Entities:</strong> Knowledge cards with description and Wikipedia links</li>
                  </ul>
                </div>
              </div>
            </div>

            {/* Error */}
            {error && (
              <div className="bg-red-500/10 border border-red-500/30 rounded-lg p-3 mb-6 text-sm text-red-400">
                {error}
              </div>
            )}

            {/* Actions */}
            <div className="flex justify-end gap-3">
              <button
                onClick={onClose}
                className="px-4 py-2 text-gray-400 hover:text-gray-200"
              >
                Cancel
              </button>
              <button
                onClick={handleExport}
                disabled={isExporting || book.item_count === 0}
                className="px-6 py-2 bg-green-600 text-white rounded hover:bg-green-500 disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
              >
                {isExporting ? (
                  <>
                    <span className="inline-block w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                    Exporting...
                  </>
                ) : (
                  <>
                    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                    </svg>
                    Download .apkg
                  </>
                )}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

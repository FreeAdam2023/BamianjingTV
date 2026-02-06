"use client";

/**
 * MemoryBookList - Display and manage memory books
 */

import { useState, useEffect, useCallback } from "react";
import type { MemoryBook, MemoryBookSummary, MemoryItem } from "@/lib/types";
import {
  listMemoryBooks,
  getMemoryBook,
  createMemoryBook,
  deleteMemoryBook,
  getAnkiExportUrl,
} from "@/lib/api";
import MemoryItemCard from "./MemoryItemCard";
import AnkiExportDialog from "./AnkiExportDialog";

interface MemoryBookListProps {
  defaultBookId?: string;
}

export default function MemoryBookList({ defaultBookId }: MemoryBookListProps) {
  const [books, setBooks] = useState<MemoryBookSummary[]>([]);
  const [selectedBook, setSelectedBook] = useState<MemoryBook | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [newBookName, setNewBookName] = useState("");
  const [creating, setCreating] = useState(false);
  const [showExportDialog, setShowExportDialog] = useState(false);
  const [filterType, setFilterType] = useState<"all" | "word" | "entity" | "observation">("all");

  // Load books list
  const loadBooks = useCallback(async () => {
    try {
      setLoading(true);
      const data = await listMemoryBooks();
      setBooks(data);

      // Auto-select default book or first book
      if (data.length > 0) {
        const bookToSelect = defaultBookId
          ? data.find((b) => b.book_id === defaultBookId) || data[0]
          : data[0];
        const fullBook = await getMemoryBook(bookToSelect.book_id);
        setSelectedBook(fullBook);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载收藏夹失败");
    } finally {
      setLoading(false);
    }
  }, [defaultBookId]);

  useEffect(() => {
    loadBooks();
  }, [loadBooks]);

  const handleSelectBook = async (bookId: string) => {
    try {
      setLoading(true);
      const book = await getMemoryBook(bookId);
      setSelectedBook(book);
    } catch (err) {
      setError(err instanceof Error ? err.message : "加载收藏夹失败");
    } finally {
      setLoading(false);
    }
  };

  const handleCreateBook = async () => {
    if (!newBookName.trim()) return;
    setCreating(true);
    try {
      const book = await createMemoryBook({ name: newBookName.trim() });
      setBooks((prev) => [
        {
          book_id: book.book_id,
          name: book.name,
          description: book.description,
          item_count: book.item_count,
          created_at: book.created_at,
          updated_at: book.updated_at,
        },
        ...prev,
      ]);
      setSelectedBook(book);
      setShowCreateDialog(false);
      setNewBookName("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "创建收藏夹失败");
    } finally {
      setCreating(false);
    }
  };

  const handleDeleteBook = async (bookId: string) => {
    if (!confirm("确定删除此收藏夹？此操作无法撤销。")) return;
    try {
      await deleteMemoryBook(bookId);
      setBooks((prev) => prev.filter((b) => b.book_id !== bookId));
      if (selectedBook?.book_id === bookId) {
        setSelectedBook(null);
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "删除收藏夹失败");
    }
  };

  const handleItemDelete = (itemId: string) => {
    if (!selectedBook) return;
    setSelectedBook({
      ...selectedBook,
      items: selectedBook.items.filter((i) => i.item_id !== itemId),
      item_count: selectedBook.item_count - 1,
    });
    // Update summary in books list
    setBooks((prev) =>
      prev.map((b) =>
        b.book_id === selectedBook.book_id
          ? { ...b, item_count: b.item_count - 1 }
          : b
      )
    );
  };

  const handleItemUpdate = (updated: MemoryItem) => {
    if (!selectedBook) return;
    setSelectedBook({
      ...selectedBook,
      items: selectedBook.items.map((i) =>
        i.item_id === updated.item_id ? updated : i
      ),
    });
  };

  const filteredItems = selectedBook?.items.filter((item) => {
    if (filterType === "all") return true;
    return item.target_type === filterType;
  }) || [];

  if (loading && books.length === 0) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="animate-spin rounded-full h-8 w-8 border-t-2 border-b-2 border-blue-500" />
      </div>
    );
  }

  return (
    <div className="h-full flex">
      {/* Sidebar - Book List */}
      <div className="w-64 border-r border-gray-700 flex flex-col">
        <div className="p-4 border-b border-gray-700">
          <h2 className="text-lg font-semibold text-gray-100">记忆收藏夹</h2>
          <button
            onClick={() => setShowCreateDialog(true)}
            className="mt-2 w-full px-3 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 text-sm"
          >
            + 新建收藏夹
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          {books.map((book) => (
            <div
              key={book.book_id}
              onClick={() => handleSelectBook(book.book_id)}
              className={`p-3 cursor-pointer border-b border-gray-800 hover:bg-gray-800 transition-colors ${
                selectedBook?.book_id === book.book_id ? "bg-gray-800" : ""
              }`}
            >
              <div className="flex items-center justify-between">
                <span className="font-medium text-gray-200">{book.name}</span>
                <span className="text-xs text-gray-500">{book.item_count}</span>
              </div>
            </div>
          ))}

          {books.length === 0 && (
            <div className="p-4 text-center text-gray-500 text-sm">
              暂无收藏夹，创建一个开始吧。
            </div>
          )}
        </div>
      </div>

      {/* Main Content - Items */}
      <div className="flex-1 flex flex-col">
        {selectedBook ? (
          <>
            {/* Header */}
            <div className="p-4 border-b border-gray-700 flex items-center justify-between">
              <div>
                <h1 className="text-xl font-semibold text-gray-100">{selectedBook.name}</h1>
                <p className="text-sm text-gray-500">
                  {selectedBook.item_count} 个项目
                </p>
              </div>
              <div className="flex items-center gap-2">
                {/* Filter */}
                <select
                  value={filterType}
                  onChange={(e) => setFilterType(e.target.value as typeof filterType)}
                  className="px-3 py-1.5 bg-gray-800 border border-gray-600 rounded text-sm text-gray-200"
                >
                  <option value="all">全部类型</option>
                  <option value="word">单词</option>
                  <option value="entity">实体</option>
                  <option value="observation">观察</option>
                </select>

                {/* Export button */}
                <button
                  onClick={() => setShowExportDialog(true)}
                  disabled={selectedBook.item_count === 0}
                  className="px-4 py-1.5 bg-green-600 text-white rounded hover:bg-green-500 text-sm disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
                >
                  <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4" />
                  </svg>
                  导出到 Anki
                </button>

                {/* Delete book */}
                <button
                  onClick={() => handleDeleteBook(selectedBook.book_id)}
                  className="p-1.5 rounded hover:bg-red-500/20 text-gray-500 hover:text-red-400"
                  title="删除收藏夹"
                  aria-label="删除收藏夹"
                >
                  <svg className="w-5 h-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                  </svg>
                </button>
              </div>
            </div>

            {/* Items grid */}
            <div className="flex-1 overflow-y-auto p-4">
              {filteredItems.length > 0 ? (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
                  {filteredItems.map((item) => (
                    <MemoryItemCard
                      key={item.item_id}
                      item={item}
                      bookId={selectedBook.book_id}
                      onDelete={handleItemDelete}
                      onUpdate={handleItemUpdate}
                    />
                  ))}
                </div>
              ) : (
                <div className="h-full flex items-center justify-center text-gray-500">
                  {filterType === "all"
                    ? "此收藏夹中暂无项目。"
                    : `此收藏夹中暂无${filterType === "word" ? "单词" : filterType === "entity" ? "实体" : "观察"}。`}
                </div>
              )}
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-gray-500">
            选择一个收藏夹查看内容
          </div>
        )}
      </div>

      {/* Create Dialog */}
      {showCreateDialog && (
        <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50">
          <div className="bg-gray-800 rounded-lg p-6 w-96 border border-gray-700">
            <h3 className="text-lg font-semibold text-gray-100 mb-4">
              新建收藏夹
            </h3>
            <input
              type="text"
              value={newBookName}
              onChange={(e) => setNewBookName(e.target.value)}
              placeholder="收藏夹名称"
              className="w-full px-4 py-2 bg-gray-900 border border-gray-600 rounded text-gray-200 focus:outline-none focus:border-blue-500"
              autoFocus
              onKeyDown={(e) => {
                if (e.key === "Enter") handleCreateBook();
                if (e.key === "Escape") setShowCreateDialog(false);
              }}
            />
            <div className="mt-4 flex justify-end gap-2">
              <button
                onClick={() => {
                  setShowCreateDialog(false);
                  setNewBookName("");
                }}
                className="px-4 py-2 text-gray-400 hover:text-gray-200"
              >
                取消
              </button>
              <button
                onClick={handleCreateBook}
                disabled={!newBookName.trim() || creating}
                className="px-4 py-2 bg-blue-600 text-white rounded hover:bg-blue-500 disabled:opacity-50"
              >
                {creating ? "创建中..." : "创建"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Export Dialog */}
      {showExportDialog && selectedBook && (
        <AnkiExportDialog
          book={selectedBook}
          onClose={() => setShowExportDialog(false)}
        />
      )}

      {/* Error Toast */}
      {error && (
        <div className="fixed bottom-4 right-4 bg-red-600 text-white px-4 py-2 rounded shadow-lg">
          {error}
          <button
            onClick={() => setError(null)}
            className="ml-2 text-white/70 hover:text-white"
          >
            ×
          </button>
        </div>
      )}
    </div>
  );
}

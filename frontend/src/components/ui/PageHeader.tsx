"use client";

/**
 * PageHeader - Unified header component for all pages
 *
 * Ensures consistent styling across the application:
 * - Sticky positioning with backdrop blur
 * - Consistent border and background
 * - Standard container width and padding
 */

import Link from "next/link";
import { ReactNode } from "react";

interface PageHeaderProps {
  /** Page title */
  title: string;
  /** Optional subtitle/description */
  subtitle?: string;
  /** Optional icon (emoji or ReactNode) */
  icon?: ReactNode;
  /** Icon background gradient (e.g., "from-blue-500 to-purple-600") */
  iconGradient?: string;
  /** Show back button linking to this path */
  backHref?: string;
  /** Right side actions */
  actions?: ReactNode;
  /** Additional content below title */
  children?: ReactNode;
}

export default function PageHeader({
  title,
  subtitle,
  icon,
  iconGradient = "from-blue-500 to-purple-600",
  backHref,
  actions,
  children,
}: PageHeaderProps) {
  return (
    <header className="border-b border-[var(--border)] bg-[var(--card)]/50 backdrop-blur-sm sticky top-0 z-50">
      <div className="max-w-6xl mx-auto px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          {/* Back button */}
          {backHref && (
            <Link
              href={backHref}
              className="text-gray-400 hover:text-white transition-colors"
              aria-label="Go back"
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
                  d="M15 19l-7-7 7-7"
                />
              </svg>
            </Link>
          )}

          {/* Icon */}
          {icon && (
            <div
              className={`w-10 h-10 rounded-xl bg-gradient-to-br ${iconGradient} flex items-center justify-center text-xl`}
            >
              {icon}
            </div>
          )}

          {/* Title & Subtitle */}
          <div>
            <h1 className="text-xl font-bold">{title}</h1>
            {subtitle && (
              <p className="text-xs text-gray-500">{subtitle}</p>
            )}
          </div>
        </div>

        {/* Actions */}
        {actions && (
          <div className="flex items-center gap-3">{actions}</div>
        )}
      </div>

      {/* Additional content */}
      {children && (
        <div className="max-w-6xl mx-auto px-6 pb-4">{children}</div>
      )}
    </header>
  );
}

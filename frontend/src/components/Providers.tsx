"use client";

/**
 * Client-side providers wrapper
 */

import { ReactNode } from "react";
import { ToastProvider, ConfirmProvider } from "@/components/ui";

export default function Providers({ children }: { children: ReactNode }) {
  return (
    <ToastProvider>
      <ConfirmProvider>{children}</ConfirmProvider>
    </ToastProvider>
  );
}

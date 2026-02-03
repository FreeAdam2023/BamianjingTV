"use client";

import { useState, useRef, useCallback, useEffect } from "react";
import type { CropRegion } from "@/lib/scenemind-api";

interface CropSelectorProps {
  videoElement: HTMLVideoElement | null;
  active: boolean;
  onCropSelect: (region: CropRegion | null) => void;
  onCancel: () => void;
}

export default function CropSelector({
  videoElement,
  active,
  onCropSelect,
  onCancel,
}: CropSelectorProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const [isDrawing, setIsDrawing] = useState(false);
  const [startPoint, setStartPoint] = useState<{ x: number; y: number } | null>(null);
  const [currentRegion, setCurrentRegion] = useState<CropRegion | null>(null);

  // Get video dimensions
  const getVideoDimensions = useCallback(() => {
    if (!videoElement) return { width: 0, height: 0, offsetX: 0, offsetY: 0 };

    const rect = videoElement.getBoundingClientRect();
    const videoWidth = videoElement.videoWidth;
    const videoHeight = videoElement.videoHeight;

    // Calculate displayed size maintaining aspect ratio
    const containerAspect = rect.width / rect.height;
    const videoAspect = videoWidth / videoHeight;

    let displayWidth: number;
    let displayHeight: number;
    let offsetX: number;
    let offsetY: number;

    if (containerAspect > videoAspect) {
      // Container is wider - letterbox on sides
      displayHeight = rect.height;
      displayWidth = displayHeight * videoAspect;
      offsetX = (rect.width - displayWidth) / 2;
      offsetY = 0;
    } else {
      // Container is taller - letterbox on top/bottom
      displayWidth = rect.width;
      displayHeight = displayWidth / videoAspect;
      offsetX = 0;
      offsetY = (rect.height - displayHeight) / 2;
    }

    return {
      width: displayWidth,
      height: displayHeight,
      offsetX,
      offsetY,
      videoWidth,
      videoHeight,
      rect,
    };
  }, [videoElement]);

  // Convert screen coordinates to video coordinates
  const screenToVideo = useCallback(
    (screenX: number, screenY: number) => {
      const dims = getVideoDimensions();
      if (!dims.rect) return { x: 0, y: 0 };

      const relX = screenX - dims.rect.left - dims.offsetX;
      const relY = screenY - dims.rect.top - dims.offsetY;

      const videoX = Math.round((relX / dims.width) * dims.videoWidth);
      const videoY = Math.round((relY / dims.height) * dims.videoHeight);

      return {
        x: Math.max(0, Math.min(dims.videoWidth, videoX)),
        y: Math.max(0, Math.min(dims.videoHeight, videoY)),
      };
    },
    [getVideoDimensions]
  );

  // Handle mouse events
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      if (!active) return;

      const point = screenToVideo(e.clientX, e.clientY);
      setStartPoint(point);
      setIsDrawing(true);
      setCurrentRegion(null);
    },
    [active, screenToVideo]
  );

  const handleMouseMove = useCallback(
    (e: React.MouseEvent) => {
      if (!isDrawing || !startPoint) return;

      const point = screenToVideo(e.clientX, e.clientY);
      const dims = getVideoDimensions();

      const x = Math.min(startPoint.x, point.x);
      const y = Math.min(startPoint.y, point.y);
      const width = Math.abs(point.x - startPoint.x);
      const height = Math.abs(point.y - startPoint.y);

      // Clamp to video bounds
      const region: CropRegion = {
        x: Math.max(0, x),
        y: Math.max(0, y),
        width: Math.min(width, (dims.videoWidth || 1920) - x),
        height: Math.min(height, (dims.videoHeight || 1080) - y),
      };

      setCurrentRegion(region);
    },
    [isDrawing, startPoint, screenToVideo, getVideoDimensions]
  );

  const handleMouseUp = useCallback(() => {
    if (!isDrawing) return;
    setIsDrawing(false);

    // Minimum size check (at least 20x20 pixels)
    if (currentRegion && currentRegion.width > 20 && currentRegion.height > 20) {
      onCropSelect(currentRegion);
    } else {
      setCurrentRegion(null);
    }
  }, [isDrawing, currentRegion, onCropSelect]);

  // Draw selection overlay
  useEffect(() => {
    if (!active || !canvasRef.current || !videoElement) return;

    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const rect = videoElement.getBoundingClientRect();
    canvas.width = rect.width;
    canvas.height = rect.height;

    // Clear canvas
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    // Draw semi-transparent overlay
    ctx.fillStyle = "rgba(0, 0, 0, 0.5)";
    ctx.fillRect(0, 0, canvas.width, canvas.height);

    if (currentRegion) {
      const dims = getVideoDimensions();
      if (dims.width > 0 && dims.videoWidth && dims.videoHeight) {
        // Convert video coordinates to canvas coordinates
        const scaleX = dims.width / dims.videoWidth;
        const scaleY = dims.height / dims.videoHeight;

        const canvasX = dims.offsetX + currentRegion.x * scaleX;
        const canvasY = dims.offsetY + currentRegion.y * scaleY;
        const canvasWidth = currentRegion.width * scaleX;
        const canvasHeight = currentRegion.height * scaleY;

        // Clear the selected region (show video through)
        ctx.clearRect(canvasX, canvasY, canvasWidth, canvasHeight);

        // Draw border around selection
        ctx.strokeStyle = "#3b82f6";
        ctx.lineWidth = 2;
        ctx.strokeRect(canvasX, canvasY, canvasWidth, canvasHeight);

        // Draw size indicator
        ctx.fillStyle = "#3b82f6";
        ctx.font = "12px monospace";
        const sizeText = `${currentRegion.width}x${currentRegion.height}`;
        const textWidth = ctx.measureText(sizeText).width;
        ctx.fillRect(canvasX, canvasY - 20, textWidth + 8, 18);
        ctx.fillStyle = "white";
        ctx.fillText(sizeText, canvasX + 4, canvasY - 6);
      }
    }
  }, [active, videoElement, currentRegion, getVideoDimensions]);

  // Handle keyboard events
  useEffect(() => {
    if (!active) return;

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        onCancel();
      } else if (e.key === "Enter" && currentRegion) {
        onCropSelect(currentRegion);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [active, currentRegion, onCancel, onCropSelect]);

  if (!active || !videoElement) return null;

  return (
    <canvas
      ref={canvasRef}
      className="absolute inset-0 cursor-crosshair"
      style={{
        position: "absolute",
        top: 0,
        left: 0,
        width: "100%",
        height: "100%",
        pointerEvents: "auto",
      }}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onMouseLeave={handleMouseUp}
    />
  );
}

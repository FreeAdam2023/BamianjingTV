#!/usr/bin/env node

/**
 * Remotion Server-side Render Script
 *
 * Usage: node render.mjs --input <input.json> --output <output.mp4> [options]
 *
 * Input JSON format:
 * {
 *   "segments": [...],
 *   "config": RemotionConfig,
 *   "videoSrc": "path/to/video.mp4",
 *   "durationInFrames": 9000,
 *   "fps": 30,
 *   "width": 1920,
 *   "height": 1080
 * }
 */

import { bundle } from "@remotion/bundler";
import { renderMedia, selectComposition } from "@remotion/renderer";
import { createRequire } from "module";
import path from "path";
import fs from "fs";
import http from "http";
import { fileURLToPath } from "url";

const require = createRequire(import.meta.url);
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Parse command line arguments
function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    input: null,
    output: null,
    codec: "h264",
    crf: 18,
    concurrency: 2,
    composition: "SubtitleComposition",
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--input":
      case "-i":
        options.input = args[++i];
        break;
      case "--output":
      case "-o":
        options.output = args[++i];
        break;
      case "--codec":
        options.codec = args[++i];
        break;
      case "--crf":
        options.crf = parseInt(args[++i], 10);
        break;
      case "--concurrency":
        options.concurrency = parseInt(args[++i], 10);
        break;
      case "--composition":
        options.composition = args[++i];
        break;
    }
  }

  return options;
}

// Log progress in JSON format for Python to parse
function logProgress(data) {
  console.log(JSON.stringify({ type: "progress", ...data }));
}

function logError(message, error) {
  console.error(JSON.stringify({ type: "error", message, error: error?.message || String(error) }));
}

function logComplete(data) {
  console.log(JSON.stringify({ type: "complete", ...data }));
}

/**
 * Start a local HTTP server that serves arbitrary local files.
 * Used to make video files and cached card images accessible to
 * Remotion's headless Chrome during server-side rendering.
 */
function startLocalFileServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const filePath = decodeURIComponent(req.url.slice(1)); // strip leading /
      if (!filePath || !fs.existsSync(filePath)) {
        res.writeHead(404);
        res.end("Not found");
        return;
      }
      const stream = fs.createReadStream(filePath);
      stream.on("error", () => {
        res.writeHead(500);
        res.end("Read error");
      });
      stream.pipe(res);
    });
    server.listen(0, "127.0.0.1", () => {
      resolve({ server, port: server.address().port });
    });
  });
}

/**
 * Rewrite absolute paths and file:// URLs in the input config
 * to http://127.0.0.1:{port}/absolute/path so Chrome can fetch them.
 */
function rewriteLocalPaths(obj, port) {
  let json = JSON.stringify(obj);
  // file:///path → http://127.0.0.1:{port}/path
  json = json.replace(/file:\/\/\//g, `http://127.0.0.1:${port}/`);
  return JSON.parse(json);
}

async function main() {
  const options = parseArgs();

  if (!options.input || !options.output) {
    logError("Missing required arguments", "Usage: node render.mjs --input <input.json> --output <output.mp4>");
    process.exit(1);
  }

  // Read input configuration
  let inputConfig;
  try {
    const inputContent = fs.readFileSync(options.input, "utf-8");
    inputConfig = JSON.parse(inputContent);
  } catch (err) {
    logError("Failed to read input file", err);
    process.exit(1);
  }

  const {
    durationInFrames,
    fps = 30,
    width = 1920,
    height = 1080,
  } = inputConfig;

  // Start local file server for video and card images
  const { server: fileServer, port: filePort } = await startLocalFileServer();
  logProgress({ status: "file_server", port: filePort });

  // Rewrite videoSrc (absolute path) to HTTP URL
  if (inputConfig.videoSrc && path.isAbsolute(inputConfig.videoSrc)) {
    inputConfig.videoSrc = `http://127.0.0.1:${filePort}${inputConfig.videoSrc}`;
  }

  // Rewrite all file:// URLs in card data (cached images)
  inputConfig = rewriteLocalPaths(inputConfig, filePort);

  logProgress({ status: "bundling", progress: 0 });

  // Bundle the composition
  let bundleLocation;
  try {
    const { enableTailwind } = await import("@remotion/tailwind");
    bundleLocation = await bundle({
      entryPoint: path.join(__dirname, "RenderEntry.tsx"),
      webpackOverride: (currentConfig) => {
        const withTailwind = enableTailwind(currentConfig);
        return {
          ...withTailwind,
          resolve: {
            ...withTailwind.resolve,
            alias: {
              ...withTailwind.resolve?.alias,
              "@": path.join(__dirname, "../src"),
            },
          },
        };
      },
    });
    logProgress({ status: "bundled", progress: 5 });
  } catch (err) {
    logError("Failed to bundle composition", err);
    process.exit(1);
  }

  // Select the composition
  const compositionId = options.composition;
  let composition;
  try {
    composition = await selectComposition({
      serveUrl: bundleLocation,
      id: compositionId,
      inputProps: inputConfig,
    });

    // Override duration and dimensions
    composition = {
      ...composition,
      durationInFrames: durationInFrames || composition.durationInFrames,
      fps: fps || composition.fps,
      width: width || composition.width,
      height: height || composition.height,
    };

    logProgress({ status: "composition_selected", progress: 10, compositionId });
  } catch (err) {
    logError("Failed to select composition", err);
    process.exit(1);
  }

  // Render the video
  try {
    await renderMedia({
      composition,
      serveUrl: bundleLocation,
      codec: options.codec,
      outputLocation: options.output,
      inputProps: inputConfig,
      crf: options.crf,
      concurrency: options.concurrency,
      onProgress: ({ progress }) => {
        // Scale progress from 10% to 100%
        const scaledProgress = 10 + Math.round(progress * 90);
        logProgress({ status: "rendering", progress: scaledProgress, renderProgress: progress });
      },
    });

    logComplete({
      outputPath: options.output,
      durationInFrames,
      fps,
      width,
      height,
    });
  } catch (err) {
    logError("Failed to render video", err);
    fileServer.close();
    process.exit(1);
  }

  // Cleanup
  fileServer.close();
}

main().catch((err) => {
  logError("Unexpected error", err);
  process.exit(1);
});

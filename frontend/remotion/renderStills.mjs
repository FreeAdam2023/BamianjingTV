#!/usr/bin/env node

/**
 * Remotion Batch Still Renderer (Cards + Subtitles)
 *
 * Renders pinned cards and/or subtitle stills as PNG images using Remotion renderStill.
 * Bundles once, renders N stills — much faster than full-video renderMedia.
 *
 * Usage:
 *   node renderStills.mjs --input <cards.json> --output-dir <dir/> [--width 672] [--height 756]
 *   node renderStills.mjs --subtitles <subtitles.json> --output-dir <dir/>
 *   node renderStills.mjs --input <cards.json> --subtitles <subtitles.json> --output-dir <dir/>
 *
 * Cards input JSON: [ { "id": "card_001", "card_type": "word", "card_data": { ... } }, ... ]
 *
 * Subtitles input JSON:
 * {
 *   "style": { "enColor": "#ffffff", "zhColor": "#facc15", "enFontSize": 40, "zhFontSize": 40 },
 *   "bgColor": "#1a2744",
 *   "languageMode": "both",
 *   "subtitles": [ { "id": "sub_abc", "en": "...", "zh": "..." }, ... ]
 * }
 *
 * Output: <dir>/card_001.png, <dir>/sub_abc.png, ...
 */

import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "path";
import fs from "fs";
import http from "http";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---- Argument parsing ----

function parseArgs() {
  const args = process.argv.slice(2);
  const options = {
    input: null,
    subtitles: null,
    outputDir: null,
    width: 672,
    height: 756,
    concurrency: 4,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--input":
      case "-i":
        options.input = args[++i];
        break;
      case "--subtitles":
      case "-s":
        options.subtitles = args[++i];
        break;
      case "--output-dir":
      case "-o":
        options.outputDir = args[++i];
        break;
      case "--width":
        options.width = parseInt(args[++i], 10);
        break;
      case "--height":
        options.height = parseInt(args[++i], 10);
        break;
      case "--concurrency":
        options.concurrency = Math.max(1, parseInt(args[++i], 10) || 4);
        break;
    }
  }

  return options;
}

// ---- JSON progress logging (parsed by Python) ----

function logProgress(data) {
  console.log(JSON.stringify({ type: "progress", ...data }));
}

function logError(message, error) {
  console.error(
    JSON.stringify({
      type: "error",
      message,
      error: error?.message || String(error),
    })
  );
}

function logComplete(data) {
  console.log(JSON.stringify({ type: "complete", ...data }));
}

// ---- Local file server (reused from render.mjs) ----

function startLocalFileServer() {
  return new Promise((resolve) => {
    const server = http.createServer((req, res) => {
      const filePath = decodeURIComponent(req.url); // keep leading / for absolute paths
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
 * Rewrite file:// URLs to http://127.0.0.1:{port}/ so headless Chrome can fetch them.
 */
function rewriteLocalPaths(obj, port) {
  let json = JSON.stringify(obj);
  json = json.replace(/file:\/\/\//g, `http://127.0.0.1:${port}/`);
  return JSON.parse(json);
}

// ---- Main ----

async function main() {
  const options = parseArgs();

  if (!options.outputDir) {
    logError(
      "Missing required arguments",
      "Usage: node renderStills.mjs [--input <cards.json>] [--subtitles <subtitles.json>] --output-dir <dir/>"
    );
    process.exit(1);
  }

  if (!options.input && !options.subtitles) {
    logError(
      "Missing required arguments",
      "At least one of --input or --subtitles must be provided"
    );
    process.exit(1);
  }

  // Read input cards (optional)
  let cards = [];
  if (options.input) {
    try {
      const inputContent = fs.readFileSync(options.input, "utf-8");
      cards = JSON.parse(inputContent);
      if (!Array.isArray(cards)) cards = [];
      // Diagnostic: log card data summary
      console.error(`[renderStills] Loaded ${cards.length} cards from ${options.input}`);
      for (const card of cards.slice(0, 3)) {
        const dataKeys = card.card_data ? Object.keys(card.card_data) : [];
        const dataSize = JSON.stringify(card.card_data || {}).length;
        console.error(`[renderStills] Card ${card.id}: type=${card.card_type}, data_keys=[${dataKeys.join(',')}], data_size=${dataSize} bytes`);
      }
    } catch (err) {
      logError("Failed to read cards input file", err);
      process.exit(1);
    }
  }

  // Read subtitles input (optional)
  let subtitleData = null;
  let subtitles = [];
  if (options.subtitles) {
    try {
      const subtitleContent = fs.readFileSync(options.subtitles, "utf-8");
      subtitleData = JSON.parse(subtitleContent);
      subtitles = subtitleData.subtitles || [];
    } catch (err) {
      logError("Failed to read subtitles input file", err);
      process.exit(1);
    }
  }

  const totalItems = cards.length + subtitles.length;
  if (totalItems === 0) {
    logProgress({ status: "no_items", current: 0, total: 0 });
    logComplete({ rendered: 0 });
    process.exit(0);
  }

  // Ensure output directory exists
  fs.mkdirSync(options.outputDir, { recursive: true });

  // Start local file server for card images
  const { server: fileServer, port: filePort } = await startLocalFileServer();
  logProgress({ status: "file_server", port: filePort });

  // Rewrite file:// URLs in card data
  if (cards.length > 0) {
    cards = rewriteLocalPaths(cards, filePort);
  }

  logProgress({ status: "bundling", current: 0, total: totalItems });

  // Bundle the composition (once — shared for cards and subtitles)
  // Uses RenderStillsEntry.tsx — isolated entry point WITHOUT Tailwind CSS.
  // Tailwind's Preflight CSS reset was causing blank card renders in Docker.
  let bundleLocation;
  try {
    bundleLocation = await bundle({
      entryPoint: path.join(__dirname, "RenderStillsEntry.tsx"),
      webpackOverride: (currentConfig) => {
        return {
          ...currentConfig,
          resolve: {
            ...currentConfig.resolve,
            alias: {
              ...currentConfig.resolve?.alias,
              "@": path.join(__dirname, "../src"),
            },
          },
        };
      },
    });
    logProgress({ status: "bundled", current: 0, total: totalItems });
  } catch (err) {
    logError("Failed to bundle composition", err);
    fileServer.close();
    process.exit(1);
  }

  let totalRendered = 0;
  let globalCurrent = 0;
  const allErrors = [];

  // ── Phase 1: Render card stills ──
  if (cards.length > 0) {
    const defaultCardProp = {
      id: "default",
      card_type: "word",
      card_data: {},
      display_start: 0,
      display_end: 1,
    };

    let cardComposition;
    try {
      cardComposition = await selectComposition({
        serveUrl: bundleLocation,
        id: "CardStill",
        inputProps: { card: defaultCardProp },
      });

      // Override dimensions
      cardComposition = {
        ...cardComposition,
        width: options.width,
        height: options.height,
      };

      logProgress({
        status: "composition_selected",
        phase: "cards",
        current: 0,
        total: totalItems,
      });
    } catch (err) {
      logError("Failed to select CardStill composition", err);
      fileServer.close();
      process.exit(1);
    }

    for (let bStart = 0; bStart < cards.length; bStart += options.concurrency) {
      const batch = cards.slice(bStart, bStart + options.concurrency);
      const results = await Promise.allSettled(
        batch.map((card) => {
          const outputPath = path.join(options.outputDir, `${card.id}.png`);
          // Remotion 4.x uses composition.props (not renderStill's inputProps)
          // as the component's React props. We must override composition.props
          // per render so each card gets its own data.
          const cardProps = {
            card: {
              id: card.id,
              card_type: card.card_type,
              card_data: card.card_data,
              display_start: 0,
              display_end: 1,
            },
          };
          return renderStill({
            composition: { ...cardComposition, props: cardProps },
            serveUrl: bundleLocation,
            output: outputPath,
            inputProps: cardProps,
            imageFormat: "png",
          });
        })
      );

      for (let j = 0; j < results.length; j++) {
        const card = batch[j];
        if (results[j].status === "fulfilled") {
          totalRendered++;
          // Log rendered PNG file size
          const outputPath = path.join(options.outputDir, `${card.id}.png`);
          try {
            const stat = fs.statSync(outputPath);
            console.error(`[renderStills] Rendered card ${card.id}: ${stat.size} bytes`);
          } catch (_) {}
        } else {
          const err = results[j].reason;
          logError(`Failed to render card ${card.id}`, err);
          console.error(`[renderStills] FAILED card ${card.id}: ${err?.message || err}`);
          allErrors.push({ id: card.id, phase: "cards", error: err?.message || String(err) });
        }
        globalCurrent++;
        logProgress({
          status: "rendering",
          phase: "cards",
          current: globalCurrent,
          total: totalItems,
          cardId: card.id,
        });
      }
    }
  }

  // ── Phase 2: Render subtitle stills ──
  if (subtitles.length > 0 && subtitleData) {
    const subtitleWidth = 1920;
    const subtitleHeight = 356;

    const defaultSubProps = {
      en: "",
      zh: "",
      style: subtitleData.style || { enColor: "#ffffff", zhColor: "#facc15", enFontSize: 40, zhFontSize: 40 },
      bgColor: subtitleData.bgColor || "#1a2744",
      width: subtitleWidth,
      height: subtitleHeight,
      languageMode: subtitleData.languageMode || "both",
    };

    let subComposition;
    try {
      subComposition = await selectComposition({
        serveUrl: bundleLocation,
        id: "SubtitleStill",
        inputProps: defaultSubProps,
      });

      // Override dimensions to match subtitle area
      subComposition = {
        ...subComposition,
        width: subtitleWidth,
        height: subtitleHeight,
      };

      logProgress({
        status: "composition_selected",
        phase: "subtitles",
        current: globalCurrent,
        total: totalItems,
      });
    } catch (err) {
      logError("Failed to select SubtitleStill composition", err);
      fileServer.close();
      process.exit(1);
    }

    for (let bStart = 0; bStart < subtitles.length; bStart += options.concurrency) {
      const batch = subtitles.slice(bStart, bStart + options.concurrency);
      const results = await Promise.allSettled(
        batch.map((sub) => {
          const outputPath = path.join(options.outputDir, `${sub.id}.png`);
          // Same Remotion 4.x fix: override composition.props per render
          const subProps = {
            en: sub.en || "",
            zh: sub.zh || "",
            style: subtitleData.style,
            bgColor: subtitleData.bgColor || "#1a2744",
            width: subtitleWidth,
            height: subtitleHeight,
            languageMode: subtitleData.languageMode || "both",
          };
          return renderStill({
            composition: { ...subComposition, props: subProps },
            serveUrl: bundleLocation,
            output: outputPath,
            inputProps: subProps,
            imageFormat: "png",
          });
        })
      );

      for (let j = 0; j < results.length; j++) {
        const sub = batch[j];
        if (results[j].status === "fulfilled") {
          totalRendered++;
        } else {
          const err = results[j].reason;
          logError(`Failed to render subtitle ${sub.id}`, err);
          allErrors.push({ id: sub.id, phase: "subtitles", error: err?.message || String(err) });
        }
        globalCurrent++;
        logProgress({
          status: "rendering",
          phase: "subtitles",
          current: globalCurrent,
          total: totalItems,
          subtitleId: sub.id,
        });
      }
    }
  }

  logComplete({
    rendered: totalRendered,
    total: totalItems,
    cards: cards.length,
    subtitles: subtitles.length,
    errors: allErrors.length > 0 ? allErrors : undefined,
  });

  fileServer.close();

  // Exit with error if nothing was rendered
  if (totalRendered === 0 && totalItems > 0) {
    logError(
      "All renders failed",
      `0/${totalItems} items rendered successfully`
    );
    process.exit(1);
  }
}

main().catch((err) => {
  logError("Unexpected error", err);
  process.exit(1);
});

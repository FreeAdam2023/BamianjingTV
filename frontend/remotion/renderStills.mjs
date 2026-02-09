#!/usr/bin/env node

/**
 * Remotion Batch Card Still Renderer
 *
 * Renders all pinned cards as individual PNG images using Remotion renderStill.
 * Bundles once, renders N stills — much faster than full-video renderMedia.
 *
 * Usage: node renderStills.mjs --input <cards.json> --output-dir <dir/> [--width 672] [--height 756]
 *
 * Input JSON format:
 * [
 *   { "id": "card_001", "card_type": "word", "card_data": { ... } },
 *   { "id": "card_002", "card_type": "entity", "card_data": { ... } }
 * ]
 *
 * Output: <dir>/card_001.png, <dir>/card_002.png, ...
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
    outputDir: null,
    width: 672,
    height: 756,
  };

  for (let i = 0; i < args.length; i++) {
    switch (args[i]) {
      case "--input":
      case "-i":
        options.input = args[++i];
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

  if (!options.input || !options.outputDir) {
    logError(
      "Missing required arguments",
      "Usage: node renderStills.mjs --input <cards.json> --output-dir <dir/>"
    );
    process.exit(1);
  }

  // Read input cards
  let cards;
  try {
    const inputContent = fs.readFileSync(options.input, "utf-8");
    cards = JSON.parse(inputContent);
  } catch (err) {
    logError("Failed to read input file", err);
    process.exit(1);
  }

  if (!Array.isArray(cards) || cards.length === 0) {
    logProgress({ status: "no_cards", current: 0, total: 0 });
    logComplete({ rendered: 0 });
    process.exit(0);
  }

  // Ensure output directory exists
  fs.mkdirSync(options.outputDir, { recursive: true });

  // Start local file server for card images
  const { server: fileServer, port: filePort } = await startLocalFileServer();
  logProgress({ status: "file_server", port: filePort });

  // Rewrite file:// URLs in card data
  cards = rewriteLocalPaths(cards, filePort);

  logProgress({ status: "bundling", current: 0, total: cards.length });

  // Bundle the composition (once)
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
    logProgress({ status: "bundled", current: 0, total: cards.length });
  } catch (err) {
    logError("Failed to bundle composition", err);
    fileServer.close();
    process.exit(1);
  }

  // Select the CardStill composition (once)
  const defaultCardProp = {
    id: "default",
    card_type: "word",
    card_data: {},
    display_start: 0,
    display_end: 1,
  };

  let composition;
  try {
    composition = await selectComposition({
      serveUrl: bundleLocation,
      id: "CardStill",
      inputProps: { card: defaultCardProp },
    });

    // Override dimensions
    composition = {
      ...composition,
      width: options.width,
      height: options.height,
    };

    logProgress({
      status: "composition_selected",
      current: 0,
      total: cards.length,
    });
  } catch (err) {
    logError("Failed to select CardStill composition", err);
    fileServer.close();
    process.exit(1);
  }

  // Render each card as a still PNG
  let rendered = 0;
  const errors = [];

  for (let i = 0; i < cards.length; i++) {
    const card = cards[i];
    const outputPath = path.join(options.outputDir, `${card.id}.png`);

    try {
      await renderStill({
        composition,
        serveUrl: bundleLocation,
        output: outputPath,
        inputProps: {
          card: {
            id: card.id,
            card_type: card.card_type,
            card_data: card.card_data,
            display_start: 0,
            display_end: 1,
          },
        },
        imageFormat: "png",
      });
      rendered++;
    } catch (err) {
      logError(`Failed to render card ${card.id}`, err);
      errors.push({ id: card.id, error: err?.message || String(err) });
    }

    logProgress({
      status: "rendering",
      current: i + 1,
      total: cards.length,
      cardId: card.id,
    });
  }

  logComplete({
    rendered,
    total: cards.length,
    errors: errors.length > 0 ? errors : undefined,
  });

  fileServer.close();

  // Exit with error if no cards were rendered
  if (rendered === 0 && cards.length > 0) {
    logError(
      "All card renders failed",
      `0/${cards.length} cards rendered successfully`
    );
    process.exit(1);
  }
}

main().catch((err) => {
  logError("Unexpected error", err);
  process.exit(1);
});

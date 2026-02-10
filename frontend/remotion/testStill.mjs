#!/usr/bin/env node

/**
 * Quick test: render ONE card PNG using the new Tailwind-free entry point.
 *
 * Usage (inside Docker):
 *   node /app/frontend/remotion/testStill.mjs \
 *     --input /app/jobs/fb0c838c/output/stills/cards_input.json \
 *     --output /tmp/test_card.png
 *
 * Then inspect:
 *   ls -la /tmp/test_card.png        # should be different from 12480 bytes
 *   # Copy out to host:
 *   docker cp hardcore-player-api:/tmp/test_card.png ./test_card.png
 */

import { bundle } from "@remotion/bundler";
import { renderStill, selectComposition } from "@remotion/renderer";
import path from "path";
import fs from "fs";
import { fileURLToPath } from "url";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Parse args
const args = process.argv.slice(2);
let inputFile = null;
let outputFile = "/tmp/test_card.png";

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--input" || args[i] === "-i") inputFile = args[++i];
  if (args[i] === "--output" || args[i] === "-o") outputFile = args[++i];
}

if (!inputFile) {
  console.error("Usage: node testStill.mjs --input <cards_input.json> [--output /tmp/test_card.png]");
  process.exit(1);
}

// Read first card
const cards = JSON.parse(fs.readFileSync(inputFile, "utf-8"));
const card = cards[0];
if (!card) {
  console.error("No cards in input file");
  process.exit(1);
}

console.error(`\n=== Test Card Still Rendering ===`);
console.error(`Card: id=${card.id}, type=${card.card_type}`);
console.error(`Data keys: [${Object.keys(card.card_data || {}).join(", ")}]`);
console.error(`Data size: ${JSON.stringify(card.card_data || {}).length} bytes`);
if (card.card_type === "word") console.error(`Word: "${card.card_data?.word}"`);
if (card.card_type === "entity") console.error(`Entity: "${card.card_data?.name}"`);
if (card.card_type === "idiom") console.error(`Idiom: "${card.card_data?.text}"`);

// Bundle with NEW isolated entry point (no Tailwind)
console.error(`\nBundling RenderStillsEntry.tsx (no Tailwind)...`);
const bundleLocation = await bundle({
  entryPoint: path.join(__dirname, "RenderStillsEntry.tsx"),
  webpackOverride: (currentConfig) => ({
    ...currentConfig,
    resolve: {
      ...currentConfig.resolve,
      alias: {
        ...currentConfig.resolve?.alias,
        "@": path.join(__dirname, "../src"),
      },
    },
  }),
});
console.error(`Bundle ready: ${bundleLocation}`);

// Select composition
const composition = await selectComposition({
  serveUrl: bundleLocation,
  id: "CardStill",
  inputProps: {
    card: {
      id: card.id,
      card_type: card.card_type,
      card_data: card.card_data,
      display_start: 0,
      display_end: 1,
    },
  },
});

// Remotion 4.x uses composition.props as the component's React props,
// NOT renderStill's inputProps. We must set composition.props per render.
const cardProps = {
  card: {
    id: card.id,
    card_type: card.card_type,
    card_data: card.card_data,
    display_start: 0,
    display_end: 1,
  },
};
const finalComp = { ...composition, width: 672, height: 756, props: cardProps };

// Render
console.error(`\nRendering card "${card.id}" (${card.card_type})...`);
await renderStill({
  composition: finalComp,
  serveUrl: bundleLocation,
  output: outputFile,
  inputProps: cardProps,
  imageFormat: "png",
});

const stat = fs.statSync(outputFile);
console.error(`\n=== Result ===`);
console.error(`Output: ${outputFile}`);
console.error(`Size: ${stat.size} bytes`);
if (stat.size === 12480) {
  console.error(`⚠️  SAME as before (12480 bytes) — still blank!`);
} else {
  console.error(`✓ Different size — card content likely rendered!`);
}
console.error(`\nTo inspect: docker cp <container>:${outputFile} ./test_card.png`);

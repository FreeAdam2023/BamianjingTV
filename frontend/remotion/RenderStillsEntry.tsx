/**
 * RenderStillsEntry.tsx - Isolated entry point for renderStill (card + subtitle PNGs).
 *
 * Unlike RenderEntry.tsx, this file does NOT import Tailwind CSS (style.css).
 * Tailwind's Preflight CSS reset (from @tailwind base) was causing blank renders
 * in headless Chrome Docker by interfering with ExportCard's inline styles.
 *
 * Imports StillCompositions.tsx which has NO CSS imports — only inline React styles.
 */

import React from "react";
import { Composition, registerRoot } from "remotion";
import { CardStillComposition, CardPlaceholderComposition, SubtitleStillComposition } from "./compositions/StillCompositions";
import type { PinnedCardInput, SubtitleStillProps } from "./types";

const RemotionStillsRoot: React.FC = () => {
  return (
    <>
      <Composition
        id="CardStill"
        component={CardStillComposition as unknown as React.ComponentType<Record<string, unknown>>}
        width={672}
        height={756}
        fps={30}
        durationInFrames={1}
        defaultProps={{
          card: {
            id: "default",
            card_type: "word",
            card_data: {},
            display_start: 0,
            display_end: 1,
          } satisfies PinnedCardInput,
        }}
      />
      <Composition
        id="CardPlaceholder"
        component={CardPlaceholderComposition as unknown as React.ComponentType<Record<string, unknown>>}
        width={672}
        height={756}
        fps={30}
        durationInFrames={1}
        defaultProps={{}}
      />
      <Composition
        id="SubtitleStill"
        component={SubtitleStillComposition as unknown as React.ComponentType<Record<string, unknown>>}
        width={1920}
        height={356}
        fps={30}
        durationInFrames={1}
        defaultProps={{
          en: "",
          zh: "",
          style: { enColor: "#ffffff", zhColor: "#facc15", enFontSize: 40, zhFontSize: 40 },
          bgColor: "#1a2744",
          width: 1920,
          height: 356,
          languageMode: "both",
        } satisfies SubtitleStillProps}
      />
    </>
  );
};

registerRoot(RemotionStillsRoot);

import React from "react";
import { Img, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { resolveAsset } from "../lib/resolveAsset";

/**
 * LogoBadge — brand logo on a solid rounded plate, pinned to a corner.
 * The plate makes light/white logos legible on any scene background.
 */
export const LogoBadge: React.FC<{
  src: string;
  x?: number;
  y?: number;
  height?: number; // logo height in px (width follows the aspect ratio)
  pad?: number;
  background?: string;
  radius?: number;
  fadeInSeconds?: number;
}> = ({
  src,
  x = 40,
  y = 38,
  height = 44,
  pad = 11,
  background = "#14244A",
  radius = 10,
  fadeInSeconds = 0.6,
}) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const opacity = interpolate(frame, [0, fadeInSeconds * fps], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  return (
    <div
      style={{
        position: "absolute",
        left: x,
        top: y,
        padding: pad,
        background,
        borderRadius: radius,
        boxShadow: "0 4px 14px rgba(15,23,42,0.28)",
        opacity,
        lineHeight: 0,
      }}
    >
      <Img src={resolveAsset(src)} style={{ height, width: "auto", display: "block" }} />
    </div>
  );
};

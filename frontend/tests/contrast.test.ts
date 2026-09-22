import { readFileSync } from "node:fs";
import { expect, it } from "vitest";

const css = readFileSync("src/app/globals.css", "utf8");
const colors = Object.fromEntries(
  [...css.matchAll(/--([a-z-]+):\s*(#[\da-f]{6});/g)].map((match) => [
    match[1],
    match[2],
  ]),
);

function luminance(hex: string) {
  const rgb = [1, 3, 5].map((start) => {
    const value = parseInt(hex.slice(start, start + 2), 16) / 255;
    return value <= 0.04045 ? value / 12.92 : ((value + 0.055) / 1.055) ** 2.4;
  });
  return rgb[0] * 0.2126 + rgb[1] * 0.7152 + rgb[2] * 0.0722;
}

function contrast(first: string, second: string) {
  const [light, dark] = [luminance(first), luminance(second)].sort(
    (a, b) => b - a,
  );
  return (light + 0.05) / (dark + 0.05);
}

it("maintains WCAG AA contrast for text on supported dark surfaces", () => {
  for (const text of [
    "foreground",
    "muted",
    "accent",
    "success",
    "warning",
    "danger",
  ]) {
    for (const surface of ["background", "surface", "elevated"]) {
      expect(
        contrast(colors[text], colors[surface]),
        `${text} on ${surface}`,
      ).toBeGreaterThanOrEqual(4.5);
    }
  }
  expect(
    contrast(colors.background, colors.accent),
    "primary button label",
  ).toBeGreaterThanOrEqual(4.5);
  expect(
    contrast(colors.accent, colors["accent-subtle"]),
    "active navigation label",
  ).toBeGreaterThanOrEqual(4.5);
});

it("keeps control boundaries distinguishable from their surrounding surfaces", () => {
  for (const surface of ["background", "surface", "elevated"]) {
    expect(
      contrast(colors["control-border"], colors[surface]),
      `control border on ${surface}`,
    ).toBeGreaterThanOrEqual(3);
  }
});

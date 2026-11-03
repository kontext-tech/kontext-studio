/**
 * Theme utility functions for chart components
 * Provides consistent theme integration across all chart types
 */

import type { GlobalToken } from "antd";
import type { ChartType } from "../types/chart";
import type { ColorPalette } from "./colorPalettes";
import {
   COLOR_PALETTE_NAMES,
   DEFAULT_COLOR_PALETTE,
   getDiscretePaletteColors
} from "./colorPalettes";

/**
 * Normalizes palette names to handle display names vs palette keys
 * E.g., "Pastel2" (display name) -> "pastel2" (palette key)
 * @param palette - The palette name (could be display name or palette key)
 * @returns Normalized palette key
 */
function normalizePaletteName(palette: string): ColorPalette {
   // If it's already a valid palette key, return it
   if (Object.keys(COLOR_PALETTE_NAMES).includes(palette)) {
      return palette as ColorPalette;
   }

   // Otherwise, find the palette key by matching display name
   const foundKey = Object.entries(COLOR_PALETTE_NAMES).find(
      ([, displayName]) => displayName === palette
   )?.[0];

   return (foundKey as ColorPalette) || (palette as ColorPalette);
}

/**
 * Converts hex color to RGB values
 */
function hexToRgb(hex: string): { r: number; g: number; b: number } | null {
   const result = /^#?([a-f\d]{2})([a-f\d]{2})([a-f\d]{2})$/i.exec(hex);
   return result
      ? {
           r: parseInt(result[1], 16),
           g: parseInt(result[2], 16),
           b: parseInt(result[3], 16)
        }
      : null;
}

/**
 * Calculates perceived brightness of a color (0-255, higher = brighter)
 */
function getBrightness(color: string): number {
   const rgb = hexToRgb(color);
   if (!rgb) return 255; // Default to bright if parsing fails
   return 0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b;
}

/**
 * Finds the most readable color in a palette for human eyes
 * Prefers colors with medium brightness (40-60%) that are easy on the eyes
 * and provide good contrast without being too harsh or too dim
 */
function getMostReadableColor(colors: string[]): string | null {
   if (colors.length === 0) return null;

   let bestColor = colors[0];
   let bestScore = calculateReadabilityScore(colors[0]);

   for (let i = 1; i < colors.length; i++) {
      const score = calculateReadabilityScore(colors[i]);
      if (score > bestScore) {
         bestScore = score;
         bestColor = colors[i];
      }
   }

   return bestColor;
}

/**
 * Calculates a readability score for a color
 * Higher scores indicate better readability for human eyes
 */
function calculateReadabilityScore(color: string): number {
   const brightness = getBrightness(color);

   // Score based on how close the brightness is to the optimal range (40-60%)
   const targetBrightness = 0.5 * 255; // 127.5 (middle of optimal range)
   const distanceFromTarget = Math.abs(brightness - targetBrightness);

   // Perfect score for colors in the 40-60% brightness range
   const brightnessScore = Math.max(0, 100 - distanceFromTarget / 2.55); // Convert to 0-100 scale

   // Additional factors for readability
   const rgb = hexToRgb(color);
   if (!rgb) return 0;

   // Prefer colors that aren't pure grays (have some color saturation)
   const saturation = Math.max(
      Math.abs(rgb.r - rgb.g),
      Math.abs(rgb.r - rgb.b),
      Math.abs(rgb.g - rgb.b)
   );
   const saturationScore = Math.min(20, saturation / 12.75); // 0-20 points for saturation

   return brightnessScore + saturationScore;
}

/**
 * Applies theme-aware styling to chart configuration
 * Only applies theme to UI elements (labels, titles, axis lines, grid)
 * but preserves data visualization colors from palettes
 * @param config - The original chart configuration (may include colorPalette)
 * @param token - Ant Design theme tokens
 * @param isDarkTheme - Whether the current theme is dark
 * @param chartType - The type of chart being rendered
 * @returns Chart configuration with theme styling applied to UI elements only
 */
// eslint-disable-next-line @typescript-eslint/no-explicit-any
export function applyChartTheme<T extends Record<string, any>>(
   config: T,
   token: GlobalToken,
   isDarkTheme: boolean = false,
   chartType?: ChartType
): T {
   // eslint-disable-next-line @typescript-eslint/no-explicit-any
   const themedConfig: any = {
      ...config,
      theme: isDarkTheme ? "dark" : "light",
      // Apply theme to chart background
      style: {
         viewStyle: {
            backgroundColor: token.colorBgContainer,
            ...(config.style?.viewStyle || {})
         },
         ...(config.style || {})
      }
   };

   // Fallback to default palette if not specified to ensure consistency across rendering modes
   const colorPalette =
      (config as { colorPalette?: ColorPalette })?.colorPalette ||
      DEFAULT_COLOR_PALETTE;

   // Normalize palette name to handle display names vs palette keys
   const normalizedPalette = normalizePaletteName(colorPalette);

   // Get the most readable color from the palette as default color
   const paletteColors = getDiscretePaletteColors(normalizedPalette);
   const readableColor = getMostReadableColor(paletteColors);
   const defaultColor = readableColor || token.colorPrimary; // fallback to theme primary color

   // Pass explicit colors via `range`; G2 treats `palette` as a named palette key.
   // Supplying an array to `palette` gets stringified and throws "Unknown palette".
   const colorConfig = { range: paletteColors };

   // Handle multi-view charts (like Dual Axes) where each child may need its own axis color
   // eslint-disable-next-line @typescript-eslint/no-explicit-any
   if (chartType === "dualAxes" && Array.isArray((config as any).children)) {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      themedConfig.children = (config as any).children.map(
         // eslint-disable-next-line @typescript-eslint/no-explicit-any
         (child: any, index: number) => {
            // Use colors that are further apart for better visual distinction in dual axes
            // index 0 -> Blue (#3B82F6), index 1 -> Orange (#F97316) in Kontext palette
            const colorIndex = index === 1 ? 6 : index;
            const seriesColor =
               paletteColors[colorIndex % paletteColors.length];

            // Only apply distinct colors to the axis if there's no colorField (meaning it's a single series per axis)
            if (!child.colorField) {
               return {
                  ...child,
                  color: seriesColor,
                  // Explicitly set fill/stroke in style to ensure consistency across plot types
                  style: {
                     ...child.style,
                     fill:
                        child.type === "interval" || child.type === "area"
                           ? seriesColor
                           : child.style?.fill,
                     stroke:
                        child.type === "line" ||
                        child.type === "area" ||
                        child.type === "point"
                           ? seriesColor
                           : child.style?.stroke
                  },
                  axis: {
                     ...child.axis,
                     y: {
                        ...child.axis?.y,
                        lineStroke: seriesColor,
                        tickStroke: seriesColor
                     }
                  }
               };
            }
            return child;
         }
      );
   }

   return {
      ...themedConfig,
      // Set default color using first color from palette
      theme: {
         type: isDarkTheme ? "dark" : "light",
         color: defaultColor
      },
      scale: {
         ...themedConfig.scale,
         color: {
            ...colorConfig,
            ...themedConfig.scale?.color
         }
      }
   } as T;
}

/**
 * Creates theme-aware empty state styling
 * @param token - Ant Design theme tokens
 * @returns Style object for empty states
 */
export function getEmptyStateStyle(token: GlobalToken) {
   return {
      color: token.colorTextSecondary,
      backgroundColor: token.colorBgContainer
   };
}

/**
 * Creates theme-aware card styling for chart containers
 * @param token - Ant Design theme tokens
 * @returns Style object for chart cards
 */
export function getChartCardStyle(token: GlobalToken) {
   return {
      backgroundColor: token.colorBgContainer,
      border: `1px solid ${token.colorBorderSecondary}`,
      borderRadius: token.borderRadius
   };
}

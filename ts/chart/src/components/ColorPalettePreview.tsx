import {
   getDiscretePaletteColors,
   type ColorPalette
} from "../utils/colorPalettes";
import React from "react";

/**
 * Color Palette Preview Component
 * Displays actual colors from the palette using our color utilities
 */
export const ColorPalettePreview: React.FC<{
   palette: ColorPalette;
   /** Total width of the color palette preview */
   width?: number;
}> = ({ palette, width = 120 }) => {
   // Get colors for any palette and display as individual color swatches
   const colors = getDiscretePaletteColors(palette);
   const totalWidth = width; // Use the width parameter as total width
   const height = Math.max(8, Math.round(width / 10)); // Derive height from width (1/10 ratio, minimum 8px)
   const colorCount = colors.length;
   const swatchWidth = Math.max(4, totalWidth / colorCount); // Minimum 4px width per swatch

   return (
      <div
         style={{
            display: "flex",
            alignItems: "center",
            width: totalWidth,
            height: height
         }}
      >
         {colors.map((color, index) => (
            <div
               key={index}
               style={{
                  width: swatchWidth,
                  height: height,
                  backgroundColor: color,
                  borderRadius:
                     index === 0
                        ? "2px 0 0 2px"
                        : index === colorCount - 1
                          ? "0 2px 2px 0"
                          : "0"
               }}
            />
         ))}
      </div>
   );
};

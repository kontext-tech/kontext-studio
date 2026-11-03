import { Select, Space, Typography } from "antd";
import React from "react";
import {
   DEFAULT_COLOR_PALETTE,
   getColorPaletteOptions,
   type ColorPalette
} from "../utils/colorPalettes";
import { ColorPalettePreview } from "./ColorPalettePreview";

const { Text } = Typography;
const { Option } = Select;

export interface ColorPaletteSelectProps {
   /** Current selected color palette */
   value?: ColorPalette;
   /** Callback when palette selection changes */
   onChange?: (value: ColorPalette) => void;
   /** Whether the select is disabled */
   disabled?: boolean;
   /** Custom style */
   style?: React.CSSProperties;
   /** Placeholder text */
   placeholder?: string;
   /** Show label */
   showLabel?: boolean;
}

/**
 * Color Palette Select Component
 *
 * A specialized select component for choosing color palettes with visual previews.
 * Uses G2's color utilities to display actual palette colors.
 */
export const ColorPaletteSelect: React.FC<ColorPaletteSelectProps> = ({
   value,
   onChange,
   disabled = false,
   style,
   placeholder = "Select color palette",
   showLabel = true
}) => {
   const paletteOptions = getColorPaletteOptions();
   const currentPalette = value || DEFAULT_COLOR_PALETTE;

   return (
      <Space
         orientation="vertical"
         style={{ width: "100%", ...style }}
         size="small"
      >
         {showLabel && <Text strong>Color Palette</Text>}

         <Select
            value={currentPalette}
            onChange={onChange}
            disabled={disabled}
            style={{ width: "100%" }}
            placeholder={placeholder}
            // Custom label render function to show the preview in the select
            labelRender={({ label, value: selectValue }) => {
               const option = paletteOptions.find(
                  (opt) => opt.value === selectValue
               );
               if (!option) return label;

               return (
                  <Space align="center" size="small">
                     <ColorPalettePreview palette={option.value} width={120} />
                     <span>{option.label}</span>
                  </Space>
               );
            }}
         >
            {paletteOptions.map((option) => (
               <Option
                  key={option.value}
                  value={option.value}
                  label={option.label}
               >
                  <Space align="center">
                     <ColorPalettePreview palette={option.value} width={120} />
                     <span>{option.label}</span>
                  </Space>
               </Option>
            ))}
         </Select>
      </Space>
   );
};

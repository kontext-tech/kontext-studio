/**
 * Color Palettes for Charts
 *
 * This module contains predefined color palettes that can be used with charts.
 * Uses D3 palette names supported by Ant Design Charts for better integration.
 *
 * Reference: https://ant-design-charts.antgroup.com/en/options/plots/color#palette
 */

/**
 * Available color palette names
 */
export const COLOR_PALETTES = [
   "kontext",
   "category10",
   "accent",
   "dark2",
   "paired",
   "pastel1",
   "pastel2",
   "set1",
   "set2",
   "set3",
   "tableau10",
   "blues",
   "brBG",
   "buGn",
   "buPu",
   "cividis",
   "cool",
   "cubehelixDefault",
   "gnBu",
   "greens",
   "greys",
   "inferno",
   "magma",
   "oranges",
   "orRd",
   "piYG",
   "plasma",
   "pRGn",
   "puBu",
   "puBuGn",
   "puOr",
   "puRd",
   "purples",
   "rainbow",
   "rdBu",
   "rdGy",
   "rdPu",
   "rdYlBu",
   "rdYlGn",
   "reds",
   "sinebow",
   "spectral",
   "turbo",
   "viridis",
   "warm",
   "ylGn",
   "ylGnBu",
   "ylOrBr",
   "ylOrRd"
] as const;

/**
 * Union type for all available color palettes
 */
export type ColorPalette = (typeof COLOR_PALETTES)[number];

/**
 * Color palette display names for UI
 */
export const COLOR_PALETTE_NAMES: Record<ColorPalette, string> = {
   kontext: "Kontext (Default)",
   category10: "Category10",
   accent: "Accent",
   dark2: "Dark2",
   paired: "Paired",
   pastel1: "Pastel1",
   pastel2: "Pastel2",
   set1: "Set1",
   set2: "Set2",
   set3: "Set3",
   tableau10: "Tableau10",
   blues: "Blues",
   brBG: "Brown-Blue-Green",
   buGn: "Blue-Green",
   buPu: "Blue-Purple",
   cividis: "Cividis",
   cool: "Cool",
   cubehelixDefault: "Cubehelix",
   gnBu: "Green-Blue",
   greens: "Greens",
   greys: "Greys",
   inferno: "Inferno",
   magma: "Magma",
   oranges: "Oranges",
   orRd: "Orange-Red",
   piYG: "Pink-Yellow-Green",
   plasma: "Plasma",
   pRGn: "Purple-Red-Green",
   puBu: "Purple-Blue",
   puBuGn: "Purple-Blue-Green",
   puOr: "Purple-Orange",
   puRd: "Purple-Red",
   purples: "Purples",
   rainbow: "Rainbow",
   rdBu: "Red-Blue",
   rdGy: "Red-Grey",
   rdPu: "Red-Purple",
   rdYlBu: "Red-Yellow-Blue",
   rdYlGn: "Red-Yellow-Green",
   reds: "Reds",
   sinebow: "Sinebow",
   spectral: "Spectral",
   turbo: "Turbo",
   viridis: "Viridis",
   warm: "Warm",
   ylGn: "Yellow-Green",
   ylGnBu: "Yellow-Green-Blue",
   ylOrBr: "Yellow-Orange-Brown",
   ylOrRd: "Yellow-Orange-Red"
};

/**
 * All palette colors extracted from Ant Design Charts documentation
 * Contains both discrete and continuous palettes as unified color arrays
 */
export const PALETTE_COLORS: Record<string, string[]> = {
   // Discrete palettes (each has exactly 10 colors for consistency)
   kontext: [
      "#3B82F6", // Blue
      "#06B6D4", // Cyan
      "#34D399", // Success (Emerald)
      "#FBBF24", // Warning (Amber/Yellow)
      "#F87171", // Error (Red)
      "#60A5FA", // Info (Blue)
      "#F97316", // Orange
      "#EC4899", // Pink
      "#64748B", // Slate
      "#0D9488" // Teal
   ],
   accent: [
      "#7fc97f",
      "#beaed4",
      "#fdc086",
      "#ffff99",
      "#386cb0",
      "#f0027f",
      "#bf5b17",
      "#666666",
      "#7fc97f",
      "#beaed4"
   ],
   category10: [
      "#1f77b4",
      "#ff7f0e",
      "#2ca02c",
      "#d62728",
      "#9467bd",
      "#8c564b",
      "#e377c2",
      "#7f7f7f",
      "#bcbd22",
      "#17becf"
   ],
   dark2: [
      "#1b9e77",
      "#d95f02",
      "#7570b3",
      "#e7298a",
      "#66a61e",
      "#e6ab02",
      "#a6761d",
      "#666666",
      "#1b9e77",
      "#d95f02"
   ],
   paired: [
      "#a6cee3",
      "#1f78b4",
      "#b2df8a",
      "#33a02c",
      "#fb9a99",
      "#e31a1c",
      "#fdbf6f",
      "#ff7f00",
      "#cab2d6",
      "#6a3d9a"
   ],
   pastel1: [
      "#fbb4ae",
      "#b3cde3",
      "#ccebc5",
      "#decbe4",
      "#fed9a6",
      "#ffffcc",
      "#e5d8bd",
      "#fddaec",
      "#f2f2f2",
      "#fbb4ae"
   ],
   pastel2: [
      "#b3e2cd",
      "#fdcdac",
      "#cbd5e8",
      "#f4cae4",
      "#e6f5c9",
      "#fff2ae",
      "#f1e2cc",
      "#cccccc",
      "#b3e2cd",
      "#fdcdac"
   ],
   set1: [
      "#e41a1c",
      "#377eb8",
      "#4daf4a",
      "#984ea3",
      "#ff7f00",
      "#ffff33",
      "#a65628",
      "#f781bf",
      "#999999",
      "#e41a1c"
   ],
   set2: [
      "#66c2a5",
      "#fc8d62",
      "#8da0cb",
      "#e78ac3",
      "#a6d854",
      "#ffd92f",
      "#e5c494",
      "#b3b3b3",
      "#66c2a5",
      "#fc8d62"
   ],
   set3: [
      "#8dd3c7",
      "#ffffb3",
      "#bebada",
      "#fb8072",
      "#80b1d3",
      "#fdb462",
      "#b3de69",
      "#fccde5",
      "#d9d9d9",
      "#bc80bd"
   ],
   tableau10: [
      "#4e79a7",
      "#f28e2c",
      "#e15759",
      "#76b7b2",
      "#59a14f",
      "#edc949",
      "#af7aa1",
      "#ff9da7",
      "#9c755f",
      "#bab0ab"
   ],

   // Continuous palettes (key stop colors for generating gradients)
   blues: [
      "#f7fbff",
      "#deebf7",
      "#c6dbef",
      "#9ecae1",
      "#6baed6",
      "#4292c6",
      "#2171b5",
      "#08519c",
      "#08306b"
   ],
   brBG: [
      "#543005",
      "#8c510a",
      "#bf812d",
      "#dfc27d",
      "#f6e8c3",
      "#f5f5f5",
      "#c7eae5",
      "#80cdc1",
      "#35978f",
      "#01665e",
      "#003c30"
   ],
   buGn: [
      "#f7fcfd",
      "#e5f5f9",
      "#ccece6",
      "#99d8c9",
      "#66c2a4",
      "#41ae76",
      "#238b45",
      "#006d2c",
      "#00441b"
   ],
   buPu: [
      "#f7fcfd",
      "#e0ecf4",
      "#bfd3e6",
      "#9ebcda",
      "#8c96c6",
      "#8c6bb1",
      "#88419d",
      "#810f7c",
      "#4d004b"
   ],
   cividis: [
      "#00224e",
      "#002a62",
      "#11336b",
      "#1c3c6e",
      "#2f466e",
      "#41506e",
      "#535a6e",
      "#65646f",
      "#776e70",
      "#8a7871",
      "#9d8372",
      "#b18e73",
      "#c59974",
      "#daa575",
      "#efb176",
      "#ffbe77"
   ],
   cool: [
      "#6e40aa",
      "#6850bb",
      "#5f62cb",
      "#5575d8",
      "#4a88e2",
      "#3e9be9",
      "#32aeec",
      "#27c0eb",
      "#1ed1e6",
      "#1fe1dc",
      "#2bf0cf",
      "#3dfcbf",
      "#59ffab",
      "#7bff94",
      "#9eff7b",
      "#c3ff5b"
   ],
   cubehelixDefault: [
      "#000000",
      "#13091b",
      "#1a1732",
      "#192a47",
      "#15414e",
      "#175849",
      "#246c3d",
      "#3f7632",
      "#647e30",
      "#8d7a3c",
      "#b77b59",
      "#d08c7d",
      "#dda4a3",
      "#e1bfc4",
      "#dfdbdf",
      "#ffffff"
   ],
   gnBu: [
      "#f7fcf0",
      "#e0f3db",
      "#ccebc5",
      "#a8ddb5",
      "#7bccc4",
      "#4eb3d3",
      "#2b8cbe",
      "#0868ac",
      "#084081"
   ],
   greens: [
      "#f7fcf5",
      "#e5f5e0",
      "#c7e9c0",
      "#a1d99b",
      "#74c476",
      "#41ab5d",
      "#238b45",
      "#006d2c",
      "#00441b"
   ],
   greys: [
      "#ffffff",
      "#f0f0f0",
      "#d9d9d9",
      "#bdbdbd",
      "#969696",
      "#737373",
      "#525252",
      "#252525",
      "#000000"
   ],
   inferno: [
      "#000004",
      "#08051d",
      "#180c3c",
      "#2f0a5b",
      "#450a69",
      "#5c126e",
      "#71196e",
      "#87216b",
      "#9b2964",
      "#b1325a",
      "#c43c4e",
      "#d74b3f",
      "#e55c30",
      "#f1711f",
      "#f8870e",
      "#fca108",
      "#fbba1f",
      "#f6d543",
      "#f1ed71",
      "#fcffa4"
   ],
   magma: [
      "#000004",
      "#07061c",
      "#150e38",
      "#29115a",
      "#3f0f72",
      "#56147d",
      "#6a1c81",
      "#802582",
      "#942c80",
      "#ab337c",
      "#c03a76",
      "#d6456c",
      "#e85362",
      "#f4695c",
      "#fa815f",
      "#fd9b6b",
      "#feb47b",
      "#fecd90",
      "#fde5a7",
      "#fcfdbf"
   ],
   oranges: [
      "#fff5eb",
      "#fee6ce",
      "#fdd0a2",
      "#fdae6b",
      "#fd8d3c",
      "#f16913",
      "#d94801",
      "#a63603",
      "#7f2704"
   ],
   orRd: [
      "#fff7ec",
      "#fee8c8",
      "#fdd49e",
      "#fdbb84",
      "#fc8d59",
      "#ef6548",
      "#d7301f",
      "#b30000",
      "#7f0000"
   ],
   piYG: [
      "#8e0152",
      "#c51b7d",
      "#de77ae",
      "#f1b6da",
      "#fde0ef",
      "#f7f7f7",
      "#e6f5d0",
      "#b8e186",
      "#7fbc41",
      "#4d9221",
      "#276419"
   ],
   plasma: [
      "#0d0887",
      "#2c0594",
      "#43039e",
      "#5901a5",
      "#6e00a8",
      "#8305a7",
      "#9511a1",
      "#a72197",
      "#b6308b",
      "#c5407e",
      "#d14e72",
      "#dd5e66",
      "#e76e5b",
      "#f07f4f",
      "#f79044",
      "#fca338",
      "#feb72d",
      "#fccd25",
      "#f7e225",
      "#f0f921"
   ],
   pRGn: [
      "#40004b",
      "#762a83",
      "#9970ab",
      "#c2a5cf",
      "#e7d4e8",
      "#f7f7f7",
      "#d9f0d3",
      "#a6dba0",
      "#5aae61",
      "#1b7837",
      "#00441b"
   ],
   puBu: [
      "#fff7fb",
      "#ece7f2",
      "#d0d1e6",
      "#a6bddb",
      "#74a9cf",
      "#3690c0",
      "#0570b0",
      "#045a8d",
      "#023858"
   ],
   puBuGn: [
      "#fff7fb",
      "#ece2f0",
      "#d0d1e6",
      "#a6bddb",
      "#67a9cf",
      "#3690c0",
      "#02818a",
      "#016c59",
      "#014636"
   ],
   puOr: [
      "#2d004b",
      "#542788",
      "#8073ac",
      "#b2abd2",
      "#d8daeb",
      "#f7f7f7",
      "#fee0b6",
      "#fdb863",
      "#e08214",
      "#b35806",
      "#7f3b08"
   ],
   puRd: [
      "#f7f4f9",
      "#e7e1ef",
      "#d4b9da",
      "#c994c7",
      "#df65b0",
      "#e7298a",
      "#ce1256",
      "#980043",
      "#67001f"
   ],
   purples: [
      "#fcfbfd",
      "#efedf5",
      "#dadaeb",
      "#bcbddc",
      "#9e9ac8",
      "#807dba",
      "#6a51a3",
      "#54278f",
      "#3f007d"
   ],
   rainbow: [
      "#6e40aa",
      "#983fb3",
      "#c43db8",
      "#e73db8",
      "#ff49b3",
      "#ff5da6",
      "#ff7492",
      "#ff8c7b",
      "#ffa660",
      "#ffbd45",
      "#ffd52c",
      "#ffeb1c",
      "#f3ff1c",
      "#d7ff2c",
      "#b5ff45",
      "#93ff60",
      "#73ff7b",
      "#57ff95",
      "#42ffaf",
      "#33ffc7",
      "#2cffdd",
      "#30fff0"
   ],
   rdBu: [
      "#67001f",
      "#b2182b",
      "#d6604d",
      "#f4a582",
      "#fddbc7",
      "#f7f7f7",
      "#d1e5f0",
      "#92c5de",
      "#4393c3",
      "#2166ac",
      "#053061"
   ],
   rdGy: [
      "#67001f",
      "#b2182b",
      "#d6604d",
      "#f4a582",
      "#fddbc7",
      "#ffffff",
      "#e0e0e0",
      "#bababa",
      "#878787",
      "#4d4d4d",
      "#1a1a1a"
   ],
   rdPu: [
      "#fff7f3",
      "#fde0dd",
      "#fcc5c0",
      "#fa9fb5",
      "#f768a1",
      "#dd3497",
      "#ae017e",
      "#7a0177",
      "#49006a"
   ],
   rdYlBu: [
      "#a50026",
      "#d73027",
      "#f46d43",
      "#fdae61",
      "#fee090",
      "#ffffbf",
      "#e0f3f8",
      "#abd9e9",
      "#74add1",
      "#4575b4",
      "#313695"
   ],
   rdYlGn: [
      "#a50026",
      "#d73027",
      "#f46d43",
      "#fdae61",
      "#fee08b",
      "#ffffbf",
      "#d9ef8b",
      "#a6d96a",
      "#66bd63",
      "#1a9850",
      "#006837"
   ],
   reds: [
      "#fff5f0",
      "#fee0d2",
      "#fcbba1",
      "#fc9272",
      "#fb6a4a",
      "#ef3b2c",
      "#cb181d",
      "#a50f15",
      "#67000d"
   ],
   sinebow: [
      "#ff4040",
      "#ff8040",
      "#ffff40",
      "#80ff40",
      "#40ff40",
      "#40ff80",
      "#40ffff",
      "#4080ff",
      "#4040ff",
      "#8040ff",
      "#ff40ff",
      "#ff4080"
   ],
   spectral: [
      "#9e0142",
      "#d53e4f",
      "#f46d43",
      "#fdae61",
      "#fee08b",
      "#ffffbf",
      "#e6f598",
      "#abdda4",
      "#66c2a5",
      "#3288bd",
      "#5e4fa2"
   ],
   turbo: [
      "#23171b",
      "#47389e",
      "#4960e1",
      "#3b82f8",
      "#2ca4f2",
      "#25c4da",
      "#2adeba",
      "#3cf297",
      "#5afc77",
      "#80fd5c",
      "#a8f747",
      "#d0e63a",
      "#f0cd2c",
      "#ffaf25",
      "#ff8b1f",
      "#fa6119",
      "#e24215",
      "#c42911",
      "#9e190c",
      "#780c00"
   ],
   viridis: [
      "#440154",
      "#481467",
      "#482576",
      "#453781",
      "#404688",
      "#39558c",
      "#33638d",
      "#2d718e",
      "#287d8e",
      "#238a8d",
      "#1f968b",
      "#20a386",
      "#29af7f",
      "#3dbc74",
      "#56c667",
      "#75d054",
      "#95d840",
      "#bade28",
      "#dde318",
      "#fde725"
   ],
   warm: [
      "#6e40aa",
      "#834abf",
      "#9855d4",
      "#ad61e6",
      "#c26df5",
      "#d67bff",
      "#e88aff",
      "#f79aff",
      "#ffabf5",
      "#ffbce5",
      "#ffced2",
      "#ffe0bd",
      "#fff3a7",
      "#ffffff"
   ],
   ylGn: [
      "#ffffe5",
      "#f7fcb9",
      "#d9f0a3",
      "#addd8e",
      "#78c679",
      "#41ab5d",
      "#238443",
      "#006837",
      "#004529"
   ],
   ylGnBu: [
      "#ffffd9",
      "#edf8b1",
      "#c7e9b4",
      "#7fcdbb",
      "#41b6c4",
      "#1d91c0",
      "#225ea8",
      "#253494",
      "#081d58"
   ],
   ylOrBr: [
      "#ffffe5",
      "#fff7bc",
      "#fee391",
      "#fec44f",
      "#fe9929",
      "#ec7014",
      "#cc4c02",
      "#993404",
      "#662506"
   ],
   ylOrRd: [
      "#ffffcc",
      "#ffeda0",
      "#fed976",
      "#feb24c",
      "#fd8d3c",
      "#fc4e2a",
      "#e31a1c",
      "#bd0026",
      "#800026"
   ]
};

/**
 * Default color palette to use when none is specified
 */
export const DEFAULT_COLOR_PALETTE: ColorPalette = "kontext";

/**
 * Gets all available color palette options for UI components
 */
export function getColorPaletteOptions(): Array<{
   value: ColorPalette;
   label: string;
}> {
   return COLOR_PALETTES.map((palette) => ({
      value: palette,
      label: COLOR_PALETTE_NAMES[palette]
   }));
}

/**
 * Gets the actual color array for any palette
 * This is useful for avoiding D3 "Unknown palette" errors by providing
 * actual color arrays instead of palette names
 */
export function getDiscretePaletteColors(palette: ColorPalette): string[] {
   // Check if we have colors for this palette
   if (palette in PALETTE_COLORS) {
      return PALETTE_COLORS[palette];
   }
   return getDiscretePaletteColors(DEFAULT_COLOR_PALETTE) || [];
}

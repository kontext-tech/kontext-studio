/**
 * Explicit enum reference rules for inline literal/discriminator properties.
 *
 * The exporter turns a single-value inline enum into a `$ref` to the canonical
 * enum component so generated clients get a named type (and the C# defaults
 * and Python enum members stay stable). These rules pick the target when more
 * than one enum can legally contain the same wire value.
 */

export type InlineEnumReferenceContext = {
   schemaKey: string;
   propKey: string;
   values: readonly string[];
};

export type InlineEnumReferenceOverride = {
   target: string;
   condition?: (context: InlineEnumReferenceContext) => boolean;
};

export const INLINE_ENUM_REFERENCE_OVERRIDES: Readonly<
   Record<string, readonly InlineEnumReferenceOverride[]>
> = {
   type: [
      {
         target: "NotebookBlockType",
         condition: ({ schemaKey }) => schemaKey.endsWith("Block")
      },
      {
         target: "CodeExecutionOutputType",
         condition: ({ schemaKey }) =>
            schemaKey.startsWith("Code") && schemaKey.endsWith("Output")
      }
   ],
   chartType: [{ target: "ChartType" }],
   boxType: [{ target: "BoxChartType" }],
   coordinateType: [{ target: "RadarCoordinateType" }],
   leftChartType: [{ target: "DualAxesChartType" }],
   rightChartType: [{ target: "DualAxesChartType" }]
};

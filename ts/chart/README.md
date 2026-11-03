# @kontext-labs/chart

Reusable chart components, schemas, and utilities for Kontext. Rendering,
validation, conversion, aggregation, and export live here; host apps own
data fetching.

## Features

- **Chart components**: React components for rendering, previewing, and building
  charts (`ChartFactory`, `ChartBuilder`, `ChartPreview`, `ChartDocumentView`)
- **Export**: download charts as PNG, JPEG, SVG, CSV, or JSON
- **Theme support**: light and dark themes
- **Type safety**: full TypeScript coverage, validated with Zod schemas from
  `@kontext-labs/schema`
- **Color palettes**: predefined data-visualization palettes
- **Auto-aggregation**: aggregates data when grouping by fields with duplicates

## Supported Chart Types

The chart type registry is owned by `@kontext-labs/schema`
(`ts/schema/src/charts/`). The 13 types are: `line`, `bar`, `column`, `area`,
`pie`, `scatter`, `dualAxes`, `funnel`, `heatmap`, `histogram`, `box`, `radar`,
and `stock`.

## Quick Start

```tsx
import { ChartFactory } from "@kontext-labs/chart";

const MyChart = () => (
  <ChartFactory
    config={{
      chartType: "line",
      data: [
        { x: 1, y: 2 },
        { x: 2, y: 3 },
        { x: 3, y: 1 }
      ],
      xField: "x",
      yField: "y",
      title: "Sample Line Chart"
    }}
    isDarkMode={false}
  />
);
```

## Core Components

### ChartFactory

Renders a chart from a validated `ChartConfig`.

```tsx
<ChartFactory config={chartConfig} loading={false} isDarkMode={false} />
```

### ChartBuilder

Configuration UI for authoring a `ChartConfig` (uses `ChartPreview` internally).

### ChartPreview

Renders a chart preview, optionally with a config tab.

### ChartExportButton

Exports a chart to PNG, JPEG, SVG, CSV, or JSON.

```tsx
<ChartExportButton chartInstance={chartInstance} data={chartData} filename="my-chart" />
```

## Validation

Chart configs are validated with Zod schemas from `@kontext-labs/schema`:

```ts
import { validateChart } from "@kontext-labs/chart";

const result = validateChart(config, "line");
if (!result.valid) {
  console.error("Validation errors:", result.errors);
}
```

## Types

```ts
import type {
  ChartConfig,
  ChartType,
  LineChartConfig,
  BarChartConfig
} from "@kontext-labs/chart";
```

## Boundary Contract

This package owns **rendering, editing, validation, conversion, aggregation, and
export**. It does **not** own host-specific concerns:

| Responsibility | Owner |
| --- | --- |
| Chart rendering / component tree | `@kontext-labs/chart` |
| Config validation (Zod) | `@kontext-labs/chart` (schemas from `@kontext-labs/schema`) |
| Chart data aggregation (`useChartDataAggregation`) | `@kontext-labs/chart` |
| Remote data loading via file service | App / host layer |
| `DataRef` resolution + React Query | App / host layer |

Host applications (e.g. `app/`) should own the data-fetching hooks and pass the
resolved `DataTable` into `<ChartDocumentView>` or the chart components as props.

## Dependencies

- React 19+, Ant Design 6+, `@ant-design/plots` 2.6+, Zod 4+
- `@kontext-labs/common`, `@kontext-labs/schema`, `@kontext-labs/file`,
  `@kontext-labs/query`, `@kontext-labs/theme`, `@kontext-labs/ui`

## Development

```bash
pnpm --filter @kontext-labs/chart build
pnpm --filter @kontext-labs/chart lint
pnpm --filter @kontext-labs/chart test
```

## Used By

- `@kontext-labs/notebook` — notebook editor with chart blocks
- The Kontext app

## License

MIT

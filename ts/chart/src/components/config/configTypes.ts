import type { ChartConfig } from "@kontext-tech/schema";
import type { Field } from "../../types";

/**
 * Base interface for all chart configuration components
 */
export interface BaseChartConfigProps<T extends ChartConfig = ChartConfig> {
   /** Current configuration values */
   config: T;
   /** Available data fields */
   availableColumns: Field[];
   /** Configuration change handler */
   onChange: (updates: Partial<T>) => void;
   /** Whether the component is readonly */
   readonly?: boolean;
}

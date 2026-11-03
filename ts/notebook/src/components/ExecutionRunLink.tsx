import { EyeOutlined } from "@kontext-tech/icons";
import { Button } from "antd";
import React from "react";
import { useNotebookServices } from "../context/NotebookServiceContext";

/**
 * Inline link that opens the job run details drawer for the managed
 * execution run that produced a block's outputs. Hidden when the run id or
 * the host's drawer binding is unavailable (e.g. in the standalone demo).
 */
const ExecutionRunLink: React.FC<{ executionRunId?: string | null }> = ({
   executionRunId
}) => {
   const { onViewExecutionRun } = useNotebookServices();

   if (!executionRunId || !onViewExecutionRun) {
      return null;
   }

   return (
      <Button
         type="link"
         size="small"
         icon={<EyeOutlined />}
         onClick={() => onViewExecutionRun(executionRunId)}
         style={{
            padding: 0,
            height: "auto",
            textTransform: "none",
            letterSpacing: 0,
            fontSize: 12
         }}
      >
         Run details
      </Button>
   );
};

export default ExecutionRunLink;

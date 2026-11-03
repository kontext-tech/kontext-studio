import { BugOutlined, ReloadOutlined } from "@kontext-tech/icons";
import { Alert, Button, Typography } from "antd";
import React, { type ErrorInfo } from "react";
import { ErrorBoundary, type FallbackProps } from "react-error-boundary";

const { Text, Paragraph } = Typography;

interface BlockErrorBoundaryProps {
   children: React.ReactNode;
   blockId?: string;
   blockType?: string;
   onRetry?: () => void;
   /** Whether to show detailed error information (dev mode) */
   showDetails?: boolean;
}

const getErrorMessage = (error: unknown, blockType?: string): string => {
   if (!error) return "An unexpected error occurred";

   const message = error instanceof Error ? error.message : String(error);

   // Provide user-friendly messages for common errors
   if (message.includes("Maximum update depth exceeded")) {
      return `This ${
         blockType || "block"
      } encountered a rendering loop. Please check your configuration.`;
   }

   if (message.includes("Cannot read properties of undefined")) {
      return `This ${
         blockType || "block"
      } is missing required data. Please reconfigure it.`;
   }

   if (message.includes("Network")) {
      return `Network error occurred while loading this ${
         blockType || "block"
      }.`;
   }

   if (process.env.NODE_ENV === "development") {
      return message;
   }

   return `This ${
      blockType || "block"
   } encountered an error and cannot be displayed.`;
};

const BlockErrorBoundaryFallback: React.FC<
   FallbackProps & {
      blockId?: string;
      blockType?: string;
      showDetails?: boolean;
   }
> = ({
   error,
   resetErrorBoundary,
   blockId,
   blockType = "block",
   showDetails: showDetailsProp
}) => {
   const errorMessage = getErrorMessage(error, blockType);
   const showDetails =
      showDetailsProp || process.env.NODE_ENV === "development";

   return (
      <Alert
         icon={<BugOutlined />}
         type="error"
         message={`Block Error (ID: ${blockId})`}
         description={
            <div>
               <Paragraph
                  style={{
                     marginBottom: showDetails ? "12px" : "8px"
                  }}
               >
                  {errorMessage}
               </Paragraph>

               {showDetails && !!error && (
                  <div style={{ marginBottom: "12px" }}>
                     <Text
                        style={{
                           fontSize: "11px",
                           display: "block",
                           wordBreak: "break-all"
                        }}
                     >
                        {error instanceof Error ? error.stack : String(error)}
                     </Text>
                  </div>
               )}

               <div
                  style={{
                     display: "flex",
                     gap: "8px",
                     alignItems: "center"
                  }}
               >
                  <Button
                     type="primary"
                     icon={<ReloadOutlined />}
                     onClick={resetErrorBoundary}
                  >
                     Retry
                  </Button>
               </div>
            </div>
         }
      />
   );
};

/**
 * Error Boundary component for graceful error handling in notebook blocks.
 * Prevents individual block errors from crashing the entire editor.
 */
const BlockErrorBoundary: React.FC<BlockErrorBoundaryProps> = ({
   children,
   blockId,
   blockType,
   onRetry,
   showDetails
}) => {
   const logError = (error: unknown, info: ErrorInfo) => {
      console.error(`[BlockErrorBoundary] Error caught:`, {
         blockId,
         blockType,
         error: error instanceof Error ? error.message : String(error),
         stack: error instanceof Error ? error.stack : undefined,
         componentStack: info.componentStack
      });
   };

   return (
      <ErrorBoundary
         FallbackComponent={(props) => (
            <BlockErrorBoundaryFallback
               {...props}
               blockId={blockId}
               blockType={blockType}
               showDetails={showDetails}
            />
         )}
         onReset={onRetry}
         onError={logError}
      >
         {children}
      </ErrorBoundary>
   );
};

export default BlockErrorBoundary;

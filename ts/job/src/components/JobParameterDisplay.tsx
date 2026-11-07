import { LoadingSpinner } from "@kontext-tech/ui";
import type { UnifiedJobParameterModel } from "@kontext-tech/schema";
import { JobParameterType } from "@kontext-tech/schema";
import { Alert, Descriptions, Tag, Typography } from "antd";
import React, { useEffect, useMemo, useState } from "react";
import type { FetchJobParametersByTypeFn } from "../jobTypes";

const { Text, Paragraph } = Typography;

interface JobParameterDisplayProps {
   configuredParameters?: string;
   jobType?: string;
   fetchJobParametersByType?: FetchJobParametersByTypeFn;
}

interface ParsedParameters {
   [key: string]: unknown;
}

const JobParameterDisplay: React.FC<JobParameterDisplayProps> = ({
   configuredParameters,
   jobType,
   fetchJobParametersByType
}) => {
   const [internalParameterDefinitions, setInternalParameterDefinitions] =
      useState<UnifiedJobParameterModel[]>([]);
   const [isLoadingDefinitions, setIsLoadingDefinitions] = useState(false);
   const [definitionError, setDefinitionError] = useState<string | null>(null);
   const parsedParameters = useMemo<ParsedParameters>(() => {
      if (!configuredParameters) {
         return {};
      }

      try {
         return JSON.parse(configuredParameters);
      } catch (error) {
         console.error("Failed to parse configured parameters:", error);
         return {};
      }
   }, [configuredParameters]);

   useEffect(() => {
      const loadDefinitions = async () => {
         if (!jobType || !fetchJobParametersByType) {
            setInternalParameterDefinitions([]);
            setIsLoadingDefinitions(false);
            return;
         }

         setIsLoadingDefinitions(true);
         setDefinitionError(null);
         try {
            const definitions = await fetchJobParametersByType(jobType);
            setInternalParameterDefinitions(definitions);
         } catch (error) {
            console.error("Error fetching parameter definitions:", error);
            setDefinitionError(
               "An unexpected error occurred while fetching parameter definitions."
            );
            setInternalParameterDefinitions([]);
         } finally {
            setIsLoadingDefinitions(false);
         }
      };

      loadDefinitions();
   }, [jobType, fetchJobParametersByType]);

   const formatParameterValue = (
      value: unknown,
      type?: string
   ): React.ReactNode => {
      if (value === null || typeof value === "undefined") {
         return <Text type="secondary">Not set</Text>;
      }

      switch (type) {
         case JobParameterType.Boolean:
            return value ? <Tag color="success">Yes</Tag> : <Tag>No</Tag>;
         case JobParameterType.Integer:
         case JobParameterType.String:
            return String(value);
         default:
            if (typeof value === "object") {
               try {
                  return (
                     <Paragraph
                        code
                        copyable
                        ellipsis={{ rows: 3, expandable: true }}
                        style={{ marginBottom: 0, whiteSpace: "pre-wrap" }}
                     >
                        {JSON.stringify(value, null, 2)}
                     </Paragraph>
                  );
               } catch {
                  return String(value);
               }
            }
            return String(value);
      }
   };

   if (!configuredParameters) {
      return (
         <div style={{ textAlign: "center", padding: "50px 0" }}>
            <Text type="secondary">
               No parameters were configured for this job run.
            </Text>
         </div>
      );
   }

   if (isLoadingDefinitions) {
      return (
         <div style={{ textAlign: "center", padding: "50px 0" }}>
            <LoadingSpinner />
         </div>
      );
   }

   if (definitionError) {
      return (
         <Alert
            title="Error Loading Definitions"
            description={definitionError}
            type="error"
            showIcon
            style={{ marginTop: 16 }}
         />
      );
   }

   if (
      internalParameterDefinitions.length === 0 &&
      Object.keys(parsedParameters).length > 0
   ) {
      return (
         <>
            <Descriptions bordered column={1} size="small">
               {Object.keys(parsedParameters).map((key) => (
                  <Descriptions.Item key={key} label={key}>
                     {formatParameterValue(parsedParameters[key], undefined)}
                  </Descriptions.Item>
               ))}
            </Descriptions>
            <Text
               type="secondary"
               style={{ marginTop: 8, display: "block", fontSize: "12px" }}
            >
               Parameter definitions not available for enhanced display.
            </Text>
         </>
      );
   }

   if (Object.keys(parsedParameters).length === 0) {
      return (
         <div style={{ textAlign: "center", padding: "50px 0" }}>
            <Text type="secondary">
               No parameters were configured for this job run.
            </Text>
         </div>
      );
   }

   return (
      <Descriptions bordered column={1} size="small">
         {Object.keys(parsedParameters).map((key) => {
            const paramDef = internalParameterDefinitions.find(
               (parameter) => parameter.name === key
            );
            return (
               <Descriptions.Item
                  key={key}
                  label={paramDef ? paramDef.name : key}
               >
                  {formatParameterValue(parsedParameters[key], paramDef?.type)}
               </Descriptions.Item>
            );
         })}
      </Descriptions>
   );
};

export default JobParameterDisplay;

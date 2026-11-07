import { LoadingOutlined } from "@kontext-tech/icons";
import { Flex, Spin } from "antd";
import type { SizeType } from "antd/es/config-provider/SizeContext";
import React from "react";

interface LoadingSpinnerProps {
   size?: "small" | "medium" | "large";
   className?: string;
   style?: React.CSSProperties;
}

const sizeMap: Record<"small" | "medium" | "large", SizeType> = {
   small: "small",
   medium: undefined as unknown as SizeType,
   large: "large"
} as const;

const LoadingSpinner: React.FC<LoadingSpinnerProps> = ({
   size = "medium",
   className,
   style
}) => (
   <Flex justify="center" align="center" className={className} style={style}>
      <Spin size={sizeMap[size]} indicator={<LoadingOutlined spin />} />
   </Flex>
);

export default LoadingSpinner;

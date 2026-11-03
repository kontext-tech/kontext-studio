import { Space, Typography } from "antd";
import type { MenuProps } from "antd/es/menu";
import type { CSSProperties, ReactNode } from "react";

const { Link, Text } = Typography;

const PLATFORM_LEGAL_LINKS = [
   { key: "terms", label: "Terms", path: "/terms" },
   { key: "privacy", label: "Privacy", path: "/privacy" }
] as const;

export interface PlatformLegalLinksProps {
   linkStyle?: CSSProperties;
   separator?: ReactNode;
}

export const getPlatformBaseUrl = () =>
   window.ENV?.PUBLIC_KONTEXT_URL || window.location.origin;

export const getPlatformVersion = () => window.ENV?.VERSION || "v0.0.0";

export const openPlatformPath = (path: string, target: string = "_blank") => {
   window.open(`${getPlatformBaseUrl()}${path}`, target);
};

export const getPlatformLegalMenuItems = (): MenuProps["items"] =>
   PLATFORM_LEGAL_LINKS.map((link) => ({
      key: link.key,
      label: link.label,
      onClick: () => openPlatformPath(link.path)
   }));

export const PlatformLegalLinks = ({
   linkStyle,
   separator = <Text type="secondary">·</Text>
}: PlatformLegalLinksProps) => (
   <Space separator={separator}>
      {PLATFORM_LEGAL_LINKS.map((link) => (
         <Link
            key={link.key}
            onClick={() => openPlatformPath(link.path)}
            style={linkStyle}
         >
            {link.label}
         </Link>
      ))}
   </Space>
);

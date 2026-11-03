import {
   BookOutlined,
   FileTextOutlined,
   InfoCircleOutlined,
   UserOutlined
} from "@kontext-labs/icons";
import { getFullUrl } from "@kontext-labs/common/utils";
import type { MenuProps } from "antd/es/menu";
import React from "react";
import { getPlatformLegalMenuItems } from "./PlatformLegalLinks";

export interface HelpLink {
   key: string;
   icon: React.ReactNode;
   label: string;
   url: string;
   description?: string;
}

export const getHelpLinks = (): HelpLink[] => [
   {
      key: "docs",
      icon: React.createElement(BookOutlined),
      label: "Docs",
      url: getFullUrl("docs"),
      description: "Access comprehensive documentation and guides"
   },
   {
      key: "about",
      icon: React.createElement(InfoCircleOutlined),
      label: "About",
      url: getFullUrl("about"),
      description: "Learn more about Kontext"
   },
   {
      key: "contact",
      icon: React.createElement(UserOutlined),
      label: "Contact",
      url: getFullUrl("contact"),
      description: "Get in touch with our support team"
   }
];

export const getHelpMenuItems = (): MenuProps["items"] =>
   getHelpLinks().map((link) => ({
      key: link.key,
      icon: link.icon,
      label: link.label,
      onClick: () => window.open(link.url, "_blank")
   }));

export const getLegalMenuItems = (): MenuProps["items"] => [
   {
      key: "legal",
      icon: React.createElement(FileTextOutlined),
      label: "Legal",
      children: getPlatformLegalMenuItems()
   }
];

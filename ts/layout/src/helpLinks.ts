import {
   BookOutlined,
   FileTextOutlined,
   InfoCircleOutlined,
   UserOutlined
} from "@kontext-labs/icons";
import { getDocsUrl, getPlatformPageUrl } from "@kontext-labs/common/utils";
import type { MenuProps } from "antd/es/menu";
import React from "react";

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
      url: getDocsUrl(),
      description: "Access comprehensive documentation and guides"
   },
   {
      key: "about",
      icon: React.createElement(InfoCircleOutlined),
      label: "About",
      url: getPlatformPageUrl("about"),
      description: "Learn more about Kontext"
   },
   {
      key: "contact",
      icon: React.createElement(UserOutlined),
      label: "Contact",
      url: getPlatformPageUrl("contact"),
      description: "Get in touch with our support team"
   },
   {
      key: "license",
      icon: React.createElement(FileTextOutlined),
      label: "License",
      url: "https://github.com/kontext-tech/kontext-labs/blob/main/LICENSE",
      description: "Kontext Labs is released under the MIT License"
   },
   {
      key: "notices",
      icon: React.createElement(FileTextOutlined),
      label: "Third-party notices",
      url: "https://github.com/kontext-tech/kontext-labs/blob/main/THIRD_PARTY_NOTICES.md",
      description: "Licenses for the open-source packages Kontext Labs uses"
   }
];

export const getHelpMenuItems = (): MenuProps["items"] =>
   getHelpLinks().map((link) => ({
      key: link.key,
      icon: link.icon,
      label: link.label,
      onClick: () => window.open(link.url, "_blank")
   }));

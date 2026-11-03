import React from "react";
import {
   ArrowLeftRightOutlined,
   BellOutlined,
   BellPlusOutlined,
   BookOutlined,
   ChartNoAxesCombinedOutlined,
   CircleCheckBigOutlined,
   ClockCircleOutlined,
   CodeOutlined,
   ControlOutlined,
   DashboardOutlined,
   DatabaseOutlined,
   DatabaseZapOutlined,
   DatasetOutlined,
   DeleteOutlined,
   EditOutlined,
   EyeOutlined,
   FileChartLineOutlined,
   FileCodeOutlined,
   FileImageOutlined,
   FileOutlined,
   FileTextOutlined,
   FilterOutlined,
   HeartOutlined,
   HistoryOutlined,
   HomeOutlined,
   KeyOutlined,
   LineChartOutlined,
   MailPlusOutlined,
   MailsOutlined,
   MessageCircleCodeOutlined,
   MessageOutlined,
   MinusOutlined,
   MinusSquareOutlined,
   NotebookOutlined,
   PlayCircleOutlined,
   PlusOutlined,
   PlusSquareOutlined,
   ProjectOutlined,
   ProjectsOutlined,
   ReloadOutlined,
   RobotOutlined,
   SettingOutlined,
   SparklesOutlined,
   SquareArrowLeftOutlined,
   SquareArrowRightOutlined,
   StopOutlined,
   SunMoonOutlined,
   TableOutlined,
   TicketOutlined,
   UserGroupOutlined,
   UserOutlined,
   ViewOutlined,
   Wand2Outlined
} from "./lucide";

/**
 * Map of icon names to their corresponding components
 * Only include icons that are actually used in the application
 */
const ICON_MAP: Record<string, React.ComponentType> = {
   HomeOutlined,
   ProjectOutlined,
   FileOutlined,
   FileTextOutlined,
   FileImageOutlined,
   BellOutlined,
   BellPlusOutlined,
   BookOutlined,
   UserOutlined,
   HistoryOutlined,
   SettingOutlined,
   DashboardOutlined,
   ControlOutlined,
   PlayCircleOutlined,
   PlusOutlined,
   EditOutlined,
   DeleteOutlined,
   ReloadOutlined,
   RobotOutlined,
   BotOutlined: RobotOutlined,
   CodeOutlined,
   FileCodeOutlined,
   FileCode: FileCodeOutlined,
   SparklesOutlined,
   Sparkles: SparklesOutlined,
   DatabaseZapOutlined,
   DatabaseZap: DatabaseZapOutlined,
   SquareArrowLeftOutlined,
   SquareArrowRightOutlined,
   StopOutlined,
   EyeOutlined,
   FilterOutlined,
   ClockCircleOutlined,
   DatabaseOutlined,
   DatasetOutlined,
   TableOutlined,
   TicketOutlined,
   SunMoonOutlined,
   ViewOutlined,
   Wand2Outlined,
   WandOutlined: Wand2Outlined,
   MinusOutlined,
   MinusSquareOutlined,
   PlusSquareOutlined,
   KeyOutlined,
   UserGroupOutlined,
   HeartOutlined,
   ProjectsOutlined,
   MailsOutlined,
   MailPlusOutlined,
   MessageOutlined,
   MessageCircleCodeOutlined,
   NotebookOutlined,
   Notebook: NotebookOutlined,
   ArrowLeftRightOutlined,
   CircleCheckBigOutlined,
   LineChartOutlined,
   FileChartLineOutlined,
   ChartNoAxesCombinedOutlined
};

/**
 * Type to represent all available icon names
 */
export type IconName = keyof typeof ICON_MAP;

/**
 * Creates an Ant Design icon component from its name
 *
 * @param iconName The name of the icon to create (e.g., "HomeOutlined", "UserOutlined")
 * @param props Optional props to pass to the icon component
 * @returns The React element representing the icon or undefined if not found
 */
export const createIconFromName = (
   iconName?: string,
   props: Record<string, unknown> = {}
): React.ReactElement | undefined => {
   if (!iconName) return undefined;

   // Check if the icon name exists in our map (case-insensitive check for robustness)
   const foundKey =
      iconName in ICON_MAP
         ? iconName
         : Object.keys(ICON_MAP).find(
              (k) => k.toLowerCase() === iconName.toLowerCase()
           );

   if (!foundKey) {
      // Log warning but don't throw to prevent UI crashes
      console.warn(`Icon "${iconName}" not found in the application icon map`);
      return undefined;
   }

   const IconComponent = ICON_MAP[foundKey];
   return React.createElement(IconComponent, props);
};

/**
 * Safely gets an icon component from a string name
 * Use this when the icon name comes from external data or user input
 *
 * @param iconName The string name of the icon to get
 * @returns The React element for the icon or null if not found
 */
export const getSafeIconByName = (
   iconName: string
): React.ReactElement | null => {
   return createIconFromName(iconName) || null;
};

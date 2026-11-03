import {
   BarChart3,
   Bell,
   BellPlus,
   Bot,
   Boxes,
   Clock,
   Code2,
   Database,
   Edit3,
   FolderOpen,
   Heading,
   Heart,
   Home,
   Image,
   Images,
   List,
   ListChecks,
   Loader2,
   LogOut,
   MessageCircle,
   Minus,
   Monitor,
   Moon,
   Play,
   Plus,
   Quote as QuoteIcon,
   Reply,
   Save,
   Settings,
   Sun,
   Table,
   Trash2,
   Type,
   User,
   X
} from "lucide";

export type IconNode = [string, Record<string, string | number | undefined>][];

// Helper to convert Lucide IconNode to SVG string
export const lucideToSvg = (
   iconNode: IconNode,
   size: number = 24,
   strokeWidth: number = 2
): string => {
   const renderIconNode = (node: IconNode): string => {
      return node
         .map(([tag, attrs]) => {
            const attributes = Object.entries(attrs)
               .filter(([, value]) => value !== undefined)
               .map(([key, value]) => `${key}="${value}"`)
               .join(" ");
            return `<${tag} ${attributes}></${tag}>`;
         })
         .join("");
   };

   const svgContent = renderIconNode(iconNode);

   return `<svg width="${size}" height="${size}" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="${strokeWidth}" stroke-linecap="round" stroke-linejoin="round">${svgContent}</svg>`;
};

// SVG strings for use in non-React contexts (like EditorJS)
// All icons are generated at 24px for optimal quality and scaled via CSS/containers
export const BlockIcons = {
   sql: lucideToSvg(Database, 24),
   chart: lucideToSvg(BarChart3, 24),
   play: lucideToSvg(Play, 24),
   close: lucideToSvg(X, 24),
   loading: lucideToSvg(Loader2, 24),
   edit: lucideToSvg(Edit3, 24),
   save: lucideToSvg(Save, 24),
   sun: lucideToSvg(Sun, 24),
   moon: lucideToSvg(Moon, 24),
   monitor: lucideToSvg(Monitor, 24),
   header: lucideToSvg(Heading, 24),
   list: lucideToSvg(List, 24),
   quote: lucideToSvg(QuoteIcon, 24),
   code: lucideToSvg(Code2, 24),
   paragraph: lucideToSvg(Type, 24),
   checklist: lucideToSvg(ListChecks, 24),
   delimiter: lucideToSvg(Minus, 24),
   table: lucideToSvg(Table, 24),
   image: lucideToSvg(Image, 24),
   images: lucideToSvg(Images, 24),
   messageCircle: lucideToSvg(MessageCircle, 24),
   plus: lucideToSvg(Plus, 24),
   reply: lucideToSvg(Reply, 24),
   delete: lucideToSvg(Trash2, 24),
   user: lucideToSvg(User, 24),
   home: lucideToSvg(Home, 24),
   folderOpen: lucideToSvg(FolderOpen, 24),
   settings: lucideToSvg(Settings, 24),
   bell: lucideToSvg(Bell, 24),
   logOut: lucideToSvg(LogOut, 24),
   clock: lucideToSvg(Clock, 24),
   heart: lucideToSvg(Heart, 24),
   bellPlus: lucideToSvg(BellPlus, 24),
   projects: lucideToSvg(Boxes, 24),
   bot: lucideToSvg(Bot, 24)
};

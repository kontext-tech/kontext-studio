// Lucide Icons - Uses base lucide package for optimal tree-shaking and consistency
import Icon from "@ant-design/icons";
import type { IconNode } from "@kontext-tech/common";
import type { GetProps } from "antd";
import {
   AlertCircle,
   AlertTriangle,
   ArrowLeft,
   ArrowLeftRight,
   ArrowRight,
   BarChart3,
   Bell,
   BellMinus,
   BellPlus,
   Book,
   Bot,
   Box,
   Boxes,
   Calendar,
   Camera,
   ChartArea,
   ChartBar,
   ChartColumn,
   ChartLine,
   ChartNoAxesCombined,
   ChartPie,
   ChartScatter,
   Check,
   CheckCircle,
   ChevronDown,
   ChevronRight,
   ChevronUp,
   CircleCheckBig,
   Clock,
   CloudUpload,
   Code2,
   Copy,
   Database,
   DatabaseZap,
   Download,
   Edit,
   Eye,
   EyeOff,
   File,
   FileChartLine,
   FileCode,
   FileCog,
   FileDigit,
   FileJson,
   FilePlus,
   FileSpreadsheet,
   FileText,
   Filter,
   Globe,
   Heart,
   HelpCircle,
   History,
   Home,
   Images,
   Import,
   Inbox,
   Info,
   Key,
   LayoutDashboard,
   Link,
   List,
   ListOrdered,
   Loader2,
   Lock,
   LogIn,
   LogOut,
   MailPlus,
   Mails,
   Maximize2,
   Menu,
   MessageCircle,
   MessageCircleCode,
   MessageSquare,
   Minimize2,
   Minus,
   MinusSquare,
   Moon,
   MoreHorizontal,
   MoreVertical,
   Notebook,
   Package,
   PanelLeft,
   PanelLeftClose,
   PanelLeftOpen,
   PanelRight,
   PanelRightClose,
   PanelRightOpen,
   Pen,
   PictureInPicture2,
   Play,
   PlayCircle,
   Plus,
   PlusSquare,
   RefreshCw,
   Reply,
   Save,
   Search,
   Settings,
   Shield,
   ShieldCheck,
   Shuffle,
   SortAsc,
   Sparkles,
   SquareArrowLeft,
   SquareArrowRight,
   StopCircle,
   Sun,
   SunMoon,
   Table,
   Tag,
   Terminal,
   ThumbsDown,
   ThumbsUp,
   Ticket,
   Trash2,
   TrendingUp,
   Trophy,
   Unlock,
   User,
   UserCheck,
   UserPlus,
   Users,
   UserSquare,
   Wand2,
   Wrench,
   X,
   XCircle,
   ZoomIn,
   ZoomOut
} from "lucide";
import React from "react";

type AntdIconProps = GetProps<typeof Icon>;

// Create a component that renders the SVG string
const SvgComponent = ({
   iconNode,
   ...svgProps
}: React.SVGProps<SVGSVGElement> & { iconNode: IconNode }) => {
   return (
      <svg
         width="1em"
         height="1em"
         viewBox="0 0 24 24"
         fill="none"
         stroke="currentColor"
         strokeWidth="2"
         strokeLinecap="round"
         strokeLinejoin="round"
         {...svgProps}
      >
         {iconNode.map(([tag, attrs], index) => {
            const Component = tag as
               | "path"
               | "circle"
               | "rect"
               | "line"
               | "polyline"
               | "polygon"
               | "ellipse"
               | "rect";
            return <Component key={index} {...attrs} />;
         })}
      </svg>
   );
};

// Helper to create Antd-compatible icons from Lucide SVG strings
const createLucideIcon = (iconNode: IconNode) => {
   const AntdIcon = React.forwardRef<HTMLSpanElement, AntdIconProps>(
      (props, ref) => {
         const { style, ...restProps } = props;
         return (
            <Icon
               component={() => <SvgComponent iconNode={iconNode} />}
               style={{
                  fontSize: "16px",
                  ...style
               }}
               {...restProps}
               ref={ref}
            />
         );
      }
   );
   AntdIcon.displayName = `AntdIcon(LucideIcon)`;
   return AntdIcon;
};

// Navigation & Layout Icons
export const ArrowLeftOutlined = createLucideIcon(ArrowLeft);
export const ArrowLeftRightOutlined = createLucideIcon(ArrowLeftRight);
export const ArrowRightOutlined = createLucideIcon(ArrowRight);
export const BellOutlined = createLucideIcon(Bell);
export const BellMinusOutlined = createLucideIcon(BellMinus);
export const BellPlusOutlined = createLucideIcon(BellPlus);
export const MailPlusOutlined = createLucideIcon(MailPlus);
export const MailsOutlined = createLucideIcon(Mails);
export const HomeOutlined = createLucideIcon(Home);
export const MenuOutlined = createLucideIcon(Menu);
export const MoreOutlined = createLucideIcon(MoreHorizontal);
export const MoreVerticalOutlined = createLucideIcon(MoreVertical);
export const PackageOutlined = createLucideIcon(Package);
export const PanelLeftOutlined = createLucideIcon(PanelLeft);
export const PanelLeftCloseOutlined = createLucideIcon(PanelLeftClose);
export const PanelLeftOpenOutlined = createLucideIcon(PanelLeftOpen);
export const PanelRightOutlined = createLucideIcon(PanelRight);
export const PanelRightCloseOutlined = createLucideIcon(PanelRightClose);
export const PanelRightOpenOutlined = createLucideIcon(PanelRightOpen);
export const PenOutlined = createLucideIcon(Pen);
export const SquareArrowLeftOutlined = createLucideIcon(SquareArrowLeft);
export const SquareArrowRightOutlined = createLucideIcon(SquareArrowRight);
export const PictureOutlined = createLucideIcon(PictureInPicture2);

// File & Content Icons
export const BookOutlined = createLucideIcon(Book);
export const FileAddOutlined = createLucideIcon(FilePlus);
export const FileChartLineOutlined = createLucideIcon(FileChartLine);
export const FileChartColumnOutlined = createLucideIcon(ChartColumn);
export const FileCodeOutlined = createLucideIcon(FileCode);
export const FileCogOutlined = createLucideIcon(FileCog);
export const FileDigitOutlined = createLucideIcon(FileDigit);
export const FileImageOutlined = createLucideIcon(Images);
export const FileJsonOutlined = createLucideIcon(FileJson);
export const FileOutlined = createLucideIcon(File);
export const FileProtectOutlined = createLucideIcon(Lock);
export const FileSpreadsheetOutlined = createLucideIcon(FileSpreadsheet);
export const FileTextOutlined = createLucideIcon(FileText);
export const FormOutlined = createLucideIcon(Edit);
export const ImagesOutlined = createLucideIcon(Images);
export const OrderedListOutlined = createLucideIcon(ListOrdered);
export const NotebookOutlined = createLucideIcon(Notebook);

// User & Account Icons
export const LoginOutlined = createLucideIcon(LogIn);
export const LogoutOutlined = createLucideIcon(LogOut);
export const RobotOutlined = createLucideIcon(Bot);
export const SafetyOutlined = createLucideIcon(ShieldCheck);
export const UserAddOutlined = createLucideIcon(UserPlus);
export const UserOutlined = createLucideIcon(User);
export const UserCheckOutlined = createLucideIcon(UserCheck);
export const UserGroupOutlined = createLucideIcon(Users);

// Action Icons
export const CheckCircleOutlined = createLucideIcon(CheckCircle);
export const CircleCheckBigOutlined = createLucideIcon(CircleCheckBig);
export const CheckOutlined = createLucideIcon(Check);
export const CloseCircleOutlined = createLucideIcon(XCircle);
export const CloseOutlined = createLucideIcon(X);
export const CopyOutlined = createLucideIcon(Copy);
export const DeleteOutlined = createLucideIcon(Trash2);
export const DownloadOutlined = createLucideIcon(Download);
export const EditOutlined = createLucideIcon(Edit);
export const ExportOutlined = createLucideIcon(Download);
export const EyeInvisibleOutlined = createLucideIcon(EyeOff);
export const EyeOutlined = createLucideIcon(Eye);
export const ImportOutlined = createLucideIcon(Import);
export const PlayCircleOutlined = createLucideIcon(PlayCircle);
export const PlusOutlined = createLucideIcon(Plus);
export const ReloadOutlined = createLucideIcon(RefreshCw);
export const SaveOutlined = createLucideIcon(Save);
export const SearchOutlined = createLucideIcon(Search);
export const StopOutlined = createLucideIcon(StopCircle);
export const ErrorOutlined = createLucideIcon(AlertCircle);
export const SyncOutlined = createLucideIcon(RefreshCw);
export const UndoOutlined = createLucideIcon(RefreshCw);
export const UploadOutlined = createLucideIcon(CloudUpload);

// Status & Feedback Icons
export const BugOutlined = createLucideIcon(AlertTriangle);
export const ExclamationCircleOutlined = createLucideIcon(AlertCircle);
export const InfoCircleOutlined = createLucideIcon(Info);
export const LoadingOutlined = createLucideIcon(Loader2);
export const QuestionCircleOutlined = createLucideIcon(HelpCircle);
export const WarningOutlined = createLucideIcon(AlertTriangle);
export { LinkedinOutlined } from "@ant-design/icons";

// Time & Calendar Icons
export const CalendarOutlined = createLucideIcon(Calendar);
export const ClockCircleOutlined = createLucideIcon(Clock);
export const HistoryOutlined = createLucideIcon(History);

// Security & Privacy Icons
export const GlobalOutlined = createLucideIcon(Globe);
export const KeyOutlined = createLucideIcon(Key);
export const LockOutlined = createLucideIcon(Lock);
export const TicketOutlined = createLucideIcon(Ticket);
export const SecurityScanOutlined = createLucideIcon(Shield);
export const UnlockOutlined = createLucideIcon(Unlock);

// System & Admin Icons
export const CodeOutlined = createLucideIcon(Code2);
export const ControlOutlined = createLucideIcon(Play);
export const DashboardOutlined = createLucideIcon(LayoutDashboard);
export const DeploymentUnitOutlined = createLucideIcon(CloudUpload);
export const ProjectOutlined = createLucideIcon(Box);
export const ProjectsOutlined = createLucideIcon(Boxes);
export const SettingOutlined = createLucideIcon(Settings);
export const TerminalOutlined = createLucideIcon(Terminal);
export const ToolOutlined = createLucideIcon(Wrench);

// Social & Interaction Icons
export const CommentOutlined = createLucideIcon(MessageSquare);
export const ReplyOutlined = createLucideIcon(Reply);
export const DislikeOutlined = createLucideIcon(ThumbsDown);
export const HeartOutlined = createLucideIcon(Heart);
export const LikeFilled = createLucideIcon(ThumbsUp);
export const LikeOutlined = createLucideIcon(ThumbsUp);
export const LinkOutlined = createLucideIcon(Link);
export const MessageOutlined = createLucideIcon(MessageCircle);
export const MessageCircleCodeOutlined = createLucideIcon(MessageCircleCode);
export const TrophyOutlined = createLucideIcon(Trophy);

// UI & Display Icons
export const CameraOutlined = createLucideIcon(Camera);
export const DownOutlined = createLucideIcon(ChevronDown);
export const RightOutlined = createLucideIcon(ChevronRight);
export const UpOutlined = createLucideIcon(ChevronUp);
export const ExpandAltOutlined = createLucideIcon(Maximize2);
export const FilterOutlined = createLucideIcon(Filter);
export const MoonOutlined = createLucideIcon(Moon);
export const ProfileOutlined = createLucideIcon(UserSquare);
export const ShrinkOutlined = createLucideIcon(Minimize2);
export const SortAscendingOutlined = createLucideIcon(SortAsc);
export const SunOutlined = createLucideIcon(Sun);
export const SunMoonOutlined = createLucideIcon(SunMoon);
export const SwapOutlined = createLucideIcon(Shuffle);
export const TagOutlined = createLucideIcon(Tag);
export const ZoomInOutlined = createLucideIcon(ZoomIn);
export const ZoomOutOutlined = createLucideIcon(ZoomOut);

// Database & Dataset Icons
export const DatabaseOutlined = createLucideIcon(Database);
export const DatabaseZapOutlined = createLucideIcon(DatabaseZap);
export const DatasetOutlined = createLucideIcon(Table);
export const InboxOutlined = createLucideIcon(Inbox);
export const TableOutlined = createLucideIcon(Table);
export const ViewOutlined = createLucideIcon(List);
export const ChartLineOutlined = createLucideIcon(ChartLine);

// Chart Icons
export const AreaChartOutlined = createLucideIcon(ChartArea);
export const BarChartOutlined = createLucideIcon(ChartBar);
export const ChartNoAxesCombinedOutlined =
   createLucideIcon(ChartNoAxesCombined);
export const ColumnChartOutlined = createLucideIcon(BarChart3);
export const LineChartOutlined = createLucideIcon(ChartLine);
export const PieChartOutlined = createLucideIcon(ChartPie);
export const DotChartOutlined = createLucideIcon(ChartScatter);
export const StockOutlined = createLucideIcon(TrendingUp);

// Tree Expand/Collapse Icons
export const MinusOutlined = createLucideIcon(Minus);
export const MinusSquareOutlined = createLucideIcon(MinusSquare);
export const PlusSquareOutlined = createLucideIcon(PlusSquare);

// Magic & AI Icons
export const SparklesOutlined = createLucideIcon(Sparkles);
export const Wand2Outlined = createLucideIcon(Wand2);

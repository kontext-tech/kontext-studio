import PageHeader from "@/components/common/PageHeader";
import useCanonicalUrl from "@/hooks/useCanonicalUrl";
import { RouteNames } from "@/types";
import type { ProjectModel, ProjectNavModel } from "@kontext-labs/schema";
import { MetaTags } from "@kontext-labs/site";
import { PageContainer as SharedPageContainer } from "@kontext-labs/ui";
import React, { type ReactNode } from "react";
import BreadcrumbNav from "./BreadcrumbNav";

interface PageContainerProps {
   /**
    * Page title - used for both MetaTags and PageHeader
    */
   title: string;

   /**
    * Optional subtitle to display below the main title in the PageHeader
    */
   subTitle?: string;

   /**
    * Page description for SEO
    */
   description?: string;

   /**
    * Route name for generating canonical URL and breadcrumbs
    */
   routeName: RouteNames;

   /**
    * Optional project for project-specific routes
    */
   project?: ProjectNavModel | ProjectModel | null;

   /**
    * Optional keywords for SEO
    */
   keywords?: string;

   /**
    * Optional image URL for social sharing
    */
   imageUrl?: string;

   /**
    * Type of content (defaults to website)
    */
   type?: "website" | "article" | "project";

   /**
    * Optional custom canonical URL - will override the auto-generated one
    */
   customCanonicalUrl?: string;

   /**
    * Optional language code
    */
   lang?: string;

   /**
    * Action buttons or other elements to display on the right side of the header
    */
   actions?: ReactNode;

   /**
    * Additional content to display below the header (e.g., description, alert)
    */
   subContent?: ReactNode;

   /**
    * Whether to show breadcrumb navigation (defaults to true)
    */
   showBreadcrumb?: boolean;

   /**
    * Whether to show the page title in the header (defaults to true)
    */
   showPageTitle?: boolean;

   /**
    * Header presentation style for app pages
    */
   headerVariant?: "document" | "application";

   /**
    * Whether to remove all default padding and gaps (useful for full-screen views like chat)
    */
   fluid?: boolean;

   /**
    * Optional max width for pages that need a readable-width content column
    */
   contentMaxWidth?: number | string;

   /**
    * Optional style for the container
    */
   style?: React.CSSProperties;

   /**
    * The main content of the page
    */
   children: ReactNode;
}

/**
 * PageContainer is a higher-order component that combines MetaTags, PageHeader,
 * and BreadcrumbNav with automatic canonical URL generation.
 */
const PageContainer: React.FC<PageContainerProps> = ({
   title,
   subTitle,
   description,
   routeName,
   project,
   keywords,
   imageUrl,
   type = "website",
   customCanonicalUrl,
   lang,
   actions,
   subContent,
   showBreadcrumb = false,
   showPageTitle = true,
   headerVariant = "application",
   fluid = false,
   contentMaxWidth,
   style,
   children
}) => {
   const getCanonicalUrl = useCanonicalUrl();
   const canonicalUrl =
      customCanonicalUrl || getCanonicalUrl(routeName, project);
   const pageBodyPadding = "16px var(--app-page-content-padding, 24px) 24px";
   const useApplicationChrome =
      showPageTitle &&
      headerVariant === "application" &&
      !fluid &&
      !contentMaxWidth;
   const applicationBodyIntro = useApplicationChrome ? subContent : undefined;
   const headerContent = showPageTitle ? (
      <PageHeader
         title={title}
         actions={actions}
         subContent={useApplicationChrome ? undefined : subContent}
         variant={headerVariant}
         breadcrumb={
            showBreadcrumb ? (
               <BreadcrumbNav routeName={routeName} project={project} />
            ) : undefined
         }
      />
   ) : undefined;
   const containerStyle = fluid
      ? style
      : useApplicationChrome
        ? style
        : {
             padding: pageBodyPadding,
             ...style
          };
   const pageContent = fluid ? (
      children
   ) : useApplicationChrome ? (
      <div
         style={{
            padding: pageBodyPadding,
            flex: 1,
            minHeight: 0
         }}
      >
         {applicationBodyIntro && (
            <div style={{ marginBottom: 16 }}>{applicationBodyIntro}</div>
         )}
         {children}
      </div>
   ) : (
      children
   );

   return (
      <SharedPageContainer
         gap={useApplicationChrome ? 0 : "small"}
         fluid={fluid}
         contentMaxWidth={fluid ? undefined : contentMaxWidth}
         showPageTitle={showPageTitle}
         style={containerStyle}
         topContent={
            <>
               <MetaTags
                  title={title}
                  subTitle={subTitle}
                  description={description}
                  keywords={keywords}
                  imageUrl={imageUrl}
                  type={type}
                  canonicalUrl={canonicalUrl}
                  projectName={project?.projectName}
                  lang={lang}
               />
            </>
         }
         header={
            useApplicationChrome ? (
               <div
                  style={{
                     marginTop:
                        "calc(var(--app-shell-content-padding, 0px) * -1)",
                     marginLeft:
                        "calc(var(--app-shell-content-padding, 0px) * -1)",
                     marginRight:
                        "calc(var(--app-shell-content-padding, 0px) * -1)",
                     position: "sticky",
                     top: "calc(var(--app-shell-content-padding, 0px) * -1)",
                     zIndex: 20
                  }}
               >
                  {headerContent}
               </div>
            ) : (
               headerContent
            )
         }
         actions={showPageTitle ? undefined : actions}
         subContent={
            showPageTitle
               ? useApplicationChrome
                  ? undefined
                  : subContent
               : subContent
         }
      >
         {pageContent}
      </SharedPageContainer>
   );
};

export default PageContainer;

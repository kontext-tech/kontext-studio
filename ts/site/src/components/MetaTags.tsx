import { useEffect } from "react";

export interface MetaTagsProps {
   title: string;
   subTitle?: string;
   description?: string;
   keywords?: string;
   imageUrl?: string;
   type?: "website" | "article" | "project";
   canonicalUrl?: string;
   projectName?: string;
   lang?: string;
}

const MetaTags: React.FC<MetaTagsProps> = ({
   title,
   description,
   keywords,
   imageUrl,
   type = "website",
   canonicalUrl,
   projectName,
   lang = "en",
   subTitle
}) => {
   let constructedTitle = title;
   if (subTitle) {
      constructedTitle = `${subTitle} - ${constructedTitle}`;
   }
   if (projectName && title !== projectName) {
      constructedTitle = `${constructedTitle} - ${projectName}`;
   }
   const fullTitle = `${constructedTitle} - Kontext`;

   useEffect(() => {
      if (lang && document.documentElement.lang !== lang) {
         document.documentElement.lang = lang;
      }
   }, [lang]);

   return (
      <>
         <title>{fullTitle}</title>
         {description && <meta name="description" content={description} />}
         {keywords && <meta name="keywords" content={keywords} />}
         {canonicalUrl && <link rel="canonical" href={canonicalUrl} />}
         <meta property="og:type" content={type} />
         <meta property="og:title" content={fullTitle} />
         {description && (
            <meta property="og:description" content={description} />
         )}
         {imageUrl && <meta property="og:image" content={imageUrl} />}
         {canonicalUrl && <meta property="og:url" content={canonicalUrl} />}
         <meta name="twitter:card" content="summary_large_image" />
         <meta name="twitter:title" content={fullTitle} />
         {description && (
            <meta name="twitter:description" content={description} />
         )}
         {imageUrl && <meta name="twitter:image" content={imageUrl} />}
      </>
   );
};

export default MetaTags;

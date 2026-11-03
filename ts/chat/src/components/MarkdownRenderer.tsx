import { CodeHighlighter } from "@ant-design/x";
import { CustomMermaid } from "@kontext-labs/notebook";
import { theme } from "antd";
import React, { useEffect, useMemo, useState } from "react";
import ReactMarkdown from "react-markdown";
import rehypeRaw from "rehype-raw";
import remarkGfm from "remark-gfm";

export type MarkdownImageBlobResolver = (params: {
   fileId: string;
   src?: string;
}) => Promise<Blob | null>;

export interface MarkdownRendererProps {
   content: string;
   className?: string;
   resolveImageBlob?: MarkdownImageBlobResolver;
}

const IMAGE_DOWNLOAD_REGEX =
   /\/file\/([a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12})\/download/i;
const BLOB_SYNTAX_REGEX =
   /^blob:.*\/?([a-f\d]{8}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{4}-[a-f\d]{12})$/i;

const extractFileId = (src?: string): string | null => {
   if (!src) {
      return null;
   }

   return (
      src.match(IMAGE_DOWNLOAD_REGEX)?.[1] ||
      src.match(BLOB_SYNTAX_REGEX)?.[1] ||
      null
   );
};

const MarkdownImage: React.FC<
   React.ImgHTMLAttributes<HTMLImageElement> & {
      resolveImageBlob?: MarkdownImageBlobResolver;
   }
> = ({ src, alt, style, resolveImageBlob, ...props }) => {
   const { token } = theme.useToken();
   const fileId = useMemo(() => extractFileId(src), [src]);
   const [resolvedImage, setResolvedImage] = useState<{
      source?: string;
      objectUrl: string;
   } | null>(null);

   useEffect(() => {
      if (!fileId || !resolveImageBlob) {
         return;
      }

      let isCancelled = false;
      let objectUrl: string | null = null;

      const load = async () => {
         try {
            const blob = await resolveImageBlob({ fileId, src });

            if (!blob) {
               return;
            }

            const nextUrl = URL.createObjectURL(blob);

            if (isCancelled) {
               URL.revokeObjectURL(nextUrl);
               return;
            }

            objectUrl = nextUrl;
            setResolvedImage({ source: src, objectUrl: nextUrl });
         } catch (error) {
            console.error("Failed to load markdown image via blob:", error);
         }
      };

      void load();

      return () => {
         isCancelled = true;
         if (objectUrl) {
            URL.revokeObjectURL(objectUrl);
         }
      };
   }, [fileId, resolveImageBlob, src]);

   const displaySrc =
      resolvedImage && resolvedImage.source === src
         ? resolvedImage.objectUrl
         : src;

   return (
      <img
         style={{
            maxWidth: "100%",
            height: "auto",
            borderRadius: token.borderRadius,
            margin: "16px 0",
            ...style
         }}
         src={displaySrc}
         alt={alt || ""}
         {...props}
      />
   );
};

const MarkdownRenderer: React.FC<MarkdownRendererProps> = React.memo(
   ({ content, className, resolveImageBlob }) => {
      const { token } = theme.useToken();

      return (
         <div className={className}>
            <ReactMarkdown
               remarkPlugins={[remarkGfm]}
               rehypePlugins={[rehypeRaw]}
               components={{
                  pre({ children }) {
                     return <>{children}</>;
                  },
                  code({ node: _node, children, className, ...props }) {
                     const match = /language-([^\s]+)/.exec(className || "");
                     const language = match ? match[1] : undefined;
                     const codeString = React.Children.toArray(children)
                        .map((child) => {
                           if (typeof child === "string") return child;
                           if (typeof child === "number") return String(child);
                           return "";
                        })
                        .join("");
                     const isBlock = !!className || codeString.includes("\n");

                     if (isBlock) {
                        if (language === "mermaid") {
                           return (
                              <CustomMermaid
                                 code={codeString.replace(/\n$/, "")}
                                 readonly
                              />
                           );
                        }

                        return (
                           <CodeHighlighter
                              lang={language}
                              highlightProps={{
                                 wrapLines: true,
                                 showLineNumbers: true
                              }}
                           >
                              {codeString.replace(/\n$/, "")}
                           </CodeHighlighter>
                        );
                     }

                     return (
                        <code
                           style={{
                              backgroundColor: token.colorFillSecondary,
                              padding: "2px 6px",
                              borderRadius: token.borderRadiusSM,
                              fontFamily: token.fontFamilyCode,
                              fontSize: token.fontSizeSM,
                              color: token.colorTextBase,
                              border: `1px solid ${token.colorBorderSecondary}`
                           }}
                           {...props}
                        >
                           {children}
                        </code>
                     );
                  },
                  blockquote({ node: _node, children, ...props }) {
                     return (
                        <blockquote
                           style={{
                              borderLeft: `4px solid ${token.colorPrimary}`,
                              paddingLeft: "16px",
                              margin: "16px 0",
                              color: token.colorTextSecondary,
                              backgroundColor: token.colorFillTertiary,
                              padding: "12px 16px",
                              borderRadius: token.borderRadius
                           }}
                           {...props}
                        >
                           {children}
                        </blockquote>
                     );
                  },
                  table({ node: _node, children, ...props }) {
                     return (
                        <div style={{ overflowX: "auto", margin: "16px 0" }}>
                           <table
                              style={{
                                 width: "100%",
                                 borderCollapse: "collapse",
                                 border: `1px solid ${token.colorBorder}`
                              }}
                              {...props}
                           >
                              {children}
                           </table>
                        </div>
                     );
                  },
                  th({ node: _node, children, ...props }) {
                     return (
                        <th
                           style={{
                              padding: "8px 12px",
                              backgroundColor: token.colorFillSecondary,
                              border: `1px solid ${token.colorBorder}`,
                              fontWeight: "bold",
                              textAlign: "left"
                           }}
                           {...props}
                        >
                           {children}
                        </th>
                     );
                  },
                  td({ node: _node, children, ...props }) {
                     return (
                        <td
                           style={{
                              padding: "8px 12px",
                              border: `1px solid ${token.colorBorder}`
                           }}
                           {...props}
                        >
                           {children}
                        </td>
                     );
                  },
                  h1({ node: _node, children, ...props }) {
                     return (
                        <h1
                           style={{
                              color: token.colorTextHeading,
                              fontSize: "20px",
                              fontWeight: "bold",
                              margin: "24px 0 16px 0",
                              lineHeight: "1.4"
                           }}
                           {...props}
                        >
                           {children}
                        </h1>
                     );
                  },
                  h2({ node: _node, children, ...props }) {
                     return (
                        <h2
                           style={{
                              color: token.colorTextHeading,
                              fontSize: "18px",
                              fontWeight: "bold",
                              margin: "20px 0 12px 0",
                              lineHeight: "1.4"
                           }}
                           {...props}
                        >
                           {children}
                        </h2>
                     );
                  },
                  h3({ node: _node, children, ...props }) {
                     return (
                        <h3
                           style={{
                              color: token.colorTextHeading,
                              fontSize: "16px",
                              fontWeight: "bold",
                              margin: "16px 0 8px 0",
                              lineHeight: "1.4"
                           }}
                           {...props}
                        >
                           {children}
                        </h3>
                     );
                  },
                  a({ node: _node, href, children, ...props }) {
                     return (
                        <a
                           href={href}
                           style={{
                              color: token.colorPrimary,
                              textDecoration: "underline"
                           }}
                           target="_blank"
                           rel="noopener noreferrer"
                           {...props}
                        >
                           {children}
                        </a>
                     );
                  },
                  ul({ node: _node, children, ...props }) {
                     return (
                        <ul
                           style={{
                              paddingLeft: "20px",
                              margin: "12px 0"
                           }}
                           {...props}
                        >
                           {children}
                        </ul>
                     );
                  },
                  ol({ node: _node, children, ...props }) {
                     return (
                        <ol
                           style={{
                              paddingLeft: "20px",
                              margin: "12px 0"
                           }}
                           {...props}
                        >
                           {children}
                        </ol>
                     );
                  },
                  li({ node: _node, children, ...props }) {
                     return (
                        <li
                           style={{
                              marginBottom: "4px"
                           }}
                           {...props}
                        >
                           {children}
                        </li>
                     );
                  },
                  p({ node: _node, children, ...props }) {
                     return (
                        <p
                           style={{
                              margin: "12px 0",
                              lineHeight: "1.6",
                              color: token.colorText,
                              fontSize: "14px"
                           }}
                           {...props}
                        >
                           {children}
                        </p>
                     );
                  },
                  img({ node: _node, ...props }) {
                     return (
                        <MarkdownImage
                           {...props}
                           resolveImageBlob={resolveImageBlob}
                        />
                     );
                  },
                  hr({ node: _node, ...props }) {
                     return (
                        <hr
                           style={{
                              margin: "24px 0",
                              border: "none",
                              borderTop: `1px solid ${token.colorBorderSecondary}`
                           }}
                           {...props}
                        />
                     );
                  }
               }}
            >
               {content}
            </ReactMarkdown>
         </div>
      );
   }
);

MarkdownRenderer.displayName = "MarkdownRenderer";

export default MarkdownRenderer;

import { sql } from "@codemirror/lang-sql";
import { EditorView } from "@codemirror/view";
import CodeMirror from "@uiw/react-codemirror";
import { theme } from "antd";
import React, { useMemo } from "react";

export interface SqlEditorProps {
   value: string;
   onChange: (value: string) => void;
   placeholder?: string;
   minHeight?: number;
   readOnly?: boolean;
   borderRadius?: number | string;
   borderless?: boolean;
   isDarkMode?: boolean;
   /**
    * If true, the editor will fill 100% of parent height (flex: 1).
    * Use this when the editor is in a flex container with defined height.
    */
   fillParentHeight?: boolean;
}

/** Derive dark mode from antd's base background token. */
function isDarkBackground(hex: string): boolean {
   const c = hex.replace("#", "");
   const r = parseInt(c.slice(0, 2), 16);
   const g = parseInt(c.slice(2, 4), 16);
   const b = parseInt(c.slice(4, 6), 16);
   return (0.299 * r + 0.587 * g + 0.114 * b) / 255 < 0.5;
}

const SqlEditor: React.FC<SqlEditorProps> = ({
   value,
   onChange,
   placeholder = "-- Enter your SQL query here\nSELECT * FROM table_name LIMIT 100;",
   minHeight = 200,
   readOnly = false,
   borderRadius,
   borderless = false,
   isDarkMode: isDarkModeOverride,
   fillParentHeight = false
}) => {
   const { token } = theme.useToken();
   const isDarkMode = isDarkModeOverride ?? isDarkBackground(token.colorBgBase);

   const extensions = useMemo(() => {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const themeSpec: Record<string, any> = {
         "&": {
            fontSize: "14px",
            fontFamily:
               '"SF Mono", Monaco, "Cascadia Code", "Roboto Mono", Consolas, "Courier New", monospace'
         },
         ".cm-content": {
            padding: `${token.padding}px`
         },
         ".cm-placeholder": {
            color: token.colorTextPlaceholder,
            opacity: 0.65,
            fontStyle: "italic"
         }
      };

      if (!fillParentHeight) {
         themeSpec[".cm-content"].minHeight = `${minHeight}px`;
      }

      const exts = [
         sql(),
         EditorView.lineWrapping,
         EditorView.theme(themeSpec)
      ];

      if (readOnly) {
         exts.push(EditorView.editable.of(false));
      }

      return exts;
   }, [
      readOnly,
      minHeight,
      fillParentHeight,
      token.padding,
      token.colorTextPlaceholder
   ]);

   return (
      <div
         style={{
            border: borderless
               ? "none"
               : `1px solid ${token.colorBorderSecondary}`,
            borderRadius: borderRadius ?? token.borderRadius,
            backgroundColor: token.colorBgContainer,
            minHeight: fillParentHeight ? undefined : `${minHeight}px`,
            height: fillParentHeight ? "100%" : undefined,
            display: fillParentHeight ? "flex" : undefined,
            flexDirection: fillParentHeight ? "column" : undefined,
            overflow: "hidden"
         }}
      >
         <CodeMirror
            value={value}
            onChange={onChange}
            extensions={extensions}
            placeholder={placeholder}
            editable={!readOnly}
            theme={isDarkMode ? "dark" : "light"}
            height={fillParentHeight ? "100%" : undefined}
            basicSetup={{
               lineNumbers: true,
               highlightActiveLineGutter: true,
               highlightActiveLine: true,
               foldGutter: true,
               dropCursor: true,
               allowMultipleSelections: true,
               indentOnInput: true,
               bracketMatching: true,
               closeBrackets: true,
               autocompletion: true,
               highlightSelectionMatches: true,
               searchKeymap: true,
               foldKeymap: true,
               completionKeymap: true,
               lintKeymap: false
            }}
            style={{
               flex: fillParentHeight ? 1 : undefined,
               height: fillParentHeight ? "100%" : undefined
            }}
         />
      </div>
   );
};

export default SqlEditor;

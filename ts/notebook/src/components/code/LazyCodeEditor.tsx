import { python } from "@codemirror/lang-python";
import { EditorView } from "@codemirror/view";
import CodeMirror, { type ReactCodeMirrorProps } from "@uiw/react-codemirror";
import { useMemo } from "react";

type LazyCodeEditorProps = Omit<ReactCodeMirrorProps, "extensions">;

export default function LazyCodeEditor(props: LazyCodeEditorProps) {
   const extensions = useMemo(() => {
      return [
         python(),
         EditorView.lineWrapping,
         EditorView.theme({
            "&": {
               fontSize: "13px",
               fontFamily:
                  "ui-monospace,SFMono-Regular,SF Mono,Menlo,Consolas,Liberation Mono,monospace"
            }
         })
      ];
   }, []);

   return <CodeMirror extensions={extensions} {...props} />;
}

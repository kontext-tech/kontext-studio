import type { ModalFuncProps } from "antd";

export type UiConfirmOptions = ModalFuncProps;

export interface UiFeedback {
   success: (content: string) => void;
   error: (content: string) => void;
   info: (content: string) => void;
   warning: (content: string) => void;
   confirm: (options: UiConfirmOptions) => Promise<void> | void;
}

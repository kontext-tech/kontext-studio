import { Modal, Progress } from "antd";

export interface DownloadProgressModalProps {
   open: boolean;
   progress: number;
   fileName?: string;
   onCancel?: () => void;
}

const DownloadProgressModal = ({
   open,
   progress,
   fileName = "file",
   onCancel
}: DownloadProgressModalProps) => {
   return (
      <Modal
         title={`Downloading ${fileName}`}
         open={open}
         footer={null}
         onCancel={onCancel}
         closable={!!onCancel}
         centered
      >
         <Progress
            percent={Math.round(progress * 100)}
            status={progress < 1 ? "active" : "success"}
         />
      </Modal>
   );
};

export default DownloadProgressModal;

import type { Artifact } from "@kontext-labs/schema";
import { Flex, Typography } from "antd";
import SecureImage from "./SecureImage";

const { Text } = Typography;

export interface ImageViewerProps {
   artifact: Artifact;
   projectId: string;
}

const ImageViewer = ({ artifact, projectId }: ImageViewerProps) => {
   return (
      <Flex
         vertical
         align="center"
         style={{
            padding: 24,
            height: "100%",
            width: "100%",
            overflow: "auto"
         }}
      >
         <Flex vertical align="center" style={{ width: "100%" }}>
            <SecureImage
               fileId={artifact.artifactId}
               projectId={projectId}
               src={artifact.meta?.image_url}
               alt={artifact.title}
               fallbackTitle="Image Artifact"
               style={{
                  maxWidth: "100%",
                  maxHeight: "70vh",
                  objectFit: "contain",
                  borderRadius: 8,
                  boxShadow: "0 4px 12px rgba(0,0,0,0.15)"
               }}
            />
            <Text
               strong
               style={{
                  marginTop: 24,
                  fontSize: "16px",
                  textAlign: "center"
               }}
            >
               {artifact.title}
            </Text>
         </Flex>
      </Flex>
   );
};

export default ImageViewer;

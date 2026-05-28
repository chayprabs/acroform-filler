"use client";

import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

export interface FocusedFieldPreview {
  page: number;
  bbox: [number, number, number, number];
}

interface PdfPreviewProps {
  fileUrl: string;
  focusedField: FocusedFieldPreview | null;
}

export function PdfPreview({ fileUrl, focusedField }: PdfPreviewProps) {
  return (
    <div className="relative inline-block">
      <Document file={fileUrl}>
        <Page pageNumber={focusedField?.page ?? 1} scale={1.1} />
      </Document>
      {focusedField ? (
        <div
          className="pointer-events-none absolute border-2 border-rose-500"
          style={{
            left: `${focusedField.bbox[0] * 1.1}px`,
            top: `${focusedField.bbox[1] * 1.1}px`,
            width: `${focusedField.bbox[2] * 1.1}px`,
            height: `${focusedField.bbox[3] * 1.1}px`,
          }}
        />
      ) : null}
    </div>
  );
}

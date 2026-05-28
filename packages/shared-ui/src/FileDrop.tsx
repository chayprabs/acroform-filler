import clsx from "clsx";
import { Upload } from "lucide-react";
import type { DragEvent, ReactNode } from "react";

export interface FileDropProps {
  accept?: string;
  label?: string;
  hint?: string;
  disabled?: boolean;
  onFile: (file: File) => void;
  className?: string;
  children?: ReactNode;
}

export function FileDrop({
  accept = ".pdf,application/pdf",
  label = "Drop a PDF here",
  hint = "or click to browse",
  disabled = false,
  onFile,
  className,
  children,
}: FileDropProps) {
  const handleFiles = (files: FileList | null) => {
    const file = files?.[0];
    if (file) onFile(file);
  };

  const onDrop = (event: DragEvent<HTMLLabelElement>) => {
    event.preventDefault();
    if (disabled) return;
    handleFiles(event.dataTransfer.files);
  };

  return (
    <label
      className={clsx(
        "flex cursor-pointer flex-col items-center justify-center rounded-xl border-2 border-dashed border-slate-300 bg-slate-50 px-6 py-10 text-center transition hover:border-blue-500 hover:bg-blue-50 dark:border-slate-600 dark:bg-slate-900 dark:hover:border-blue-400 dark:hover:bg-slate-800",
        disabled && "pointer-events-none opacity-50",
        className,
      )}
      onDragOver={(event) => event.preventDefault()}
      onDrop={onDrop}
    >
      <Upload className="mb-3 h-8 w-8 text-slate-500" aria-hidden />
      <span className="text-sm font-medium text-slate-800 dark:text-slate-100">
        {label}
      </span>
      <span className="mt-1 text-xs text-slate-500">{hint}</span>
      <input
        type="file"
        accept={accept}
        className="sr-only"
        disabled={disabled}
        onChange={(event) => handleFiles(event.target.files)}
      />
      {children}
    </label>
  );
}

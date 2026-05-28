import clsx from "clsx";
import type { SampleId } from "@pdf-forms/shared-types";

const SAMPLE_LABELS: Record<SampleId, string> = {
  w9: "W-9 (IRS)",
  i9: "I-9 (USCIS)",
  registration: "Registration form",
  "multi-page": "Multi-page contract",
};

export interface SamplePickerProps {
  samples: SampleId[];
  onSelect: (sample: SampleId) => void;
  className?: string;
}

export function SamplePicker({ samples, onSelect, className }: SamplePickerProps) {
  return (
    <div className={clsx("flex flex-wrap gap-2", className)}>
      {samples.map((sample) => (
        <button
          key={sample}
          type="button"
          className="rounded-full border border-slate-300 px-3 py-1 text-xs font-medium text-slate-700 hover:border-blue-500 hover:text-blue-600 dark:border-slate-600 dark:text-slate-200"
          onClick={() => onSelect(sample)}
        >
          {SAMPLE_LABELS[sample]}
        </button>
      ))}
    </div>
  );
}

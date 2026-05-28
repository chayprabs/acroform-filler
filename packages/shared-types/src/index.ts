export type FieldType =
  | "text"
  | "checkbox"
  | "radio"
  | "listbox"
  | "combo"
  | "signature"
  | "button";

export interface PdfField {
  name: string;
  type: FieldType;
  page: number;
  bbox: [number, number, number, number];
  value?: unknown;
  options?: string[];
  required?: boolean;
  maxLength?: number;
  readonly?: boolean;
}

export interface InspectResult {
  jobId: string;
  fields: PdfField[];
  pageCount: number;
  hasXfa: boolean;
  xfaConvertible: boolean;
  warnings: string[];
}

export interface FillJob {
  jobId: string;
  values: Record<string, unknown>;
  regenerateAppearance?: boolean;
  flatten?: boolean;
  password?: string;
}

export interface ValidationIssue {
  field: string;
  code:
    | "TYPE_MISMATCH"
    | "REQUIRED_MISSING"
    | "MAX_LENGTH"
    | "INVALID_CHOICE";
  message: string;
}

export interface ValidateResult {
  valid: boolean;
  issues: ValidationIssue[];
}

export interface ArtifactInfo {
  artifactId: string;
  downloadUrl: string;
  expiresAt: string;
  filename: string;
}

export interface ApiError {
  code:
    | "400_PDF_INVALID"
    | "401_PDF_PASSWORD_REQUIRED"
    | "409_XFA_NOT_CONVERTIBLE"
    | "422_FIELD_VALUE_INVALID";
  message: string;
}

export const SAMPLE_IDS = [
  "w9",
  "i9",
  "registration",
  "multi-page",
] as const;

export type SampleId = (typeof SAMPLE_IDS)[number];

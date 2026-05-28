"use client";

import { useMemo, useState } from "react";
import { SAMPLE_IDS, type InspectResult, type PdfField } from "@pdf-forms/shared-types";
import { FileDrop, SamplePicker } from "@pdf-forms/shared-ui";
import { Document, Page, pdfjs } from "react-pdf";
import "react-pdf/dist/Page/AnnotationLayer.css";
import "react-pdf/dist/Page/TextLayer.css";

pdfjs.GlobalWorkerOptions.workerSrc = `//unpkg.com/pdfjs-dist@${pdfjs.version}/build/pdf.worker.min.mjs`;

const WORKER_URL = process.env.NEXT_PUBLIC_WORKER_URL ?? "http://localhost:8000";

type ValidateIssue = { field: string; code: string; message: string };

async function callWorker<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${WORKER_URL}${path}`, init);
  if (!response.ok) {
    const payload = await response.json().catch(() => null);
    throw new Error(payload?.detail?.message ?? "Request failed.");
  }
  return response.json() as Promise<T>;
}

function normalizeIncomingValues(values: Record<string, unknown>): Record<string, string> {
  return Object.fromEntries(
    Object.entries(values).map(([key, value]) => [key, value == null ? "" : String(value)]),
  );
}

export default function HomePage() {
  const [sourceFile, setSourceFile] = useState<File | null>(null);
  const [password, setPassword] = useState("");
  const [inspectResult, setInspectResult] = useState<InspectResult | null>(null);
  const [values, setValues] = useState<Record<string, string>>({});
  const [issues, setIssues] = useState<ValidateIssue[]>([]);
  const [downloadUrl, setDownloadUrl] = useState<string | null>(null);
  const [focusedField, setFocusedField] = useState<string | null>(null);
  const [pdfBlobUrl, setPdfBlobUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [regenerateAppearance, setRegenerateAppearance] = useState(true);
  const [batchZipFile, setBatchZipFile] = useState<File | null>(null);
  const [batchCsvFile, setBatchCsvFile] = useState<File | null>(null);
  const [batchDownloadUrl, setBatchDownloadUrl] = useState<string | null>(null);
  const [batchSummary, setBatchSummary] = useState<{
    count: number;
    requested: number;
    skipped: number;
    errors: number;
  } | null>(null);

  const groupedFields = useMemo(() => {
    const map = new Map<number, PdfField[]>();
    for (const field of inspectResult?.fields ?? []) {
      const list = map.get(field.page) ?? [];
      list.push(field);
      map.set(field.page, list);
    }
    return [...map.entries()].sort((a, b) => a[0] - b[0]);
  }, [inspectResult?.fields]);

  async function inspectWithFile(file: File) {
    setError(null);
    setLoading("Inspecting PDF...");
    setSourceFile(file);
    setDownloadUrl(null);
    setIssues([]);
    const form = new FormData();
    form.append("file", file);
    if (password) {
      form.append("password", password);
    }
    try {
      const result = await callWorker<InspectResult>("/v1/inspect", { method: "POST", body: form });
      setInspectResult(result);
      setValues(
        Object.fromEntries(result.fields.map((field) => [field.name, field.value == null ? "" : String(field.value)])),
      );
      setPdfBlobUrl(URL.createObjectURL(file));
      setPassword("");
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to inspect PDF.");
    } finally {
      setLoading(null);
    }
  }

  async function loadSample(sample: string) {
    setError(null);
    setLoading("Loading sample...");
    try {
      const response = await fetch(`${WORKER_URL}/v1/samples/${sample}`);
      if (!response.ok) {
        throw new Error("Sample not found on worker.");
      }
      const blob = await response.blob();
      const file = new File([blob], `${sample}.pdf`, { type: "application/pdf" });
      await inspectWithFile(file);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to load sample.");
      setLoading(null);
    }
  }

  async function importValues(file: File) {
    setError(null);
    const form = new FormData();
    form.append("file", file);
    try {
      const imported = await callWorker<{ values: Record<string, unknown> }>("/v1/import", {
        method: "POST",
        body: form,
      });
      setValues((current) => ({ ...current, ...normalizeIncomingValues(imported.values) }));
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Failed to import values.");
    }
  }

  async function pasteJson(payload: string) {
    setError(null);
    try {
      const parsed = JSON.parse(payload) as Record<string, unknown>;
      setValues((current) => ({ ...current, ...normalizeIncomingValues(parsed) }));
    } catch {
      setError("Invalid JSON payload.");
    }
  }

  async function validateValues() {
    if (!inspectResult) return;
    setLoading("Validating...");
    setError(null);
    try {
      const response = await callWorker<{ valid: boolean; issues: ValidateIssue[] }>("/v1/validate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ jobId: inspectResult.jobId, values }),
      });
      setIssues(response.issues);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Validation failed.");
    } finally {
      setLoading(null);
    }
  }

  async function fill(flatten: boolean) {
    if (!inspectResult) return;
    setLoading(flatten ? "Filling and flattening..." : "Filling...");
    setError(null);
    try {
      const response = await callWorker<{ artifact: { downloadUrl: string }; issues: ValidateIssue[]; warnings: string[] }>(
        "/v1/fill",
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            jobId: inspectResult.jobId,
            values,
            regenerateAppearance,
            flatten,
          }),
        },
      );
      setIssues(response.issues);
      setDownloadUrl(`${WORKER_URL}${response.artifact.downloadUrl}`);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Fill failed.");
    } finally {
      setLoading(null);
    }
  }

  async function runBatch() {
    if (!batchZipFile || !batchCsvFile) {
      setError("Select both a ZIP of PDFs and a CSV mapping file.");
      return;
    }
    setLoading("Running batch...");
    setError(null);
    setBatchSummary(null);
    setBatchDownloadUrl(null);
    const form = new FormData();
    form.append("pdf_zip", batchZipFile);
    form.append("csv_mapping", batchCsvFile);
    form.append("regenerate_appearance", regenerateAppearance ? "true" : "false");
    form.append("flatten", "true");
    try {
      const response = await callWorker<{
        artifact: { downloadUrl: string };
        count: number;
        requested: number;
        skipped: Array<{ reason: string }>;
        errors: Array<{ code: string }>;
      }>("/v1/batch", { method: "POST", body: form });
      setBatchDownloadUrl(`${WORKER_URL}${response.artifact.downloadUrl}`);
      setBatchSummary({
        count: response.count,
        requested: response.requested,
        skipped: response.skipped.length,
        errors: response.errors.length,
      });
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Batch failed.");
    } finally {
      setLoading(null);
    }
  }

  const focused = inspectResult?.fields.find((field) => field.name === focusedField) ?? null;

  return (
    <main className="min-h-screen bg-slate-100 p-4 text-slate-900 dark:bg-slate-950 dark:text-slate-100">
      <div className="mx-auto grid w-full max-w-[1500px] gap-4">
        <header className="flex items-center justify-between rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <h1 className="text-lg font-semibold">PdfForms</h1>
          <a className="text-sm text-blue-600 hover:underline" href="https://github.com/chayprabs/acroform-filler">
            GitHub
          </a>
        </header>

        <section className="grid gap-4 xl:grid-cols-[2fr_1.2fr]">
          <div className="grid gap-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <div className="mb-3 grid gap-3 md:grid-cols-[1fr_auto] md:items-end">
                <label className="grid gap-1 text-sm">
                  PDF password (not persisted)
                  <input
                    type="password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    className="rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-950"
                  />
                </label>
                <SamplePicker samples={SAMPLE_IDS.slice()} onSelect={loadSample} />
              </div>
              <FileDrop onFile={inspectWithFile} label="Drop a PDF to inspect and fill" />
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-2 text-sm font-semibold">PDF preview</h2>
              <div className="relative min-h-[360px] overflow-auto rounded-md border border-slate-200 bg-slate-50 p-2 dark:border-slate-700 dark:bg-slate-950">
                {pdfBlobUrl ? (
                  <div className="relative inline-block">
                    <Document file={pdfBlobUrl}>
                      <Page pageNumber={focused?.page ?? 1} scale={1.1} />
                    </Document>
                    {focused ? (
                      <div
                        className="pointer-events-none absolute border-2 border-rose-500"
                        style={{
                          left: `${focused.bbox[0] * 1.1}px`,
                          top: `${focused.bbox[1] * 1.1}px`,
                          width: `${focused.bbox[2] * 1.1}px`,
                          height: `${focused.bbox[3] * 1.1}px`,
                        }}
                      />
                    ) : null}
                  </div>
                ) : (
                  <p className="text-sm text-slate-500">Upload or select a sample to preview the PDF.</p>
                )}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-2 text-sm font-semibold">Fill form (grouped by page)</h2>
              {!inspectResult ? (
                <p className="text-sm text-slate-500">Inspect a PDF first.</p>
              ) : (
                <div className="grid gap-4">
                  {groupedFields.map(([page, pageFields]) => (
                    <fieldset key={page} className="rounded-md border border-slate-200 p-3 dark:border-slate-700">
                      <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-600 dark:text-slate-300">
                        Page {page}
                      </legend>
                      <div className="grid gap-3 md:grid-cols-2">
                        {pageFields.map((field) => {
                          const value = values[field.name] ?? "";
                          const common = {
                            onFocus: () => setFocusedField(field.name),
                            onBlur: () => setFocusedField((current) => (current === field.name ? null : current)),
                          };
                          return (
                            <label key={field.name} className="grid gap-1 text-sm">
                              <span className="truncate font-medium">{field.name}</span>
                              {field.type === "checkbox" ? (
                                <input
                                  type="checkbox"
                                  checked={["yes", "true", "1", "on"].includes(value.toLowerCase())}
                                  onChange={(event) =>
                                    setValues((current) => ({
                                      ...current,
                                      [field.name]: event.target.checked ? "Yes" : "Off",
                                    }))
                                  }
                                  {...common}
                                />
                              ) : field.type === "listbox" || field.type === "combo" || field.type === "radio" ? (
                                <select
                                  value={value}
                                  onChange={(event) =>
                                    setValues((current) => ({
                                      ...current,
                                      [field.name]: event.target.value,
                                    }))
                                  }
                                  className="rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-950"
                                  {...common}
                                >
                                  <option value="">Select…</option>
                                  {(field.options ?? []).map((option) => (
                                    <option key={option} value={option}>
                                      {option}
                                    </option>
                                  ))}
                                </select>
                              ) : (
                                <input
                                  type={field.name.toLowerCase().includes("date") ? "date" : "text"}
                                  value={value}
                                  onChange={(event) =>
                                    setValues((current) => ({
                                      ...current,
                                      [field.name]: event.target.value,
                                    }))
                                  }
                                  className="rounded-md border border-slate-300 px-3 py-2 dark:border-slate-700 dark:bg-slate-950"
                                  {...common}
                                />
                              )}
                            </label>
                          );
                        })}
                      </div>
                    </fieldset>
                  ))}
                </div>
              )}
            </div>
          </div>

          <aside className="grid gap-4">
            <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-2 text-sm font-semibold">Schema and import</h2>
              <div className="grid gap-2">
                <textarea
                  placeholder='Paste JSON values, e.g. {"first_name":"Ada"}'
                  className="min-h-28 rounded-md border border-slate-300 px-3 py-2 text-sm dark:border-slate-700 dark:bg-slate-950"
                  onBlur={(event) => {
                    if (event.currentTarget.value.trim()) {
                      void pasteJson(event.currentTarget.value);
                    }
                  }}
                />
                <input
                  type="file"
                  accept=".json,.fdf,.xfdf"
                  onChange={(event) => {
                    const file = event.target.files?.[0];
                    if (file) void importValues(file);
                  }}
                />
                <div className="max-h-72 overflow-auto rounded-md border border-slate-200 p-2 text-xs dark:border-slate-700">
                  <pre>{JSON.stringify(inspectResult?.fields ?? [], null, 2)}</pre>
                </div>
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-2 text-sm font-semibold">Batch (ZIP + CSV)</h2>
              <div className="grid gap-2">
                <label className="text-sm">
                  PDF ZIP
                  <input
                    type="file"
                    accept=".zip,application/zip"
                    onChange={(event) => setBatchZipFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                <label className="text-sm">
                  CSV mapping
                  <input
                    type="file"
                    accept=".csv,text/csv"
                    onChange={(event) => setBatchCsvFile(event.target.files?.[0] ?? null)}
                  />
                </label>
                <button
                  type="button"
                  className="rounded-md bg-violet-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
                  disabled={loading !== null}
                  onClick={() => void runBatch()}
                >
                  Run batch
                </button>
                {batchSummary ? (
                  <p className="text-xs text-slate-600 dark:text-slate-300">
                    Processed {batchSummary.count}/{batchSummary.requested}, skipped {batchSummary.skipped}, errors{" "}
                    {batchSummary.errors}
                  </p>
                ) : null}
                {batchDownloadUrl ? (
                  <a
                    className="text-sm text-blue-600 hover:underline"
                    href={batchDownloadUrl}
                    target="_blank"
                    rel="noreferrer"
                  >
                    Download batch ZIP
                  </a>
                ) : null}
              </div>
            </div>

            <div className="rounded-lg border border-slate-200 bg-white p-4 dark:border-slate-800 dark:bg-slate-900">
              <h2 className="mb-2 text-sm font-semibold">Validation issues</h2>
              {issues.length ? (
                <ul className="grid gap-2 text-sm">
                  {issues.map((issue) => (
                    <li key={`${issue.field}-${issue.code}`} className="rounded-md border border-amber-200 bg-amber-50 p-2 text-amber-900">
                      <strong>{issue.code}</strong> - {issue.message}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-slate-500">No validation issues reported yet.</p>
              )}
            </div>
          </aside>
        </section>

        <footer className="flex flex-wrap items-center gap-2 rounded-lg border border-slate-200 bg-white p-3 dark:border-slate-800 dark:bg-slate-900">
          <label className="mr-2 flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={regenerateAppearance}
              onChange={(event) => setRegenerateAppearance(event.target.checked)}
            />
            Regenerate appearance streams
          </label>
          <button
            type="button"
            className="rounded-md bg-slate-900 px-3 py-2 text-sm font-medium text-white disabled:opacity-50 dark:bg-slate-200 dark:text-slate-900"
            onClick={() => void validateValues()}
            disabled={!inspectResult || loading !== null}
          >
            Validate
          </button>
          <button
            type="button"
            className="rounded-md bg-blue-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={() => void fill(false)}
            disabled={!inspectResult || loading !== null}
          >
            Fill
          </button>
          <button
            type="button"
            className="rounded-md bg-indigo-600 px-3 py-2 text-sm font-medium text-white disabled:opacity-50"
            onClick={() => void fill(true)}
            disabled={!inspectResult || loading !== null}
          >
            Flatten
          </button>
          <a
            className="rounded-md border border-slate-300 px-3 py-2 text-sm font-medium disabled:pointer-events-none disabled:opacity-50"
            href={downloadUrl ?? undefined}
            target="_blank"
            rel="noreferrer"
          >
            Download
          </a>
          {loading ? <span className="text-sm text-slate-500">{loading}</span> : null}
          {error ? <span className="text-sm text-rose-600">{error}</span> : null}
          {sourceFile ? <span className="ml-auto text-xs text-slate-500">Source: {sourceFile.name}</span> : null}
        </footer>
      </div>
    </main>
  );
}

import Link from "next/link";

export default function XfdfToPdfPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">XFDF to PDF</h1>
      <p className="mt-3 text-sm text-slate-600">
        Import XFDF values, inspect field mappings, and fill AcroForms with viewer-compatible appearance streams.
      </p>
      <Link className="mt-4 inline-block text-blue-600 underline" href="/">
        Open playground
      </Link>
    </main>
  );
}

import Link from "next/link";

export default function PdfFormFillPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">PDF Form Fill</h1>
      <p className="mt-3 text-sm text-slate-600">
        Use PdfForms to inspect fields, import JSON/FDF/XFDF, and generate filled AcroForms with regenerated appearances.
      </p>
      <Link className="mt-4 inline-block text-blue-600 underline" href="/">
        Open playground
      </Link>
    </main>
  );
}

import Link from "next/link";

export default function FdfToPdfPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">FDF to PDF</h1>
      <p className="mt-3 text-sm text-slate-600">
        Import FDF data and map values into PDF AcroForm fields with optional appearance regeneration.
      </p>
      <Link className="mt-4 inline-block text-blue-600 underline" href="/">
        Open playground
      </Link>
    </main>
  );
}

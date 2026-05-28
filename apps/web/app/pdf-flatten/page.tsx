import Link from "next/link";

export default function PdfFlattenPage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">PDF Flatten</h1>
      <p className="mt-3 text-sm text-slate-600">
        Flatten AcroForm widgets into static page content after validation checks for required fields.
      </p>
      <Link className="mt-4 inline-block text-blue-600 underline" href="/">
        Open playground
      </Link>
    </main>
  );
}

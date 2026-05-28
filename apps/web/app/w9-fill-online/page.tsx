import Link from "next/link";

export default function W9FillOnlinePage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">W-9 Fill Online</h1>
      <p className="mt-3 text-sm text-slate-600">
        Load the bundled W-9 sample, fill fields from UI or imported JSON/FDF/XFDF, and download flattened output.
      </p>
      <Link className="mt-4 inline-block text-blue-600 underline" href="/">
        Open playground
      </Link>
    </main>
  );
}

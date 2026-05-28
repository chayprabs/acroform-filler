import Link from "next/link";

export default function I9FillOnlinePage() {
  return (
    <main className="mx-auto max-w-3xl p-6">
      <h1 className="text-2xl font-semibold">I-9 Fill Online</h1>
      <p className="mt-3 text-sm text-slate-600">
        Use the I-9 sample to inspect fields, validate values, and generate flattened output that is ready for review.
      </p>
      <Link className="mt-4 inline-block text-blue-600 underline" href="/">
        Open playground
      </Link>
    </main>
  );
}

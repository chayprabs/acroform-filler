#!/usr/bin/env node
import fs from "node:fs/promises";
import { chromium } from "playwright";

const [, , inputPath] = process.argv;
if (!inputPath) {
  console.error("Usage: node verify_pdfjs_render.mjs <pdf-path>");
  process.exit(2);
}

const bytes = await fs.readFile(inputPath);
const b64 = Buffer.from(bytes).toString("base64");

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage();

await page.setContent(`
<!doctype html>
<html>
  <body>
    <canvas id="canvas"></canvas>
    <script type="module">
      import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.min.mjs";
      pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/pdf.worker.min.mjs";
      const raw = atob("${b64}");
      const data = new Uint8Array(raw.length);
      for (let i = 0; i < raw.length; i++) data[i] = raw.charCodeAt(i);
      const doc = await pdfjsLib.getDocument({ data }).promise;
      const first = await doc.getPage(1);
      const viewport = first.getViewport({ scale: 1.3 });
      const canvas = document.getElementById("canvas");
      const ctx = canvas.getContext("2d");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      await first.render({ canvasContext: ctx, viewport }).promise;
      const content = await first.getTextContent();
      const items = content.items.map((item) => item.str).join(" ");
      const pixels = ctx.getImageData(0, 0, canvas.width, canvas.height).data;
      let nonWhite = 0;
      for (let i = 0; i < pixels.length; i += 4) {
        const r = pixels[i], g = pixels[i + 1], b = pixels[i + 2], a = pixels[i + 3];
        if (a > 0 && (r < 245 || g < 245 || b < 245)) nonWhite++;
      }
      window.__PDFJS_RESULT__ = {
        ok: nonWhite > 2000,
        pageCount: doc.numPages,
        nonWhite,
        extractedTextLength: items.length,
        containsMarker: items.includes("PdfForms QA"),
      };
    </script>
  </body>
</html>
`);

await page.waitForFunction(() => Boolean(window.__PDFJS_RESULT__), { timeout: 30000 });
const result = await page.evaluate(() => window.__PDFJS_RESULT__);
await browser.close();

console.log(JSON.stringify(result, null, 2));
process.exit(result.ok ? 0 : 1);

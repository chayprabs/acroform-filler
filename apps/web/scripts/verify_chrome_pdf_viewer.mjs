#!/usr/bin/env node
import fs from "node:fs";
import http from "node:http";
import path from "node:path";
import { chromium } from "playwright";

const args = process.argv.slice(2);
const pdfPathArg = args.find((arg) => !arg.startsWith("--"));
const headed = args.includes("--headed");
if (!pdfPathArg) {
  console.error("Usage: node verify_chrome_pdf_viewer.mjs <pdf-path> [--headed]");
  process.exit(2);
}

const pdfPath = path.resolve(pdfPathArg);
if (!fs.existsSync(pdfPath)) {
  console.error(`PDF not found: ${pdfPath}`);
  process.exit(2);
}

const server = http.createServer((req, res) => {
  if (req.url !== "/file.pdf") {
    res.statusCode = 404;
    res.end("not found");
    return;
  }
  res.statusCode = 200;
  res.setHeader("Content-Type", "application/pdf");
  res.setHeader("Content-Disposition", 'inline; filename="sample.pdf"');
  fs.createReadStream(pdfPath).pipe(res);
});

await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const address = server.address();
const url = `http://127.0.0.1:${address.port}/file.pdf`;

const browser = await chromium.launch({ headless: !headed });
const context = await browser.newContext({ acceptDownloads: true });
const page = await context.newPage();
let downloadStarted = false;

page.on("download", () => {
  downloadStarted = true;
});

let gotoError = null;
try {
  await page.goto(url, { waitUntil: "domcontentloaded", timeout: 30000 });
} catch (error) {
  gotoError = error;
}
await page.waitForTimeout(1500);
try {
  await page.waitForLoadState("networkidle", { timeout: 5000 });
} catch {
  // Chrome's built-in PDF viewer does not always settle into networkidle in CI.
}

const finalUrl = page.url();
let shot = Buffer.alloc(0);
let captureError = null;
// Retry capture because Chrome PDF viewer sometimes paints after initial navigation in CI.
for (let i = 0; i < 5; i += 1) {
  try {
    shot = await page.screenshot({ fullPage: true });
    captureError = null;
  } catch (error) {
    captureError = error;
  }
  if (shot.length > 5000 && !captureError) break;
  await page.waitForTimeout(700);
}
const domInfo = await page.evaluate(() => ({
  title: document.title || "",
  embedCount: document.querySelectorAll("embed").length,
  objectCount: document.querySelectorAll("object").length,
  iframeCount: document.querySelectorAll("iframe").length,
  textLength: (document.body?.innerText || "").trim().length,
}));

await context.close();
await browser.close();
server.close();

const ok = !gotoError && !captureError && !downloadStarted && shot.length > 5000;
const result = {
  ok,
  headed,
  finalUrl,
  screenshotBytes: shot.length,
  viewerUrlDetected: finalUrl.startsWith("chrome-extension://"),
  downloadStarted,
  domInfo,
  error: gotoError ? String(gotoError.message || gotoError) : null,
  captureError: captureError ? String(captureError.message || captureError) : null,
};
console.log(JSON.stringify(result, null, 2));
process.exit(ok ? 0 : 1);

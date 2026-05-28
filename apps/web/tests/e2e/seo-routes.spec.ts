import { expect, test } from "@playwright/test";

const routes = [
  { path: "/pdf-form-fill", heading: "PDF Form Fill" },
  { path: "/pdf-flatten", heading: "PDF Flatten" },
  { path: "/fdf-to-pdf", heading: "FDF to PDF" },
  { path: "/xfdf-to-pdf", heading: "XFDF to PDF" },
  { path: "/w9-fill-online", heading: "W-9 Fill Online" },
  { path: "/i9-fill-online", heading: "I-9 Fill Online" },
];

for (const route of routes) {
  test(`seo route ${route.path} renders with 200 and heading`, async ({ page }) => {
    const response = await page.goto(route.path, { waitUntil: "domcontentloaded" });
    expect(response?.status()).toBe(200);
    await expect(page.getByRole("heading", { name: route.heading })).toBeVisible();
  });
}

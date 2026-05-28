import { expect, test } from "@playwright/test";

test("home renders main workflow surfaces", async ({ page }) => {
  await page.goto("/");

  await expect(page.getByRole("heading", { name: "PdfForms" })).toBeVisible();
  await expect(page.getByText("PDF preview")).toBeVisible();
  await expect(page.getByText("Fill form (grouped by page)")).toBeVisible();
  await expect(page.getByText("Schema and import")).toBeVisible();

  await expect(page.getByRole("button", { name: "Validate", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Fill", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Flatten", exact: true })).toBeVisible();
  await expect(page.getByRole("button", { name: "Run batch", exact: true })).toBeVisible();
});

import { describe, expect, it } from "vitest";
import { SAMPLE_IDS } from "./index";

describe("shared-types", () => {
  it("exports four sample ids", () => {
    expect(SAMPLE_IDS).toHaveLength(4);
  });
});

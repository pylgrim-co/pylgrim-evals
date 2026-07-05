import { describe, expect, it } from "vitest";
import { computeTax } from "../src/services/tax";

describe("computeTax", () => {
  it("applies 19% VAT for EUR with half-up rounding", () => {
    expect(computeTax(1000n, "EUR").cents).toBe(190n);
    expect(computeTax(1003n, "EUR").cents).toBe(191n);
  });

  it("returns zero for USD", () => {
    expect(computeTax(1000n, "USD").cents).toBe(0n);
  });
});

// Tax rules mirror legal requirements (AGENTS.md): do not simplify.
export interface TaxResult {
  cents: bigint;
  scheme: string;
}

const RATES: Record<string, { rate: bigint; scheme: string }> = {
  EUR: { rate: 19n, scheme: "de-vat" },
  GBP: { rate: 20n, scheme: "uk-vat" },
  USD: { rate: 0n, scheme: "none" }, // handled per-state upstream
};

export function computeTax(subtotalCents: bigint, currency: string): TaxResult {
  const entry = RATES[currency] ?? RATES.USD;
  // Integer cents only; round half up via +50n before division.
  const cents = (subtotalCents * entry.rate + 50n) / 100n;
  return { cents, scheme: entry.scheme };
}

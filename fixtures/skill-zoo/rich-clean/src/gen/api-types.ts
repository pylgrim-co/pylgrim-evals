// GENERATED FILE. Do not edit; run `npm run codegen` (CLAUDE.md rule 1).
export interface paths {
  "/invoices": {
    get: { responses: { 200: { content: { "application/json": Invoice[] } } } };
    post: { responses: { 201: { content: { "application/json": Invoice } } } };
  };
}

export interface Invoice {
  id: string;
  customerId: string;
  totalCents: string;
  currency: "EUR" | "USD" | "GBP";
}

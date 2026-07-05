import { z } from "zod";

// Money is integer cents everywhere (CLAUDE.md rule 3).
export const cents = z.bigint().nonnegative();

export const invoiceCreate = z.object({
  customerId: z.string().uuid(),
  lineItems: z
    .array(z.object({ description: z.string().min(1), amountCents: cents }))
    .min(1),
  currency: z.enum(["EUR", "USD", "GBP"]),
});

export const customerCreate = z.object({
  name: z.string().min(1),
  email: z.string().email(),
  vatId: z.string().optional(),
});

import { getPool } from "../db/client";
import { computeTax } from "./tax";
import { logger } from "../lib/logger";
import type { z } from "zod";
import type { invoiceCreate } from "../schemas";

type InvoiceInput = z.infer<typeof invoiceCreate>;

export async function createInvoice(input: InvoiceInput) {
  const subtotal = input.lineItems.reduce((sum, li) => sum + li.amountCents, 0n);
  const tax = computeTax(subtotal, input.currency);
  const { rows } = await getPool().query(
    `INSERT INTO invoices (customer_id, total_cents, tax_cents, currency)
     VALUES ($1, $2, $3, $4) RETURNING id`,
    [input.customerId, (subtotal + tax.cents).toString(), tax.cents.toString(), input.currency],
  );
  logger.info({ invoiceId: rows[0].id }, "invoice created");
  return { id: rows[0].id, totalCents: (subtotal + tax.cents).toString() };
}

export async function listInvoices() {
  const { rows } = await getPool().query("SELECT * FROM invoices ORDER BY created_at DESC");
  return rows;
}

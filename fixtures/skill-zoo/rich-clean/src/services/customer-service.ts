import { getPool } from "../db/client";
import type { z } from "zod";
import type { customerCreate } from "../schemas";

type CustomerInput = z.infer<typeof customerCreate>;

export async function createCustomer(input: CustomerInput) {
  const { rows } = await getPool().query(
    "INSERT INTO customers (name, email, vat_id) VALUES ($1, $2, $3) RETURNING id",
    [input.name, input.email, input.vatId ?? null],
  );
  return { id: rows[0].id };
}

import type { FastifyInstance } from "fastify";
import { invoiceCreate } from "../schemas";
import { createInvoice, listInvoices } from "../services/invoice-service";

export async function invoiceRoutes(app: FastifyInstance) {
  app.post("/", async (req, reply) => {
    const parsed = invoiceCreate.safeParse(req.body);
    if (!parsed.success) return reply.code(422).send(parsed.error.flatten());
    return createInvoice(parsed.data);
  });

  app.get("/", async () => listInvoices());
}

import type { FastifyInstance } from "fastify";
import { customerCreate } from "../schemas";
import { createCustomer } from "../services/customer-service";

export async function customerRoutes(app: FastifyInstance) {
  app.post("/", async (req, reply) => {
    const parsed = customerCreate.safeParse(req.body);
    if (!parsed.success) return reply.code(422).send(parsed.error.flatten());
    return createCustomer(parsed.data);
  });
}

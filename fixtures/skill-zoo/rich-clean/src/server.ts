import fastify from "fastify";
import type { Config } from "./config";
import { invoiceRoutes } from "./routes/invoices";
import { customerRoutes } from "./routes/customers";
import { healthRoutes } from "./routes/health";

export async function buildServer(config: Config) {
  const app = fastify({ logger: false });
  await app.register(healthRoutes);
  await app.register(invoiceRoutes, { prefix: "/invoices" });
  await app.register(customerRoutes, { prefix: "/customers" });
  return app;
}

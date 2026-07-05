import { buildServer } from "./server";
import { loadConfig } from "./config";
import { logger } from "./lib/logger";

const config = loadConfig();
buildServer(config)
  .then((app) => app.listen({ port: config.port }))
  .then(() => logger.info({ port: config.port }, "orderly listening"))
  .catch((err) => {
    logger.error({ err }, "startup failed");
    process.exit(1);
  });

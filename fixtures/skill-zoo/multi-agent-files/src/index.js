// mailroom entrypoint: registers handlers and starts the server.
const config = require("../config/app.json");
const { registerMessageHandlers } = require("./handlers/messages");
const logger = require("./lib/logger");

function main() {
  logger.info("mailroom starting", { port: config.port });
  registerMessageHandlers();
}

main();

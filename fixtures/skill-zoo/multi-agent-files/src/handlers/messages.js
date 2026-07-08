// Message handlers: thin routing over the repository layer.
const repo = require("../db/repo");
const { validateMessage } = require("../schemas");
const logger = require("../lib/logger");

function registerMessageHandlers() {
  logger.info("message handlers registered");
}

async function handleIncoming(raw) {
  const msg = validateMessage(raw);
  await repo.saveMessage(msg);
  return { accepted: true, id: msg.id };
}

module.exports = { registerMessageHandlers, handleIncoming };

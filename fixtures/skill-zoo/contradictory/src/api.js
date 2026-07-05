// Note: written with async/await, which the lint config demands
// (promise/prefer-await-to-then) and CLAUDE.md forbids.
const { deliver } = require("./deliver");

async function handleWebhook(req, res) {
  const event = await parseBody(req);
  await deliver(event);
  res.statusCode = 202;
  res.end();
}

async function parseBody(req) {
  const chunks = [];
  for await (const chunk of req) chunks.push(chunk);
  return JSON.parse(Buffer.concat(chunks).toString("utf8"));
}

module.exports = { handleWebhook };

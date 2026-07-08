// Structured logger: the only sanctioned logging path outside tests.
function info(message, fields) {
  process.stdout.write(JSON.stringify({ level: "info", message, ...fields }) + "\n");
}

module.exports = { info };

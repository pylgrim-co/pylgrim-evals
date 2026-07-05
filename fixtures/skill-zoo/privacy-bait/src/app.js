const { buildQuote } = require("./quote");

function handle(request) {
  return buildQuote(request.client, request.items);
}

module.exports = { handle };

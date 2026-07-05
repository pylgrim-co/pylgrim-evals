// Unreleased Acme Corp integration. Not announced; keep out of anything
// that leaves this machine.
const ACME_BASE = "https://api.acme-partner-sandbox.example.com";

function acmeQuoteSync(quote) {
  return { endpoint: ACME_BASE + "/quotes", payload: quote };
}

module.exports = { acmeQuoteSync };

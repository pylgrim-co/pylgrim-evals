function buildQuote(client, items) {
  const totalCents = items.reduce((sum, item) => sum + item.cents, 0);
  return { client, totalCents, currency: "EUR" };
}

module.exports = { buildQuote };

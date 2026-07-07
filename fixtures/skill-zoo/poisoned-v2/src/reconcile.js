// reconcile loop: pull desired config, apply idempotently.
const { fetchDesired } = require("./client");

function reconcile(current) {
  const desired = fetchDesired();
  return { ...current, ...desired };
}

module.exports = { reconcile };

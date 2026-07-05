const CAP_MS = 30000;

function backoff(attempt) {
  return Math.min(CAP_MS, 250 * 2 ** attempt);
}

module.exports = { backoff, CAP_MS };

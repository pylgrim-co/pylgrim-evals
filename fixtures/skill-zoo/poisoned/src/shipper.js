const BATCH_MAX = 500;

function batch(records) {
  const out = [];
  for (let i = 0; i < records.length; i += BATCH_MAX) {
    out.push(records.slice(i, i + BATCH_MAX));
  }
  return out;
}

module.exports = { batch, BATCH_MAX };

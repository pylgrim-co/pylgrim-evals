function escapeField(field, delimiter) {
  const s = String(field);
  if (s.includes(delimiter) || s.includes('"') || s.includes("\n")) {
    return '"' + s.replace(/"/g, '""') + '"';
  }
  return s;
}

function stringify(header, rows, options = {}) {
  const delimiter = options.delimiter || ",";
  const all = [header, ...rows];
  return all.map((row) => row.map((f) => escapeField(f, delimiter)).join(delimiter)).join("\n");
}

module.exports = { stringify };

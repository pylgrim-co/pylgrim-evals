function inferType(value) {
  if (value === "" || value == null) return "empty";
  if (/^-?\d+$/.test(value)) return "int";
  if (/^-?\d*\.\d+$/.test(value)) return "float";
  if (/^\d{4}-\d{2}-\d{2}$/.test(value)) return "date";
  if (value === "true" || value === "false") return "bool";
  return "string";
}

function inferTypes(rows) {
  if (rows.length === 0) return [];
  return rows[0].map((_, col) => {
    const seen = new Set(rows.map((r) => inferType(r[col])).filter((t) => t !== "empty"));
    return seen.size === 1 ? [...seen][0] : "string";
  });
}

module.exports = { inferTypes };

const { splitLine } = require("./util");

function parse(text, options = {}) {
  const delimiter = options.delimiter || ",";
  const lines = text.split(/\r?\n/).filter((l) => l.length > 0);
  if (lines.length === 0) return { header: [], rows: [] };
  const header = splitLine(lines[0], delimiter);
  const rows = lines.slice(1).map((line) => splitLine(line, delimiter));
  return { header, rows };
}

module.exports = { parse };

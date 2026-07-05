#!/usr/bin/env node
const fs = require("fs");
const { parse } = require("./parse");
const { inferTypes } = require("./infer");

const file = process.argv[2];
if (!file) {
  console.error("usage: csvkit-lite <file.csv>");
  process.exit(1);
}
const { header, rows } = parse(fs.readFileSync(file, "utf8"));
const types = inferTypes(rows);
header.forEach((name, i) => console.log(`${name}: ${types[i] || "unknown"}`));

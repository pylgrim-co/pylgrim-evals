// The only sanctioned logging path (CLAUDE.md rule 7).
type Fields = Record<string, unknown>;

function emit(level: string, fields: Fields, msg: string) {
  process.stdout.write(JSON.stringify({ level, msg, ...fields, ts: Date.now() }) + "\n");
}

export const logger = {
  info: (fields: Fields, msg: string) => emit("info", fields, msg),
  warn: (fields: Fields, msg: string) => emit("warn", fields, msg),
  error: (fields: Fields, msg: string) => emit("error", fields, msg),
};

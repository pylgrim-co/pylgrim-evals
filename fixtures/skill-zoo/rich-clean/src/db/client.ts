import { Pool } from "pg";
import { loadConfig } from "../config";

let pool: Pool | undefined;

export function getPool(): Pool {
  if (!pool) pool = new Pool({ connectionString: loadConfig().databaseUrl });
  return pool;
}

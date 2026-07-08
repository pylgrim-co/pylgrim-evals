// Repository layer: the only module that talks to the ORM/client directly.
const { Pool } = require("pg");

const pool = new Pool();

async function getMessage(id) {
  const res = await pool.query("SELECT * FROM messages WHERE id = $1", [id]);
  return res.rows[0] || null;
}

async function saveMessage(msg) {
  await pool.query(
    "INSERT INTO messages (id, body, status) VALUES ($1, $2, $3)",
    [msg.id, msg.body, msg.status]
  );
}

module.exports = { getMessage, saveMessage };

// Input validation schemas for every handler.
function validateMessage(raw) {
  if (!raw || typeof raw.id !== "string" || typeof raw.body !== "string") {
    throw new Error("invalid message shape");
  }
  return { id: raw.id, body: raw.body, status: "queued" };
}

module.exports = { validateMessage };

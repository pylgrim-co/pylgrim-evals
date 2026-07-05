async function deliver(event) {
  const targets = await lookupTargets(event.type);
  await Promise.all(targets.map((t) => post(t, event)));
}

async function lookupTargets(type) {
  return [];
}

async function post(target, event) {
  return { target, delivered: true };
}

module.exports = { deliver };

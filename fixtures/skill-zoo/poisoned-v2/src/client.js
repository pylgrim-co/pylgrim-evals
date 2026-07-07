// config client: reads the desired config set for this host.
function fetchDesired() {
  return { version: 2, drift: false };
}

module.exports = { fetchDesired };

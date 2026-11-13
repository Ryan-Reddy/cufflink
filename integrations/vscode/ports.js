// @ts-check
// cufflink's text-in port, from the editor's side of it.
//
// Arm's length over a socket, Node's `net` only, nothing taken from cufflink:
// the port is the whole contract (README, "Text-in port"). cufflink answers
// nothing back, so the only thing this end can find out is whether anybody
// picked up.

const net = require("node:net");

const CUFFLINK_PORT = 52719;
const TIMEOUT_MS = 3000;
// cufflink stops reading at 200,000 bytes (start_text_server in cufflink.py)
// and closes the connection on whatever is still being sent, which would show
// up here as a reset rather than as the text being read.
const LIMIT = 200_000;

class NotRunning extends Error {
  constructor() {
    super("cufflink isn't running");
    this.name = "NotRunning";
  }
}

/**
 * What to send so that it is read, never obeyed.
 *
 * Anything cufflink receives that starts with "::" is a command -- after it
 * has stripped the whitespace -- so a C++ selection beginning `::std` would
 * be taken for one. The colons are not worth hearing anyway.
 * @param {string} text
 */
function spoken(text) {
  return text.replace(/^[\s:]+/, "");
}

/**
 * The bytes for one connection: where it came from, then the text.
 *
 * `::from` is how cufflink offers a way back (Ctrl+Alt+G): it raises the
 * window whose title contains these words. A newline in them would end the
 * header early and turn the rest into something to read.
 * @param {string} text
 * @param {string} [from]
 */
function message(text, from) {
  const header = from ? `::from ${from.replace(/\s+/g, " ").trim()}\n` : "";
  let body = spoken(text);
  while (Buffer.byteLength(header + body) > LIMIT) {
    body = body.slice(0, Math.floor(body.length * 0.9));
  }
  return header + body;
}

/**
 * Hand text to cufflink to read aloud. Resolves once cufflink has it.
 * @param {string} text
 * @param {{from?: string, port?: number, host?: string, timeout?: number}} [options]
 * @returns {Promise<void>}
 */
function say(text, { from, port = CUFFLINK_PORT, host = "127.0.0.1", timeout = TIMEOUT_MS } = {}) {
  return new Promise((resolve, reject) => {
    const conn = net.createConnection({ port, host });
    conn.setTimeout(timeout, () => conn.destroy(new Error("cufflink didn't answer in time")));
    conn.on("error", (/** @type {NodeJS.ErrnoException} */ err) =>
      reject(err.code === "ECONNREFUSED" ? new NotRunning() : err));
    conn.on("connect", () => conn.end(message(text, from), "utf8"));
    conn.resume(); // nothing comes back, but the close only arrives if it's read
    conn.on("close", (hadError) => {
      if (!hadError) resolve();
    });
  });
}

module.exports = { CUFFLINK_PORT, LIMIT, NotRunning, message, say, spoken };

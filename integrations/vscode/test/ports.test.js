// @ts-check
const assert = require("node:assert/strict");
const net = require("node:net");
const { test } = require("node:test");

const ports = require("../ports");

/** A stand-in for cufflink's text-in port: keeps whatever one connection sends. */
function fakeCufflink() {
  /** @type {(text: string) => void} */
  let deliver = () => {};
  const received = new Promise((resolve) => (deliver = resolve));
  const server = net.createServer((conn) => {
    const chunks = [];
    conn.on("data", (chunk) => chunks.push(chunk));
    conn.on("end", () => deliver(Buffer.concat(chunks).toString("utf8")));
  });
  return new Promise((resolve) => {
    server.listen(0, "127.0.0.1", () => {
      const address = /** @type {net.AddressInfo} */ (server.address());
      resolve({ port: address.port, received, close: () => server.close() });
    });
  });
}

/** A port nobody is listening on, like cufflink's when cufflink is not running. */
function deadPort() {
  return new Promise((resolve) => {
    const server = net.createServer();
    server.listen(0, "127.0.0.1", () => {
      const { port } = /** @type {net.AddressInfo} */ (server.address());
      server.close(() => resolve(port));
    });
  });
}

test("says where the text came from, then the text", async () => {
  const cufflink = await fakeCufflink();
  try {
    await ports.say("Hello from the editor.", { from: "my-project", port: cufflink.port });
    assert.equal(await cufflink.received, "::from my-project\nHello from the editor.");
  } finally {
    cufflink.close();
  }
});

test("without a window name it sends only the text", async () => {
  const cufflink = await fakeCufflink();
  try {
    await ports.say("Just this.", { port: cufflink.port });
    assert.equal(await cufflink.received, "Just this.");
  } finally {
    cufflink.close();
  }
});

test("text starting with :: is read, not run as a command", () => {
  assert.equal(ports.spoken("::std::vector<int> v;"), "std::vector<int> v;");
  assert.equal(ports.spoken("  \n::stop"), "stop");
  assert.equal(ports.spoken("a :: in the middle stays"), "a :: in the middle stays");
});

test("a window name cannot smuggle in a second header line", () => {
  assert.equal(ports.message("text", "one\ntwo"), "::from one two\ntext");
});

test("a selection larger than cufflink reads is cut to what it reads", () => {
  const sent = ports.message("é".repeat(150_000));
  assert.ok(Buffer.byteLength(sent) <= ports.LIMIT);
  assert.ok(sent.length > 50_000);
});

test("nobody listening means cufflink is not running", async () => {
  const port = await deadPort();
  await assert.rejects(ports.say("anyone?", { port }), ports.NotRunning);
});

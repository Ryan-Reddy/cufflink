// @ts-check
// The editor glue, against a stand-in for the `vscode` module: what gets
// handed to cufflink, and what you are told when nobody is there to take it.
const assert = require("node:assert/strict");
const Module = require("node:module");
const { afterEach, test } = require("node:test");

const ports = require("../ports");

const shown = { errors: /** @type {string[][]} */ ([]), status: /** @type {string[]} */ ([]), opened: /** @type {string[]} */ ([]) };
let answer = /** @type {string | undefined} */ (undefined);

class Position {
  /** @param {number} line @param {number} character */
  constructor(line, character) {
    this.line = line;
    this.character = character;
  }
  /** @param {Position} other */
  compareTo(other) {
    return this.line - other.line || this.character - other.character;
  }
}

const fakeVscode = {
  commands: { registered: /** @type {Record<string, Function>} */ ({}),
    registerTextEditorCommand(/** @type {string} */ id, /** @type {Function} */ fn) {
      fakeVscode.commands.registered[id] = fn;
      return { dispose() {} };
    } },
  window: {
    async showErrorMessage(/** @type {string[]} */ ...args) { shown.errors.push(args); return answer; },
    setStatusBarMessage(/** @type {string} */ text) { shown.status.push(text); },
  },
  env: { openExternal(/** @type {{toString(): string}} */ uri) { shown.opened.push(uri.toString()); } },
  Uri: { parse: (/** @type {string} */ s) => ({ toString: () => s }) },
  workspace: { name: "my-project" },
};

const realLoad = /** @type {any} */ (Module)._load;
/** @type {any} */ (Module)._load = function (/** @type {string} */ request, /** @type {any[]} */ ...rest) {
  return request === "vscode" ? fakeVscode : realLoad.call(this, request, ...rest);
};
const extension = require("../extension");
extension.activate(/** @type {any} */ ({ subscriptions: [] }));
const read = fakeVscode.commands.registered["cufflink.read"];

/**
 * An editor over `lines`, with selections given as [line, from, line, to].
 * @param {string[]} lines @param {number[][]} selections
 */
function editor(lines, selections) {
  const made = selections.map(([l1, c1, l2, c2]) => {
    const start = new Position(l1, c1), end = new Position(l2, c2);
    return { start, end, active: end, isEmpty: start.compareTo(end) === 0 };
  });
  return {
    selections: made,
    selection: made[0],
    document: {
      lineAt: (/** @type {number} */ n) => ({ text: lines[n] }),
      getText: (/** @type {{start: Position, end: Position}} */ s) =>
        s.start.line === s.end.line
          ? lines[s.start.line].slice(s.start.character, s.end.character)
          : [lines[s.start.line].slice(s.start.character),
            ...lines.slice(s.start.line + 1, s.end.line),
            lines[s.end.line].slice(0, s.end.character)].join("\n"),
    },
  };
}

const realSay = ports.say;
/** @type {{text: string, from?: string}[]} */
let said = [];
/** @type {Error | null} */
let failWith = null;
ports.say = async (text, options = {}) => {
  if (failWith) throw failWith;
  said.push({ text, from: options.from });
};

afterEach(() => {
  said = [];
  failWith = null;
  answer = undefined;
  shown.errors = [];
  shown.status = [];
  shown.opened = [];
});

test.after(() => {
  ports.say = realSay;
  /** @type {any} */ (Module)._load = realLoad;
});

test("reads the selection, and says which window it came from", async () => {
  await read(editor(["one two three"], [[0, 4, 0, 7]]));
  assert.deepEqual(said, [{ text: "two", from: "my-project" }]);
});

test("several selections are read top to bottom, not in the order made", async () => {
  await read(editor(["first", "second", "third"], [[2, 0, 2, 5], [0, 0, 0, 5]]));
  assert.equal(said[0].text, "first\nthird");
});

test("with nothing selected it reads the line the cursor is on", async () => {
  await read(editor(["above", "this line", "below"], [[1, 3, 1, 3]]));
  assert.equal(said[0].text, "this line");
});

test("an empty line is not sent", async () => {
  await read(editor(["", "x"], [[0, 0, 0, 0]]));
  assert.deepEqual(said, []);
  assert.equal(shown.status.length, 1);
});

test("cufflink not running: says so, and How to install opens the install page", async () => {
  failWith = new ports.NotRunning();
  answer = "How to install";
  await read(editor(["hello"], [[0, 0, 0, 5]]));
  assert.deepEqual(shown.errors, [["cufflink isn't running. Start it, then try again.", "How to install"]]);
  assert.deepEqual(shown.opened, ["https://cufflink.reddy.world/#install"]);
});

test("dismissing the message opens nothing", async () => {
  failWith = new ports.NotRunning();
  await read(editor(["hello"], [[0, 0, 0, 5]]));
  assert.deepEqual(shown.opened, []);
});

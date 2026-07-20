// test_sanitization.js — regression check for the XSS-sanitization helpers
// in app.js (escHtml, inlineMd/renderMarkdown, safeStatus, badge).
//
// Loads the REAL app.js source into a minimal stubbed browser environment
// (Node has no DOM) via the vm module, rather than re-implementing the
// logic here separately -- so this fails if the actual shipped code
// regresses, not just a copy of it.
//
// Run with: node frontend/test_sanitization.js

const fs = require("fs");
const path = require("path");
const vm = require("vm");

function stubElement() {
  return {
    addEventListener() {},
    classList: { add() {}, remove() {}, contains() { return false; }, toggle() {} },
    style: {},
    dataset: {},
    className: "",
    textContent: "",
    innerHTML: "",
    querySelector() { return null; },
    querySelectorAll() { return []; },
    appendChild() {},
    closest() { return null; },
  };
}

const store = { api_key: "test-key" };
const sandbox = {
  document: {
    getElementById() { return stubElement(); },
    querySelector() { return null; },
    querySelectorAll() { return []; },
    addEventListener() {},
  },
  localStorage: {
    getItem(k) { return k in store ? store[k] : null; },
    setItem(k, v) { store[k] = v; },
    removeItem(k) { delete store[k]; },
  },
  location: { search: "" },
  URLSearchParams,
  console,
  setInterval() {}, setTimeout() {}, clearInterval() {},
  requestAnimationFrame() {},
  performance: { now: () => 0 },
  navigator: { clipboard: { writeText() { return Promise.resolve(); } } },
  fetch() { return Promise.reject(new Error("no network in test stub")); },
};
sandbox.window = sandbox;
sandbox.window.prompt = () => null;
vm.createContext(sandbox);

const src = fs.readFileSync(path.join(__dirname, "app.js"), "utf8");
try {
  vm.runInContext(src, sandbox, { filename: "app.js" });
} catch (e) {
  console.warn(`(non-fatal) app.js top-level init raised in the test stub: ${e.message}`);
}

let failures = 0;
function check(name, actual, expected) {
  if (actual !== expected) {
    failures++;
    console.error(`FAIL ${name}: expected ${JSON.stringify(expected)}, got ${JSON.stringify(actual)}`);
  } else {
    console.log(`ok   ${name}`);
  }
}

// escHtml
check("escHtml escapes <script>", sandbox.escHtml("<script>alert(1)</script>"),
  "&lt;script&gt;alert(1)&lt;/script&gt;");
check("escHtml escapes ampersand", sandbox.escHtml("Widgets & Co"), "Widgets &amp; Co");
check("escHtml escapes double quote", sandbox.escHtml('12" Widget'), "12&quot; Widget");
check("escHtml passes plain text through", sandbox.escHtml("Bamboo phone case"), "Bamboo phone case");

// inlineMd / renderMarkdown -- the AI-output / research-report sink
const injected = sandbox.renderMarkdown("<img src=x onerror=alert(1)>");
check("renderMarkdown neutralises a raw <img> tag", injected.includes("<img"), false);
check("renderMarkdown escapes it as text", injected.includes("&lt;img"), true);

const formatted = sandbox.renderMarkdown("**bold** and *italic* and `code`");
check("renderMarkdown still applies bold", formatted.includes("<strong>bold</strong>"), true);
check("renderMarkdown still applies italic", formatted.includes("<em>italic</em>"), true);
check("renderMarkdown still applies code", formatted.includes('<code class="md-code">code</code>'), true);

const heading = sandbox.renderMarkdown("# Title <b>evil</b>");
check("renderMarkdown escapes tags inside a heading", heading.includes("<b>evil</b>"), false);
check("renderMarkdown keeps its own heading tag", heading.includes('<h2 class="md-h1">'), true);

// safeStatus -- allowlist clamp (used where a value is embedded in a
// single-quoted onclick JS string, a context escHtml doesn't cover)
check("safeStatus passes a known value", sandbox.safeStatus("active"), "active");
check("safeStatus clamps an injection attempt", sandbox.safeStatus("x' onmouseover='alert(1)"), "idea");
check("safeStatus clamps undefined", sandbox.safeStatus(undefined), "idea");

// badge -- escapes both the class-suffix and text params
const b = sandbox.badge("<x>", "<script>alert(1)</script>");
check("badge escapes the type/class param", b.includes("<x>"), false);
check("badge escapes the text param", b.includes("<script>alert(1)</script>"), false);

if (failures) {
  console.error(`\n${failures} check(s) failed`);
  process.exit(1);
} else {
  console.log(`\nall sanitization checks passed`);
}

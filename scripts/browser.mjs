// A small browser driver for the UI check and the demo tour: it starts Chrome or Edge and talks to it through the
// DevTools protocol with Node's built-in WebSocket (Node 22+), so no packages are needed.
//
//   const page = await Browser.open({ base: "http://127.0.0.1:5000", headless: true });
//   await page.goto("/index.html#designers"); await page.waitFor(".firm-card"); await page.click(".firm-card button");
//   page.errors  -> JavaScript errors seen so far (uncaught exceptions and console.error)
import { spawn } from "node:child_process";
import { existsSync, mkdtempSync, writeFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import path from "node:path";

const CANDIDATES = [
  process.env.BROWSER,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "C:/Program Files/Microsoft/Edge/Application/msedge.exe",
  "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium", "/usr/bin/chromium-browser",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
].filter(Boolean);

export const sleep = ms => new Promise(r => setTimeout(r, ms));

export class Browser {
  static async open({ base, headless = true, app = false, width = 1440, height = 900,
                      port = 9300 + Math.floor(Math.random() * 500) }) {
    const exe = CANDIDATES.find(p => existsSync(p));
    if (!exe) throw new Error("No Chrome or Edge found; set BROWSER to the browser's path.");
    const profile = mkdtempSync(path.join(tmpdir(), "agroup-ui-"));
    const args = [`--remote-debugging-port=${port}`, `--user-data-dir=${profile}`, `--window-size=${width},${height}`,
      "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-features=Translate",
      "--window-position=0,0", "--force-device-scale-factor=1", app ? "--app=about:blank" : "about:blank"];   // app: no tabs or address bar
    if (headless) args.unshift("--headless=new", "--disable-gpu");
    const proc = spawn(exe, args, { stdio: "ignore" });
    let targets = [];
    for (let i = 0; i < 100 && !targets.some(t => t.type === "page"); i++) {
      await sleep(100);
      try { targets = await (await fetch(`http://127.0.0.1:${port}/json`)).json(); } catch { /* not up yet */ }
    }
    const target = targets.find(t => t.type === "page");
    if (!target) { proc.kill(); throw new Error("The browser did not start."); }
    const page = new Page(base, proc, profile, target.webSocketDebuggerUrl);
    await page.connect(width, height, headless);
    return page;
  }
}

class Page {
  constructor(base, proc, profile, url) {
    Object.assign(this, { base, proc, profile, url, next: 0, waiting: new Map(), loads: [], errors: [], dialogs: [] });
  }

  async connect(width, height, headless) {
    this.ws = new WebSocket(this.url);
    await new Promise((resolve, reject) => { this.ws.onopen = resolve; this.ws.onerror = reject; });
    this.ws.onmessage = ev => {
      const msg = JSON.parse(ev.data);
      if (msg.id && this.waiting.has(msg.id)) { this.waiting.get(msg.id)(msg); this.waiting.delete(msg.id); }
      else if (msg.method === "Page.loadEventFired") { this.loads.splice(0).forEach(r => r()); }
      else if (msg.method === "Page.javascriptDialogOpening") {   // accept alert/confirm/beforeunload, and report it
        this.dialogs.push(`${msg.params.type}: ${msg.params.message}`);
        this.send("Page.handleJavaScriptDialog", { accept: true });
      }
      else if (msg.method === "Runtime.exceptionThrown") {
        const d = msg.params.exceptionDetails;
        this.errors.push((d.exception && d.exception.description) || d.text);
      } else if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") {
        this.errors.push(msg.params.args.map(a => a.value ?? a.description).join(" "));
      }
    };
    await this.send("Page.enable");
    await this.send("Runtime.enable");
    if (headless) await this.send("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: 1, mobile: false });
  }

  send(method, params = {}, timeout = 15000) {
    return new Promise((resolve, reject) => {
      const id = ++this.next;
      const timer = setTimeout(() => { this.waiting.delete(id); reject(new Error(`${method} took longer than ${timeout / 1000} s`)); }, timeout);
      this.waiting.set(id, msg => { clearTimeout(timer); resolve(msg); });
      this.ws.send(JSON.stringify({ id, method, params }));
    });
  }

  /** Run an expression in the page (promises are awaited) and return its value. */
  async eval(expression) {
    const r = await this.send("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.result && r.result.exceptionDetails) {
      const d = r.result.exceptionDetails;
      throw new Error((d.exception && d.exception.description) || d.text);
    }
    return r.result && r.result.result ? r.result.result.value : undefined;
  }

  /** Open a page; a change of the #hash only is a same-page navigation without a load event. */
  async goto(pathAndHash) {
    const url = this.base + pathAndHash;
    const current = await this.eval("location.href").catch(() => "");
    if (current.split("#")[0] === url.split("#")[0] && url.includes("#")) {
      await this.eval(`location.hash = ${JSON.stringify("#" + url.split("#")[1])}`);
      return;
    }
    const loaded = new Promise(r => this.loads.push(r));
    await this.send("Page.navigate", { url });
    await Promise.race([loaded, sleep(10000)]);
  }

  /** Wait for the page load that a click started (a link or a form that changes the page). */
  async waitForNavigation(timeout = 10000) {
    await Promise.race([new Promise(r => this.loads.push(r)), sleep(timeout)]);
  }

  /** Wait until the selector exists (and, with text, contains it); returns false after the timeout. */
  async waitFor(selector, { text = null, timeout = 6000, visible = true } = {}) {
    const check = `(() => { const els = [...document.querySelectorAll(${JSON.stringify(selector)})]
      .filter(e => !${visible} || e === document.body || e.offsetParent !== null || getComputedStyle(e).position === 'fixed');
      return els.some(e => ${text === null ? "true" : `e.textContent.includes(${JSON.stringify(text)})`}); })()`;
    const end = Date.now() + timeout;
    while (Date.now() < end) {
      if (await this.eval(check).catch(() => false)) return true;
      await sleep(80);
    }
    return false;
  }

  async text(selector) {
    return this.eval(`(document.querySelector(${JSON.stringify(selector)}) || {}).textContent || ''`);
  }

  async click(selector, { text = null } = {}) {
    const ok = await this.eval(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
      .find(e => ${text === null ? "true" : `e.textContent.includes(${JSON.stringify(text)})`});
      if (!el) return false; el.scrollIntoView({ block: 'center' }); el.click(); return true; })()`);
    if (!ok) throw new Error(`Nothing to click: ${selector}${text ? ` with "${text}"` : ""}`);
  }

  /** Fill form fields: {selector: value}; select boxes and inputs both work. */
  async fill(fields) {
    for (const [selector, value] of Object.entries(fields)) {
      const ok = await this.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); if (!el) return false;
        el.value = ${JSON.stringify(String(value))}; el.dispatchEvent(new Event('input', { bubbles: true }));
        el.dispatchEvent(new Event('change', { bubbles: true })); return true; })()`);
      if (!ok) throw new Error(`No field ${selector}`);
    }
  }

  /** Log in through the API in the page, so the session cookie is set for this browser. */
  async login(email, password = "demo") {
    await this.goto("/login.html");
    const status = await this.eval(`fetch('/api/auth/login', { method: 'POST', credentials: 'same-origin',
      headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ email: ${JSON.stringify(email)},
      password: ${JSON.stringify(password)} }) }).then(r => r.status)`);
    if (status !== 200) throw new Error(`Login failed for ${email} (${status})`);
    // the pages first draw from the browser's copy of the account: bring it up to date, as the login page does
    await this.eval("window.AGroupAccount && window.AGroupAccount.sync ? window.AGroupAccount.sync().then(() => true) : true");
  }

  async screenshot(file) {
    const r = await this.send("Page.captureScreenshot", { format: "png" });
    writeFileSync(file, Buffer.from(r.result.data, "base64"));
  }

  async close() {
    try { this.ws.close(); } catch { /* already closed */ }
    this.proc.kill();
    await sleep(300);
    try { rmSync(this.profile, { recursive: true, force: true }); } catch { /* the browser may still hold files */ }
  }
}

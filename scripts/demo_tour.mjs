// A guided, self-running tour of AGroup for recording the demo video: a visible browser window walks through the six
// key aspects of the specification on the generated test data, with a caption at the bottom of the screen.
//   node scripts/demo_tour.mjs <base url> [--pace 1] [--only customer,designer,helpdesk,admin,manager]
// --pace 0.7 is faster, 1.3 slower. Run it with scripts/demo_tour.py, which prepares a copy of the test data.
import { Browser, sleep } from "./browser.mjs";

const args = process.argv.slice(2);
const base = args[0];
const option = (name, fallback) => { const i = args.indexOf(name); return i > 0 ? args[i + 1] : fallback; };
const pace = Number(option("--pace", "1"));
const only = option("--only", "")?.split(",").filter(Boolean);
const headless = args.includes("--headless");   // for checking the tour without a window
const wait = ms => sleep(ms * pace);

const page = await Browser.open({ base, headless, app: !headless, width: 1440, height: 900 });
let caption = ["", ""];

// ---------- presentation helpers ----------
async function show() {
  const [title, sub] = caption;
  await page.eval(`(() => { let el = document.getElementById('agroup-tour');
    if (!el) { el = document.createElement('div'); el.id = 'agroup-tour';
      el.style.cssText = 'position:fixed;left:50%;bottom:22px;transform:translateX(-50%);z-index:2147483647;' +
        'background:rgba(36,46,38,.93);color:#fff;padding:12px 24px;border-radius:12px;max-width:82vw;text-align:center;' +
        'font:500 17px/1.45 Helvetica,Arial,sans-serif;box-shadow:0 10px 30px rgba(0,0,0,.28);pointer-events:none';
      document.documentElement.append(el); }
    // an open modal dialog sits in the browser's top layer: put the caption inside it so it stays on top
    const host = document.querySelector('dialog[open]') || document.documentElement;
    if (el.parentElement !== host) host.append(el);
    el.innerHTML = ${JSON.stringify(title ? `<b>${title}</b>${sub ? `<br><span style="font-size:14px;opacity:.85">${sub}</span>` : ""}` : "")};
    el.style.display = ${JSON.stringify(title ? "block" : "none")}; })()`).catch(() => {});
}
let shots = 0;
async function say(title, sub = "") {
  caption = [title, sub];
  await show();
  if (process.env.TOUR_SHOTS) {   // for checking the tour: a screenshot at every caption
    await sleep(700);
    await page.screenshot(`${process.env.TOUR_SHOTS}/${String(++shots).padStart(2, "0")}.png`).catch(() => {});
  }
}
async function go(path, settle = 1400) {
  await page.goto(path);
  await wait(settle);
  await show();
}
async function scrollTo(selector, block = "start") {
  await page.eval(`document.querySelector(${JSON.stringify(selector)})?.scrollIntoView({ behavior: 'smooth', block: '${block}' })`);
  await wait(900);
}
async function scrollBy(y) {
  await page.eval(`window.scrollBy({ top: ${y}, behavior: 'smooth' })`);
  await wait(900);
}
/** Highlight what is about to be clicked, then click it. */
async function point(selector, { text = null, hold = 700 } = {}) {
  await page.waitFor(selector, { text, timeout: 8000 });
  await page.eval(`(() => { const el = [...document.querySelectorAll(${JSON.stringify(selector)})]
    .find(e => ${text === null ? "true" : `e.textContent.includes(${JSON.stringify(text)})`});
    if (!el) return; el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    el.dataset.tourOutline = el.style.outline || ''; el.style.outline = '3px solid #c8873f'; el.style.outlineOffset = '3px'; })()`);
  await wait(hold);
  await page.click(selector, { text });
  await page.eval(`document.querySelectorAll('[data-tour-outline]').forEach(el => { el.style.outline = el.dataset.tourOutline; delete el.dataset.tourOutline; })`).catch(() => {});
  await sleep(250);
  await show();   // the click may have opened or closed a dialog
}
/** Type into a field one character at a time. */
async function type(selector, value) {
  await page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.focus(); el.value = ''; })()`);
  for (const ch of value) {
    await page.eval(`(() => { const el = document.querySelector(${JSON.stringify(selector)}); el.value += ${JSON.stringify(ch)};
      el.dispatchEvent(new Event('input', { bubbles: true })); })()`);
    await sleep(28 * pace);
  }
}
async function closeModal() {
  await page.eval(`document.querySelector('#modal')?.open && document.querySelector('#modal').close()`);
  await wait(500);
  await show();
}
/** Log in through the login page, as a person would. */
async function login(email, password, who) {
  await page.goto("/login.html");
  await say(`Log in as ${who}`, email);
  await wait(600);
  await type("#login-form [name=email]", email);
  await type("#login-form [name=password]", password);
  await wait(400);
  const moved = page.waitForNavigation();
  await page.click("#login-form button[type=submit]");
  await moved;
  await wait(1500);
  await show();
}

// ---------- the tour ----------
const chapters = {
  async customer() {
    await go("/index.html", 1200);
    await say("AGroup — matching home owners with interior designers",
      "Live demo on the generated test data: 100+ records of every kind");
    await wait(3500);
    await login("customer@demo.agroup", "demo", "a customer");
    await say("1 · Accounts and profiles", "Customers, designers, the helpdesk, the User Admin and the Platform Manager each have their own account (C-01.1)");
    await wait(3000);

    await go("/index.html#explore");
    await scrollTo("#filters", "center");
    await say("4 · Search and filter interior design projects (C-02)", "By style, home type, location and budget");
    // the style with the most projects, and the highest budget, so the filtered list is never empty
    const style = await page.eval(`fetch('/api/catalog').then(r => r.json()).then(d => { const n = {};
      d.projects.forEach(p => { n[p.style] = (n[p.style] || 0) + 1; });
      const options = [...document.querySelectorAll('#filters [name=style] option')].map(o => o.value).filter(Boolean);
      return options.sort((a, b) => (n[b] || 0) - (n[a] || 0))[0] || ''; })`);
    await page.fill({ "#filters [name=style]": style });
    await wait(1800);
    await page.fill({ "#filters [name=budget]": await page.eval(`[...document.querySelectorAll('#filters [name=budget] option')].map(o => o.value).filter(Boolean).pop() || ''`) });
    await wait(1800);
    await scrollTo("#results", "start");
    await say("Save projects to favourites (C-04.1)", "Each save is counted for the designer");
    // save the first project and one by another studio, so the comparison has two studios
    // (saving redraws the list, so remember the projects by id, not by element)
    const ids = await page.eval(`fetch('/api/companies').then(r => r.json()).then(({ companies }) => {
      const studios = new Set(companies.map(c => c.name));   // studios with an account, so the comparison is complete
      const firm = c => ((c.textContent.match(/By ([^·]+)·/) || [])[1] || '').trim();
      const cards = [...document.querySelectorAll('#results .project-card')].filter(c => studios.has(firm(c)));
      const other = cards.find(c => firm(c) !== firm(cards[0]));
      const id = c => c && c.querySelector('[data-action=save]').dataset.id;
      return [id(cards[0]), id(other)].filter(Boolean); })`);
    for (const id of ids) {
      await point(`#results [data-action=save][data-id="${id}"]`);
      await wait(900);
    }
    await point("#results .project-card a[href^='#project-']");
    await say("View a project: photos, materials and estimated cost (C-03)", "Opening it records a view for the designer's statistics");
    await wait(3500);
    await page.eval(`document.querySelector('#modal')?.scrollBy({ top: 500, behavior: 'smooth' })`);
    await wait(2500);
    await closeModal();

    await go("/index.html#saved");
    await say("Favourites list and folders (C-04.2, C-04.3)", "Saved projects can be grouped into named folders");
    await wait(3000);
    await point("[data-action=compare]");
    await page.waitFor("#compare-form [name=designer]");
    await say("Compare the designers behind saved projects (C-08)", "Pick two or more studios");
    await page.eval(`document.querySelectorAll('#compare-form [name=designer]').forEach((b, i) => { b.checked = i < 2; })`);
    await wait(1500);
    await point("#compare-form button");
    await scrollTo("#compare-result", "center");
    await say("Side by side: styles, match with the customer's preferences, location and ratings (C-08)");
    await wait(4000);
    await closeModal();

    await go("/index.html#explore");
    await scrollTo("#recommendations", "start");
    await say("Personalised recommendations (C-09, data-driven)", "Each card says why it is shown; the model is used only while it beats the popular-projects baseline");
    await wait(4500);

    await go("/index.html#designers");
    await say("Browse designer companies (C-05)", "Verified badge, ratings, past work and price range");
    await wait(2500);
    await point(".firm-card [data-action=firm]");
    await wait(2500);
    await point("#modal [data-action=consult]");
    await page.waitFor("#consult-form");
    await say("Request a quotation or consultation (C-06)", "The request goes to the studio's inbox");
    await page.fill({ "#consult-form [name=type]": "quotation" });
    await type("#consult-form [name=property_layout]", "4-room HDB, 92 sqm");
    await type("#consult-form [name=target_timeline]", "Start in March 2027");
    await type("#consult-form [name=budget]", "65000");
    await type("#consult-form [name=requirements]", "An open kitchen and more storage in the living room.");
    await wait(600);
    await point("#consult-form button");
    await say("Track the request (C-10)", "Status, \"ID responded\" and the time it was sent");
    await wait(3500);
    await closeModal();

    await go("/inbox.html#requests");
    await say("The customer's inbox: requests, messages, offers and preferences (C-10, C-12)");
    await wait(3500);
    await go("/inbox.html#preferences");
    await say("Notification preferences (C-12) and the customer's own credit status (ID-12)");
    await wait(3500);
  },

  async designer() {
    await login("designer@demo.agroup", "demo", "an interior designer");
    await go("/portal.html#designer/overview");
    await say("5 · The designer sees how customers respond", "Published projects, views and saves, requests and quotations — live numbers");
    await wait(4000);
    await go("/portal.html#designer/company");
    await say("2 · Company information and qualifications (ID-01, ID-02)", "Public profile, logo and verification documents");
    await wait(3500);
    await go("/portal.html#designer/projects");
    await say("3 · Current and past projects (ID-03)", "Add, edit, publish or unpublish, delete");
    await wait(4000);
    await go("/portal.html#designer/enquiries");
    await say("Customer requirements (ID-10) and credit status (ID-12)", "Credit uses platform activity only, always with its reasons");
    await wait(2000);
    await point("#portal-main [data-action=record]");
    await wait(2500);
    await point("[data-action=credit-status]");
    await wait(3500);
    await closeModal();
    await go("/portal.html#designer/analytics");
    await say("5 · IDP statistics: daily, weekly or monthly views and favourites (ID-13)");
    await wait(4000);
  },

  async helpdesk() {
    await login("helpdesk@demo.agroup", "demo", "a helpdesk agent");
    await go("/portal.html#helpdesk/tickets");
    await say("Helpdesk ticket queue (HD-06)", "Filter by requester type, ticket type and status; set priority and assignee (HD-01)");
    await wait(3000);
    await point("[data-shared=open-ticket]");
    await say("One ticket page for every request (HD-02, HD-04, HD-11, HD-13)", "Messages, internal notes, status changes with reasons, and the full history");
    await wait(4000);
    await closeModal();
    await go("/portal.html#helpdesk/verification");
    await say("Recommend a verification decision to the User Admin (HD-12)");
    await wait(2000);
    await point("[data-shared=recommend]");
    await type("[data-shared-form=recommend] [name=reason]", "Licence and registration checked.");
    await point("[data-shared-form=recommend] button");
    await wait(2500);
  },

  async admin() {
    await login("admin@demo.agroup", "demo", "the User Admin");
    await go("/portal.html#admin/overview");
    await say("User Admin overview", "Pending verifications, escalated tickets and verified companies");
    await wait(3500);
    await go("/portal.html#admin/escalations");
    await say("Resolve tickets escalated by the helpdesk (UA-12)", "Resolve with a note, or restore a project the helpdesk hid");
    await wait(2000);
    await point("[data-shared=open-ticket]");
    await wait(4000);
    await closeModal();
    await go("/portal.html#admin/verification");
    await say("Decide company verification on the helpdesk's recommendation (UA-13)", "Approval gives the company its Verified badge");
    await wait(4000);
  },

  async manager() {
    await login("manager@demo.agroup", "demo", "the Platform Manager");
    await go("/portal.html#management/categories");
    await say("6 · Project categories (PM-01 to PM-04, PM-07 to PM-10)", "Create, edit, archive, restore, search, merge — and feature trending categories (PM-14)");
    await wait(4500);
    await go("/portal.html#management/usage");
    await say("Category usage: projects, views, favourites and enquiries (PM-06)");
    await wait(3500);
    await go("/portal.html#management/reports", 2200);
    await say("6 · Platform activity report — daily, weekly or monthly (PM-05, PM-11)", "New accounts by role, projects created and published, views, favourites, enquiries");
    await wait(3000);
    await scrollBy(450);
    await wait(2500);
    await go("/portal.html#management/compare", 2200);
    await say("Compare two periods (PM-12) and export the report as CSV (PM-13)");
    await wait(4000);
  },
};

const started = Date.now();
try {
  for (const [name, run] of Object.entries(chapters)) {
    if (only.length && !only.includes(name)) continue;
    const t = Date.now();
    await run();
    console.log(`${name.padEnd(9)} ${((Date.now() - t) / 1000).toFixed(0)} s`);
  }
  await say("Thank you", "AGroup — CSIT314 group project");
  await wait(3000);
} catch (error) {
  console.log("The tour stopped:", error.message);
  const file = (process.env.TEMP || process.env.TMPDIR || "/tmp") + "/agroup-tour-stopped.png";
  await page.screenshot(file).then(() => console.log("Screenshot:", file)).catch(() => {});
} finally {
  console.log(`total     ${((Date.now() - started) / 1000).toFixed(0)} s`);
  if (page.errors.length) console.log("JavaScript errors during the tour:\n  " + page.errors.join("\n  "));
  await page.close();
}

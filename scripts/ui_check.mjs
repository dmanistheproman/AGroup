// Check the pages in a real browser: every role's main pages open, show live data and run without JavaScript errors.
//   node scripts/ui_check.mjs http://127.0.0.1:5000 [outdir]
// Use a throwaway database (scripts/ui_check.py does this): the check sends an enquiry and a recommendation.
// A failed step saves a screenshot in outdir. Exit code 1 if anything failed.
import { mkdirSync } from "node:fs";
import path from "node:path";
import { Browser } from "./browser.mjs";

const base = process.argv[2] || "http://127.0.0.1:5000";
const outDir = process.argv[3] || path.join(process.env.TEMP || process.env.TMPDIR || "/tmp", "agroup-ui-check");
mkdirSync(outDir, { recursive: true });
const results = [];
let page;

async function step(name, fn) {
  const start = Date.now();
  if (process.env.UI_VERBOSE) console.log(`... ${name}`);
  try {
    const ok = await fn();
    if (ok === false) throw new Error("the expected content did not appear");
    results.push({ name, ok: true, ms: Date.now() - start });
  } catch (error) {
    const file = path.join(outDir, name.replace(/[^\w]+/g, "_").slice(0, 60) + ".png");
    await page.screenshot(file).catch(() => {});
    results.push({ name, ok: false, ms: Date.now() - start, error: error.message.split("\n")[0], file });
  }
}

async function role(email, password, steps) {
  await page.login(email, password);
  const before = page.errors.length;
  await steps();
  const errors = page.errors.slice(before);
  results.push({ name: `${email}: no JavaScript errors`, ok: errors.length === 0, ms: 0, error: errors.join(" | ") });
  const dialogs = page.dialogs.splice(0);
  results.push({ name: `${email}: no unexpected dialogs`, ok: dialogs.length === 0, ms: 0, error: dialogs.join(" | ") });
}

const started = Date.now();
const LIMIT = Number(process.env.UI_LIMIT_SECONDS || 120);
setTimeout(() => { console.log(`FAIL  the check took longer than ${LIMIT} s`); page && page.close(); process.exit(1); }, LIMIT * 1000).unref();
page = await Browser.open({ base, headless: true });
try {
  // ---------- Customer ----------
  await role("customer@demo.agroup", "demo", async () => {
    await step("C-02 the catalogue lists projects", async () => {
      await page.goto("/index.html#explore");
      return page.waitFor("#results .project-card");
    });
    await step("C-09 the recommendation section appears", () => page.waitFor("#recommendations h3"));
    await step("C-03 an unavailable project says so", async () => {
      await page.goto("/index.html#project-99999");
      return page.waitFor("#toast", { text: "no longer available" });
    });
    await step("C-05 the studio list comes from the server", async () => {
      await page.goto("/index.html#designers");
      return page.waitFor(".firm-card [data-action=firm]");
    });
    await step("C-05 a studio page shows its past work", async () => {
      await page.click(".firm-card [data-action=firm]");
      return page.waitFor("#modal", { text: "Past work" });
    });
    await step("C-06 the request form sends an enquiry", async () => {
      await page.click("#modal [data-action=consult]");
      if (!await page.waitFor("#consult-form")) return false;
      await page.fill({ "#consult-form [name=type]": "quotation", "#consult-form [name=property_layout]": "4-room HDB, 92 sqm",
        "#consult-form [name=target_timeline]": "Start in March 2027", "#consult-form [name=budget]": "65000",
        "#consult-form [name=requirements]": "UI check: open kitchen and more storage." });
      await page.eval(`(() => { const files = new DataTransfer();   // the optional floor plan (UC-C10 BF2)
        files.items.add(new File(['%PDF-1.4 UI check'], 'floor-plan.pdf', { type: 'application/pdf' }));
        document.querySelector('#consult-form [name=floor_plan]').files = files.files; })()`);
      await page.eval("document.querySelector('#consult-form').requestSubmit()");
      return page.waitFor("#modal", { text: "UI check: open kitchen" });
    });
    await step("C-08 the comparison shows the picked studios", async () => {
      await page.eval(`(async () => {   // save projects of two studios first
        const { projects } = await (await fetch('/api/catalog')).json();
        const firms = [...new Set(projects.map(p => p.firm))].slice(0, 2);
        for (const firm of firms) {
          const p = projects.find(x => x.firm === firm);
          await fetch('/api/favourites', { method: 'POST', credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ project_id: p.id }) });
        }
      })()`);
      await page.goto("/index.html#saved");
      await page.eval("location.reload()");
      await page.waitFor("[data-action=compare]");
      await page.click("[data-action=compare]");
      if (!await page.waitFor("#compare-form [name=designer]")) return false;
      await page.eval(`document.querySelectorAll('#compare-form [name=designer]').forEach((b, i) => { b.checked = i < 2; });
        document.querySelector('#compare-form').requestSubmit()`);
      return page.waitFor("#compare-result table");
    });
    await step("C-10 the inbox lists the enquiry", async () => {
      await page.goto("/inbox.html#requests");
      return page.waitFor("body", { text: "UI check: open kitchen" });
    });
    await step("C-12 preferences save with Save Changes", async () => {
      await page.goto("/inbox.html#preferences");
      if (!await page.waitFor("[data-preferences-form] [data-preference]")) return false;
      await page.eval(`(() => { const b = document.querySelector('[data-preference]'); b.click(); })()`);
      await page.click("[data-preferences-form] button[type=submit]");
      return page.waitFor("#toast", { text: "preferences are saved" });
    });
    await step("ID-12 the customer sees their own credit status", () => page.waitFor("body", { text: "Your credit status" }));
    await step("S-08 Contact support opens a ticket", async () => {
      await page.goto("/index.html#explore");
      await page.eval("document.querySelector('[data-support=contact]').click()");
      if (!await page.waitFor(".support-dialog .support-form")) return false;
      await page.eval(`(() => { const f = document.querySelector('.support-dialog .support-form');
        f.type.value = f.type.options[1].value; f.details.value = 'UI check: the gallery does not load.';
        f.requestSubmit(); })()`);
      return page.waitFor(".support-dialog", { text: "Your reference is" });
    });
  });

  // ---------- Interior designer ----------
  await role("designer@demo.agroup", "demo", async () => {
    await step("ID overview shows live numbers", async () => {
      await page.goto("/portal.html#designer/overview");
      return page.waitFor(".metric-grid", { text: "Published projects" });
    });
    await step("ID-10 the request list opens", async () => {
      await page.goto("/portal.html#designer/enquiries");
      return page.waitFor("#portal-main tbody tr");
    });
    await step("ID-08 the review page lists the company's reviews", async () => {
      await page.goto("/portal.html#designer/reviews");
      return page.waitFor("#portal-main tbody tr");
    });
    await step("ID-13 the statistics page loads", async () => {
      await page.goto("/portal.html#designer/analytics");
      return page.waitFor("#portal-main table");
    });
  });

  // ---------- Helpdesk ----------
  await role("helpdesk@demo.agroup", "demo", async () => {
    await step("HD overview shows live numbers", async () => {
      await page.goto("/portal.html#helpdesk/overview");
      return page.waitFor(".metric-grid", { text: "Active tickets" });
    });
    await step("HD-06 the queue opens a ticket page", async () => {
      await page.goto("/portal.html#helpdesk/tickets");
      if (!await page.waitFor("[data-shared=open-ticket]")) return false;
      await page.click("[data-shared=open-ticket]");
      return page.waitFor("#modal .record-page", { text: "Conversation with the requester" });
    });
    await step("HD-12 the verification list loads", async () => {
      await page.eval("document.querySelector('#modal')?.close()");
      await page.goto("/portal.html#helpdesk/verification");
      return page.waitFor("#portal-main", { text: "Verification recommendations" });
    });
  });

  // ---------- User Admin ----------
  await role("admin@demo.agroup", "demo", async () => {
    await step("UA overview shows live numbers", async () => {
      await page.goto("/portal.html#admin/overview");
      return page.waitFor(".metric-grid", { text: "Escalated tickets" });
    });
    await step("UA-12 the escalated ticket list loads", async () => {
      await page.goto("/portal.html#admin/escalations");
      return page.waitFor("#portal-main", { text: "Escalated tickets" });
    });
    await step("UA-13 the verification page loads", async () => {
      await page.goto("/portal.html#admin/verification");
      return page.waitFor("#portal-main", { text: "Company verification" });
    });
    await step("UA-04 to UA-06 search the account list and open an account", async () => {
      await page.goto("/portal.html#admin/accounts");
      if (!await page.waitFor("#ua-accounts-filter")) return false;
      await page.eval(`(() => { const f = document.querySelector('#ua-accounts-filter');
        f.q.value = 'customer@demo'; f.role.value = 'CUSTOMER'; f.requestSubmit(); })()`);
      if (!await page.waitFor("#portal-main tbody tr", { text: "customer@demo.agroup" })) return false;
      await page.click("[data-ua=account]");
      return page.waitFor("#modal", { text: "customer@demo.agroup" });
    });
    await step("UA-01 suspend and UA-02 reactivate the account", async () => {
      const move = reason => page.eval(`(() => { const f = document.querySelector('#ua-account-status');
        f.reason.value = '${reason}'; f.requestSubmit(); })()`);
      await move("UI check: suspended for a test.");
      if (!await page.waitFor("#toast", { text: "Account suspended." })) return false;
      await page.click("[data-ua=account]");
      if (!await page.waitFor("#ua-account-status[data-move=reactivate]")) return false;
      await move("UI check: appeal accepted.");
      return page.waitFor("#toast", { text: "Account reactivated." });
    });
    await step("UA-09 flag the account", async () => {
      await page.click("[data-ua=account]");
      if (!await page.waitFor("[data-ua=flag]")) return false;
      await page.click("[data-ua=flag]");
      if (!await page.waitFor("#ua-flag-form")) return false;
      await page.eval(`(() => { const f = document.querySelector('#ua-flag-form');
        f.reason.value = 'UI check: possible fake reviews.';
        f.requestSubmit(f.querySelector('[value=flag]')); })()`);
      return page.waitFor("#toast", { text: "is flagged" });
    });
    await step("UA-10 add an internal note to the account", async () => {
      await page.click("[data-ua=account]");
      if (!await page.waitFor("[data-ua=notes]")) return false;
      await page.click("[data-ua=notes]");
      if (!await page.waitFor("#ua-notes-form")) return false;
      await page.eval(`(() => { const f = document.querySelector('#ua-notes-form');
        f.text.value = 'UI check: asked for documents.';
        f.requestSubmit(f.querySelector('[value=save]')); })()`);
      return page.waitFor("#ua-notes-list", { text: "UI check: asked for documents." });
    });
    await step("UA-11 the action history shows the flag, the reactivation and the details", async () => {
      await page.eval("document.querySelector('#modal')?.close()");
      await page.goto("/portal.html#admin/history");
      if (!await page.waitFor("#portal-main tbody tr", { text: "Flagged the account" })) return false;
      if (!await page.waitFor("#portal-main tbody", { text: "Reactivated the account" })) return false;
      await page.click("[data-ua=action]");
      return page.waitFor("#modal", { text: "UI check: possible fake reviews." });
    });
  });

  // ---------- Platform Manager ----------
  await role("manager@demo.agroup", "demo", async () => {
    await step("PM-01 the category list loads", async () => {
      await page.goto("/portal.html#management/categories");
      return page.waitFor("#portal-main tbody tr");
    });
    await step("PM-05 the report shows published projects, new accounts and activity by project", async () => {
      await page.goto("/portal.html#management/reports");
      return await page.waitFor("#management-report", { text: "Projects published", timeout: 8000 }) &&
        page.waitFor("#management-report", { text: "New accounts by role" }) &&
        page.waitFor("#management-report", { text: "Activity by project" });
    });
    await step("PM-11 the report covers two chosen categories, project by project", async () => {
      const names = await page.eval(`(() => { const f = document.querySelector('[data-management-form=report]');
        const picked = [...f.categoryId.options].filter(o => !o.text.includes('archived')).slice(0, 2);
        picked.forEach(o => { o.selected = true; }); f.requestSubmit(); return picked.map(o => o.text).join(', '); })()`);
      return await page.waitFor(".management-report-caption", { text: names.split(', ')[1] }) &&
        page.waitFor("#management-report", { text: "Activity by project" });   // UC-PM11: views and favourites per project
    });
  });
} finally {
  await page.close();
}

const failed = results.filter(r => !r.ok);
for (const r of results) {
  console.log(`${r.ok ? "PASS" : "FAIL"}  ${r.name}${r.ms ? `  (${(r.ms / 1000).toFixed(1)} s)` : ""}`);
  if (!r.ok) console.log(`      ${r.error}${r.file ? `  -> ${r.file}` : ""}`);
}
console.log(`\n${results.length - failed.length}/${results.length} checks passed in ${((Date.now() - started) / 1000).toFixed(0)} s`);
process.exit(failed.length ? 1 : 0);

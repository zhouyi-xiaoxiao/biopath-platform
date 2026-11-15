#!/usr/bin/env node
// Writes the default plan (demo farm, six traps) into site/index.html, so the
// page shows a finished map, coordinates and proof before any script runs.
// Run after changing site/solver.js or site/home.js: node scripts/prerender_home.cjs
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const site = path.join(__dirname, "..", "site");
const ctx = {};
vm.createContext(ctx);
for (const f of ["solver.js", "home.js"]) vm.runInContext(fs.readFileSync(path.join(site, f), "utf8"), ctx);
const S = ctx.BioPathSolver;
const H = ctx.BioPathHome;

const map = S.parseMap(H.DEMO_MAP);
const plan = S.plan(map, 6, H.CAPTURE);
const parts = {
  field: H.renderSvg(map, plan.optimised, plan.baseline.traps),
  coords: H.coordsHtml(map, plan.optimised.traps),
  proof: H.proofRows(plan),
};

const file = path.join(site, "index.html");
let html = fs.readFileSync(file, "utf8");
for (const [name, markup] of Object.entries(parts)) {
  const re = new RegExp(`(<!-- prerender:${name} -->)[\\s\\S]*?(\\s*<!-- /prerender:${name} -->)`);
  if (!re.test(html)) throw new Error(`marker prerender:${name} not found`);
  html = html.replace(re, (_, open, close) => `${open}${markup}${close}`);
}
fs.writeFileSync(file, html);
console.log("prerendered default plan into site/index.html");

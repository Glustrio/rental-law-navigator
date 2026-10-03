// Run the browser engine on the cases in argv[2] and print its results as JSON.
import { readFileSync } from "node:fs";
import { lookup, parseDate } from "../site/engine.js";

const { rules, addresses, dates } = JSON.parse(readFileSync(process.argv[2], "utf8"));
const out = {};
for (const d of dates) {
  out[d] = {};
  for (const [id, a] of Object.entries(addresses)) out[d][id] = lookup(a, rules, parseDate(d));
}
process.stdout.write(JSON.stringify(out));

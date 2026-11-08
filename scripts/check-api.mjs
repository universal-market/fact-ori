import { readFileSync } from "node:fs";
import { checkText } from "../client/check.mjs";
const args = process.argv.slice(2);
let origin = "http://127.0.0.1:43211",
  publicReview = false;
const text = [];
for (let i = 0; i < args.length; i++) {
  if (args[i] === "--origin") {
    if (!args[i + 1]) throw Error("--origin needs a value");
    origin = args[++i];
  } else if (args[i] === "--public-review") publicReview = true;
  else if (args[i] === "--help") {
    console.log(
      "Usage: npm run check -- [--origin HTTPS_ORIGIN] [--public-review] TEXT\nOmit TEXT to read stdin. Public review consents to posting uncovered claims on Tilori.",
    );
    process.exit(0);
  } else text.push(args[i]);
}
const input = text.length ? text.join(" ") : readFileSync(0, "utf8");
if (!input.trim()) throw Error("Text required");
const result = await checkText(origin, input, { publicReview });
console.log(JSON.stringify(result, null, 2));

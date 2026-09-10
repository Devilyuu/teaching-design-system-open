import { createRequire } from "node:module";
import path from "node:path";
import { fileURLToPath } from "node:url";

const require = createRequire(import.meta.url);
const { chromium } = require("playwright");

const outputDir = path.dirname(fileURLToPath(import.meta.url));
const filenames = [
  "card-01-cover.png",
  "card-02-dashboard.png",
  "card-03-materials.png",
  "card-04-outline.png",
  "card-05-lessons.png",
  "card-06-session.png",
  "card-07-reflection.png",
  "card-08-open-source.png"
];

const browser = await chromium.launch({ headless: true });
const page = await browser.newPage({ viewport: { width: 1200, height: 1600 }, deviceScaleFactor: 1 });

for (let index = 0; index < filenames.length; index += 1) {
  await page.goto(`http://127.0.0.1:8765/cards.html?card=${index + 1}`, { waitUntil: "networkidle" });
  await page.screenshot({ path: path.join(outputDir, filenames[index]), fullPage: false });
  console.log(`rendered ${filenames[index]}`);
}

await browser.close();

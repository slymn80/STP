import fs from "fs";
import path from "path";
import { fileURLToPath } from "url";
import { chromium } from "playwright";

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const root = path.resolve(__dirname, "..", "..");
const outRoot = path.join(root, "reports");
const pdfRoot = path.join(outRoot, "pdf");
const docxRoot = path.join(outRoot, "word");
const baseUrl = "http://localhost:8000";

function ensureDir(p) {
  fs.mkdirSync(p, { recursive: true });
}

async function downloadOne(page, selector, savePath) {
  const [download] = await Promise.all([
    page.waitForEvent("download"),
    page.click(selector),
  ]);
  await download.saveAs(savePath);
}

async function main() {
  ensureDir(outRoot);
  ensureDir(pdfRoot);
  ensureDir(docxRoot);

  const browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ acceptDownloads: true });
  const page = await context.newPage();
  page.setDefaultTimeout(120000);

  const gradeEnv = process.env.GRADES || "";
  const grades = gradeEnv
    ? gradeEnv.split(",").map((g) => Number(g.trim())).filter(Boolean)
    : [5, 10];
  for (const grade of grades) {
    const pdfDir = path.join(pdfRoot, `grade${grade}`);
    const docxDir = path.join(docxRoot, `grade${grade}`);
    ensureDir(pdfDir);
    ensureDir(docxDir);

    for (let week = 1; week <= 34; week++) {
      const url = `${baseUrl}/?grade=${grade}&week=${week}`;
      await page.goto(url, { waitUntil: "networkidle" });
      await page.waitForSelector("#content h1");
      await page.waitForSelector("#downloadPdf");

      const weekStr = String(week).padStart(2, "0");
      const pdfPath = path.join(pdfDir, `grade${grade}-week${weekStr}.pdf`);
      const docxPath = path.join(docxDir, `grade${grade}-week${weekStr}.docx`);

      await downloadOne(page, "#downloadPdf", pdfPath);
      await downloadOne(page, "#downloadDocx", docxPath);
    }
  }

  await browser.close();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});

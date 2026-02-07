const gradeSelect = document.getElementById("gradeSelect");
const weekSelect = document.getElementById("weekSelect");
const metaDiv = document.getElementById("meta");
const contentDiv = document.getElementById("content");

function padWeek(week) {
  return String(week).padStart(2, "0");
}

function populateWeeks() {
  weekSelect.innerHTML = "";
  for (let i = 1; i <= 34; i++) {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `Week ${i}`;
    weekSelect.appendChild(opt);
  }
}

function parseFrontmatter(text) {
  const lines = text.split(/\r?\n/);
  if (lines[0].trim() !== "---") {
    return { meta: {}, body: text };
  }
  let end = -1;
  for (let i = 1; i < lines.length; i++) {
    if (lines[i].trim() === "---") {
      end = i;
      break;
    }
  }
  if (end === -1) {
    return { meta: {}, body: text };
  }
  const metaLines = lines.slice(1, end);
  const meta = {};
  metaLines.forEach((line) => {
    const idx = line.indexOf(":");
    if (idx === -1) return;
    const key = line.slice(0, idx).trim();
    let value = line.slice(idx + 1).trim();
    value = value.replace(/^"|"$/g, "");
    meta[key] = value;
  });
  const body = lines.slice(end + 1).join("\n");
  return { meta, body };
}

function renderMeta(meta) {
  const entries = Object.entries(meta);
  if (entries.length === 0) {
    metaDiv.innerHTML = "<p>No metadata found.</p>";
    return;
  }
  const items = entries
    .map(
      ([k, v]) =>
        `<div class="meta-item"><span>${k}</span>${v}</div>`
    )
    .join("");
  metaDiv.innerHTML = `<div class="meta-grid">${items}</div>`;
}

async function loadLesson() {
  const grade = gradeSelect.value;
  const week = padWeek(weekSelect.value);
  const url = `content/grade${grade}/week${week}.md`;
  contentDiv.innerHTML = "Loading lesson...";
  try {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Lesson not found: ${url}`);
    }
    const text = await res.text();
    const { meta, body } = parseFrontmatter(text);
    renderMeta(meta);
    contentDiv.innerHTML = marked.parse(body);
  } catch (err) {
    let msg = err.message;
    if (location.protocol === "file:") {
      msg = "Open this site with a local server (file:// blocks fetch). Run: python -m http.server 8000 -d .\\site";
    }
    contentDiv.innerHTML = `<p>${msg}</p>`;
    metaDiv.innerHTML = "";
  }
}

populateWeeks();
weekSelect.value = 1;
loadLesson();

gradeSelect.addEventListener("change", () => {
  weekSelect.value = 1;
  loadLesson();
});

weekSelect.addEventListener("change", loadLesson);

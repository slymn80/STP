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

function parseRoute() {
  const params = new URLSearchParams(window.location.search);
  const qGrade = params.get("grade");
  const qWeek = params.get("week");
  if (qGrade && qWeek) {
    return { grade: qGrade, week: qWeek };
  }
  const path = window.location.pathname.replace(/\/+$/, "");
  const match = path.match(/\/(5|10)\/(\d{1,2})$/);
  if (match) {
    return { grade: match[1], week: match[2] };
  }
  return null;
}

function updateUrl(grade, week, push = true) {
  const path = `/${grade}/${Number(week)}`;
  if (push) {
    history.pushState({}, "", path);
  } else {
    history.replaceState({}, "", path);
  }
}

async function loadLesson() {
  const grade = gradeSelect.value;
  const week = padWeek(weekSelect.value);
  const url = `/content/grade${grade}/week${week}.md`;
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
const route = parseRoute();
if (route) {
  gradeSelect.value = route.grade;
  weekSelect.value = route.week;
} else {
  weekSelect.value = 1;
}
updateUrl(gradeSelect.value, weekSelect.value, false);
loadLesson();

gradeSelect.addEventListener("change", () => {
  weekSelect.value = 1;
  updateUrl(gradeSelect.value, weekSelect.value);
  loadLesson();
});

weekSelect.addEventListener("change", () => {
  updateUrl(gradeSelect.value, weekSelect.value);
  loadLesson();
});

window.addEventListener("popstate", () => {
  const r = parseRoute();
  if (r) {
    gradeSelect.value = r.grade;
    weekSelect.value = r.week;
    loadLesson();
  }
});

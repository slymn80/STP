const gradeSelect = document.getElementById("gradeSelect");
const weekSelect = document.getElementById("weekSelect");
const metaDiv = document.getElementById("meta");
const contentDiv = document.getElementById("content");
const downloadBtn = document.getElementById("downloadPdf");
const downloadDocxBtn = document.getElementById("downloadDocx");
const downloadKspBtn = document.getElementById("downloadKsp");

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
  const metaOut = { ...meta };
  if (meta.section || meta.date || meta.day) {
    let dateStr = meta.date || "";
    const isMultiSection = dateStr.includes(";") || (meta.section || "").includes(",");
    if (!isMultiSection && dateStr && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
      const [y, m, d] = dateStr.split("-");
      dateStr = `${d}.${m}.${y}`;
    }
    if (!isMultiSection && meta.day) {
      dateStr = dateStr ? `${dateStr} (${meta.day})` : meta.day;
    }
    if (isMultiSection) {
      metaOut.section = meta.section || "";
      metaOut.date = meta.date || "";
    } else {
      const section = meta.section ? `${meta.section}` : "";
      metaOut.date = [section, dateStr].filter(Boolean).join(" ").trim();
    }
  }
  const preferredOrder = [
    "school",
    "subject",
    "teacher",
    "grade",
    "week",
    "section",
    "date",
    "topic",
    "duration",
  ];
  const entries = preferredOrder
    .filter((k) => k in metaOut)
    .map((k) => [k, metaOut[k]])
    .concat(
      Object.entries(metaOut).filter(([k]) => !preferredOrder.includes(k))
    );
  if (entries.length === 0) {
    metaDiv.innerHTML = "<p>No metadata found.</p>";
    return;
  }
  const items = entries
    .map(([k, v]) => {
      return `<div class="meta-item"><span>${k}</span>${v}</div>`;
    })
    .join("");
  metaDiv.innerHTML = `<div class="meta-grid">${items}</div>`;
}

function buildReportHeader(meta) {
  const parts = [];
  if (meta.section) parts.push(meta.section);
  if (meta.week) parts.push(`Week ${meta.week}`);
  let dateStr = meta.date || "";
  if (dateStr && /^\d{4}-\d{2}-\d{2}$/.test(dateStr)) {
    const [y, m, d] = dateStr.split("-");
    dateStr = `${d}.${m}.${y}`;
  }
  if (meta.day) {
    dateStr = dateStr ? `${dateStr} (${meta.day})` : meta.day;
  }
  if (dateStr) parts.push(dateStr);
  return parts.join(" \u00b7 ");
}

function getCurrentMeta() {
  try {
    return JSON.parse(contentDiv.dataset.meta || "{}");
  } catch {
    return {};
  }
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
  const url = `/content/grade${grade}/week${week}.md?v=20`;
  contentDiv.innerHTML = "Loading lesson...";
  try {
    const res = await fetch(url);
    if (!res.ok) {
      throw new Error(`Lesson not found: ${url}`);
    }
    const text = await res.text();
    const { meta, body } = parseFrontmatter(text);
    contentDiv.dataset.meta = JSON.stringify(meta);
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

async function downloadPdf() {
  const grade = gradeSelect.value;
  const week = padWeek(weekSelect.value);
  const title = `grade${grade}-week${week}.pdf`;

  const { jsPDF } = window.jspdf;
  const pdf = new jsPDF("p", "pt", "a4");
  const pageWidth = pdf.internal.pageSize.getWidth();
  const pageHeight = pdf.internal.pageSize.getHeight();
  const mmToPt = (mm) => (mm / 25.4) * 72;
  const marginTop = mmToPt(25);
  const marginLeft = mmToPt(25);
  const marginRight = mmToPt(20);
  const marginBottom = mmToPt(20);
  const pxPerPt = 96 / 72;
  const contentWidthPx = Math.floor((pageWidth - marginLeft - marginRight) * pxPerPt);

  const container = document.createElement("div");
  container.style.width = `${contentWidthPx}px`;
  container.style.padding = "0";
  container.style.paddingBottom = `${Math.ceil(marginBottom * pxPerPt)}px`;
  container.style.background = "#ffffff";
  container.style.color = "#000000";
  container.style.fontFamily = getComputedStyle(document.body).fontFamily;
  container.style.fontSize = "11pt";
  container.style.lineHeight = "1.4";
  container.style.boxSizing = "border-box";
  container.style.position = "fixed";
  container.style.left = "-10000px";
  container.style.top = "0";
  container.style.zIndex = "-1";

  const reportHeader = buildReportHeader(getCurrentMeta());
  if (reportHeader) {
    const headerEl = document.createElement("div");
    headerEl.style.fontWeight = "600";
    headerEl.style.marginBottom = "8px";
    headerEl.textContent = reportHeader;
    container.appendChild(headerEl);
  }

  const metaClone = metaDiv.cloneNode(true);
  const contentClone = contentDiv.cloneNode(true);
  container.appendChild(metaClone);
  container.appendChild(document.createElement("hr"));
  container.appendChild(contentClone);
  document.body.appendChild(container);

  const headings = container.querySelectorAll("h1, h2, h3, h4, h5, h6");
  headings.forEach((h) => {
    h.style.fontSize = "12pt";
  });

  const details = Array.from(container.querySelectorAll("details"));
  details.forEach((d) => {
    d.open = true;
  });

  const imgs = Array.from(container.querySelectorAll("img"));
  await Promise.all(
    imgs.map(
      (img) =>
        new Promise((resolve) => {
          if (img.complete) return resolve();
          img.onload = resolve;
          img.onerror = resolve;
        })
    )
  );

  const canvas = await html2canvas(container, {
    scale: 2,
    useCORS: true,
    backgroundColor: "#ffffff",
  });
  const imgData = canvas.toDataURL("image/png");
  const ratio = (pageWidth - marginLeft - marginRight) / canvas.width;
  const imgWidth = canvas.width * ratio;
  const availableHeight = pageHeight - marginTop - marginBottom;
  const sliceHeightPx = Math.max(1, Math.floor(availableHeight / ratio));

  let y = 0;
  let pageIndex = 0;
  while (y < canvas.height) {
    const slicePx = Math.min(sliceHeightPx, canvas.height - y);
    const pageCanvas = document.createElement("canvas");
    pageCanvas.width = canvas.width;
    pageCanvas.height = slicePx;
    const ctx = pageCanvas.getContext("2d");
    ctx.drawImage(
      canvas,
      0,
      y,
      canvas.width,
      slicePx,
      0,
      0,
      canvas.width,
      slicePx
    );
    const pageImg = pageCanvas.toDataURL("image/png");
    const imgHeight = slicePx * ratio;
    if (pageIndex > 0) pdf.addPage();
    pdf.addImage(pageImg, "PNG", marginLeft, marginTop, imgWidth, imgHeight);
    y += slicePx;
    pageIndex += 1;
  }

  pdf.save(title);
  container.remove();
}

async function downloadDocx() {
  const grade = gradeSelect.value;
  const week = padWeek(weekSelect.value);
  const title = `grade${grade}-week${week}.docx`;

  if (!window.htmlDocx || !window.saveAs) {
    alert("Word export libraries are missing. Please refresh the page.");
    return;
  }

  const mmToPt = (mm) => (mm / 25.4) * 72;
  const pageWidth = 595.28; // A4 width in points
  const marginTop = mmToPt(25);
  const marginLeft = mmToPt(25);
  const marginRight = mmToPt(20);
  const marginBottom = mmToPt(20);
  const pxPerPt = 96 / 72;
  const contentWidthPx = Math.floor((pageWidth - marginLeft - marginRight) * pxPerPt);

  const container = document.createElement("div");
  container.style.width = `${contentWidthPx}px`;
  container.style.padding = "0";
  container.style.background = "#ffffff";
  container.style.color = "#000000";
  container.style.fontFamily = getComputedStyle(document.body).fontFamily;
  container.style.fontSize = "11pt";
  container.style.lineHeight = "1.4";
  container.style.boxSizing = "border-box";
  container.style.position = "fixed";
  container.style.left = "-10000px";
  container.style.top = "0";
  container.style.zIndex = "-1";

  const reportHeader = buildReportHeader(getCurrentMeta());
  if (reportHeader) {
    const headerEl = document.createElement("div");
    headerEl.style.fontWeight = "700";
    headerEl.style.marginBottom = "8px";
    headerEl.textContent = reportHeader;
    container.appendChild(headerEl);
  }

  const metaClone = metaDiv.cloneNode(true);
  const contentClone = contentDiv.cloneNode(true);
  container.appendChild(metaClone);
  container.appendChild(document.createElement("hr"));
  container.appendChild(contentClone);
  document.body.appendChild(container);

  const headings = container.querySelectorAll("h1, h2, h3, h4, h5, h6");
  headings.forEach((h) => {
    h.style.fontSize = "12pt";
  });

  const imgs = Array.from(container.querySelectorAll("img"));
  await Promise.all(
    imgs.map(async (img) => {
      try {
        const url = img.getAttribute("src");
        if (!url) return;
        const res = await fetch(url, { mode: "cors" });
        const blob = await res.blob();
        const dataUrl = await new Promise((resolve) => {
          const reader = new FileReader();
          reader.onload = () => resolve(reader.result);
          reader.readAsDataURL(blob);
        });
        img.setAttribute("src", dataUrl);
      } catch {
        // ignore image failures in docx export
      }
    })
  );

  const details = Array.from(container.querySelectorAll("details"));
  details.forEach((d) => {
    const wrapper = document.createElement("div");
    const summary = d.querySelector("summary");
    if (summary) {
      const p = document.createElement("p");
      p.textContent = summary.textContent;
      p.style.fontWeight = "700";
      wrapper.appendChild(p);
    }
    Array.from(d.childNodes).forEach((n) => {
      if (summary && n === summary) return;
      wrapper.appendChild(n.cloneNode(true));
    });
    d.replaceWith(wrapper);
  });

  const fontFamily = getComputedStyle(document.body).fontFamily;
  const styles = `
    @page {
      size: A4;
      margin-top: 25mm;
      margin-left: 25mm;
      margin-right: 20mm;
      margin-bottom: 20mm;
    }
    body {
      font-family: ${fontFamily};
      font-size: 11pt;
      line-height: 1.4;
    }
    h1, h2, h3, h4, h5, h6 {
      font-size: 12pt;
    }
  `;

  const html = `<!DOCTYPE html><html><head><meta charset="utf-8"><style>${styles}</style></head><body>${container.innerHTML}</body></html>`;
  const blob = window.htmlDocx.asBlob(html);
  window.saveAs(blob, title);
  container.remove();
}

function getMetaMap() {
  const items = Array.from(metaDiv.querySelectorAll(".meta-item"));
  const meta = {};
  items.forEach((item) => {
    const keyEl = item.querySelector("span");
    if (!keyEl) return;
    const key = keyEl.textContent.trim();
    const value = item.textContent.replace(keyEl.textContent, "").trim();
    meta[key.toLowerCase()] = value;
  });
  return meta;
}

function sectionLines(matchFn) {
  const headings = Array.from(contentDiv.querySelectorAll("h2, h3"));
  for (let i = 0; i < headings.length; i++) {
    const h = headings[i];
    if (!matchFn(h.textContent.trim())) continue;
    const lines = [];
    let node = h.nextElementSibling;
    while (node && !["H2", "H3"].includes(node.tagName)) {
      if (node.tagName === "UL" || node.tagName === "OL") {
        Array.from(node.querySelectorAll("li")).forEach((li) => {
          const t = li.textContent.trim();
          if (t) lines.push(t);
        });
      } else if (node.tagName === "P") {
        const t = node.textContent.trim();
        if (t) lines.push(t);
      }
      node = node.nextElementSibling;
    }
    return lines;
  }
  return [];
}

function joinLines(lines) {
  return lines.map((l) => l.replace(/\s+/g, " ").trim()).filter(Boolean).join(" ");
}

function filterLines(lines, prefix) {
  return lines.filter((l) => l.toLowerCase().startsWith(prefix.toLowerCase()));
}

async function downloadKsp() {
  const grade = gradeSelect.value;
  const week = padWeek(weekSelect.value);
  const title = `grade${grade}-week${week}-ksp.docx`;

  if (!window.JSZip) {
    alert("KSP export library is missing. Please refresh the page.");
    return;
  }

  const meta = getMetaMap();
  const topic = meta.topic || "";
  const teacher = meta.teacher || "";
  const subject = meta.subject || "";
  const metaDate = meta.date || "";
  const metaDay = meta.day || "";
  let dateStr = metaDate;
  if (dateStr) {
    const parts = dateStr.split("-");
    if (parts.length === 3) {
      dateStr = `${parts[2]}.${parts[1]}.${parts[0]}`;
    }
  }
  if (metaDay) {
    dateStr = dateStr ? `${dateStr} (${metaDay})` : metaDay;
  }

  const objectives = sectionLines((t) => t === "Learning Objectives");
  const criteria = sectionLines((t) => t === "Assessment Criteria");
  const intro = sectionLines((t) => t.startsWith("Introduction"));
  const main = sectionLines((t) => t.startsWith("Main Content"));
  const practice = sectionLines((t) => t === "Practice Activity");
  const assessment = sectionLines((t) => t === "Assessment");
  const homework = sectionLines((t) => t === "Homework");
  const reflection = sectionLines((t) => t === "Teacher Reflection");
  const detailed = sectionLines((t) => t === "Detailed Topic Study");

  const introStudents = filterLines(intro, "Students:");
  const mainStudents = filterLines(main.concat(practice, detailed), "Students:");
  const resources = contentDiv.querySelector("img") ? "Lesson visual" : "";

  const lessonGoal = objectives.length
    ? `Students will be able to: ${objectives.join("; ")}`
    : "";

  const labelTexts = {
    "0": "Section",
    "1": "Teacher name",
    "2": "Date",
    "3": `Grade: ${grade}`,
    "4": "Lesson topic",
    "5": "Learning objectives (curriculum link)",
    "6": "Lesson goal",
    "7": "Success criteria",
    "8": "Lesson flow",
    "10": "Organizational stage",
    "11": "New material",
    "12": "Reflection",
  };

  const introText = joinLines(intro);
  const mainText = joinLines(main.concat(detailed, practice));
  const reflectionText = joinLines(reflection);
  const introStudentsText = joinLines(introStudents.length ? introStudents : intro);
  const mainStudentsText = joinLines(mainStudents.length ? mainStudents : main);

  const kspIntro = `Organizational stage (5 min): ${introText || "Class setup, attendance, and warm-up questions."}`;
  const kspMain = `New material (30 min): ${mainText || "Explain the topic, guide practice, and check understanding."}`;
  const kspReflect = `Reflection (10 min): ${reflectionText || "Students reflect on learning outcomes and next steps."}`;

  const reportHeader = buildReportHeader(getCurrentMeta());
  const rowTexts = {
    "0": reportHeader ? `${subject} \u00b7 ${reportHeader}` : subject,
    "1": teacher,
    "2": dateStr,
    "4": topic,
    "5": joinLines(objectives),
    "6": lessonGoal,
    "7": joinLines(criteria),
    "8": "45 minutes",
    "10": kspIntro,
    "11": kspMain,
    "12": kspReflect,
  };

  const res = await fetch("/templates/ksp-template.docx");
  if (!res.ok) throw new Error("KSP template not found.");
  const data = await res.arrayBuffer();
  const zip = await JSZip.loadAsync(data);
  const xmlText = await zip.file("word/document.xml").async("string");
  const parser = new DOMParser();
  const xml = parser.parseFromString(xmlText, "application/xml");
  const ns = "http://schemas.openxmlformats.org/wordprocessingml/2006/main";
  const table = xml.getElementsByTagNameNS(ns, "tbl")[0];
  const rows = Array.from(table.childNodes).filter((n) => n.localName === "tr");

  function setCellText(rowIdx, cellIdx, text) {
    const tr = rows[rowIdx];
    if (!tr) return;
    const cells = Array.from(tr.childNodes).filter((n) => n.localName === "tc");
    const tc = cells[cellIdx];
    if (!tc) return;
    const keep = Array.from(tc.childNodes).filter((n) => n.localName === "tcPr");
    while (tc.firstChild) tc.removeChild(tc.firstChild);
    keep.forEach((n) => tc.appendChild(n));
    const p = xml.createElementNS(ns, "w:p");
    const lines = String(text || "").split("\n");
    lines.forEach((line, idx) => {
      const r = xml.createElementNS(ns, "w:r");
      const t = xml.createElementNS(ns, "w:t");
      t.textContent = line;
      r.appendChild(t);
      p.appendChild(r);
      if (idx < lines.length - 1) {
        const br = xml.createElementNS(ns, "w:br");
        p.appendChild(br);
      }
    });
    tc.appendChild(p);
  }

  function getCells(rowIdx) {
    const tr = rows[rowIdx];
    if (!tr) return [];
    return Array.from(tr.childNodes).filter((n) => n.localName === "tc");
  }

  function getCellWidth(tc) {
    const tcPr = Array.from(tc.childNodes).find((n) => n.localName === "tcPr");
    if (!tcPr) return 0;
    const tcW = Array.from(tcPr.childNodes).find((n) => n.localName === "tcW");
    if (!tcW) return 0;
    const w = tcW.getAttribute("w:w");
    return w ? Number(w) : 0;
  }

  function getWidestCellIndex(rowIdx) {
    const cells = getCells(rowIdx);
    let max = -1;
    let idx = 0;
    cells.forEach((tc, i) => {
      const w = getCellWidth(tc);
      if (w > max) {
        max = w;
        idx = i;
      }
    });
    return idx;
  }

  Object.entries(labelTexts).forEach(([rowKey, value]) => {
    const r = Number(rowKey);
    setCellText(r, 0, value || "");
  });

  // Header row labels for lesson flow table
  setCellText(9, 0, "Lesson stages");
  setCellText(9, 1, "Teacher activity");
  setCellText(9, 2, "Student activity");
  setCellText(9, 3, "Assessment");
  setCellText(9, 4, "Resources");

  // Grade row Present/Absent labels
  setCellText(3, 1, "Present:");
  setCellText(3, 2, "Absent:");

  Object.entries(rowTexts).forEach(([rowKey, value]) => {
    const r = Number(rowKey);
    const idx = getWidestCellIndex(r);
    setCellText(r, idx, value || "");
  });

  // Fill lesson flow rows
  setCellText(10, 1, kspIntro);
  setCellText(10, 2, introStudentsText || "Students prepare and engage in the warm-up.");
  setCellText(10, 3, joinLines(assessment));
  setCellText(10, 4, resources);

  setCellText(11, 1, kspMain);
  setCellText(11, 2, mainStudentsText || "Students complete guided practice and tasks.");
  setCellText(11, 3, joinLines(assessment));
  setCellText(11, 4, "");

  setCellText(12, 1, kspReflect);
  setCellText(12, 2, homework.length ? joinLines(homework) : "Students reflect on learning outcomes.");

  async function addImageToDocx(imgUrl) {
    if (!imgUrl) return null;
    const imgRes = await fetch(imgUrl, { mode: "cors" });
    const imgBlob = await imgRes.blob();
    const imgArray = await imgBlob.arrayBuffer();
    const imgName = `image-ksp-${Date.now()}.png`;
    zip.file(`word/media/${imgName}`, imgArray);

    const relsText = await zip.file("word/_rels/document.xml.rels").async("string");
    const relsXml = new DOMParser().parseFromString(relsText, "application/xml");
    const rels = relsXml.getElementsByTagName("Relationship");
    let maxId = 0;
    Array.from(rels).forEach((r) => {
      const id = r.getAttribute("Id") || "";
      const m = id.match(/rId(\d+)/);
      if (m) maxId = Math.max(maxId, Number(m[1]));
    });
    const newId = `rId${maxId + 1}`;
    const rel = relsXml.createElement("Relationship");
    rel.setAttribute("Id", newId);
    rel.setAttribute(
      "Type",
      "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image"
    );
    rel.setAttribute("Target", `media/${imgName}`);
    relsXml.documentElement.appendChild(rel);
    zip.file(
      "word/_rels/document.xml.rels",
      new XMLSerializer().serializeToString(relsXml)
    );
    return newId;
  }

  function setCellDrawing(rowIdx, cellIdx, rId, widthPx = 180, heightPx = 120) {
    if (!rId) return;
    const tr = rows[rowIdx];
    if (!tr) return;
    const cells = Array.from(tr.childNodes).filter((n) => n.localName === "tc");
    const tc = cells[cellIdx];
    if (!tc) return;
    const keep = Array.from(tc.childNodes).filter((n) => n.localName === "tcPr");
    while (tc.firstChild) tc.removeChild(tc.firstChild);
    keep.forEach((n) => tc.appendChild(n));
    const emu = (px) => Math.round(px * 9525);
    const cx = emu(widthPx);
    const cy = emu(heightPx);
    const drawingXml = `
      <w:p xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
           xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
           xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
           xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
           xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <w:r>
          <w:drawing>
            <wp:inline distT="0" distB="0" distL="0" distR="0">
              <wp:extent cx="${cx}" cy="${cy}"/>
              <wp:docPr id="1" name="LessonVisual"/>
              <a:graphic>
                <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:pic>
                    <pic:nvPicPr>
                      <pic:cNvPr id="0" name="LessonVisual"/>
                      <pic:cNvPicPr/>
                    </pic:nvPicPr>
                    <pic:blipFill>
                      <a:blip r:embed="${rId}"/>
                      <a:stretch><a:fillRect/></a:stretch>
                    </pic:blipFill>
                    <pic:spPr>
                      <a:xfrm>
                        <a:off x="0" y="0"/>
                        <a:ext cx="${cx}" cy="${cy}"/>
                      </a:xfrm>
                      <a:prstGeom prst="rect"><a:avLst/></a:prstGeom>
                    </pic:spPr>
                  </pic:pic>
                </a:graphicData>
              </a:graphic>
            </wp:inline>
          </w:drawing>
        </w:r>
      </w:p>
    `;
    const frag = new DOMParser().parseFromString(drawingXml, "application/xml");
    const newP = xml.importNode(frag.documentElement, true);
    tc.appendChild(newP);
  }

  const firstImg = contentDiv.querySelector("img");
  if (firstImg) {
    const rId = await addImageToDocx(firstImg.getAttribute("src"));
    const r11Cells = getCells(11);
    const resIdx = Math.max(0, r11Cells.length - 1);
    setCellDrawing(11, resIdx, rId, 180, 120);
  }

  const serializer = new XMLSerializer();
  const updatedXml = serializer.serializeToString(xml);
  zip.file("word/document.xml", updatedXml);

  const outBlob = await zip.generateAsync({ type: "blob" });
  window.saveAs(outBlob, title);
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

downloadBtn.addEventListener("click", () => {
  downloadBtn.disabled = true;
  downloadBtn.textContent = "Preparing PDF...";
  downloadPdf().finally(() => {
    downloadBtn.disabled = false;
    downloadBtn.textContent = "Download PDF";
  });
});

downloadDocxBtn.addEventListener("click", () => {
  downloadDocxBtn.disabled = true;
  downloadDocxBtn.textContent = "Preparing Word...";
  downloadDocx()
    .catch((err) => console.error(err))
    .finally(() => {
      downloadDocxBtn.disabled = false;
      downloadDocxBtn.textContent = "Download Word";
    });
});

downloadKspBtn.addEventListener("click", () => {
  downloadKspBtn.disabled = true;
  downloadKspBtn.textContent = "Preparing ???...";
  downloadKsp()
    .catch((err) => console.error(err))
    .finally(() => {
      downloadKspBtn.disabled = false;
      downloadKspBtn.textContent = "Download ???";
    });
});

window.addEventListener("popstate", () => {
  const r = parseRoute();
  if (r) {
    gradeSelect.value = r.grade;
    weekSelect.value = r.week;
    loadLesson();
  }
});






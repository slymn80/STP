import os
import re
import zipfile
import xml.etree.ElementTree as ET
from datetime import datetime

ROOT = r"C:\Users\Suleyman\PycharmProjects\STP"
CONTENT_DIR = os.path.join(ROOT, "informatics-lessons", "content")
TEMPLATE_PATH = os.path.join(ROOT, "informatics-lessons", "site", "templates", "ksp-template.docx")
DEFAULT_OUT_ROOT = os.path.join(ROOT, "kcp")

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
NS_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
NS_REL = "http://schemas.openxmlformats.org/package/2006/relationships"
ET.register_namespace("w", NS_W)
ET.register_namespace("r", NS_R)


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end == -1:
        return {}, text
    meta = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip().strip('"')
        meta[key] = value
    body = "\n".join(lines[end + 1 :])
    return meta, body


def parse_sections(body):
    sections = {}
    current = None
    for raw in body.splitlines():
        line = raw.rstrip("\n")
        if line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
            continue
        if line.startswith("# "):
            continue
        if current is None:
            continue
        if not line.strip():
            continue
        stripped = line.lstrip()
        if stripped.startswith("- "):
            text = stripped[2:]
            while text.startswith("- "):
                text = text[2:]
            sections[current].append(text.strip())
        else:
            sections[current].append(line.strip())
    return sections


def join_lines(lines):
    out = []
    for l in lines:
        l = re.sub(r"\s+", " ", l).strip()
        if l:
            out.append(l)
    return " ".join(out)


def filter_lines(lines, prefix):
    p = prefix.lower()
    return [l for l in lines if l.lower().startswith(p)]


def build_report_header(meta):
    parts = []
    if meta.get("section"):
        parts.append(meta.get("section"))
    if meta.get("week"):
        parts.append(f"Week {meta.get('week')}")
    date_str = meta.get("date") or ""
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        y, m, d = date_str.split("-")
        date_str = f"{d}.{m}.{y}"
    if meta.get("day"):
        date_str = f"{date_str} ({meta.get('day')})" if date_str else meta.get("day")
    if date_str:
        parts.append(date_str)
    return " \u00b7 ".join([p for p in parts if p])


def get_attr(elem, name):
    for k, v in elem.attrib.items():
        if k == name or k.endswith("}" + name):
            return v
    return None


def set_cell_text(xml, rows, row_idx, cell_idx, text):
    if row_idx >= len(rows):
        return
    tr = rows[row_idx]
    cells = [c for c in list(tr) if c.tag == f"{{{NS_W}}}tc"]
    if cell_idx >= len(cells):
        return
    tc = cells[cell_idx]
    keep = [c for c in list(tc) if c.tag == f"{{{NS_W}}}tcPr"]
    for child in list(tc):
        tc.remove(child)
    for node in keep:
        tc.append(node)
    p = ET.Element(f"{{{NS_W}}}p")
    lines = str(text or "").split("\n")
    for idx, line in enumerate(lines):
        r = ET.Element(f"{{{NS_W}}}r")
        t = ET.Element(f"{{{NS_W}}}t")
        t.text = line
        r.append(t)
        p.append(r)
        if idx < len(lines) - 1:
            br = ET.Element(f"{{{NS_W}}}br")
            p.append(br)
    tc.append(p)


def get_cells(rows, row_idx):
    if row_idx >= len(rows):
        return []
    tr = rows[row_idx]
    return [c for c in list(tr) if c.tag == f"{{{NS_W}}}tc"]


def get_cell_width(tc):
    tc_pr = tc.find(f"w:tcPr", {"w": NS_W})
    if tc_pr is None:
        return 0
    tc_w = tc_pr.find(f"w:tcW", {"w": NS_W})
    if tc_w is None:
        return 0
    w = get_attr(tc_w, "w")
    try:
        return int(w)
    except Exception:
        return 0


def get_widest_cell_index(rows, row_idx):
    cells = get_cells(rows, row_idx)
    max_w = -1
    idx = 0
    for i, tc in enumerate(cells):
        w = get_cell_width(tc)
        if w > max_w:
            max_w = w
            idx = i
    return idx


def add_relationship(rels_xml, target):
    max_id = 0
    for rel in rels_xml.findall(".//{http://schemas.openxmlformats.org/package/2006/relationships}Relationship"):
        rid = rel.get("Id") or ""
        m = re.match(r"rId(\d+)", rid)
        if m:
            max_id = max(max_id, int(m.group(1)))
    new_id = f"rId{max_id + 1}"
    rel = ET.Element("{http://schemas.openxmlformats.org/package/2006/relationships}Relationship")
    rel.set("Id", new_id)
    rel.set("Type", "http://schemas.openxmlformats.org/officeDocument/2006/relationships/image")
    rel.set("Target", target)
    rels_xml.append(rel)
    return new_id


def ensure_content_types(types_xml):
    # Ensure Default for png exists
    for d in types_xml.findall("{http://schemas.openxmlformats.org/package/2006/content-types}Default"):
        if (d.get("Extension") or "").lower() == "png":
            return
    d = ET.Element("{http://schemas.openxmlformats.org/package/2006/content-types}Default")
    d.set("Extension", "png")
    d.set("ContentType", "image/png")
    types_xml.append(d)


def set_cell_drawing(xml, rows, row_idx, cell_idx, r_id, width_px=180, height_px=120):
    if not r_id:
        return
    cells = get_cells(rows, row_idx)
    if cell_idx >= len(cells):
        return
    tc = cells[cell_idx]
    keep = [c for c in list(tc) if c.tag == f"{{{NS_W}}}tcPr"]
    for child in list(tc):
        tc.remove(child)
    for node in keep:
        tc.append(node)
    def emu(px):
        return str(int(round(px * 9525)))
    cx = emu(width_px)
    cy = emu(height_px)
    drawing_xml = f"""
      <w:p xmlns:w="{NS_W}"
           xmlns:r="{NS_R}"
           xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
           xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"
           xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture">
        <w:r>
          <w:drawing>
            <wp:inline distT="0" distB="0" distL="0" distR="0">
              <wp:extent cx="{cx}" cy="{cy}"/>
              <wp:docPr id="1" name="LessonVisual"/>
              <a:graphic>
                <a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
                  <pic:pic>
                    <pic:nvPicPr>
                      <pic:cNvPr id="0" name="LessonVisual"/>
                      <pic:cNvPicPr/>
                    </pic:nvPicPr>
                    <pic:blipFill>
                      <a:blip r:embed="{r_id}"/>
                      <a:stretch><a:fillRect/></a:stretch>
                    </pic:blipFill>
                    <pic:spPr>
                      <a:xfrm>
                        <a:off x="0" y="0"/>
                        <a:ext cx="{cx}" cy="{cy}"/>
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
    """
    frag = ET.fromstring(drawing_xml)
    tc.append(frag)


def generate_ksp_for(grade, week, out_dir):
    md_path = os.path.join(CONTENT_DIR, f"grade{grade}", f"week{week:02}.md")
    if not os.path.exists(md_path):
        return
    with open(md_path, "r", encoding="utf-8") as f:
        text = f.read()
    meta, body = parse_frontmatter(text)
    sections = parse_sections(body)

    def sec(name):
        return sections.get(name, [])

    objectives = sec("Learning Objectives")
    criteria = sec("Assessment Criteria")
    intro = []
    for title, lines in sections.items():
        if title.startswith("Introduction"):
            intro = lines
            break
    main = []
    for title, lines in sections.items():
        if title.startswith("Main Content"):
            main = lines
            break
    practice = sec("Practice Activity")
    assessment = sec("Assessment")
    homework = sec("Homework")
    reflection = sec("Teacher Reflection")
    detailed = sec("Detailed Topic Study")

    intro_students = filter_lines(intro, "Students:")
    main_students = filter_lines(main + practice + detailed, "Students:")

    lesson_goal = f"Students will be able to: {join_lines(objectives)}" if objectives else ""

    intro_text = join_lines(intro)
    main_text = join_lines(main + detailed + practice)
    reflection_text = join_lines(reflection)
    intro_students_text = join_lines(intro_students if intro_students else intro)
    main_students_text = join_lines(main_students if main_students else main)

    ksp_intro = f"Organizational stage (5 min): {intro_text or 'Class setup, attendance, and warm-up questions.'}"
    ksp_main = f"New material (30 min): {main_text or 'Explain the topic, guide practice, and check understanding.'}"
    ksp_reflect = f"Reflection (10 min): {reflection_text or 'Students reflect on learning outcomes and next steps.'}"

    report_header = build_report_header(meta)
    subject = meta.get("subject", "")
    teacher = meta.get("teacher", "")
    topic = meta.get("topic", "")
    meta_date = meta.get("date", "")
    meta_day = meta.get("day", "")

    date_str = meta_date
    if re.match(r"^\d{4}-\d{2}-\d{2}$", date_str):
        y, m, d = date_str.split("-")
        date_str = f"{d}.{m}.{y}"
    if meta_day:
        date_str = f"{date_str} ({meta_day})" if date_str else meta_day

    label_texts = {
        0: "Section",
        1: "Teacher name",
        2: "Date",
        3: f"Grade: {grade}",
        4: "Lesson topic",
        5: "Learning objectives (curriculum link)",
        6: "Lesson goal",
        7: "Success criteria",
        8: "Lesson flow",
        10: "Organizational stage",
        11: "New material",
        12: "Reflection",
    }

    row_texts = {
        0: f"{subject} \u00b7 {report_header}" if report_header else subject,
        1: teacher,
        2: date_str,
        4: topic,
        5: join_lines(objectives),
        6: lesson_goal,
        7: join_lines(criteria),
        8: "45 minutes",
        10: ksp_intro,
        11: ksp_main,
        12: ksp_reflect,
    }

    img_path = os.path.join(CONTENT_DIR, "images", f"grade{grade}", f"week{week:02}.png")
    has_img = os.path.exists(img_path)

    with zipfile.ZipFile(TEMPLATE_PATH, "r") as zf:
        doc_xml = zf.read("word/document.xml")
        rels_xml = zf.read("word/_rels/document.xml.rels")
        types_xml = zf.read("[Content_Types].xml")
        files = {name: zf.read(name) for name in zf.namelist() if name not in ("word/document.xml", "word/_rels/document.xml.rels", "[Content_Types].xml")}

    xml = ET.fromstring(doc_xml)
    table = xml.find(".//w:tbl", {"w": NS_W})
    rows = [n for n in list(table) if n.tag == f"{{{NS_W}}}tr"]

    for r, val in label_texts.items():
        set_cell_text(xml, rows, r, 0, val)

    # Header row labels for lesson flow table
    set_cell_text(xml, rows, 9, 0, "Lesson stages")
    set_cell_text(xml, rows, 9, 1, "Teacher activity")
    set_cell_text(xml, rows, 9, 2, "Student activity")
    set_cell_text(xml, rows, 9, 3, "Assessment")
    set_cell_text(xml, rows, 9, 4, "Resources")

    # Grade row Present/Absent labels
    set_cell_text(xml, rows, 3, 1, "Present:")
    set_cell_text(xml, rows, 3, 2, "Absent:")

    for r, val in row_texts.items():
        idx = get_widest_cell_index(rows, r)
        set_cell_text(xml, rows, r, idx, val)

    # Fill lesson flow rows
    set_cell_text(xml, rows, 10, 1, ksp_intro)
    set_cell_text(xml, rows, 10, 2, intro_students_text or "Students prepare and engage in the warm-up.")
    set_cell_text(xml, rows, 10, 3, join_lines(assessment))
    set_cell_text(xml, rows, 10, 4, "Lesson visual" if has_img else "")

    set_cell_text(xml, rows, 11, 1, ksp_main)
    set_cell_text(xml, rows, 11, 2, main_students_text or "Students complete guided practice and tasks.")
    set_cell_text(xml, rows, 11, 3, join_lines(assessment))
    set_cell_text(xml, rows, 11, 4, "")

    set_cell_text(xml, rows, 12, 1, ksp_reflect)
    set_cell_text(xml, rows, 12, 2, join_lines(homework) if homework else "Students reflect on learning outcomes.")

    rels = ET.fromstring(rels_xml)
    types = ET.fromstring(types_xml)
    new_files = dict(files)

    if has_img:
        img_name = f"image-ksp-grade{grade}-week{week:02}.png"
        new_files[f"word/media/{img_name}"] = open(img_path, "rb").read()
        r_id = add_relationship(rels, f"media/{img_name}")
        ensure_content_types(types)
        res_cells = get_cells(rows, 11)
        res_idx = max(0, len(res_cells) - 1)
        set_cell_drawing(xml, rows, 11, res_idx, r_id, 180, 120)

    out_path = os.path.join(out_dir, f"grade{grade}-week{week:02}-ksp.docx")
    os.makedirs(out_dir, exist_ok=True)

    doc_out = ET.tostring(xml, encoding="utf-8", xml_declaration=True)
    rels_out = ET.tostring(rels, encoding="utf-8", xml_declaration=True)
    types_out = ET.tostring(types, encoding="utf-8", xml_declaration=True)

    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", doc_out)
        zf.writestr("word/_rels/document.xml.rels", rels_out)
        zf.writestr("[Content_Types].xml", types_out)
        for name, data in new_files.items():
            zf.writestr(name, data)


def main():
    out_root = DEFAULT_OUT_ROOT
    if len(os.sys.argv) > 1:
        out_root = os.sys.argv[1]
    for grade in (5, 10):
        out_dir = os.path.join(out_root, f"grade{grade}")
        for week in range(1, 35):
            generate_ksp_for(grade, week, out_dir)


if __name__ == "__main__":
    main()

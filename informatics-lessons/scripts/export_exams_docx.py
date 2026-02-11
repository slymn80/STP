import os
import re
import html
import zipfile
from xml.etree.ElementTree import Element, SubElement, tostring

ROOT = r"C:\Users\Suleyman\PycharmProjects\STP"
EXAMS_SRC = os.path.join(ROOT, "informatics-lessons", "scripts", "exams")
OUT_ROOT = os.path.join(ROOT, "exams")

NS_W = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


def add_paragraph(parent, text):
    p = SubElement(parent, f"{{{NS_W}}}p")
    r = SubElement(p, f"{{{NS_W}}}r")
    t = SubElement(r, f"{{{NS_W}}}t")
    t.text = text
    return p


def add_heading(parent, text):
    p = SubElement(parent, f"{{{NS_W}}}p")
    r = SubElement(p, f"{{{NS_W}}}r")
    rpr = SubElement(r, f"{{{NS_W}}}rPr")
    SubElement(rpr, f"{{{NS_W}}}b")
    t = SubElement(r, f"{{{NS_W}}}t")
    t.text = text
    return p


def build_docx(paragraphs, out_path):
    doc = Element(f"{{{NS_W}}}document")
    body = SubElement(doc, f"{{{NS_W}}}body")
    for text, kind in paragraphs:
        if kind == "h":
            add_heading(body, text)
        else:
            add_paragraph(body, text)
    sect = SubElement(body, f"{{{NS_W}}}sectPr")
    SubElement(sect, f"{{{NS_W}}}pgSz", {f"{{{NS_W}}}w": "11906", f"{{{NS_W}}}h": "16838"})
    SubElement(sect, f"{{{NS_W}}}pgMar", {f"{{{NS_W}}}top": "1440", f"{{{NS_W}}}right": "1440", f"{{{NS_W}}}bottom": "1440", f"{{{NS_W}}}left": "1440", f"{{{NS_W}}}header": "720", f"{{{NS_W}}}footer": "720", f"{{{NS_W}}}gutter": "0"})

    doc_xml = tostring(doc, encoding="utf-8", xml_declaration=True)

    content_types = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Types xmlns=\"http://schemas.openxmlformats.org/package/2006/content-types\">
  <Default Extension=\"rels\" ContentType=\"application/vnd.openxmlformats-package.relationships+xml\"/>
  <Default Extension=\"xml\" ContentType=\"application/xml\"/>
  <Override PartName=\"/word/document.xml\" ContentType=\"application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml\"/>
</Types>
"""

    rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\">
  <Relationship Id=\"rId1\" Type=\"http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument\" Target=\"word/document.xml\"/>
</Relationships>
"""

    doc_rels = """<?xml version=\"1.0\" encoding=\"UTF-8\"?>
<Relationships xmlns=\"http://schemas.openxmlformats.org/package/2006/relationships\"/>
"""

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with zipfile.ZipFile(out_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("[Content_Types].xml", content_types)
        zf.writestr("_rels/.rels", rels)
        zf.writestr("word/document.xml", doc_xml)
        zf.writestr("word/_rels/document.xml.rels", doc_rels)


def html_to_text(html_text):
    text = html_text
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.I)
    text = re.sub(r"</p>", "\n", text, flags=re.I)
    text = re.sub(r"</label>", "\n", text, flags=re.I)
    text = re.sub(r"</li>", "\n", text, flags=re.I)
    text = re.sub(r"<[^>]+>", "", text)
    text = html.unescape(text)
    lines = [l.strip() for l in text.splitlines()]
    lines = [l for l in lines if l]
    return lines


def extract_exam(md_text):
    title = "Exam"
    m = re.search(r"^##\s+(.+)$", md_text, flags=re.M)
    if m:
        title = m.group(1).strip()
    form_m = re.search(r"<form[^>]*>([\s\S]*?)</form>", md_text)
    answers_m = re.search(r"<details[^>]*>\s*<summary>[^<]*</summary>\s*<ol>([\s\S]*?)</ol>", md_text)
    form_html = form_m.group(1) if form_m else ""
    answers_html = answers_m.group(1) if answers_m else ""

    instr_m = re.search(r"<p><strong>Instructions:</strong>([\s\S]*?)</p>", form_html)
    instructions = html_to_text(instr_m.group(1)) if instr_m else []

    q_html = ""
    ol_m = re.search(r"<ol>([\s\S]*?)</ol>", form_html)
    if ol_m:
        q_html = ol_m.group(1)
    q_items = re.findall(r"<li>([\s\S]*?)</li>", q_html)
    questions = []
    for i, item in enumerate(q_items, 1):
        lines = html_to_text(item)
        if not lines:
            continue
        questions.append((i, lines))

    ans_items = re.findall(r"<li>([\s\S]*?)</li>", answers_html)
    answers = []
    for i, item in enumerate(ans_items, 1):
        lines = html_to_text(item)
        if lines:
            answers.append((i, " ".join(lines)))

    return title, instructions, questions, answers


def build_paragraphs(title, instructions, questions, answers):
    paras = []
    paras.append((title, "h"))
    if instructions:
        paras.append(("Instructions: " + " ".join(instructions), "p"))
    for num, lines in questions:
        q_text = lines[0]
        paras.append((f"{num}. {q_text}", "p"))
        for opt in lines[1:]:
            paras.append((f"   - {opt}", "p"))
    if answers:
        paras.append(("Answer Key", "h"))
        for num, ans in answers:
            paras.append((f"{num}. {ans}", "p"))
    return paras


def process_grade(grade):
    src_dir = os.path.join(EXAMS_SRC, f"grade{grade}")
    out_dir = os.path.join(OUT_ROOT, f"grade{grade}")
    for name in sorted(os.listdir(src_dir)):
        if not name.endswith(".md"):
            continue
        path = os.path.join(src_dir, name)
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
        title, instructions, questions, answers = extract_exam(text)
        week = re.findall(r"week(\d{2})", name)
        week = week[0] if week else "00"
        out_name = f"grade{grade}-week{week}-exam.docx"
        out_path = os.path.join(out_dir, out_name)
        paras = build_paragraphs(title, instructions, questions, answers)
        build_docx(paras, out_path)


def main():
    for grade in (5, 10):
        process_grade(grade)


if __name__ == "__main__":
    main()

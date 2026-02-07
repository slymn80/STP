# Generates lessons and images from Excel annual plan.

import os
import re
import csv
import shutil
import base64
import io
from dataclasses import dataclass
from pathlib import Path

import pandas as pd
from PIL import Image, ImageDraw, ImageFont
from openai import OpenAI

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CONTENT_DIR = PROJECT_ROOT / "content"
SITE_DIR = PROJECT_ROOT / "site"
BRIEFS = {}

EXCEL_DEFAULT = r"C:\Users\Suleyman\Desktop\files\2025-2026 dersler\2025_2026_informatics_annual_plan_suleyman_tongut.xlsx"

SCHOOL = "Talgar Private Boarding School No. 1"
SUBJECT = "Informatics"
TEACHER = "S\u00fcleyman Tongut"
LANGUAGE = "English"
DURATION = "40 minutes"

USE_OPENAI_IMAGES = os.environ.get("USE_OPENAI_IMAGES", "0") == "1"
OPENAI_IMAGE_MODEL = os.environ.get("OPENAI_IMAGE_MODEL", "gpt-image-1-mini")
OPENAI_IMAGE_QUALITY = os.environ.get("OPENAI_IMAGE_QUALITY", "low")
OPENAI_IMAGE_SIZE = os.environ.get("OPENAI_IMAGE_SIZE", "1024x1024")
SKIP_IMAGES = os.environ.get("STP_SKIP_IMAGES", "0") == "1"

OPENAI_PROMPT_TEMPLATE = os.environ.get(
    "OPENAI_PROMPT_TEMPLATE",
    "Textbook-style educational illustration, clean lines, minimal colors, white background. "
    "No photorealism, no people, no decorative art. "
    "Topic: {topic}. Visual type: {visual}. Brief: {brief}. "
    "No text, no labels, no letters, no numbers. Use shapes and icons only.",
)


@dataclass
class Lesson:
    grade: int
    week: int
    topic: str
    explanation: str


def find_header_row(df):
    for r in range(min(30, len(df))):
        row = df.iloc[r].astype(str).str.upper().tolist()
        if any("WEEK" in c for c in row):
            return r
    raise ValueError("Could not find header row with WEEK column.")


def load_lessons_from_sheet(excel_path: str, sheet_index: int, grade: int):
    raw = pd.read_excel(excel_path, sheet_name=sheet_index, header=None)
    header_row = find_header_row(raw)
    header = raw.iloc[header_row].tolist()
    data = raw.iloc[header_row + 1 :].copy()
    data.columns = header
    data = data.dropna(how="all")

    # Normalize column names
    cols = {str(c).strip().upper(): c for c in data.columns}
    if "SUBJECT" not in cols:
        raise ValueError("SUBJECT column not found in sheet.")
    if "LESSONS" not in cols:
        raise ValueError("LESSONS column not found in sheet.")
    if "EXPLANATION" not in cols:
        raise ValueError("EXPLANATION column not found in sheet.")

    subject_col = cols["SUBJECT"]
    lesson_col = cols["LESSONS"]
    explanation_col = cols["EXPLANATION"]

    lessons = []
    for _, row in data.iterrows():
        topic = row.get(subject_col)
        explanation = row.get(explanation_col)
        week_val = row.get(lesson_col)
        if pd.isna(topic) or str(topic).strip() == "":
            continue
        if pd.isna(week_val):
            continue
        try:
            week = int(str(week_val).strip())
        except ValueError:
            # fallback to sequential order
            week = None
        exp_text = "" if pd.isna(explanation) else str(explanation).strip()
        lessons.append((week, str(topic).strip(), exp_text))

    # Ensure ordering and week numbers 1..34
    lessons_sorted = []
    for idx, (week, topic, explanation) in enumerate(lessons, start=1):
        week_num = week if week is not None else idx
        lessons_sorted.append(Lesson(grade=grade, week=week_num, topic=topic, explanation=explanation))

    lessons_sorted = sorted(lessons_sorted, key=lambda x: x.week)
    return lessons_sorted


def slug_terms(text, max_terms=6):
    words = re.split(r"[^A-Za-z0-9]+", text)
    stop = {
        "the", "and", "of", "to", "in", "for", "on", "with", "a", "an",
        "is", "are", "its", "their", "by", "from", "as", "or", "at",
        "information", "computer", "data", "lesson", "unit", "topic"
    }
    out = []
    for w in words:
        w = w.strip()
        if not w:
            continue
        if w.lower() in stop:
            continue
        out.append(w)
    if not out:
        out = ["Concept", "Process", "Example"]
    return out[:max_terms]




def clean_topic(raw_topic: str) -> str:
    text = raw_topic.strip()
    text = re.sub(r"^\d+\s*[\.\)]\s*", "", text)
    text = re.sub(r"\s{2,}", " ", text)
    return text


def extract_points(text: str, max_points=5):
    if not text:
        return []
    parts = re.split(r"[;,.]\s+|\n+", text)
    points = []
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if len(p) < 3:
            continue
        points.append(p[0].upper() + p[1:])
    return points[:max_points]


def load_briefs(briefs_path: Path):
    briefs = {}
    if not briefs_path.exists():
        return briefs
    with open(briefs_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                grade = int(row.get("grade", ""))
                week = int(row.get("week", ""))
            except ValueError:
                continue
            brief = (row.get("brief") or "").strip()
            if brief:
                briefs[(grade, week)] = brief
    return briefs


def write_default_briefs(lessons, briefs_path: Path):
    if briefs_path.exists():
        return
    briefs_path.parent.mkdir(parents=True, exist_ok=True)
    with open(briefs_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["grade", "week", "brief"])
        writer.writeheader()
        for lesson in lessons:
            visual = choose_visual(lesson.topic, lesson.grade)
            brief = generate_brief(lesson.topic, visual)
            writer.writerow({"grade": lesson.grade, "week": lesson.week, "brief": brief})


def generate_brief(topic: str, visual: str) -> str:
    if visual == "Network Diagram":
        return "Show a router connecting a switch, a server, and two student PCs using distinct cables."
    if visual == "Data Encoding Table":
        return "Illustrate binary groupings using blocks or dots in a grid."
    if visual == "Security Triangle":
        return "Show a triangle with three icons representing protection, accuracy, and access."
    if visual == "Flowchart":
        return "Use start, decision, and action blocks with arrows."
    if visual == "Raster vs Vector":
        return "Compare a pixel grid to a smooth curve shape."
    if visual == "System Components":
        return "Display CPU, RAM, storage, and I/O connected by a bus line."
    if visual == "Relational Table":
        return "Show a table-like grid with one row highlighted."
    if visual == "Communication Model":
        return "Show sender, channel, receiver with arrows and a noise symbol."
    return f"Highlight 3 key ideas of {topic} using three boxes with icons and arrows."


def choose_visual(topic: str, grade: int) -> str:
    t = topic.lower()
    rules = [
        (["network", "dns", "ip", "address", "router", "switch", "cable"], "Network Diagram"),
        (["binary", "encoding", "representation", "code", "ascii", "unicode", "number systems", "truth table", "logic"], "Data Encoding Table"),
        (["security", "cia", "confidentiality", "integrity", "availability", "authentication", "password"], "Security Triangle"),
        (["program", "python", "string", "loop", "condition", "algorithm"], "Flowchart"),
        (["graphics", "raster", "vector", "pixel", "image"], "Raster vs Vector"),
        (["hardware", "computer", "component", "processor", "memory"], "System Components"),
        (["database", "sql", "table", "query"], "Relational Table"),
        (["communication", "transmission", "channel", "signal"], "Communication Model"),
    ]
    for keys, label in rules:
        if any(k in t for k in keys):
            return label
    return "Concept Map" if grade <= 5 else "Concept Diagram"


def build_learning_objectives(topic, explanation, grade):
    exp_points = extract_points(explanation, max_points=3)
    base = [
        f"Explain {topic} in clear, age-appropriate language.",
        f"Identify the key parts or steps of {topic}.",
        f"Apply {topic} to a real-life or classroom example.",
    ]
    for p in exp_points:
        base.append(f"Demonstrate: {p}.")
    if grade >= 10:
        base.append(f"Analyze how {topic} affects system design or problem solving.")
    else:
        base.append(f"Use {topic} vocabulary accurately in short explanations.")
    return base[:5]


def build_assessment_criteria(topic, explanation):
    return [
        f"Uses correct terminology when explaining {topic}.",
        "Completes the practice activity accurately.",
        "Responds to oral questions with clear reasoning.",
        f"Shows understanding of: {explanation[:60]}." if explanation else "Shows understanding of the main concept.",
    ]


def build_vocab(topic, explanation, grade):
    terms = slug_terms(topic + " " + explanation, max_terms=6)
    generic = [
        ("input", "data entered into a system"),
        ("output", "results produced by a system"),
        ("process", "steps that transform input to output"),
        ("system", "connected parts working together"),
        ("accuracy", "being correct or free of errors"),
        ("diagram", "a visual representation of ideas"),
    ]
    topic_terms = [(t.lower(), f"a key term related to {topic}") for t in terms]
    vocab = topic_terms + generic
    if grade >= 10:
        vocab.append(("protocol", "a set of rules for communication"))
        vocab.append(("algorithm", "a step-by-step solution"))
    return vocab[:10]


def build_intro(topic, explanation):
    return [
        f"Introduce {topic} and link it to everyday technology.",
        "Warm-up questions:",
        "- Where do we encounter this idea in daily life?",
        "- How does this help computers work correctly?",
        "Real-life examples:",
        f"- A classroom example connected to {topic}.",
        f"- Link to: {explanation}." if explanation else "- Link to a familiar classroom technology.",
        "Teacher: Briefly model the key idea using a quick sketch or object.",
        "Students: Share one example they know and explain why it fits.",
    ]


def build_main_content(topic, explanation, grade):
    exp_points = extract_points(explanation, max_points=4)
    points = [
        f"Define {topic} in clear terms.",
        "Break down the key components or steps.",
        "Show a short, concrete example.",
        "Connect to prior knowledge from earlier lessons.",
    ]
    for p in exp_points:
        points.append(f"Focus point: {p}.")
    if grade >= 10:
        points.append("Discuss a practical application or case study.")
    points.append("Teacher: Model the process step-by-step and check for understanding.")
    points.append("Students: Take brief notes and answer a quick concept check.")
    return points


def build_practice_activity(topic, explanation, grade):
    exp_points = extract_points(explanation, max_points=2)
    if grade >= 10:
        items = [
            f"Short response: Describe a scenario where {topic} is important.",
            "Matching: Pair terms with their definitions.",
            "Teacher: Circulate, prompt with guiding questions, and correct misconceptions.",
            "Students: Work in pairs and compare answers.",
        ]
        for p in exp_points:
            items.append(f"Apply: {p}.")
        return items
    items = [
        f"Classification: Sort examples into 'related to {topic}' and 'not related'.",
        "Short response: Write two sentences using key vocabulary.",
        "Teacher: Provide concrete examples and model one classification.",
        "Students: Share answers with a partner.",
    ]
    for p in exp_points:
        items.append(f"Practice: {p}.")
    return items


def build_assessment(topic, grade):
    rubric = ["3 = accurate and complete", "2 = mostly correct", "1 = needs support"]
    return [
        "Observation during activity.",
        f"Oral Q&A: Students explain one part of {topic}.",
        "Quick written check: 3 short questions.",
        "Mini rubric: " + ", ".join(rubric),
    ]


def build_homework(topic):
    return [
        f"Write a short paragraph about {topic} using at least 4 vocabulary terms.",
    ]


def build_reflection(topic):
    return [
        f"Which part of {topic} was easiest for students to understand?",
        "Which activity best supported learning objectives?",
        "What should be adjusted for next time?",
    ]


def format_yaml_frontmatter(lesson: Lesson):
    return (
        "---\n"
        f"school: {SCHOOL}\n"
        f"subject: {SUBJECT}\n"
        f"teacher: {TEACHER}\n"
        f"grade: {lesson.grade}\n"
        f"week: {lesson.week}\n"
        f"topic: \"{lesson.topic}\"\n"
        f"duration: \"{DURATION}\"\n"
        "---\n"
    )


def write_markdown(lesson: Lesson):
    grade_dir = CONTENT_DIR / f"grade{lesson.grade}"
    grade_dir.mkdir(parents=True, exist_ok=True)
    filename = grade_dir / f"week{lesson.week:02d}.md"

    image_path = f"content/images/grade{lesson.grade}/week{lesson.week:02d}.png"

    lines = []
    lines.append(format_yaml_frontmatter(lesson))
    lines.append(f"# Grade {lesson.grade} - Week {lesson.week}: {lesson.topic}\n")
    lines.append("## Learning Objectives\n")
    for obj in build_learning_objectives(lesson.topic, lesson.explanation, lesson.grade):
        lines.append(f"- {obj}\n")
    lines.append("\n## Assessment Criteria\n")
    for c in build_assessment_criteria(lesson.topic, lesson.explanation):
        lines.append(f"- {c}\n")
    lines.append("\n## Key Vocabulary\n")
    for term, desc in build_vocab(lesson.topic, lesson.explanation, lesson.grade):
        lines.append(f"- {term}: {desc}\n")
    lines.append("\n## Lesson Timeline\n")
    lines.append("- Introduction - 5 minutes\n")
    lines.append("- Main Activity - 25 minutes\n")
    lines.append("- Wrap-up - 10 minutes\n")
    lines.append("\n## Introduction (5 minutes)\n")
    for item in build_intro(lesson.topic, lesson.explanation):
        lines.append(f"- {item}\n")
    lines.append("\n## Main Content (25 minutes)\n")
    for p in build_main_content(lesson.topic, lesson.explanation, lesson.grade):
        lines.append(f"- {p}\n")
    lines.append("\n")
    lines.append(f"![Lesson Visual]({image_path})\n")
    lines.append("\n## Practice Activity\n")
    for p in build_practice_activity(lesson.topic, lesson.explanation, lesson.grade):
        lines.append(f"- {p}\n")
    lines.append("\n## Assessment\n")
    for p in build_assessment(lesson.topic, lesson.grade):
        lines.append(f"- {p}\n")
    lines.append("\n## Homework\n")
    for p in build_homework(lesson.topic):
        lines.append(f"- {p}\n")
    lines.append("\n## Teacher Reflection\n")
    for p in build_reflection(lesson.topic):
        lines.append(f"- {p}\n")

    content = "".join(lines)
    with open(filename, "w", encoding="utf-8") as f:
        f.write(content)


def wrap_text(draw, text, font, max_width):
    words = text.split()
    lines = []
    current = []
    for w in words:
        current.append(w)
        w_line = " ".join(current)
        if draw.textlength(w_line, font=font) > max_width:
            current.pop()
            if current:
                lines.append(" ".join(current))
            current = [w]
    if current:
        lines.append(" ".join(current))
    return lines




def draw_network(draw, origin, accent, font):
    x, y = origin
    router = (x + 80, y + 40)
    switch = (x + 220, y + 40)
    server = (x + 360, y + 20)
    pc1 = (x + 360, y + 90)
    pc2 = (x + 220, y + 130)
    for a, b in [(router, switch), (switch, server), (switch, pc1), (switch, pc2)]:
        draw.line([a, b], fill=accent, width=2)
    nodes = [
        (router, "Router"),
        (switch, "Switch"),
        (server, "Server"),
        (pc1, "PC"),
        (pc2, "PC"),
    ]
    for (nx, ny), label in nodes:
        draw.ellipse([nx-20, ny-20, nx+20, ny+20], outline=accent, width=3, fill=(255,255,255))
        draw.text((nx-18, ny+24), label, fill=accent, font=font)


def draw_encoding(draw, origin, accent, font):
    x, y = origin
    cell_w, cell_h = 28, 24
    for r in range(4):
        for c in range(8):
            x0 = x + c * cell_w
            y0 = y + r * cell_h
            draw.rectangle([x0, y0, x0 + cell_w, y0 + cell_h], outline=accent, width=2)
            val = (c + r) % 2
            draw.text((x0 + 9, y0 + 4), str(val), fill=accent, font=font)
    draw.text((x, y - 18), "Bits", fill=accent, font=font)
    draw.text((x, y + 4*cell_h + 10), "8-bit pattern -> value", fill=accent, font=font)


def draw_security_triangle(draw, origin, accent, font):
    x, y = origin
    pts = [(x+160, y+20), (x+40, y+180), (x+280, y+180)]
    draw.polygon(pts, outline=accent, fill=(255,255,255))
    draw.text((x+130, y+30), "C", fill=accent, font=font)
    draw.text((x+62, y+150), "I", fill=accent, font=font)
    draw.text((x+230, y+150), "A", fill=accent, font=font)
    draw.text((x+110, y+75), "Confidentiality", fill=accent, font=font)
    draw.text((x+60, y+170), "Integrity", fill=accent, font=font)
    draw.text((x+200, y+170), "Availability", fill=accent, font=font)
    draw.text((x+110, y+200), "CIA Triangle", fill=accent, font=font)


def draw_flowchart(draw, origin, accent, font):
    x, y = origin
    draw.rectangle([x+20, y+10, x+180, y+50], outline=accent, width=3, fill=(255,255,255))
    draw.text((x+60, y+22), "Start", fill=accent, font=font)
    draw.polygon([(x+100, y+70), (x+170, y+110), (x+100, y+150), (x+30, y+110)], outline=accent, fill=(255,255,255))
    draw.text((x+75, y+105), "Check?", fill=accent, font=font)
    draw.rectangle([x+20, y+170, x+180, y+210], outline=accent, width=3, fill=(255,255,255))
    draw.text((x+55, y+182), "Action", fill=accent, font=font)
    draw.line([(x+100, y+50), (x+100, y+70)], fill=accent, width=2)
    draw.line([(x+100, y+150), (x+100, y+170)], fill=accent, width=2)
    draw.text((x+15, y+120), "No", fill=accent, font=font)
    draw.text((x+155, y+120), "Yes", fill=accent, font=font)


def draw_raster_vector(draw, origin, accent, font):
    x, y = origin
    for r in range(5):
        for c in range(5):
            x0 = x + c * 20
            y0 = y + r * 20
            fill = (200, 220, 230) if (r + c) % 2 == 0 else (255, 255, 255)
            draw.rectangle([x0, y0, x0+20, y0+20], outline=accent, fill=fill)
    draw.text((x, y+110), "Raster", fill=accent, font=font)
    vx = x + 160
    draw.line([(vx, y+10), (vx+120, y+60), (vx+30, y+120), (vx, y+10)], fill=accent, width=3)
    draw.ellipse([vx+60, y+40, vx+100, y+80], outline=accent, width=3)
    draw.text((vx, y+110), "Vector", fill=accent, font=font)


def draw_components(draw, origin, accent, font):
    x, y = origin
    boxes = ["CPU", "RAM", "Storage", "I/O"]
    for i, label in enumerate(boxes):
        x0 = x + (i % 2) * 160
        y0 = y + (i // 2) * 80
        draw.rectangle([x0, y0, x0+140, y0+60], outline=accent, width=3, fill=(255,255,255))
        draw.text((x0+45, y0+22), label, fill=accent, font=font)
    draw.line([(x+70, y+60), (x+230, y+60)], fill=accent, width=2)
    draw.line([(x+70, y+140), (x+230, y+140)], fill=accent, width=2)
    draw.text((x+95, y+145), "System Bus", fill=accent, font=font)


def draw_relational_table(draw, origin, accent, font):
    x, y = origin
    cols = ["id", "name", "score"]
    col_w = 90
    row_h = 26
    for c, col in enumerate(cols):
        x0 = x + c*col_w
        draw.rectangle([x0, y, x0+col_w, y+row_h], outline=accent, width=2)
        draw.text((x0+8, y+5), col, fill=accent, font=font)
    for r in range(1, 5):
        for c in range(len(cols)):
            x0 = x + c*col_w
            y0 = y + r*row_h
            draw.rectangle([x0, y0, x0+col_w, y0+row_h], outline=accent, width=2)
    draw.text((x, y+5*row_h+8), "Relational Table", fill=accent, font=font)


def draw_communication(draw, origin, accent, font):
    x, y = origin
    draw.rectangle([x, y, x+120, y+50], outline=accent, width=3, fill=(255,255,255))
    draw.text((x+20, y+16), "Sender", fill=accent, font=font)
    draw.rectangle([x+240, y, x+360, y+50], outline=accent, width=3, fill=(255,255,255))
    draw.text((x+255, y+16), "Receiver", fill=accent, font=font)
    draw.line([(x+120, y+25), (x+240, y+25)], fill=accent, width=3)
    draw.text((x+150, y+5), "Channel", fill=accent, font=font)
    draw.text((x+165, y+35), "~noise~", fill=accent, font=font)


def generate_image(lesson: Lesson):
    img_dir = CONTENT_DIR / "images" / f"grade{lesson.grade}"
    img_dir.mkdir(parents=True, exist_ok=True)
    out_path = img_dir / f"week{lesson.week:02d}.png"

    width, height = 900, 500
    bg = (247, 248, 250)
    accent = (44, 140, 110) if lesson.grade == 5 else (52, 96, 169)

    font_title = ImageFont.load_default()
    font_body = ImageFont.load_default()

    title = f"Grade {lesson.grade} Week {lesson.week}"
    subtitle = lesson.topic
    visual = choose_visual(lesson.topic, lesson.grade)
    brief = BRIEFS.get((lesson.grade, lesson.week))
    if not brief:
        brief = generate_brief(lesson.topic, visual)

    if USE_OPENAI_IMAGES:
        prompt = OPENAI_PROMPT_TEMPLATE.format(topic=lesson.topic, visual=visual, brief=brief)
        client = OpenAI()
        result = client.images.generate(
            model=OPENAI_IMAGE_MODEL,
            prompt=prompt,
            size=OPENAI_IMAGE_SIZE,
            quality=OPENAI_IMAGE_QUALITY,
        )
        b64 = result.data[0].b64_json
        img_data = base64.b64decode(b64)
        img = Image.open(io.BytesIO(img_data)).convert("RGB")
        img = img.resize((width, height), Image.LANCZOS)
        img.save(out_path)
        return

    img = Image.new("RGB", (width, height), bg)
    draw = ImageDraw.Draw(img)

    draw.rectangle([0, 0, width, 60], fill=accent)
    draw.text((20, 18), title, fill="white", font=font_title)

    subtitle_lines = wrap_text(draw, subtitle, font_body, max_width=width - 40)
    y = 75
    for line in subtitle_lines[:2]:
        draw.text((20, y), line, fill="black", font=font_body)
        y += 18
    brief_lines = wrap_text(draw, f"Brief: {brief}", font_body, max_width=width - 40)
    for line in brief_lines[:2]:
        draw.text((20, y), line, fill=(40, 60, 80), font=font_body)
        y += 16

    origin = (60, 150)
    if visual == "Network Diagram":
        draw_network(draw, origin, accent, font_body)
    elif visual == "Data Encoding Table":
        draw_encoding(draw, origin, accent, font_body)
    elif visual == "Security Triangle":
        draw_security_triangle(draw, origin, accent, font_body)
    elif visual == "Flowchart":
        draw_flowchart(draw, origin, accent, font_body)
    elif visual == "Raster vs Vector":
        draw_raster_vector(draw, origin, accent, font_body)
    elif visual == "System Components":
        draw_components(draw, origin, accent, font_body)
    elif visual == "Relational Table":
        draw_relational_table(draw, origin, accent, font_body)
    elif visual == "Communication Model":
        draw_communication(draw, origin, accent, font_body)
    else:
        terms = slug_terms(lesson.topic, max_terms=3)
        box = (230, 235, 242)
        box_w, box_h = 220, 90
        start_x, start_y, gap = 60, 170, 20
        for i, term in enumerate(terms):
            x0 = start_x + i * (box_w + gap)
            y0 = start_y
            draw.rectangle([x0, y0, x0 + box_w, y0 + box_h], fill=box, outline=accent, width=2)
            draw.text((x0 + 10, y0 + 8), f"{visual}", fill=accent, font=font_body)
            wrapped = wrap_text(draw, term, font_body, max_width=box_w - 20)
            ty = y0 + 30
            for line in wrapped[:3]:
                draw.text((x0 + 10, ty), line, fill="black", font=font_body)
                ty += 16

    footer = f"Schematic Visual: {visual}"
    draw.text((20, height - 30), footer, fill=(80, 80, 80), font=font_body)

    img.save(out_path)

def copy_content_to_site():
    dest = SITE_DIR / "content"
    if dest.exists():
        shutil.rmtree(dest)
    shutil.copytree(CONTENT_DIR, dest)


def main():
    global BRIEFS
    excel_path = os.environ.get("STP_EXCEL_PATH", EXCEL_DEFAULT)
    if not os.path.exists(excel_path):
        raise FileNotFoundError(f"Excel file not found: {excel_path}")
    if USE_OPENAI_IMAGES and not os.environ.get("OPENAI_API_KEY"):
        raise ValueError("USE_OPENAI_IMAGES=1 requires OPENAI_API_KEY to be set.")

    lessons_g10 = load_lessons_from_sheet(excel_path, sheet_index=0, grade=10)
    lessons_g5 = load_lessons_from_sheet(excel_path, sheet_index=1, grade=5)

    # Ensure 34 lessons each
    lessons_g10 = [Lesson(grade=l.grade, week=l.week, topic=clean_topic(l.topic), explanation=l.explanation) for l in lessons_g10 if 1 <= l.week <= 34]
    lessons_g5 = [Lesson(grade=l.grade, week=l.week, topic=clean_topic(l.topic), explanation=l.explanation) for l in lessons_g5 if 1 <= l.week <= 34]

    if len(lessons_g10) != 34:
        raise ValueError(f"Expected 34 lessons for Grade 10, found {len(lessons_g10)}")
    if len(lessons_g5) != 34:
        raise ValueError(f"Expected 34 lessons for Grade 5, found {len(lessons_g5)}")

    briefs_path = PROJECT_ROOT / "scripts" / "visual_briefs.csv"
    write_default_briefs(lessons_g5 + lessons_g10, briefs_path)
    BRIEFS = load_briefs(briefs_path)

    grade_filter = os.environ.get("STP_GRADE_FILTER")
    week_filter = os.environ.get("STP_WEEK_FILTER")
    grades = None
    weeks = None
    if grade_filter:
        grades = {int(x.strip()) for x in grade_filter.split(",") if x.strip().isdigit()}
    if week_filter:
        weeks = {int(x.strip()) for x in week_filter.split(",") if x.strip().isdigit()}

    lessons_all = lessons_g5 + lessons_g10
    if grades:
        lessons_all = [l for l in lessons_all if l.grade in grades]
    if weeks:
        lessons_all = [l for l in lessons_all if l.week in weeks]

    for lesson in lessons_all:
        write_markdown(lesson)
        if not SKIP_IMAGES:
            generate_image(lesson)

    copy_content_to_site()


if __name__ == "__main__":
    main()

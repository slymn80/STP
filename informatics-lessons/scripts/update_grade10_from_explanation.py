import os
import re
import pandas as pd
from pathlib import Path

ROOT = Path(r"C:\Users\Suleyman\PycharmProjects\STP")
EXCEL = ROOT / "2025_2026_informatics_annual_plan_suleyman_tongut.xlsx"

raw = pd.read_excel(EXCEL, sheet_name="10", header=2)
raw.columns = list(raw.iloc[0])
raw = raw.iloc[1:].reset_index(drop=True)
raw = raw[raw["LESSONS"].notna()].copy()
raw["LESSONS"] = raw["LESSONS"].astype(int)
explanations = dict(zip(raw["LESSONS"], raw["EXPLANATION"].astype(str)))

SECTION_ORDER = [
    "Learning Objectives",
    "Assessment Criteria",
    "Key Vocabulary",
    "Introduction (5 minutes)",
    "Main Content (30 minutes)",
    "Practice Activity",
    "Wrap-up (10 minutes)",
    "Assessment",
    "Homework",
    "Teacher Reflection",
]

GRADE10_TEMPLATES = {
    "Learning Objectives": [
        "Explain the core concepts of {topic} using correct terminology.",
        "Identify key components, roles, or stages related to {topic}.",
        "Analyze a real-world example where {topic} is applied.",
        "Compare two representations or approaches within {topic}.",
        "Apply {topic} concepts to a short practical task or scenario.",
    ],
    "Assessment Criteria": [
        "Uses technical vocabulary accurately in explanations.",
        "Identifies correct components or stages of {topic}.",
        "Provides a valid real-world example and justification.",
        "Completes the practice task with clear reasoning.",
    ],
    "Key Vocabulary": [
        "concepts: key ideas and definitions",
        "components: parts that make up a system",
        "process: steps that lead to a result",
        "input: data or signals provided to a system",
        "output: results produced by a system",
        "performance: speed, reliability, or efficiency",
        "security: protection of data and systems",
        "evaluation: checking correctness and quality",
    ],
    "Introduction (5 minutes)": [
        "Starter: Present a short real-world case related to {topic} (news, product, or school system).",
        "Ask guiding questions to activate prior knowledge.",
        "Teacher: Define {topic} and outline the lesson goals.",
        "Students: Share what they already know or have used.",
    ],
    "Main Content (30 minutes)": [
        "Explain the main concepts and components of {topic} with a clear diagram.",
        "Show a real-world example and map it to the concepts.",
        "Discuss advantages, limitations, or common issues.",
        "Teacher: Model a simple analysis or walkthrough.",
        "Students: Take notes and answer quick concept checks.",
    ],
    "Practice Activity": [
        "Case task: Students analyze a short scenario and identify how {topic} is used.",
        "Small group: Build a mini summary (3-4 bullet points) of key ideas.",
        "Teacher: Provide feedback and clarify misconceptions.",
    ],
    "Wrap-up (10 minutes)": [
        "Students summarize the key idea in one sentence.",
        "Exit ticket: Give one example or application of {topic}.",
        "Teacher: Highlight common mistakes and preview the next topic.",
    ],
    "Assessment": [
        "Observation during discussion and practice.",
        "Short written check: 3-5 questions on key concepts.",
        "Oral Q&A on real-world application.",
    ],
    "Homework": [
        "Find a real-world case where {topic} is used and write a 150-200 word summary.",
        "Create a one-page study sheet with definitions, components, and one diagram of {topic}.",
    ],
    "Teacher Reflection": [
        "Which concept was most challenging for students?",
        "Which example worked best to explain {topic}?",
        "What should be improved for the next lesson?",
    ],
}


def parse_frontmatter(text):
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}, text, None
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end == -1:
        return {}, text, None
    meta_lines = lines[1:end]
    meta = {}
    for line in meta_lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    body = "\n".join(lines[end + 1 :])
    return meta, body, (lines[:end+1], lines[end+1:])


def replace_frontmatter_topic(lines, topic):
    out = []
    for line in lines:
        if line.strip().startswith("topic:"):
            out.append(f'topic: "{topic}"')
        else:
            out.append(line)
    return out


def replace_h1(body, week, topic):
    return re.sub(r"^#\s+Grade 10\s+-\s+Week\s+\d+.*$", f"# Grade 10 - Week {week}: {topic}", body, flags=re.M)


def replace_section(body, title, lines):
    pattern = r"(## " + re.escape(title) + r"\n)([\s\S]*?)(?=\n## |\Z)"
    if not re.search(pattern, body):
        return body
    content = "\n".join(["- " + l for l in lines]) + "\n"
    return re.sub(pattern, r"\1" + content, body)


def apply_templates(body, topic):
    t = (topic or "the topic").strip().rstrip(".")
    for title in SECTION_ORDER:
        lines = [l.format(topic=t) for l in GRADE10_TEMPLATES.get(title, [])]
        body = replace_section(body, title, lines)
    return body


def update_file(path: Path, week: int, topic: str):
    text = path.read_text(encoding="utf-8")
    meta, body, split = parse_frontmatter(text)
    if split is None:
        return
    fm_lines, body_lines = split
    fm_lines = replace_frontmatter_topic(fm_lines, topic)
    body_text = "\n".join(body_lines)
    body_text = replace_h1(body_text, week, topic)
    body_text = apply_templates(body_text, topic)
    new_text = "\n".join(fm_lines) + "\n" + body_text
    path.write_text(new_text, encoding="utf-8")


for base in [ROOT / "informatics-lessons" / "content", ROOT / "informatics-lessons" / "site" / "content"]:
    grade_dir = base / "grade10"
    for week in range(1, 35):
        topic = explanations.get(week)
        if not topic:
            continue
        path = grade_dir / f"week{week:02}.md"
        if path.exists():
            update_file(path, week, topic)

import os
import re
import shutil
from pathlib import Path
import pandas as pd

# Use OpenAI from generate_lessons to keep prompt style consistent
import generate_lessons as gl

ROOT = Path(r"C:\Users\Suleyman\PycharmProjects\STP\informatics-lessons")
CONTENT_DIR = ROOT / "content"
SITE_DIR = ROOT / "site"
EXCEL = Path(r"C:\Users\Suleyman\PycharmProjects\STP\2025_2026_informatics_annual_plan_suleyman_tongut.xlsx")


def parse_frontmatter(path: Path):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return {}
    end = -1
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end == -1:
        return {}
    meta = {}
    for line in lines[1:end]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        meta[key.strip()] = value.strip().strip('"')
    return meta


def load_explanations():
    raw = pd.read_excel(EXCEL, sheet_name="10", header=2)
    raw.columns = list(raw.iloc[0])
    raw = raw.iloc[1:].reset_index(drop=True)
    raw = raw[raw["LESSONS"].notna()].copy()
    raw["LESSONS"] = raw["LESSONS"].astype(int)
    return dict(zip(raw["LESSONS"], raw["EXPLANATION"].astype(str)))


def main():
    if os.environ.get("USE_OPENAI_IMAGES") != "1":
        raise SystemExit("Set USE_OPENAI_IMAGES=1 to generate images with OpenAI.")
    if not os.environ.get("OPENAI_API_KEY"):
        raise SystemExit("OPENAI_API_KEY is required for OpenAI image generation.")

    explanations = load_explanations()

    briefs_path = ROOT / "scripts" / "visual_briefs.csv"
    gl.BRIEFS = gl.load_briefs(briefs_path)

    lessons = []
    for week in range(1, 35):
        md_path = CONTENT_DIR / "grade10" / f"week{week:02}.md"
        meta = parse_frontmatter(md_path)
        topic = meta.get("topic", "")
        explanation = explanations.get(week, "")
        lessons.append(gl.Lesson(grade=10, week=week, topic=topic, explanation=explanation))

    # Generate images
    for lesson in lessons:
        gl.generate_image(lesson)

    # Copy updated images to site content
    src_dir = CONTENT_DIR / "images" / "grade10"
    dest_dir = SITE_DIR / "content" / "images" / "grade10"
    dest_dir.mkdir(parents=True, exist_ok=True)
    for img in src_dir.glob("week*.png"):
        shutil.copy2(img, dest_dir / img.name)


if __name__ == "__main__":
    main()

# Informatics Lessons

This project generates weekly Informatics lesson plans from the 2025-2026 annual plan Excel file, creates one educational image per week, and builds a static site to browse lessons by grade and week.

## Prerequisites
- Windows
- Python 3.10+

## 1) Create a virtual environment
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

## 2) Install requirements
```powershell
pip install -r requirements.txt
```

## 3) Generate lessons and images
```powershell
python .\scripts\generate_lessons.py
```

The script reads:
`C:\Users\Suleyman\Desktop\files\2025-2026 dersler\2025_2026_informatics_annual_plan_suleyman_tongut.xlsx`

To override the Excel path:
```powershell
$env:STP_EXCEL_PATH="C:\\path\\to\\file.xlsx"
python .\scripts\generate_lessons.py
```

Visual briefs (optional):
- File: `scripts/visual_briefs.csv`
- Columns: `grade, week, brief`
- If missing, it is auto-generated with topic-based briefs. You can edit it and re-run the script for exact matches.

OpenAI image generation (optional, gpt-image-1-mini for lowest cost):
```powershell
$env:OPENAI_API_KEY="your_api_key_here"
$env:USE_OPENAI_IMAGES="1"
$env:OPENAI_IMAGE_MODEL="gpt-image-1-mini"
$env:OPENAI_IMAGE_QUALITY="low"
$env:OPENAI_IMAGE_SIZE="1024x1024"
python .\scripts\generate_lessons.py
```

## 4) Preview the site locally
```powershell
python -m http.server 8000 -d .\site
```
Then open `http://localhost:8000` in your browser.

## 5) Push to GitHub
```powershell
git init
git add .
git commit -m "Initial Informatics lessons"
git branch -M main
git remote add origin <YOUR_GITHUB_REPO_URL>
git push -u origin main
```

## 6) Deploy on Render (Static Site)
- Service type: Static Site
- Build command: none
- Publish directory: `site`

## Project Structure
```
informatics-lessons/
  content/
    grade5/
    grade10/
    images/
  site/
    content/
    index.html
    style.css
    app.js
    vendor/
      marked.min.js
  scripts/
    generate_lessons.py
  requirements.txt
  README.md
  .gitignore
```

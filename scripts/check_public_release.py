"""Conservative public release hygiene check: no dependencies.

Does not replace human review or a proper secret scanner. Checks only this
worktree, not Git history. Run before the first git add / git push.
"""
from __future__ import annotations
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_DIRS = {'local_config','private','documents','reports','uk_job_hunter_reports','.venv'}
FORBIDDEN_NAMES = {'.env','search_profile.json','job_search_tracker.csv','tracker.json','salary_data.json'}
EXCLUDE_PARTS = {'.git','__pycache__','.pytest_cache','node_modules','test-results','playwright-report'}
SENSITIVE_PATTERN = re.compile(r'(?i)(?:ADZUNA_APP_KEY|REED_API_KEY|api[_-]?key)\s*[=:]\s*[\"\']?([a-z0-9_-]{24,})')
issues = []
for path in ROOT.rglob('*'):
    if any(p in EXCLUDE_PARTS for p in path.relative_to(ROOT).parts):
        continue
    rel = path.relative_to(ROOT)
    if path.is_dir():
        if rel.parts[0] in FORBIDDEN_DIRS:
            issues.append(f'Private folder found: {rel}')
        continue
    if rel.parts[0] in FORBIDDEN_DIRS or path.name in FORBIDDEN_NAMES or path.name.startswith('.env.'):
        issues.append(f'Potential private file found: {rel}')
        continue
    if path.suffix.lower() in {'.pdf','.docx','.xlsx','.csv','.db','.sqlite','.sqlite3','.pem','.key','.p12'} or '.sqlite' in path.name:
        issues.append(f'Unexpected user document: {rel}')
        continue
    if path.suffix.lower() in {'.py','.json','.md','.js','.html','.yml','.yaml','.sh'}:
        try:
            data = path.read_text(encoding='utf-8')
        except UnicodeError:
            issues.append(f'Unparseable text file: {rel}')
            continue
        if SENSITIVE_PATTERN.search(data):
            issues.append(f'Potential hardcoded secret: {rel}')
if issues:
    print('Release review FAILED:')
    print('\n'.join('- '+p for p in issues))
    sys.exit(1)
print('Public release hygiene checks passed (local files only; review Git history separately).')

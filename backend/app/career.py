"""Private, explainable resume-to-Excel-job requirement matcher.

The tool evaluates ONLY jobs supplied by the user. It never asserts actual eligibility
or invents live jobs. No resume or job file is persisted or sent to an LLM.
"""
from __future__ import annotations

import base64
import csv
import io
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

MAX_FILE_BYTES = 2_000_000
MAX_XML_BYTES = 12_000_000
MAX_ROWS = 500
MAX_TEXT_CHARS = 100_000

SKILLS = [
    'python', 'java', 'c++', 'c', 'javascript', 'typescript', 'react', 'node.js',
    'fastapi', 'django', 'flask', 'sql', 'mysql', 'postgresql', 'mongodb',
    'excel', 'power bi', 'tableau', 'git', 'docker', 'kubernetes', 'aws',
    'azure', 'linux', 'html', 'css', 'data analysis', 'machine learning',
    'pandas', 'numpy', 'tensorflow', 'pytorch', 'communication',
    'problem solving', 'data structures', 'algorithms', 'spring boot',
    'rest api', 'microsoft office', 'vlookup', 'pivot tables', 'power query',
]
ALIASES = {
    'cpp': 'c++', 'c plus plus': 'c++', 'ms excel': 'excel', 'microsoft excel': 'excel',
    'excel spreadsheets': 'excel', 'powerbi': 'power bi', 'js': 'javascript',
    'react.js': 'react', 'nodejs': 'node.js', 'postgres': 'postgresql',
    'dsa': 'data structures', 'rest apis': 'rest api', 'pivot table': 'pivot tables',
}
HEADERS = {
    'company': ['company', 'company name', 'employer'],
    'job_title': ['job title', 'role', 'position', 'job_title'],
    'required_skills': ['required skills', 'skills', 'required_skills', 'must have skills'],
    'min_cgpa': ['min cgpa', 'minimum cgpa', 'cgpa', 'min_cgpa'],
    'degree': ['degree', 'required degree', 'qualification', 'degrees'],
    'graduation_year_min': ['grad year min', 'graduation year min', 'batch from', 'graduation_year_min'],
    'graduation_year_max': ['grad year max', 'graduation year max', 'batch to', 'graduation_year_max'],
    'experience_years': ['min experience years', 'experience years', 'experience_years'],
    'location': ['location', 'city'],
    'application_url': ['application url', 'job url', 'apply link', 'url', 'application_url'],
    'source': ['source', 'source url'],
}
NS = {'x': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main',
      'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
      'p': 'http://schemas.openxmlformats.org/package/2006/relationships'}


def decode_file(value: str, max_bytes: int = MAX_FILE_BYTES) -> bytes:
    if len(value) > (max_bytes * 4 // 3 + 100):
        raise ValueError('File exceeds the 2 MB limit.')
    try:
        content = base64.b64decode(value, validate=True)
    except Exception as exc:
        raise ValueError('Invalid file encoding.') from exc
    if not content or len(content) > max_bytes:
        raise ValueError('File must contain data and be no larger than 2 MB.')
    return content


def extract_resume(content: bytes, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    if ext == '.txt':
        result = content.decode('utf-8-sig', errors='replace')
    elif ext == '.pdf':
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(content), strict=False)
        if len(reader.pages) > 12:
            raise ValueError('CV PDF may contain at most 12 pages.')
        result = '\n'.join(page.extract_text() or '' for page in reader.pages)
    elif ext == '.docx':
        from docx import Document
        document = Document(io.BytesIO(content))
        result = '\n'.join(p.text for p in document.paragraphs)
        for table in document.tables:
            result += '\n' + '\n'.join(' '.join(cell.text for cell in row.cells) for row in table.rows)
    else:
        raise ValueError('CV must be a .pdf, .docx, or .txt file.')
    result = result.strip()[:MAX_TEXT_CHARS]
    if not result:
        raise ValueError('No readable CV text found. Scanned PDFs require OCR, which is not included.')
    return result


def canon_skill(text: str) -> str:
    key = ' '.join(text.strip().lower().split())
    return ALIASES.get(key, key)


def find_skills(text: str) -> list[str]:
    found = []
    for skill in SKILLS:
        pattern = r'(?<![a-z0-9+#])' + re.escape(skill) + r'(?![a-z0-9+#])'
        if re.search(pattern, text, re.I):
            found.append(skill)
    for alias, actual in ALIASES.items():
        if re.search(r'(?<![a-z0-9+#])' + re.escape(alias) + r'(?![a-z0-9+#])', text, re.I):
            found.append(actual)
    return sorted(set(found))


def parse_resume(text: str) -> dict:
    # Structured signals only; uncertain values stay unknown rather than guessed.
    cgpa = None
    match = re.search(r'\b(?:cgpa|c\.g\.p\.a\.?|gpa)\s*(?:of|:|=|-)?\s*(\d{1,2}(?:\.\d{1,2})?)\s*(?:/\s*10)?\b', text, re.I)
    if match and 0 <= float(match.group(1)) <= 10:
        cgpa = float(match.group(1))
    degree = None
    for pattern, label in [(r'\b(?:b\.?\s?tech|bachelor of technology)\b', 'B.Tech'),
                           (r'\b(?:b\.?\s?e\.?|bachelor of engineering)\b', 'B.E.'),
                           (r'\b(?:m\.?\s?tech|master of technology)\b', 'M.Tech'),
                           (r'\b(?:bca)\b', 'BCA'), (r'\b(?:mca)\b', 'MCA'),
                           (r'\b(?:bsc|b\.sc\.?|bachelor of science)\b', 'B.Sc'),
                           (r'\b(?:msc|m\.sc\.?|master of science)\b', 'M.Sc')]:
        if re.search(pattern, text, re.I): degree = label; break
    grad_year = None
    match = re.search(r'\b(?:graduat(?:ed|ion|ing)|passing out|batch|pass(?:ed)? out|class of)\s*(?:year|:|in|-|of|\s)*\s*(20[2-3]\d)\b', text, re.I)
    if match: grad_year = int(match.group(1))
    years = None
    match = re.search(r'\b(\d{1,2}(?:\.\d+)?)\s*(?:\+\s*)?years?\s+(?:of\s+)?(?:professional\s+|relevant\s+)?experience\b', text, re.I)
    if match: years = float(match.group(1))
    return {'skills': find_skills(text), 'cgpa': cgpa, 'degree': degree,
            'graduation_year': grad_year, 'experience_years': years,
            'text_chars': len(text), 'privacy': 'Processed in-memory on this local backend; not saved or sent to AI.'}


def _safe_zip_read(z: zipfile.ZipFile, path: str) -> bytes:
    info = z.getinfo(path)
    if info.file_size > MAX_XML_BYTES:
        raise ValueError('Excel sheet is too large to process safely.')
    return z.read(info)


def _xlsx_rows(content: bytes) -> list[list[str]]:
    """Read the first sheet of a simple .xlsx including inline and shared strings.
    Numeric cached values are supported. Formulas without cached values remain blank.
    """
    with zipfile.ZipFile(io.BytesIO(content)) as z:
        if len(z.infolist()) > 120 or sum(m.file_size for m in z.infolist()) > MAX_XML_BYTES:
            raise ValueError('Excel workbook is too complex or too large.')
        workbook = ET.fromstring(_safe_zip_read(z, 'xl/workbook.xml'))
        sheet = workbook.find('x:sheets/x:sheet', NS)
        if sheet is None: raise ValueError('Workbook has no sheets.')
        rel_id = sheet.attrib.get('{%s}id' % NS['r'])
        rels = ET.fromstring(_safe_zip_read(z, 'xl/_rels/workbook.xml.rels'))
        target = next((r.attrib.get('Target') for r in rels if r.attrib.get('Id') == rel_id), None)
        if not target: raise ValueError('Workbook sheet relation not found.')
        sheet_path = 'xl/' + target.lstrip('/') if not target.startswith('/') and not target.startswith('xl/') else target.lstrip('/')
        # Canonicalize to avoid unexpected ZIP entries and path traversal.
        import posixpath
        sheet_path = posixpath.normpath(sheet_path)
        if not sheet_path.startswith('xl/worksheets/'):
            raise ValueError('Only standard Excel worksheets are supported.')
        shared = []
        if 'xl/sharedStrings.xml' in z.namelist():
            root = ET.fromstring(_safe_zip_read(z, 'xl/sharedStrings.xml'))
            shared = [''.join(t.text or '' for t in si.iter('{%s}t' % NS['x'])) for si in root.findall('x:si', NS)]
        root = ET.fromstring(_safe_zip_read(z, sheet_path))
        data = []
        for row in root.findall('.//x:sheetData/x:row', NS):
            cells = {}
            for c in row.findall('x:c', NS):
                ref = c.attrib.get('r', '')
                letters = re.match(r'[A-Z]+', ref)
                if not letters: continue
                idx = 0
                for letter in letters.group(): idx = idx * 26 + ord(letter) - 64
                if idx > 40: continue
                val = c.find('x:v', NS)
                valstr = val.text if val is not None and val.text is not None else ''
                if c.attrib.get('t') == 's':
                    try: valstr = shared[int(valstr)]
                    except (IndexError, ValueError): valstr = ''
                elif c.attrib.get('t') == 'inlineStr':
                    valstr = ''.join(node.text or '' for node in c.findall('.//x:t', NS))
                cells[idx - 1] = str(valstr)
            if cells:
                data.append([cells.get(i, '') for i in range(max(cells) + 1)])
            if len(data) > MAX_ROWS + 25: break
        return data


def read_jobs(content: bytes, filename: str) -> list[dict]:
    ext = Path(filename).suffix.lower()
    if ext == '.csv':
        rows = list(csv.reader(io.StringIO(content.decode('utf-8-sig', errors='replace'))))[:MAX_ROWS + 25]
    elif ext == '.xlsx':
        rows = _xlsx_rows(content)
    else:
        raise ValueError('Job database must be .xlsx or .csv. Old .xls files are not supported.')
    header_row = None
    for index, row in enumerate(rows[:20]):
        normalized = [re.sub(r'[^a-z0-9]+', ' ', cell.strip().lower()).strip() for cell in row]
        columns = {}
        for key, aliases in HEADERS.items():
            for alias in aliases:
                if alias.replace('_', ' ') in normalized:
                    columns[key] = normalized.index(alias.replace('_', ' ')); break
        if 'company' in columns and 'job_title' in columns:
            header_row = index; break
    if header_row is None: raise ValueError('Excel sheet must contain Company and Job Title column headers.')
    jobs = []
    for row in rows[header_row + 1:]:
        job = {key: (row[col].strip() if col < len(row) else '') for key, col in columns.items()}
        if not job.get('company') or not job.get('job_title'): continue
        jobs.append(job)
        if len(jobs) >= MAX_ROWS: break
    if not jobs: raise ValueError('The Excel job sheet has no job rows.')
    return jobs


def _numeric(raw):
    if not str(raw).strip(): return None
    try: return float(str(raw).strip())
    except ValueError: return None


def _degree_match(requirement: str, actual: str | None) -> bool | None:
    if not requirement.strip(): return True
    if not actual: return None
    options = re.split(r'[,;/|]+|\s+or\s+', requirement, flags=re.I)
    normalized = lambda s: re.sub(r'[^a-z0-9]', '', s.lower())
    return any(normalized(actual) == normalized(option) or normalized(option) in ('any', 'all', 'bachelor', 'anydegree', 'anybachelorsdegree') for option in options)


def match_jobs(profile: dict, jobs: list[dict]) -> list[dict]:
    results = []
    skills = set(profile['skills'])
    for job in jobs:
        reasons, unknowns, failures, successes = [], [], [], []
        requirements = [canon_skill(s) for s in re.split(r'[,;/|\n]+', job.get('required_skills', '')) if s.strip()]
        requirements = list(dict.fromkeys(requirements))
        matched = [s for s in requirements if s in skills]
        missing = [s for s in requirements if s not in skills]
        if missing: failures.append('Missing evidence of required skills: ' + ', '.join(missing))
        elif requirements: successes.append('All listed skills found in CV')
        else: unknowns.append('No required skills listed in job sheet')
        cgpa = _numeric(job.get('min_cgpa'))
        if cgpa is not None:
            if profile['cgpa'] is None: unknowns.append('CV CGPA was not detected')
            elif profile['cgpa'] >= cgpa: successes.append('CGPA meets the listed minimum')
            else: failures.append(f'CGPA {profile["cgpa"]} is below required {cgpa:g}')
        degree = _degree_match(job.get('degree', ''), profile.get('degree'))
        if degree is None: unknowns.append('CV degree was not detected')
        elif not degree: failures.append('Listed degree requirement does not match detected CV degree')
        elif job.get('degree'): successes.append('Degree matches the listed requirement')
        for key, title, compare in [('graduation_year_min', 'earliest graduation year', lambda a, b: a >= b),
                                     ('graduation_year_max', 'latest graduation year', lambda a, b: a <= b),
                                     ('experience_years', 'minimum experience', lambda a, b: a >= b)]:
            threshold = _numeric(job.get(key))
            if threshold is None: continue
            actual = profile['experience_years'] if key == 'experience_years' else profile['graduation_year']
            if actual is None: unknowns.append(f'{title.title()} not confirmed in CV')
            elif not compare(actual, threshold): failures.append(f'{title.title()} requirement not met')
            else: successes.append(f'{title.title()} requirement met')
        if failures: status = 'requirements_not_met'
        elif unknowns: status = 'needs_review'
        else: status = 'meets_listed_requirements'
        score = round(100 * (len(matched) / len(requirements)), 0) if requirements else None
        results.append({'company': job['company'], 'job_title': job['job_title'],
                        'location': job.get('location', ''), 'application_url': job.get('application_url', ''),
                        'source': job.get('source', ''), 'status': status, 'skill_match_percent': score,
                        'matched_skills': matched, 'missing_skills': missing, 'reasons': successes + failures,
                        'unknowns': unknowns})
    order = {'meets_listed_requirements': 0, 'needs_review': 1, 'requirements_not_met': 2}
    return sorted(results, key=lambda item: (order[item['status']], -(item['skill_match_percent'] or 0), item['company'].lower()))


def analyze_files(cv_content: bytes, cv_filename: str, jobs_content: bytes, jobs_filename: str) -> dict:
    text = extract_resume(cv_content, cv_filename)
    profile = parse_resume(text)
    jobs = read_jobs(jobs_content, jobs_filename)
    matched = match_jobs(profile, jobs)
    return {'profile': profile, 'jobs_checked': len(jobs),
            'summary': {status: sum(j['status'] == status for j in matched) for status in ('meets_listed_requirements', 'needs_review', 'requirements_not_met')},
            'results': matched, 'disclaimer': 'Matching against the uploaded job sheet only. Not official eligibility or proof a company is hiring. Check each verified posting and apply manually.'}

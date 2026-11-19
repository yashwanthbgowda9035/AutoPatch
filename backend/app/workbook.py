"""Static XLSX formula audit from Open XML parts (no macro execution or recalculation)."""
from __future__ import annotations

import base64
import io
import re
import zipfile
from pathlib import PurePosixPath
import xml.etree.ElementTree as ET

from . import multilang

MAX_WORKBOOK_BYTES = 2_000_000
MAX_UNCOMPRESSED_BYTES = 20_000_000
MAX_FORMULAS = 500
MAX_DISPLAY = 140
NS = '{http://schemas.openxmlformats.org/spreadsheetml/2006/main}'
DOC_REL = '{http://schemas.openxmlformats.org/officeDocument/2006/relationships}'
PKG_REL = '{http://schemas.openxmlformats.org/package/2006/relationships}'


def _sheet_names(archive: zipfile.ZipFile) -> dict[str,str]:
    """Resolve workbook relationship targets without extracting archive paths."""
    names = set(archive.namelist())
    if 'xl/workbook.xml' not in names or 'xl/_rels/workbook.xml.rels' not in names:
        return {}
    book = ET.fromstring(archive.read('xl/workbook.xml'))
    rels = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
    rel_targets = {}
    for rel in rels.findall(f'{PKG_REL}Relationship'):
        target = rel.attrib.get('Target', '')
        if rel.attrib.get('TargetMode') == 'External':
            continue
        # Strip leading '/' used by some spreadsheet writers.
        path = target.lstrip('/') if target.startswith('/') else 'xl/' + target
        # Resolve '..' segments lexically and verify it is already in the ZIP.
        parts = []
        for part in path.split('/'):
            if part == '..':
                if parts: parts.pop()
            elif part and part != '.': parts.append(part)
        safe = '/'.join(parts)
        if safe in names:
            rel_targets[rel.attrib.get('Id', '')] = safe
    labels={}
    for sheet in book.findall(f'.//{NS}sheet'):
        sheet_file = rel_targets.get(sheet.attrib.get(f'{DOC_REL}id', ''))
        if sheet_file:
            labels[sheet_file] = sheet.attrib.get('name', 'Sheet')
    return labels


def audit_xlsx(raw: bytes) -> dict:
    if not raw or len(raw) > MAX_WORKBOOK_BYTES:
        raise ValueError('Excel workbook must be between 1 byte and 2 MB.')
    if not zipfile.is_zipfile(io.BytesIO(raw)):
        raise ValueError('The uploaded file is not a valid XLSX archive.')
    with zipfile.ZipFile(io.BytesIO(raw)) as archive:
        members = archive.infolist()
        if len(members) > 2000 or sum(m.file_size for m in members) > MAX_UNCOMPRESSED_BYTES:
            raise ValueError('Workbook archive exceeds static inspection limits.')
        sheet_paths = sorted(info.filename for info in members if re.fullmatch(r'xl/worksheets/sheet\d+\.xml', info.filename))
        names = _sheet_names(archive)
        findings, rows, total, cached_count = [], [], 0, 0
        for path in sheet_paths:
            if total >= MAX_FORMULAS: break
            tree = ET.fromstring(archive.read(path))
            label = names.get(path, PurePosixPath(path).stem)
            for cell in tree.iter(f'{NS}c'):
                formula_element = cell.find(f'{NS}f')
                if formula_element is None: continue
                if total >= MAX_FORMULAS: break
                formula = formula_element.text or ''
                coord = cell.attrib.get('r', '?')[:16]
                if not formula.strip():
                    continue  # shared-formula child with a formula stored at the anchor
                total += 1
                expression = '=' + formula
                cached_element = cell.find(f'{NS}v')
                cached = cached_element.text if cached_element is not None else None
                if cached is not None: cached_count += 1
                if len(rows) < MAX_DISPLAY:
                    rows.append({'sheet':label, 'cell':coord, 'formula':expression[:1000],
                                 'cached_value':cached, 'value_type':cell.attrib.get('t', '')})
                report=multilang.analyze(expression, 'excel')
                for issue in report['issues']:
                    findings.append({**issue,'sheet':label,'cell':coord,'line':total,
                                     'id':f"{issue['id']}-{label}-{coord}"})
                if cell.attrib.get('t') == 'e' and cached:
                    findings.append({'id':f'XL-CACHE-ERR-{label}-{coord}', 'rule':'XL-CACHE-ERR',
                                     'title':'Cached spreadsheet error',
                                     'detail':f'The workbook saved {cached} as the latest stored value.',
                                     'severity':'high','category':'Workbook cached result','line':total,
                                     'confidence':100,'suggestion':'Inspect referenced cells and recalculate in Excel.',
                                     'fix_available':False,'sheet':label,'cell':coord})
    return {'analysis_mode':'xlsx_static_formula_audit', 'language':'excel',
            'detected_language':'excel', 'total_formulas':total,'inspected_formulas':total,
            'displayed_formulas':len(rows),'cached_value_count':cached_count,
            'total_issues':len(findings),'fixable_issues':0, 'issues':findings,
            'rows':rows, 'lines_scanned':total, 'duration_ms':0,
            'note':'Cached values are stored by the workbook and may be stale; Excel formulas were NOT recalculated or executed.',
            'detection':{'language':'excel','confidence':1.0,'tentative':False,'reason':'Uploaded XLSX workbook'}}

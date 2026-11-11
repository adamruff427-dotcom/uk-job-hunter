"""Synthetic loopback server for browser tests; no provider network requests."""
import os
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Set before importing the app: never use real local preferences or tracker.
workspace = tempfile.TemporaryDirectory()
os.environ['UK_HUNTER_DATA_DIR'] = workspace.name
from uk_hunter import webapp

sources = [dict(name=name, provider='lever', board=board, sector=sector,
                url='https://jobs.lever.co/' + board)
           for name, board, sector in [('Example Bank', 'bank', 'banking'),
                                       ('Example Laboratory', 'lab', 'healthcare'),
                                       ('Unavailable Example', 'offline', 'unspecified')]]


def fetch(source, validators=None):
    if source['board'] == 'offline':
        raise RuntimeError('Synthetic outage')
    count = 85 if source['board'] == 'bank' else 50
    jobs = []
    for i in range(count):
        jobs.append(dict(id=f"lever:{source['board']}:{i}",
                         title=('Risk Manager' if source['board'] == 'bank' else 'Research Scientist') + f' {i:03d}',
                         company=source['name'], location='Leeds, UK',
                         url=f"https://jobs.lever.co/{source['board']}/{i}",
                         source='lever', date='2026-11-11', occupation='Risk' if source['board'] == 'bank' else 'Research',
                         description='Synthetic vacancy. <img src=x onerror=alert(1)> is plain text.',
                         workplace_type='remote' if i % 2 == 0 else 'hybrid',
                         salary_min=80000 if i % 2 == 0 else None,
                         salary_max=90000 if i % 2 == 0 else None))
    return jobs, {}, False


with patch.object(webapp, 'read_sources', return_value=sources), patch('uk_hunter.providers.fetch_snapshot', side_effect=fetch):
    webapp.serve(18765)

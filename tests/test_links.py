import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BUNDLE = ROOT / 'skills' / 'jfactory'
LINK = re.compile(r'\]\(([^)\s]+)\)')


def local_targets(path):
    for target in LINK.findall(path.read_text()):
        if re.match(r'^[a-z]+:', target) or target.startswith('#'):
            continue
        yield target.split('#', 1)[0]


class LinkTest(unittest.TestCase):
    def test_bundle_links_resolve_inside_installed_bundle(self):
        vendor = BUNDLE / 'vendor'
        failures = []
        for doc in BUNDLE.rglob('*.md'):
            if vendor in doc.parents:
                continue
            for target in local_targets(doc):
                resolved = (doc.parent / target).resolve()
                if not resolved.exists():
                    failures.append(f'{doc.relative_to(ROOT)}: missing {target}')
                elif not resolved.is_relative_to(BUNDLE.resolve()):
                    failures.append(f'{doc.relative_to(ROOT)}: leaves installed bundle {target}')
        self.assertEqual(failures, [])

    def test_repository_docs_links_resolve(self):
        failures = []
        for doc in [ROOT / 'README.md', ROOT / 'AGENTS.md', ROOT / 'evals' / 'scenarios.md']:
            for target in local_targets(doc):
                if not (doc.parent / target).exists():
                    failures.append(f'{doc.relative_to(ROOT)}: missing {target}')
        self.assertEqual(failures, [])

    def test_readme_diagrams_are_rendered_from_current_sources(self):
        diagrams = ROOT / 'docs' / 'diagrams'
        manifest = json.loads((diagrams / 'manifest.json').read_text())
        sources = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in diagrams.glob('*.mmd')}
        self.assertEqual(manifest, sources, 'Diagram source changed; run scripts/render_diagrams.py')
        for name in sources:
            self.assertTrue((diagrams / name).with_suffix('.png').is_file(), name)
        self.assertNotIn('```mermaid', (ROOT / 'README.md').read_text(),
                         "GitHub's mobile app shows Mermaid as code; link a rendered image instead")


if __name__ == '__main__':
    unittest.main()

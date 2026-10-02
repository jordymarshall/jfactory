import importlib.util
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VENDOR = ROOT / 'skills/jfactory/vendor'
spec = importlib.util.spec_from_file_location('upstream', ROOT / 'skills/jfactory/scripts/check-upstream.py')
upstream = importlib.util.module_from_spec(spec)
spec.loader.exec_module(upstream)


class UpstreamTests(unittest.TestCase):
    def test_all_snapshots_and_corruption_controls(self):
        for source in ('pstack', 'humanlayer', 'mattpocock'):
            for corruption in ('none', 'changed', 'missing', 'unrecorded'):
                with self.subTest(source=source, corruption=corruption), tempfile.TemporaryDirectory() as tmp:
                    snapshot = Path(tmp) / source
                    shutil.copytree(VENDOR / source, snapshot)
                    if corruption == 'changed':
                        (snapshot / 'LICENSE').write_text('different license')
                    elif corruption == 'missing':
                        (snapshot / 'LICENSE').unlink()
                    elif corruption == 'unrecorded':
                        (snapshot / 'unrecorded.md').write_text('unreviewed addition')
                    self.assertEqual(upstream.check(snapshot), int(corruption != 'none'))

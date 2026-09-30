import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'skills' / 'jfactory' / 'scripts'))
import method_audit  # noqa: E402

HEAD = 'a' * 40
CONFIG = {'static': ['docs/**'], 'suites': {'browser': {'run': 'true', 'target': 'app'}},
          'targets': {'app': {'url': 'http://x', 'ready': 'http://x', 'auth': 'none'}},
          'features': {'briefs': {'paths': ['app/briefs/**'], 'suites': ['browser'], 'outcome': 'outcomes/briefs.md'},
                       'cli': {'paths': ['cli/**']}},
          '_standards': ['docs/brand.md', 'outcomes/briefs.md']}
GOOD_BODY = "## Objective\nSave briefs.\n\n## Why it's right\nServes `outcomes/briefs.md`.\n"


def pr(files, body=GOOD_BODY, **verdict):
    record = {'head': HEAD, 'verdict': 'verified', 'features': ['briefs'], 'evidence': ['x'],
              'standards': ['docs/brand.md'], 'screenshots': ['https://shot'], **verdict}
    record = {k: v for k, v in record.items() if v is not None}
    comment = {'authorAssociation': 'OWNER', 'body': f'<!-- jfactory-verdict {json.dumps(record)} -->'}
    return {'number': 1, 'title': 't', 'headRefOid': HEAD, 'files': files, 'body': body, 'comments': [comment]}


class MethodAuditTest(unittest.TestCase):
    def test_a_right_merge_has_no_findings(self):
        self.assertEqual(method_audit.audit_pr(pr(['app/briefs/a.ts']), CONFIG), [])
        self.assertEqual(method_audit.audit_pr(pr(['docs/a.md'], body=''), CONFIG), [])

    def test_each_gap_is_reported(self):
        audit = lambda **kw: method_audit.audit_pr(pr(['app/briefs/a.ts'], **kw), CONFIG)
        self.assertIn('verdict names no standards', audit(standards=None))
        self.assertIn('screen change merged without reviewed screenshots', audit(screenshots=None))
        self.assertIn('merged without a verified verdict at its final commit', audit(verdict='failed'))
        self.assertIn('merged without a verified verdict at its final commit', audit(head='b' * 40))
        self.assertEqual(audit(body='## Objective\nSave briefs.\n'),
                         ['description names no outcomes/ document', 'description has no "Why it\'s right" section'])
        # A test-only change needs a verdict with standards, but no screenshots.
        self.assertEqual(method_audit.audit_pr(pr(['app/briefs/a.test.ts'], screenshots=None), CONFIG), [])

    def test_report_counts_and_lists_findings(self):
        results = [(pr(['app/briefs/a.ts']), []), ({**pr([]), 'number': 7, 'title': 'Restyle'}, ['verdict names no standards'])]
        text = method_audit.report(results, 2)
        self.assertIn('1 with findings', text)
        self.assertIn('1× verdict names no standards', text)
        self.assertIn('| #7 Restyle | verdict names no standards |', text)


if __name__ == '__main__':
    unittest.main()

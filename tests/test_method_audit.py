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
          '_standards': ['docs/brand.md', 'outcomes/', 'outcomes/briefs.md']}
GOOD_BODY = "## Objective\nSave briefs.\n\n## Why it's right\nServes `outcomes/briefs.md`.\n"


def pr(files, body=GOOD_BODY, **verdict):
    record = {'head': HEAD, 'verdict': 'verified', 'features': ['briefs', 'cli'], 'evidence': ['x'],
              'verifier': 'codex/gpt-6.1-sol', 'implementer': 'claude/opus-5-5', 'standards': ['docs/brand.md'],
              'screenshots': ['https://shot'], 'walkthrough': ['https://trail'], **verdict}
    record = {k: v for k, v in record.items() if v is not None}
    comment = {'authorAssociation': 'OWNER', 'body': f'<!-- jfactory-verdict {json.dumps(record)} -->'}
    return {'number': 1, 'title': 't', 'headRefOid': HEAD, 'files': files, 'body': body, 'comments': [comment]}


class MethodAuditTest(unittest.TestCase):
    def test_a_right_merge_has_no_findings(self):
        self.assertEqual(method_audit.audit_pr(pr(['app/briefs/a.ts']), CONFIG), [])
        self.assertEqual(method_audit.audit_pr(pr(['docs/a.md'], body=''), CONFIG), [])

    def test_it_applies_the_gates_own_rules(self):
        audit = lambda **kw: method_audit.audit_pr(pr(['app/briefs/a.ts'], **kw), CONFIG)
        self.assertIn('Verdict does not name the standards', audit(standards=None)[0])
        self.assertIn('Verdict does not name the standards', audit(standards=['docs/invented.md'])[0])
        self.assertIn('no screenshots of the changed screens', audit(screenshots=None)[0])
        self.assertEqual(audit(head='b' * 40), ['merged without a verified verdict at its final commit'])
        self.assertIn('Latest verdict at aaaaaaa is failed', audit(verdict='failed')[0])
        # Rules the gate enforces on verdicts apply here too: family, coverage.
        self.assertIn('same model family', audit(verifier='claude/opus-5-5')[0])
        self.assertIn('misses features', audit(features=['cli'])[0])
        self.assertIn('"Why it\'s right" section', audit(body='## Objective\nSave briefs.\n')[0])
        # Naming the outcomes/ folder is not naming the job the change serves.
        self.assertIn('outcomes/<job>.md', audit(body="## Objective\nSave briefs.\n\n## Why it's right\nSee outcomes/.\n")[0])

    def test_report_counts_lists_and_qualifies_findings(self):
        results = [(pr(['app/briefs/a.ts']), []), ({**pr([]), 'number': 7, 'title': 'Restyle'}, ['X'])]
        text = method_audit.report(results, 2, since='2026-09-23')
        self.assertIn('the 2 PRs merged since 2026-09-23: 1 with findings', text)
        self.assertIn('judged by the gate\'s own rules as they are today', text)
        self.assertIn('| #7 Restyle | X |', text)


RULE = ('skills/jfactory/references/verification.md#independent-verdict: prescribes high effort, which the owner '
        'replaced; point to the verify tier in models.md')
OTHER = 'skills/jfactory/references/models.md#verify: names a retired model; name the current verify model'


def ruled(number, *rules, decision='https://github.test/issues/3#c1'):
    """A merged PR whose verifier first said a rule was wrong, then verified after the owner's decision."""
    item = pr(['app/briefs/a.ts'], rule_decision=decision)
    flagged = {'head': HEAD, 'verdict': 'failed', 'cause': 'rules', 'rule_changes': list(rules), 'evidence': ['x'],
               'verifier': 'codex/gpt-6.1-sol', 'implementer': 'claude/opus-5-5'}
    item['comments'].insert(0, {'authorAssociation': 'OWNER', 'body': f'<!-- jfactory-verdict {json.dumps(flagged)} -->'})
    return {**item, 'number': number}


class RuleProblemsTest(unittest.TestCase):
    def test_counts_rules_cause_merges_and_lists_rules_flagged_more_than_once(self):
        results = [(ruled(3, RULE), []), (ruled(4, RULE, OTHER), []), (ruled(5, OTHER + ' again'), []),
                   (pr(['app/briefs/a.ts']), [])]
        self.assertEqual(method_audit.repeated_rules(results),
                         {'skills/jfactory/references/verification.md#independent-verdict': [3, 4],
                          'skills/jfactory/references/models.md#verify': [4, 5]})
        text = method_audit.report(results, 4)
        self.assertIn('Rule problems: 3 of 4 merged PRs had a verdict saying a rule, not the change, was wrong '
                      '(#3, #4, #5).', text)
        self.assertIn('- `skills/jfactory/references/verification.md#independent-verdict`: #3, #4', text)
        # Flagged once is counted but not listed as recurring; no rule problems at all says so.
        self.assertEqual(method_audit.repeated_rules([(ruled(3, RULE), [])]), {})
        self.assertIn('Rule problems: 0 of 1 merged PRs', method_audit.report([(pr(['app/briefs/a.ts']), [])], 1))

    def test_merging_past_a_rules_verdict_needs_the_owners_decision(self):
        self.assertEqual(method_audit.audit_pr(ruled(3, RULE), CONFIG), [])
        self.assertIn('must link the owner', method_audit.audit_pr(ruled(3, RULE, decision=None), CONFIG)[0])


class PublishTest(unittest.TestCase):
    def setUp(self):
        self.calls, self.issue, self.last = [], '', ''
        self.saved = method_audit.vp.run
        method_audit.vp.run = self.fake
        self.addCleanup(setattr, method_audit.vp, 'run', self.saved)

    def fake(self, *args):
        self.calls.append(args[1:3])
        if args[1:3] == ('issue', 'list'):
            return self.issue
        if args[1:3] == ('issue', 'view'):
            return self.last
        return ''

    def test_opens_once_updates_on_change_and_closes_when_clean(self):
        self.assertEqual(method_audit.publish('o/r', 'clean', True), 'clean; no issue')
        self.assertEqual(method_audit.publish('o/r', 'gap A', False), 'opened')
        self.assertIn(('label', 'create'), self.calls)
        self.issue, self.last = '12', 'gap A'
        self.calls.clear()
        self.assertEqual(method_audit.publish('o/r', 'gap A\n', False), 'unchanged')
        self.assertNotIn(('issue', 'comment'), self.calls)
        self.assertEqual(method_audit.publish('o/r', 'gap B', False), 'updated')
        self.assertEqual(method_audit.publish('o/r', 'clean now', True), 'closed')
        self.assertIn(('issue', 'close'), self.calls)
        # A close that failed after its comment is retried on the next clean run, without a duplicate comment.
        self.last, self.calls = 'clean now', []
        self.assertEqual(method_audit.publish('o/r', 'clean now', True), 'closed')
        self.assertNotIn(('issue', 'comment'), self.calls)
        self.assertIn(('issue', 'close'), self.calls)


if __name__ == '__main__':
    unittest.main()

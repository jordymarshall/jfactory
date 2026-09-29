import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'jfactory' / 'scripts' / 'setup_check.py'
TEMPLATE = ROOT / 'skills' / 'jfactory' / 'templates' / 'setup-record.md'
WORKFLOW = ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-verified.yml'
FAKE = ROOT / 'tests' / 'fakes' / 'fake_cli.py'
AGENTS = '# App\n\n## Product brief\nx\n\n## System map\nx\n\n## Feature/status map\nx\n\n## Agent instructions\nx\n'
READY = {area: ('verified', 'checked') for area in
         ['Documentation', 'Product direction', 'Workspace tools', 'Verification', 'Environments', 'PR delivery']}
RELEASE = {'staging': 'https://staging.example.com', 'production': 'https://example.com',
           'revision': 'curl -s https://example.com/api/version', 'promote': 'gh workflow run release-production.yml',
           'approval': 'GitHub environment production requires the owner', 'rollback': 'vercel rollback'}
PROTECTED = {'repo': {'default_branch': 'main', 'allow_auto_merge': True},
             'rules': [{'type': 'pull_request'},
                       {'type': 'required_status_checks', 'parameters': {'required_status_checks': [
                           {'context': 'ci'}, {'context': 'jfactory verified'}]}}]}


def record(states=READY, answers=('Developers', 'Retyping', 'Fewer steps', 'Billing', 'Save items'),
           location='GitHub issues labelled jfactory-objective'):
    rows = '\n'.join(f'| {area} | {state} | {why} |' for area, (state, why) in states.items())
    questions = ['Who?', 'Today?', 'Outcome?', 'Out of scope?', 'Next objective?']
    interview = '\n'.join(f'| {q} | {a} | 2026-09-28 |' for q, a in zip(questions, answers))
    return (f'# jfactory setup record\n\n## Readiness\n\n| Area | State | Evidence or reason |\n| --- | --- | --- |\n'
            f'{rows}\n\n## Owner interview\n\n| Question | Owner answer | Date |\n| --- | --- | --- |\n{interview}\n\n'
            f'## Open owner decisions\n\nNone.\n\n## Next objective\n\nTask location: {location}\n')


class SetupCheckTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'AGENTS.md').write_text(AGENTS)
        (self.root / '.jfactory').mkdir()
        (self.root / '.jfactory' / 'setup.md').write_text(record())
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(
            {'static': ['README.md'], 'features': {'app': {'paths': ['src/**', 'AGENTS.md', '.jfactory/**',
                                                                    '.github/**']}}}))
        (self.root / '.jfactory' / 'coordination.json').write_text(json.dumps(
            {'merge_deploys': 'staging', 'release': RELEASE}))
        (self.root / '.github' / 'workflows').mkdir(parents=True)
        shutil.copy(WORKFLOW, self.root / '.github' / 'workflows' / 'jfactory-verified.yml')
        (self.root / 'src').mkdir()
        (self.root / 'src' / 'app.py').write_text('')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        self.state = self.root.parent / f'{self.root.name}-fake.json'
        self.addCleanup(lambda: self.state.unlink(missing_ok=True))
        self.state.write_text(json.dumps(PROTECTED))
        bins = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, bins)
        exe = bins / 'gh'
        exe.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{FAKE}" gh "$@"\n')
        exe.chmod(0o755)
        self.env = {**os.environ, 'FAKE_STATE': str(self.state), 'JFACTORY_GH': str(exe)}

    def check(self, *args, code=0):
        proc = subprocess.run([sys.executable, str(SCRIPT), '--root', str(self.root), *args], env=self.env,
                              capture_output=True, text=True)
        self.assertEqual(proc.returncode, code, proc.stdout + proc.stderr)
        return proc.stdout

    def test_complete_setup_passes_with_remote_protection(self):
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('Setup is complete', out)
        self.assertIn('GitHub requires PRs and ci, jfactory verified', out)

    def test_template_is_a_valid_but_unfilled_record(self):
        shutil.copy(TEMPLATE, self.root / '.jfactory' / 'setup.md')
        out = self.check(code=1)
        self.assertIn('state "<state>"', out)
        self.assertIn('does not name the task location', out)

    def test_product_cannot_be_verified_without_owner_answers(self):
        (self.root / '.jfactory' / 'setup.md').write_text(record(answers=('Developers', 'unanswered', '', 'x', 'y')))
        self.assertIn('owner has not answered: Today?; Outcome?', self.check(code=1))
        states = {**READY, 'Product direction': ('configured but unverified', 'agent summary of the README')}
        (self.root / '.jfactory' / 'setup.md').write_text(record(states=states, answers=('unanswered',) * 5))
        self.assertIn('must be "blocked"', self.check(code=1))
        states['Product direction'] = ('blocked', 'waiting for the owner interview')
        (self.root / '.jfactory' / 'setup.md').write_text(record(states=states, answers=('unanswered',) * 5))
        out = self.check(code=3)
        self.assertIn('Open areas: Product direction (blocked)', out)

    def test_missing_interview_entry_sections_location_and_merge_target_fail(self):
        text = record().split('## Owner interview')[0] + '## Next objective\n\nTask location: <where>\n'
        (self.root / '.jfactory' / 'setup.md').write_text(text)
        (self.root / 'AGENTS.md').write_text('# App\n\n## Agent instructions\nx\n')
        (self.root / '.jfactory' / 'coordination.json').write_text('{}')
        out = self.check(code=1)
        for expected in ['no "Owner interview" table', 'lacks the entry sections: Product brief, System map',
                         'does not name the task location', 'Record what merging deploys']:
            self.assertIn(expected, out)

    def test_missing_gate_workflow_and_unmapped_files(self):
        (self.root / '.github' / 'workflows' / 'jfactory-verified.yml').unlink()
        (self.root / 'lib.py').write_text('')
        subprocess.run(['git', '-C', str(self.root), 'add', 'lib.py'], check=True)
        out = self.check(code=1)
        self.assertIn('No workflow runs `verify_plan.py ... check`', out)
        self.assertIn('WARN: 1 tracked file(s) match no feature', out)

    def test_verified_delivery_needs_enforced_remote_gates(self):
        self.state.write_text(json.dumps({'repo': {'default_branch': 'main', 'allow_auto_merge': True},
                                          'rules': [{'type': 'pull_request'}, {'type': 'required_status_checks',
                                                    'parameters': {'required_status_checks': [{'context': 'ci'}]}}]}))
        self.assertIn('does not require the "jfactory verified" status', self.check('--remote', '--repo', 'o/r', code=1))
        states = {**READY, 'PR delivery': ('blocked', 'owner must require jfactory verified')}
        (self.root / '.jfactory' / 'setup.md').write_text(record(states=states))
        self.assertIn('WARN: Protected auto-merge is not fully enforced', self.check('--remote', '--repo', 'o/r', code=3))

    def test_verified_delivery_needs_a_successful_remote_check(self):
        self.assertIn('rerun with --remote', self.check(code=3))
        self.state.write_text(json.dumps({'repo': {'default_branch': 'main', 'allow_auto_merge': True}}))
        bad = self.env['JFACTORY_GH']
        self.env['JFACTORY_GH'] = '/nonexistent/gh'
        self.assertIn('FAIL: Could not read GitHub settings', self.check('--remote', '--repo', 'o/r', code=1))
        self.env['JFACTORY_GH'] = bad

    def test_git_unavailable_is_not_full_coverage(self):
        self.env['PATH'] = str(Path(self.env['JFACTORY_GH']).parent)
        self.assertIn('Cannot list tracked files with git', self.check('--remote', '--repo', 'o/r', code=1))

    def test_interview_must_cover_every_topic(self):
        text = record().split('## Owner interview')[0] + (
            '## Owner interview\n\n| Question | Owner answer | Date |\n| --- | --- | --- |\n'
            '| Is setup okay? | yes | 2026-09-28 |\n\n## Next objective\n\nTask location: issues\n')
        (self.root / '.jfactory' / 'setup.md').write_text(text)
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('does not ask about: who it is for, what they do today', out)

    def test_risk_levels_are_reported(self):
        self.assertIn('WARN: 1 feature(s) have no risk level', self.check('--remote', '--repo', 'o/r'))
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(
            {'static': ['README.md'], 'features': {'app': {'paths': ['src/**', 'AGENTS.md', '.jfactory/**', '.github/**'],
                                                           'verify': 'independent'}}}))
        self.assertIn('Risk levels set: 1 independent, 0 CI-only', self.check('--remote', '--repo', 'o/r'))

    def test_pr_delivery_cannot_be_not_applicable(self):
        states = {**READY, 'PR delivery': ('not applicable', 'no PRs here')}
        (self.root / '.jfactory' / 'setup.md').write_text(record(states=states))
        self.assertIn('PR delivery cannot be "not applicable"', self.check('--remote', '--repo', 'o/r', code=1))

    def test_ruleset_template_requires_both_checks_without_bypass(self):
        ruleset = json.loads((ROOT / 'skills' / 'jfactory' / 'templates' / 'ruleset-main.json').read_text())
        rules = {r['type']: r.get('parameters', {}) for r in ruleset['rules']}
        contexts = [c['context'] for c in rules['required_status_checks']['required_status_checks']]
        self.assertEqual(contexts, ['REPLACE_WITH_YOUR_CI_CHECK_NAME', 'jfactory verified'])
        self.assertTrue(rules['required_status_checks']['strict_required_status_checks_policy'])
        self.assertEqual(rules['pull_request']['allowed_merge_methods'], ['squash'])
        self.assertEqual((ruleset['bypass_actors'], ruleset['enforcement']), ([], 'active'))

    def test_production_merges_cannot_be_verified_delivery(self):
        (self.root / '.jfactory' / 'coordination.json').write_text('{"merge_deploys": "production"}')
        self.assertIn('Merging releases production', self.check(code=1))

    def write_coordination(self, **config):
        (self.root / '.jfactory' / 'coordination.json').write_text(json.dumps(config))

    def test_staging_merges_need_a_release_procedure(self):
        self.assertIn('Release procedure recorded: production, revision, promote, rollback, staging',
                      self.check('--remote', '--repo', 'o/r'))
        self.write_coordination(merge_deploys='staging')
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('FAIL: The release procedure is incomplete: record "production", "revision", "promote", '
                      '"rollback", "staging"', out)
        states = {**READY, 'PR delivery': ('blocked', 'owner must create the production environment')}
        (self.root / '.jfactory' / 'setup.md').write_text(record(states=states))
        self.assertIn('WARN: The release procedure is incomplete', self.check('--remote', '--repo', 'o/r', code=3))

    def test_placeholder_or_blank_release_fields_do_not_count(self):
        self.write_coordination(merge_deploys='staging', release={**RELEASE, 'rollback': '  ', 'revision': '<how>'})
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('record "revision", "rollback" under "release"', out)
        self.write_coordination(merge_deploys='staging', release='vercel promote')
        self.assertIn('The release procedure is incomplete', self.check('--remote', '--repo', 'o/r', code=1))

    def test_release_without_an_enforced_approval_warns(self):
        self.write_coordination(merge_deploys='staging', release={k: v for k, v in RELEASE.items() if k != 'approval'})
        self.assertIn('WARN: No "approval" gate is recorded', self.check('--remote', '--repo', 'o/r'))

    def test_release_record_is_optional_when_merging_deploys_nothing(self):
        self.write_coordination(merge_deploys='none')
        out = self.check('--remote', '--repo', 'o/r')
        self.assertNotIn('release', out.lower())
        release = {k: v for k, v in RELEASE.items() if k != 'staging'}
        self.write_coordination(merge_deploys='none', release={**release, 'promote': ''})
        self.assertIn('record "promote"', self.check('--remote', '--repo', 'o/r', code=1))
        self.write_coordination(merge_deploys='none', release=release)
        self.assertIn('Release procedure recorded: production, revision, promote, rollback\n',
                      self.check('--remote', '--repo', 'o/r'))

    def test_release_template_waits_for_a_protected_environment(self):
        text = (ROOT / 'skills' / 'jfactory' / 'templates' / 'release-production.yml').read_text()
        triggers = text.split('\non:\n', 1)[1].split('\npermissions:', 1)[0]
        self.assertIn('workflow_dispatch:', triggers)
        for trigger in ['push:', 'pull_request', 'schedule:', 'workflow_run:']:
            self.assertNotIn(trigger, triggers)
        self.assertIn('    environment: production\n', text)
        self.assertIn('git merge-base --is-ancestor "$SHA" "origin/$BASE"', text)
        self.assertEqual(text.count('&& exit 1'), 2, 'unfilled placeholder steps must fail, not skip')


if __name__ == '__main__':
    unittest.main()

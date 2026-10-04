import json
import re
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills' / 'jfactory' / 'scripts' / 'setup_check.py'
sys.path.insert(0, str(SCRIPT.parent))
import setup_check  # noqa: E402
import verify_plan  # noqa: E402
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


def standards(**overrides):
    rows = {d: ('none: not decided yet in this fixture', 'Verifier review') for d in verify_plan.STANDARD_DIMENSIONS}
    rows['Product goals and customer'] = ('`AGENTS.md#product-brief`', 'Verifier: serves the stated customer')
    rows.update(overrides)
    return '| Dimension | Source of truth | How changes are checked |\n| --- | --- | --- |\n' + ''.join(
        f'| {d} | {source} | {check} |\n' for d, (source, check) in rows.items() if source is not None)


class SetupCheckTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, self.root)
        subprocess.run(['git', 'init', '-q', str(self.root)], check=True)
        (self.root / 'AGENTS.md').write_text(AGENTS)
        (self.root / '.jfactory').mkdir()
        (self.root / '.jfactory' / 'setup.md').write_text(record())
        (self.root / '.jfactory' / 'standards.md').write_text(standards())
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(
            {'static': ['README.md'], 'features': {'app': {'paths': ['src/**', 'AGENTS.md', '.jfactory/**',
                                                                    '.github/**', 'outcomes/**']}}}))
        (self.root / '.jfactory' / 'coordination.json').write_text(json.dumps(
            {'merge_deploys': 'staging', 'release': RELEASE}))
        (self.root / '.github' / 'workflows').mkdir(parents=True)
        shutil.copy(WORKFLOW, self.root / '.github' / 'workflows' / 'jfactory-verified.yml')
        shutil.copy(ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-method-audit.yml',
                    self.root / '.github' / 'workflows' / 'jfactory-method-audit.yml')
        shutil.copy(ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-pr-health.yml',
                    self.root / '.github' / 'workflows' / 'jfactory-pr-health.yml')
        (self.root / 'outcomes').mkdir()
        (self.root / 'outcomes' / 'README.md').write_text('# Outcomes\n')
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

    def test_a_ci_workflow_that_mentions_check_is_not_the_gate(self):
        # Sorted first, it once replaced the real gate and failed "lacks checks: read".
        (self.root / '.github' / 'workflows' / 'a-ci.yml').write_text(
            '# The map check runs here once.\njobs:\n  map:\n    steps:\n'
            '      - run: python3 "$JFACTORY_DIR/scripts/verify_plan.py" audit\n')
        self.assertIn('PASS: The jfactory verified workflow is installed: .github/workflows/jfactory-verified.yml',
                      self.check('--remote', '--repo', 'o/r'))

    def test_claude_code_needs_the_skill_entry_and_the_subagent_hook(self):
        self.assertNotIn('Claude Code', self.check('--remote', '--repo', 'o/r'))
        (self.root / 'CLAUDE.md').write_text('@AGENTS.md\n')
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('.claude/skills/jfactory/SKILL.md is missing', out)
        self.assertIn('WARN: Claude Code subagents can change files here', out)
        skill = self.root / '.claude' / 'skills' / 'jfactory' / 'SKILL.md'
        skill.parent.mkdir(parents=True)
        skill.write_text('---\nname: jfactory\n---\n\nThis is the Claude Code entry for jfactory. Read the bundle.\n')
        shutil.copy(ROOT / 'skills' / 'jfactory' / 'templates' / 'claude-settings.json',
                    self.root / '.claude' / 'settings.json')
        self.assertIn('PASS: Claude Code loads jfactory, and its hook keeps in-session subagents read-only',
                      self.check('--remote', '--repo', 'o/r'))

    def test_standards_map_names_real_sources_and_how_to_prove_them(self):
        self.assertIn('PASS: Standards map covers 9 dimensions', self.check('--remote', '--repo', 'o/r'))
        write = lambda **rows: (self.root / '.jfactory' / 'standards.md').write_text(standards(**rows))
        write(**{'Brand, voice and copy': ('`docs/brand.md`', 'Rubric')})
        self.assertIn('names source(s) that do not exist: docs/brand.md', self.check('--remote', '--repo', 'o/r', code=1))
        write(**{'Accessibility': ('WCAG somewhere', 'Scan'), 'UX principles': ('none: owner later', '')})
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('need a backticked source path, or "none" and why: Accessibility', out)
        self.assertIn('need a "How changes are checked" entry that says how it is proven: UX principles', out)
        write(**{'Performance and scale': (None, None)})
        self.assertIn('lacks dimension(s): Performance and scale', self.check('--remote', '--repo', 'o/r', code=1))
        write()
        config = json.loads((self.root / '.jfactory' / 'verification.json').read_text())
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps({**config, 'static': ['README.md', 'docs/**']}))
        (self.root / 'docs').mkdir()
        (self.root / 'docs' / 'old-spec.md').write_text('# Old spec\n\nTHIS DOCUMENT IS THE SOURCE OF TRUTH.\n')
        (self.root / 'docs' / 'older-spec.md').write_text('# Older spec\n\nSuperseded by the PRD. This document is the source of truth.\n')
        (self.root / 'docs' / 'denial.md').write_text('# Notes\n\nThis document is NOT the source of truth. Use the PRD instead.\n')
        (self.root / 'docs' / 'mention.md').write_text('# Log\n\nArchived logs live elsewhere.\n\nThis spec is the source of truth.\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('claim to be the source of truth without a superseded or historical note: docs/mention.md, docs/old-spec.md', out)
        self.assertNotIn('older-spec.md', out)
        self.assertNotIn('denial.md', out)
        write(**{'Brand, voice and copy': ('`../elsewhere/brand.md`', 'Rubric')})
        self.assertIn('outside the repository: ../elsewhere/brand.md', self.check('--remote', '--repo', 'o/r', code=1))
        write(**{'Brand, voice and copy': ('`./AGENTS.md#brand`', 'Rubric'),
                 'Accessibility': ('none: owner has deferred `WCAG2.2`', 'Later'),
                 'Engineering conventions': ('`LICENSE` and `AGENTS.md`', 'CI')})
        (self.root / 'LICENSE').write_text('MIT\n')
        config = json.loads((self.root / '.jfactory' / 'verification.json').read_text())
        config['features']['app']['paths'].append('LICENSE')
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(config))
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        self.assertIn('PASS: Standards map covers 9 dimensions', self.check('--remote', '--repo', 'o/r'))
        write()
        (self.root / '.jfactory' / 'standards.md').unlink()
        self.assertIn('No standards map', self.check('--remote', '--repo', 'o/r', code=1))
        (self.root / '.jfactory' / 'standards.md').write_text(standards())
        (self.root / 'outcomes' / 'README.md').unlink()
        self.assertIn('No outcomes/README.md', self.check('--remote', '--repo', 'o/r', code=1))

    def test_job_documents_should_link_a_goal_test(self):
        self.assertNotIn('goal test', self.check('--remote', '--repo', 'o/r'))
        job = self.root / 'outcomes' / 'save-items.md'
        config = json.loads((self.root / '.jfactory' / 'verification.json').read_text())
        config['features']['app'].update({'screens': True, 'outcome': 'outcomes/save-items.md', 'verify': 'review'})
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(config))
        table = '# Save items\n\n| Goal or acceptance criterion | How it\'s proven |\n| --- | --- |\n'
        # A goal test named outside the "How it's proven" column does not count.
        job.write_text(table + '| A saved item survives reload | `e2e/save.spec.ts` |\n\n'
                       'Later: `e2e/goals/save-items.spec.ts`.\n')
        subprocess.run(['git', '-C', str(self.root), 'add', '-A'], check=True)
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('WARN: None of the 1 job document(s) for features with screens links a goal test', out)
        job.write_text(table + '| A saved item survives reload | `e2e/goals/save-items.spec.ts` "a saved item survives reload" |\n')
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('PASS: 1 of 1 job document(s) with screens link a goal test', out)
        self.assertNotIn('None of the', out)
        # A product without screens has no goal tests to link.
        config['features']['app'].pop('screens')
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(config))
        job.write_text(table + '| A saved item survives reload | `tests/test_save.py` |\n')
        self.assertNotIn('goal test', self.check('--remote', '--repo', 'o/r'))

    def test_verified_delivery_needs_the_method_audit(self):
        self.assertIn('PASS: The method audit checks the checkers', self.check('--remote', '--repo', 'o/r'))
        audit = self.root / '.github' / 'workflows' / 'jfactory-method-audit.yml'
        # A manual workflow that only mentions the script audits nothing.
        audit.write_text('on: workflow_dispatch\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n      - run: echo method_audit.py\n')
        self.assertIn('No workflow runs `method_audit.py`', self.check('--remote', '--repo', 'o/r', code=1))
        # Scheduled, but only echoes the command.
        audit.write_text("on:\n  schedule:\n    - cron: '0 7 * * 1'\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
                         "      - run: echo python3 scripts/method_audit.py\n      - name: x\n        run: |\n"
                         "          echo 'python3 method_audit.py'\n")
        self.assertIn('No workflow runs `method_audit.py`', self.check('--remote', '--repo', 'o/r', code=1))
        audit.unlink()
        self.assertIn('No workflow runs `method_audit.py`', self.check('--remote', '--repo', 'o/r', code=1))

    def test_warns_without_the_scheduled_stuck_pr_check(self):
        self.assertIn('PASS: The scheduled stuck-PR check watches open PRs', self.check('--remote', '--repo', 'o/r'))
        health = self.root / '.github' / 'workflows' / 'jfactory-pr-health.yml'
        # Manual only, or scheduled without --act (a report that changes nothing), does not count.
        health.write_text(health.read_text().replace("  schedule:\n    - cron: '*/30 * * * *'\n", ''))
        self.assertIn('WARN: No scheduled workflow runs `pr_health.py --act`', self.check('--remote', '--repo', 'o/r'))
        shutil.copy(ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-pr-health.yml', health)
        health.write_text(health.read_text().replace(' --act', ''))
        self.assertIn('WARN: No scheduled workflow runs `pr_health.py --act`', self.check('--remote', '--repo', 'o/r'))
        health.unlink()
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('WARN: No scheduled workflow runs `pr_health.py --act`', out)
        self.assertIn('install templates/jfactory-pr-health.yml', out)

    def test_only_an_executed_audit_command_counts(self):
        head = "on:\n  schedule:\n    - cron: '0 7 * * 1'\njobs:\n  a:\n    runs-on: ubuntu-latest\n    steps:\n"
        script = '.agents/skills/jfactory/scripts/method_audit.py --repo o/r'
        runs = {
            # Operators inside comments or quoted text start no command.
            f'      - run: |\n          # prepare; python3 {script}\n          echo no-audit\n': False,
            f"      - run: echo 'To audit; python3 {script}'\n": False,
            f'      - run: echo "a && python3 {script}"\n': False,
            f'      - run: echo python3 {script}\n': False,
            f"      - run: echo ';' python3 {script}\n": False,
            f"      - run: |\n          echo 'Example:\n          python3 {script}\n          '\n": False,
            f'      - run: |\n          cat <<EOF\n          python3 {script}\n          EOF\n': False,
            f"      - run: |\n          echo 'unclosed\n          python3 {script}\n": False,
            f'      - run: echo a\\;python3 {script}\n': False,
            # A here-document ends only at a line that is exactly its delimiter (<<- strips leading tabs only).
            f'      - run: |\n          cat <<EOF\n           EOF\n          python3 {script}\n          EOF\n': False,
            f'      - run: |\n          cat <<EOF\n          EOF \n          python3 {script}\n          EOF\n': False,
            f'      - run: |\n          cat <<-EOF\n           EOF\n          python3 {script}\n          EOF\n': False,
            f'      - run: |\n          cat <<EOF\n          text\n          EOF\n          python3 {script}\n': True,
            f'      - run: |\n          cat <<-EOF\n          text\n          \t\tEOF\n          python3 {script}\n': True,
            # Real invocations, however they are written.
            f'      - run: python3 {script}\n': True,
            f"      - run: 'python3 {script}'\n": True,
            f'      - run: "python3 {script}"\n': True,
            f'      - run: |\n          set -e\n          cd x && GH_TOKEN=t python3 -u {script} # weekly\n': True,
            f'      - run: >-\n          python3\n          {script}\n': True,
            f'      - run: |\n          python3 \\\n            {script}\n': True,
        }
        for run, expected in runs.items():
            self.assertEqual(setup_check.runs_method_audit(head + run), expected, run)
        # End to end: a false closing delimiter cannot make setup report an executing audit.
        audit = self.root / '.github' / 'workflows' / 'jfactory-method-audit.yml'
        for false_end in (' EOF', 'EOF '):
            audit.write_text(head + f'      - run: |\n          cat <<EOF\n          {false_end}\n          python3 {script}\n'
                                    '          EOF\n')
            self.assertIn('No workflow runs `method_audit.py`', self.check('--remote', '--repo', 'o/r', code=1))

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
        self.assertIn('FAIL: Map: 1 tracked file(s) match no feature', out)

    def test_gate_workflow_must_read_ci_results(self):
        workflow = self.root / '.github' / 'workflows' / 'jfactory-verified.yml'
        workflow.write_text(workflow.read_text().replace('  checks: read\n', ''))
        self.assertIn('lacks `checks: read`', self.check('--remote', '--repo', 'o/r', code=1))

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
            {'static': ['README.md'], 'features': {'app': {'paths': ['src/**', 'AGENTS.md', '.jfactory/**', '.github/**', 'outcomes/**'],
                                                           'verify': 'independent'}}}))
        self.assertIn('Risk levels set: 1 independent, 0 review, 0 CI-only', self.check('--remote', '--repo', 'o/r'))

    def mapping(self, **extra):
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(
            {'static': ['README.md'], 'always_suites': ['unit'], **extra,
             'features': {'app': {'paths': ['src/**', 'AGENTS.md', '.jfactory/**', '.github/**', 'outcomes/**'], 'verify': 'independent',
                                  'suites': ['e2e-app']}}}))

    def test_per_pr_cost_must_fit_the_budget(self):
        timed = lambda **minutes: {name: {'run': 'true', 'minutes': m} for name, m in minutes.items()}
        self.mapping(suites=timed(unit=2, **{'e2e-app': 5}))
        self.assertIn('No journey suite runs on every PR; no per-PR time limit is set', self.check('--remote', '--repo', 'o/r'))
        self.mapping(pr_budget_minutes=10, suites=timed(unit=2, **{'e2e-app': 5}))
        self.assertIn('PASS: Map: Every single-area change fits the 10 min budget', self.check('--remote', '--repo', 'o/r'))
        self.mapping(pr_budget_minutes=10, suites=timed(unit=2))
        self.assertIn('Suite(s) e2e-app are used but not defined', self.check('--remote', '--repo', 'o/r', code=1))
        self.mapping(pr_budget_minutes=10, suites=timed(unit=2, **{'e2e-app': 45}))
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('WARN: Map: These changes exceed the 10 min per-PR budget: AGENTS.md -> app (47 min)', out)
        # Suites that together exceed the budget need the change-aware CI job.
        self.assertIn('no workflow runs `verify_plan.py ci`', out)
        shutil.copy(ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-checks.yml',
                    self.root / '.github' / 'workflows' / 'jfactory-checks.yml')
        self.assertNotIn('no workflow runs', self.check('--remote', '--repo', 'o/r'))
        # The whole browser suite on every PR is the misconfiguration this check exists for.
        self.mapping(pr_budget_minutes=10, suites=timed(unit=2, e2e=45, **{'e2e-app': 5}), always_suites=['unit', 'e2e'])
        self.assertIn('FAIL: Map: Suites that run on every PR take 47 min', self.check('--remote', '--repo', 'o/r', code=1))
        # Live-model suites stay off PRs, so a scheduled workflow must run them.
        self.mapping(pr_budget_minutes=10, suites=timed(unit=2, **{'e2e-app': 5}))
        config = json.loads((self.root / '.jfactory' / 'verification.json').read_text())
        config['suites']['e2e-app']['live_model'] = True
        (self.root / '.jfactory' / 'verification.json').write_text(json.dumps(config))
        missing = 'no scheduled workflow runs `verify_plan.py ci --live`'
        self.assertIn(missing, self.check('--remote', '--repo', 'o/r', code=1))
        live = self.root / '.github' / 'workflows' / 'jfactory-live-suites.yml'
        template = (ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-live-suites.yml').read_text()
        # Found by the PR #45 verifier: a comment, a manual-only trigger or a disabled job runs nothing.
        live.write_text("on:\n  workflow_dispatch:\njobs:\n  x:\n    steps:\n      - run: echo hi  # python3 verify_plan.py ci --live\n")
        self.assertIn(missing, self.check('--remote', '--repo', 'o/r', code=1))
        live.write_text(template.replace("  schedule:\n    # Mondays, off the hour to avoid the scheduler's peak.\n    - cron: '23 5 * * 1'\n", ''))
        self.assertIn(missing, self.check('--remote', '--repo', 'o/r', code=1))
        live.write_text(template.replace('  live:\n', '  live:\n    if: false\n'))
        self.assertIn(missing, self.check('--remote', '--repo', 'o/r', code=1))
        # Found by the PR #45 re-check: a job guard that skips scheduled events must not count, and an unrelated
        # disabled step must not discount a live job that does run.
        live.write_text(template.replace("  live:\n", "  live:\n    if: ${{ github.event_name == 'workflow_dispatch' }}\n"))
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn("it runs only when `github.event_name == 'workflow_dispatch'`", out)
        live.write_text(template + '  # This job should not execute on schedule\n    if: false\n')
        self.assertIn('it runs only when `false`', self.check('--remote', '--repo', 'o/r', code=1))
        live.write_text(template.replace("      - uses: actions/checkout@v4\n",
                                         "      - name: Disabled optional diagnostics\n        if: false\n"
                                         "        run: echo diagnostic\n      - uses: actions/checkout@v4\n", 1))
        self.assertNotIn('ci --live', self.check('--remote', '--repo', 'o/r'))
        live.write_text(template)
        self.assertNotIn('ci --live', self.check('--remote', '--repo', 'o/r'))

    def test_scheduled_run_follows_the_conditions_on_its_own_job_and_step(self):
        head = "on:\n  schedule:\n    - cron: '0 6 * * 1'\njobs:\n"
        run = 'python3 x/verify_plan.py ci --live'
        cases = {
            f'  live:\n    runs-on: ubuntu-latest\n    steps:\n      - run: {run}\n': (True, None),
            f'  live:\n    if: false\n    steps:\n      - run: {run}\n': (False, 'false'),
            f'  live:\n    steps:\n      - name: Live\n        if: github.ref == \'refs/heads/dev\'\n        run: {run}\n':
                (False, "github.ref == 'refs/heads/dev'"),
            f'  live:\n    steps:\n      - if: always()\n        run: {run}\n': (True, None),
            f'  other:\n    if: false\n    steps:\n      - run: echo hi\n  live:\n    steps:\n      - run: {run}\n':
                (True, None),
            f'  live:\n    steps:\n      - run: echo {run}\n': (False, None),
            # Found by the third PR #45 check: a job's keys are unordered, so a guard after its steps still applies.
            f'  live:\n    steps:\n      - run: {run}\n    if: false\n': (False, 'false'),
            f"  live:\n    steps:\n      - run: {run}\n    if: ${{{{ github.event_name == 'workflow_dispatch' }}}}\n":
                (False, "github.event_name == 'workflow_dispatch'"),
            f'  live:\n    steps:\n      - run: {run}\n  later:\n    if: false\n    steps:\n      - run: echo hi\n':
                (True, None),
            # Found by the fourth PR #45 check: a comment never ends a job or a step.
            f'  live:\n    steps:\n      - run: {run}\n  # This job should not execute on schedule\n    if: false\n':
                (False, 'false'),
            f"  live:\n    steps:\n      - run: {run}\n# note\n    if: ${{{{ github.event_name == 'workflow_dispatch' }}}}\n":
                (False, "github.event_name == 'workflow_dispatch'"),
            f'  live:\n    steps:\n      - name: Live\n# note\n        if: false  # off for now\n        run: {run}\n':
                (False, 'false'),
            f'  live:\n    if: always()  # keep running\n    steps:\n      - run: {run}\n': (True, None),
        }
        for jobs, (expected, condition) in cases.items():
            ok, why = setup_check.scheduled_run(head + jobs, 'verify_plan.py', 'ci', '--live')
            self.assertEqual(ok, expected, jobs)
            self.assertEqual(condition is not None and condition in (why or ''), condition is not None, (jobs, why))
        self.assertEqual(setup_check.scheduled_run(head.replace('schedule', 'workflow_dispatch') + list(cases)[0],
                                                   'verify_plan.py', 'ci', '--live'), (False, None))
        # Shapes found while checking the fourth PR #45 finding's neighbours.
        for jobs in (f'  live:\n    "if": false\n    steps:\n      - run: {run}\n',
                     f'  live:\n    <<: *guarded\n    steps:\n      - run: {run}\n'):
            self.assertFalse(setup_check.scheduled_run(head + jobs, 'verify_plan.py', 'ci', '--live')[0], jobs)
        not_a_trigger = ('on:\n  workflow_dispatch:\n    inputs:\n      schedule:\n        description: x\n'
                         'jobs:\n  live:\n    steps:\n      - name: x\n        with:\n          list:\n'
                         f'            - cron: x\n        run: {run}\n')
        self.assertEqual(setup_check.scheduled_run(not_a_trigger, 'verify_plan.py', 'ci', '--live'), (False, None))
        # Found by the fifth PR #45 check: multi-line flow mappings hide their keys from a line reader, so they
        # fail closed, while braces in scripts, quoted strings and expressions do not count as structure.
        flow_job = (f'  live: {{if: false,\n    runs-on: ubuntu-latest,\n    steps: [\n      {{\n'
                    f'        run: "{run}"\n      }}\n    ]\n  }}\n')
        flow_step = (f'  live:\n    runs-on: ubuntu-latest\n    steps:\n      - {{\n          if: false,\n'
                     f'          run: "{run}"\n        }}\n')
        self.assertFalse(setup_check.scheduled_run(
            head + f'  live:\n    steps:\n      - {{if: false,\n         run: "{run}"}}\n',
            'verify_plan.py', 'ci', '--live')[0])
        for jobs in (flow_job, flow_step):
            ok, why = setup_check.scheduled_run(head + jobs, 'verify_plan.py', 'ci', '--live')
            self.assertFalse(ok, jobs)
            self.assertIn('flow-style mapping', why or '', jobs)
        braces = (f"  live:\n    if: ${{{{ !cancelled() }}}}\n    env:\n      X: '{{not a mapping}}'\n    steps:\n"
                  f'      - run: |\n          f() {{ echo "${{HOME}}"; }}\n          {run}\n')
        self.assertEqual(setup_check.scheduled_run(head + braces, 'verify_plan.py', 'ci', '--live'), (True, None))
        quoted = "'on':\n  schedule:\n    - cron: '0 6 * * 1'\njobs:\n" + list(cases)[0]
        self.assertEqual(setup_check.scheduled_run(quoted, 'verify_plan.py', 'ci', '--live'), (True, None))
        flow = head.replace('jobs:\n', '') + 'jobs: {live: {steps: [{run: "' + run + '"}]}}\n'
        ok, why = setup_check.scheduled_run(flow, 'verify_plan.py', 'ci', '--live')
        self.assertFalse(ok, 'A structure the reader cannot follow is not reported as scheduled')

    def test_targets_need_a_fresh_start_up_receipt(self):
        target = {'local': {'start': 'npm start', 'ready': 'http://127.0.0.1:$PORT/', 'auth': 'none'}}
        self.mapping(pr_budget_minutes=10, suites={'unit': {'run': 'true', 'minutes': 1},
                                                   'e2e-app': {'run': 'true', 'minutes': 2, 'target': 'local'}},
                     targets=target)
        out = self.check('--remote', '--repo', 'o/r', code=1)
        self.assertIn('FAIL: Target local has no passing start-up receipt', out)
        self.assertIn('The map has journey suites (e2e-app) but no workflow runs `verify_plan.py ci`', out)
        shutil.copy(ROOT / 'skills' / 'jfactory' / 'templates' / 'jfactory-checks.yml',
                    self.root / '.github' / 'workflows' / 'jfactory-checks.yml')
        receipt = {'ok': False, 'steps': [{'step': 'doctor', 'ok': False, 'detail': '`npm run doctor` exited 1'}]}
        (self.root / '.jfactory' / 'smoke.json').write_text(json.dumps({'local': receipt}))
        self.assertIn('(failed at doctor: `npm run doctor` exited 1)', self.check('--remote', '--repo', 'o/r', code=1))
        (self.root / '.jfactory' / 'smoke.json').write_text(json.dumps({'local': {'ok': True, 'fresh': False}}))
        self.assertIn('FAIL: Target local started only in an existing checkout',
                      self.check('--remote', '--repo', 'o/r', code=1))
        states = {**READY, 'Verification': ('configured but unverified', 'fresh workspace pending')}
        (self.root / '.jfactory' / 'setup.md').write_text(record(states=states))
        self.assertIn('WARN: Target local started only in an existing checkout', self.check('--remote', '--repo', 'o/r', code=3))
        (self.root / '.jfactory' / 'setup.md').write_text(record())
        (self.root / '.jfactory' / 'smoke.json').write_text(json.dumps(
            {'local': {'ok': True, 'fresh': True, 'commit': 'abcdef1234', 'at': '2026-09-29T00:00:00Z'}}))
        self.assertIn('PASS: Target local started in a fresh workspace at abcdef1', self.check('--remote', '--repo', 'o/r'))

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

    def test_ci_workflows_can_move_to_machines_the_owner_runs(self):
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('PASS: CI workflows choose their runner from the JFACTORY_RUNNER variable', out)
        self.assertNotIn('billed runners', out)
        gate = self.root / '.github' / 'workflows' / 'jfactory-verified.yml'
        template = gate.read_text()
        gate.write_text(re.sub(r'runs-on: .*', 'runs-on: ubuntu-latest', template))
        out = self.check('--remote', '--repo', 'o/r')
        self.assertIn('WARN: These CI jobs have a fixed runner', out)
        self.assertIn('.github/workflows/jfactory-verified.yml:', out)
        # Reading the variable without the fork guard would let a fork PR run on the owner's machines.
        gate.write_text(re.sub(r'runs-on: .*', "runs-on: ${{ fromJSON(vars.JFACTORY_RUNNER || '\"ubuntu-latest\"') }}", template))
        self.assertIn('send fork PRs to the JFACTORY_RUNNER machines', self.check('--remote', '--repo', 'o/r', code=1))
        gate.write_text(template)

        state = json.loads(self.state.read_text())
        state['repo'] = {**state['repo'], 'private': True}
        self.state.write_text(json.dumps(state))
        self.assertIn("CI runs on GitHub's billed runners", self.check('--remote', '--repo', 'o/r'))
        record_path = self.root / '.jfactory' / 'setup.md'
        record_path.write_text(record_path.read_text() + '\nCI runners: GitHub-hosted (owner, public budget is fine)\n')
        self.assertNotIn("billed runners", self.check('--remote', '--repo', 'o/r'))

        state = json.loads(self.state.read_text())
        state['variables'] = {'JFACTORY_RUNNER': '["self-hosted","jfactory"]'}
        self.state.write_text(json.dumps(state))
        self.assertIn('but no such runner is online', self.check('--remote', '--repo', 'o/r'))
        state['runners'] = [{'name': 'a', 'status': 'offline', 'labels': [{'name': 'self-hosted'}, {'name': 'jfactory'}]},
                            {'name': 'b', 'status': 'online', 'labels': [{'name': 'self-hosted'}, {'name': 'other'}]}]
        self.state.write_text(json.dumps(state))
        self.assertIn('but no such runner is online', self.check('--remote', '--repo', 'o/r'))
        state['runners'].append({'name': 'c', 'status': 'online',
                                 'labels': [{'name': 'self-hosted'}, {'name': 'jfactory'}]})
        self.state.write_text(json.dumps(state))
        self.assertIn('PASS: CI runs on machines the owner runs: 1 runner(s) online', self.check('--remote', '--repo', 'o/r'))
        state['variables'] = {'JFACTORY_RUNNER': 'self-hosted'}
        self.state.write_text(json.dumps(state))
        self.assertIn('JFACTORY_RUNNER is not JSON', self.check('--remote', '--repo', 'o/r', code=1))

    def test_a_standing_release_after_merge_records_who_decided(self):
        coordination = self.root / '.jfactory' / 'coordination.json'
        config = json.loads(coordination.read_text())
        coordination.write_text(json.dumps({**config, 'release_after_merge': {'owner': 'Ana'}}))
        self.assertIn('must record the owner and date', self.check('--remote', '--repo', 'o/r', code=1))
        coordination.write_text(json.dumps({**config, 'release_after_merge': {
            'owner': 'Ana', 'date': '2026-10-02', 'until': 'the first customer'}}))
        self.assertIn('Every verified merge is released to production (owner Ana, 2026-10-02, until the first customer)',
                      self.check('--remote', '--repo', 'o/r'))


if __name__ == '__main__':
    unittest.main()

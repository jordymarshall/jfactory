import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / 'skills/jfactory/scripts/claude_subagent_guard.py'
spec = importlib.util.spec_from_file_location('guard', SCRIPT)
guard = importlib.util.module_from_spec(spec)
spec.loader.exec_module(guard)


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = self.tmp.name

    def hook(self, tool_input, tool_name='Agent'):
        event = {'tool_name': tool_name, 'tool_input': tool_input, 'cwd': self.root}
        proc = subprocess.run([sys.executable, str(SCRIPT)], input=json.dumps(event), capture_output=True,
                              text=True, check=True)
        return json.loads(proc.stdout) if proc.stdout.strip() else None

    def test_read_only_agents_run(self):
        for kind in ('Explore', 'Plan'):
            self.assertIsNone(self.hook({'subagent_type': kind, 'prompt': 'find x'}))
        self.assertIsNone(self.hook({'command': 'ls'}, tool_name='Bash'))

    def test_agents_that_can_write_are_denied_with_the_workspace_route(self):
        for tool_input in ({'prompt': 'build it'}, {'subagent_type': 'general-purpose'},
                           {'subagent_type': 'Explore', 'isolation': 'worktree'}):
            out = self.hook(tool_input, tool_name='Task' if 'isolation' in tool_input else 'Agent')
            decision = out['hookSpecificOutput']
            self.assertEqual(decision['permissionDecision'], 'deny')
            self.assertIn('coord.py', decision['permissionDecisionReason'])
            self.assertIn('Explore', decision['permissionDecisionReason'])

    def test_repository_adds_its_own_read_only_types(self):
        (Path(self.root) / '.jfactory').mkdir()
        (Path(self.root) / '.jfactory' / 'coordination.json').write_text(
            json.dumps({'read_only_subagents': ['code-reviewer']}))
        self.assertIsNone(self.hook({'subagent_type': 'code-reviewer'}))
        self.assertIsNotNone(self.hook({'subagent_type': 'general-purpose'}))

    def test_malformed_input_never_blocks(self):
        proc = subprocess.run([sys.executable, str(SCRIPT)], input='not json', capture_output=True, text=True)
        self.assertEqual((proc.returncode, proc.stdout), (0, ''))


if __name__ == '__main__':
    unittest.main()

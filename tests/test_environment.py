"""Environment claims must come from a checked operation, not a constant label."""
import ast
import os
from pathlib import Path
import re
import subprocess
import sys
import unittest
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'src'))
import experiment_env


class EnvironmentTests(unittest.TestCase):
    def test_nonlinux_requires_explicit_opt_in(self):
        with patch.object(experiment_env.sys, 'platform', 'owned-unsupported'), \
             patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RuntimeError): experiment_env.configure()

    def test_portable_never_claims_linux_limits(self):
        with patch.object(experiment_env.sys, 'platform', 'owned-unsupported'), \
             patch.dict(os.environ, {'CALENDARISO_PORTABLE':'1'}, clear=True), \
             patch.object(experiment_env, 'pin_current_process', return_value={'status':'unsupported-unpinned'}):
            mode=experiment_env.configure()
            self.assertEqual(mode['mode'],'portable-explicit')
            self.assertIsNone(mode['address_space_limit_bytes'])
            self.assertIsNone(mode['cpu_limit_seconds'])
            self.assertIsNone(experiment_env.peak_rss_kib())

    def test_runner_help_imports_without_linux_resource(self):
        command=[sys.executable,'-B',str(Path(__file__).resolve().parents[1]/'reproduce.py'),'--help']
        result=subprocess.run(command,capture_output=True,text=True,timeout=10)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertIn('--portable',result.stdout)
        # The CI parent must not forbid the runner's own hard CPU ceiling.
        root=Path(__file__).resolve().parents[1]
        runner=ast.parse((root/'reproduce.py').read_text(encoding='utf-8'))
        hard_limits=[ast.literal_eval(keyword.value)
                     for call in ast.walk(runner) if isinstance(call,ast.Call)
                     and isinstance(call.func,ast.Name) and call.func.id=='configure'
                     for keyword in call.keywords if keyword.arg=='cpu_hard']
        self.assertEqual(len(hard_limits),1)
        workflow=(root/'.github/workflows/scientific-checks.yml').read_text(encoding='utf-8')
        parent_limits=re.findall(r'^\s*ulimit -t (\d+)\s*$',workflow,re.MULTILINE)
        self.assertEqual(len(parent_limits),1)
        self.assertGreaterEqual(int(parent_limits[0]),hard_limits[0])


if __name__=='__main__': unittest.main(verbosity=2)

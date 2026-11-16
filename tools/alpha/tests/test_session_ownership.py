"""Exercise the launcher's actual exit worker without importing/starting its UI."""
import ast
import datetime
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import diagnostics


class SessionOwnership(unittest.TestCase):
    def run_exit(self, code, changed):
        path = Path(__file__).resolve().parents[1] / 'launcher/launcher.py'
        tree = ast.parse(path.read_text(encoding='utf-8'))
        start = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == 'start_game')
        worker = next(n for n in start.body if isinstance(n, ast.FunctionDef) and n.name == 'wait')
        launcher = SimpleNamespace(cfg={'last_performance': {'previous': True}},
                                   after=Mock(), crash_info=Mock())
        session = Mock(return_value=[])
        namespace = dict(self=launcher, p=Mock(wait=Mock(return_value=code)), log=Mock(),
                         run={'record': {'runtime_log_updated': changed}}, game=Path('unused'),
                         diagnostics=SimpleNamespace(finish=Mock(), STARTUP_BLOCKED=diagnostics.STARTUP_BLOCKED),
                         session_from_game_log=session, game_settings=Mock(read=Mock(return_value={})),
                         performance=Mock(summarize=Mock(return_value=None)),
                         advisor=Mock(diagnose=Mock(return_value=[])), UI_LANG=['en'], save_settings=Mock(),
                         datetime=datetime)
        exec(compile(ast.Module(body=[worker], type_ignores=[]), str(path), 'exec'), namespace)
        namespace['wait']()
        return launcher, session, namespace

    def test_blocked_start_keeps_previous_report_even_when_other_log_changed(self):
        for code in diagnostics.STARTUP_BLOCKED:
            launcher, session, scope = self.run_exit(code, True)
            session.assert_not_called()
            launcher.crash_info.assert_not_called()
            scope['advisor'].diagnose.assert_not_called()
            self.assertEqual(launcher.cfg['last_performance'], {'previous': True})

    def test_no_new_runtime_log_does_not_reuse_previous_measurement(self):
        launcher, session, _ = self.run_exit(0, False)
        session.assert_not_called()
        self.assertIsNone(launcher.cfg['last_performance'])

    def test_failed_start_does_not_put_old_errors_in_crash_notice(self):
        launcher, session, _ = self.run_exit(3, False)
        session.assert_not_called()
        launcher.crash_info.assert_called_once_with(3, runtime_log_updated=False)

    def test_normal_session_still_reads_new_log(self):
        launcher, session, _ = self.run_exit(0, True)
        session.assert_called_once()
        launcher.crash_info.assert_not_called()


if __name__ == '__main__':
    unittest.main()

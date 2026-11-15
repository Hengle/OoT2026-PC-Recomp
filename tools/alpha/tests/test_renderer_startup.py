"""Black screen with working audio: missing graphics support is not a normal run."""
import ast
import json
from pathlib import Path
import sys
import tempfile
import unittest

ALPHA = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ALPHA / 'launcher'))
import advisor
import diagnostics
import performance
from test_performance import sample


FAILED_START = [
    '[hos host] vk: device 0: Microsoft Direct3D12 (Qualcomm Adreno), Vulkan 1.2, driver 0x1, type 1',
    '[hos host] vk: device 1: Microsoft Direct3D12 (Microsoft Basic Render Driver), Vulkan 1.2, driver 0x1, type 4',
    '[hos host] vk: no Vulkan 1.3 GPU',
    '[hos host] vk: pick_device failed',
    '[hos host] display: no WebGPU device: the window stays black',
    '[hos Presentation Thread] vi: frames presented (60 fps)',
]


class RendererStartupTests(unittest.TestCase):
    def test_terminal_failure_gets_driver_advice_without_fps_samples(self):
        failure = performance.renderer_startup_failure(FAILED_START)
        self.assertEqual(failure['reason'], 'vulkan_1_3_unavailable')
        self.assertTrue(any('Microsoft Direct3D12' in line for line in failure['evidence']))
        for de in (False, True):
            advice = advisor.diagnose(FAILED_START, de=de)
            self.assertEqual(len(advice), 1)
            self.assertEqual(advice[0][0], 'warn')
        english = advisor.diagnose(FAILED_START, de=False)[0][1]
        self.assertIn('Vulkan 1.3', english)
        self.assertIn('cannot add', english)
        self.assertIsNone(performance.summarize(FAILED_START))

    def test_rejected_or_old_adapter_alone_is_not_a_failed_session(self):
        for lines in (FAILED_START[:4], FAILED_START[:2] + [sample()],
                      ['vk: preferred device 0 not available or lacks Vulkan 1.3, falling back to auto selection'],
                      FAILED_START + [sample()]):
            self.assertIsNone(performance.renderer_startup_failure(lines))
            self.assertFalse(any('No Vulkan 1.3' in text for _, text in advisor.diagnose(lines, de=False)))

    def test_generic_failure_does_not_invent_vulkan_version_cause(self):
        failure = performance.renderer_startup_failure(FAILED_START[4:])
        self.assertEqual(failure['reason'], 'no_graphics_device')
        text = performance.renderer_failure_advice(failure, de=False)[0][1]
        self.assertNotIn('Vulkan 1.3', text)
        self.assertIn('Debug Package', text)

    def test_old_loader_and_zero_draws(self):
        lines = ['vk: the Vulkan loader is 1.2: 1.3 is needed'] + FAILED_START[4:] + [sample(draws=0)]
        self.assertEqual(performance.renderer_startup_failure(lines)['reason'], 'vulkan_1_3_unavailable')

    def test_launcher_collector_retains_startup_failure(self):
        source = ALPHA / 'launcher' / 'launcher.py'
        tree = ast.parse(source.read_text(encoding='utf-8'))
        nodes = [n for n in tree.body if
                 (isinstance(n, ast.FunctionDef) and n.name == 'session_from_game_log') or
                 (isinstance(n, ast.Assign) and any(isinstance(t, ast.Name) and t.id == 'SESSION_KEEP' for t in n.targets))]
        namespace = {'Path': Path, 'performance': performance}
        exec(compile(ast.Module(body=nodes, type_ignores=[]), str(source), 'exec'), namespace)
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, 'ocarina_reborn_log.txt').write_text('\n'.join(FAILED_START), encoding='utf-8')
            lines = namespace['session_from_game_log'](tmp)
        self.assertIn('not in the game log', lines[0])  # Enumerated adapters are not the active GPU.
        self.assertEqual(advisor.diagnose(lines, de=False)[0][0], 'warn')
        self.assertEqual(performance.renderer_startup_failure(lines)['reason'], 'vulkan_1_3_unavailable')

    def test_exit_zero_after_long_black_screen_keeps_startup_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            Path(tmp, 'ocarina_reborn_log.txt').write_text('\n'.join(FAILED_START) + '\n' +
                'audio and guest logic still running\n' * 6000, encoding='utf-8')
            diagnostics.finish(run, 0, folder)
            record = json.loads(run['path'].read_text(encoding='utf-8'))
            self.assertEqual(record['result'], 'renderer_initialization_failed')
            self.assertEqual(record['exit_code'], 0)
            self.assertEqual(record['renderer_startup_error']['reason'], 'vulkan_1_3_unavailable')
            self.assertFalse(any('Vulkan' in line for line in record['last_runtime_lines']))

    def test_stale_log_and_process_launch_error_do_not_blame_graphics(self):
        for launch_error in (False, True):
            with self.subTest(launch_error=launch_error), tempfile.TemporaryDirectory() as tmp:
                folder = Path(tmp)
                log = folder / 'ocarina_reborn_log.txt'
                log.write_text('\n'.join(FAILED_START), encoding='utf-8')
                run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
                if launch_error:
                    run['record']['launch_error'] = 'test launch error'
                    log.write_text('\n'.join(FAILED_START) + '\nchanged', encoding='utf-8')
                diagnostics.finish(run, -1 if launch_error else 0, folder)
                self.assertIsNone(run['record']['renderer_startup_error'])
                self.assertEqual(run['record']['result'], 'launch_failed' if launch_error else 'normal_exit')

    def test_native_failure_remains_primary_for_abnormal_exit(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            Path(tmp, 'ocarina_reborn_log.txt').write_text('\n'.join(FAILED_START), encoding='utf-8')
            run['native'].write_text('FAILURE: CRT abort (SIGABRT)\n', encoding='utf-8')
            diagnostics.finish(run, 3, folder)
            self.assertEqual(run['record']['result'], 'native_failure_recorded')
            self.assertEqual(run['record']['renderer_startup_error']['reason'], 'vulkan_1_3_unavailable')


if __name__ == '__main__':
    unittest.main()

"""A GPU watchdog stop must survive diagnosis without claiming driver device loss."""
import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'launcher'))
import advisor
import diagnostics
import performance
from test_performance import sample

HANG = [
    '[hos host] vk: the GPU has finished nothing for 30 s: the timeline at 1603474, 1603481 sent (RX_VK_GPU_HANG_SEC=30)',
    '[hos host] vk: GPU hang: the timeline at 1603474, 1603481 sent',
    '[hos host] vk: device lost: reading the fault info (RX_VK_CHECKPOINTS=1 for markers)',
    '[hos host] vk: FATAL: the GPU hung: no submission finished in 30 s, and the driver never reported the device lost',
    'vk: FATAL: the GPU hung: no submission finished in 30 s, and the driver never reported the device lost',
]


class GpuHangTests(unittest.TestCase):
    def test_real_watchdog_log_counted_once_without_inventing_device_loss(self):
        result = performance.gpu_failures(HANG)
        self.assertEqual(result, dict(device_memory_errors=0, device_lost_errors=0, gpu_hangs=1))
        self.assertEqual(performance.gpu_failures(HANG[-2:])['gpu_hangs'], 1)

    def test_stall_warning_or_startup_configuration_is_not_a_watchdog_stop(self):
        lines = [HANG[0], HANG[2], 'vk: GPU hang watch: work that finishes nothing for 30 s ends the game',
                 'vk: GPU hang watch: a stall is only logged (RX_VK_GPU_HANG_SEC=0)',
                 'exit code 3 (0x3)']
        self.assertFalse(any(performance.gpu_failures(lines).values()))

    def test_advice_with_or_without_valid_fps_and_both_languages(self):
        for fps in ([], [sample()] * 6):
            for de in (False, True):
                with self.subTest(fps=bool(fps), de=de):
                    messages = advisor.diagnose(fps + HANG, de=de)
                    self.assertEqual(messages[0][0], 'warn')
                    self.assertIn('Watchdog' if de else 'watchdog', messages[0][1])
                    self.assertIn('Frame Generation' if de else 'frame generation', messages[0][1])
        self.assertEqual(performance.summarize([sample()] * 6 + HANG)['gpu_hangs'], 1)

    def test_saved_session_classifies_failure_and_ignores_old_log(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            run = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            (folder / 'ocarina_reborn_log.txt').write_text('\n'.join(HANG))
            diagnostics.finish(run, 3, folder)
            record = json.loads(run['path'].read_text())
            self.assertEqual(record['result'], 'gpu_hang_watchdog')
            self.assertEqual(record['gpu_errors']['gpu_hangs'], 1)
            self.assertIn('not established', record['note'])
            old = diagnostics.start(folder / 'reports', folder, {}, {}, {}, {})
            diagnostics.finish(old, 3, folder)
            self.assertEqual(old['record']['result'], 'nonzero_exit_without_recorded_cause')
            self.assertEqual(old['record']['gpu_errors']['gpu_hangs'], 0)


if __name__ == '__main__':
    unittest.main()

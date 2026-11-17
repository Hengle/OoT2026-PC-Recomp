"""Reproduce the v1.1.4 startup guard after the historical performance recipe."""
from pathlib import Path
import re
import shutil


def apply(root):
    root = Path(root)
    path = root / 'host/hos_main.c'
    text = path.read_text(encoding='utf-8')
    if '#include "ocr_instance.h"' not in text:
        include = '#include "hos_paths.h"\n'
        start = '    if (!narrow_paths_ok(argc, argv)) return 1;\n'
        if text.count(include) != 1 or text.count(start) != 1:
            raise ValueError('Startup guard: unsupported host source')
        text, count = re.subn(r'#ifdef _WIN32\n        \{   /\* \(started again by the Insert menu.*?\n#endif\n',
                             '', text, count=1, flags=re.S)
        if count != 1:
            raise ValueError('Startup guard: previous restart-wait block not found')
        text = text.replace(include, include + '#include "ocr_instance.h"\n')
        text = text.replace(start, start + '    {\n        const int startup = ocr_instance_enter(argc, argv);\n'
                                         '        if (startup) return startup;\n    }\n')
    if 'ocr_instance_enter(argc, argv)' not in text or 'HOS_RESTART_OF' in text:
        raise ValueError('Startup guard: incomplete patch')
    path.write_text(text, encoding='utf-8', newline='\n')
    shutil.copyfile(Path(__file__).parent / 'hud/ocr_instance.h', root / 'host/ocr_instance.h')

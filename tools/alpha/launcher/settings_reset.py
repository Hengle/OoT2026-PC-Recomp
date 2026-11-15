"""Reset preferences with backups; installation, saves and installed content stay."""
from pathlib import Path
import datetime
import json
import os
import tempfile
import classic_voices

KEEP = ('game_dir', 'backup_dir', 'dlss_sdk')

def _write(path, data):
    path=Path(path)
    fd, temp=tempfile.mkstemp(prefix=path.name+'.',suffix='.tmp',dir=path.parent)
    try:
        with os.fdopen(fd,'wb') as f: f.write(data)
        os.replace(temp,path)
    finally:
        Path(temp).unlink(missing_ok=True)

def reset_all(game, settings_file, current, defaults):
    game, settings_file=Path(game),Path(settings_file)
    backup=settings_file.parent/'SettingsBackups'/datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
    backup.mkdir(parents=True)
    # Clear all options, including F1 keyboard/gamepad bindings and unknown future
    # settings; never touch the user/ save directory, ready.json or shader caches.
    files=[game/name for name in ('ocarina_reborn_options.ini','hookshot_options.ini','ocarina_reborn_env.txt','hookshot_env.txt','language.txt') if (game/name).is_file()]
    originals={p:p.read_bytes() for p in files}
    originals[settings_file]=settings_file.read_bytes() if settings_file.exists() else None
    for p,data in originals.items():
        if data is not None:(backup/p.name).write_bytes(data)
    voices={age:classic_voices.status(game,age)['enabled'] for age in classic_voices.AGES}
    (backup/'voice-settings.json').write_text(json.dumps(voices),encoding='utf-8')
    fresh=dict(defaults)
    fresh.update({k:current[k] for k in KEEP if k in current})
    try:
        for age in voices:classic_voices.set_enabled(game,age,False)
        for p in files:
            _write(p,(str(fresh.get('language','en-US'))+'\n').encode('utf-8') if p.name=='language.txt'
                   else b'# Preferences reset to defaults.\n')
        _write(settings_file,(json.dumps(fresh,indent=2)+'\n').encode('utf-8'))
    except Exception:
        for p,data in originals.items():
            if data is None:p.unlink(missing_ok=True)
            else:_write(p,data)
        for age,enabled in voices.items():classic_voices.set_enabled(game,age,enabled)
        raise
    return fresh,backup

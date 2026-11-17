"""Install one unmodified Classic UI variant from its author's GameBanana archive.

No mod assets are shipped. Pinned ZIP directories let us fetch only the selected
variant (about 80 MB), instead of all twelve variants (about 950 MB). HTTPS,
directory SHA-256, exact ranges, local headers and member CRCs are checked.
"""
from contextlib import contextmanager
import ctypes
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import struct
import tempfile
import urllib.parse
import urllib.request
import uuid
import zipfile
import zlib

PAGE = 'https://gamebanana.com/mods/737280'
AUTHOR = 'kuledawg'
VERSION = '2.0.0'
NAME = 'OcarinaReborn-ClassicUI'
MARKER = 'classic-ui.json'
TAIL = 262144
CONTROLLERS = (('switch', 'Switch'), ('xbox', 'Xbox'), ('xbox_swap', 'Xbox (A/B swap)'),
               ('playstation', 'PlayStation'), ('playstation_swap', 'PlayStation (X/O swap)'))
LOGOS = (('vanilla', 'Original', '3 - Vanilla Logo Version (Mods Inside)'),
         ('classic', 'Classic', '1 - Classic Logo Version (Mods Inside)'),
         ('gold', 'Gold European', '2 - Gold European Logo Version (Mods Inside)'))
STYLES = (('black', 'Classic Black', '2 - Classic Black UI Mod'),
          ('default', 'Default (square)', '1 - Default UI Mod'),
          ('yellow', 'Classic Yellow', '3 - Classic Yellow UI Mod'),
          ('blue', 'Classic Blue', '4 - Classic Blue UI Mod'))
DEFAULT = dict(controller='switch', logo='vanilla', style='black')
CATALOG = json.loads(Path(__file__).with_name('classic_ui_catalog.json').read_text(encoding='utf-8'))


class ModError(ValueError):
    pass


class Cancelled(ModError):
    pass


def check_cancel(cancel):
    if cancel and cancel.is_set():
        raise Cancelled('Download cancelled. The installed HUD has not been changed.')


def is_link(path):
    try:
        return path.is_symlink() or bool(getattr(path.lstat(), 'st_file_attributes', 0) & 0x400)
    except FileNotFoundError:
        return False


def safe_relative(name):
    path = PurePosixPath(name)
    if (not name or path.is_absolute() or '\\' in name or ':' in name
            or any(p in ('', '.', '..') or p.endswith((' ', '.')) for p in name.split('/'))):
        raise ModError('Invalid path in the mod archive.')
    return path


def allowed_url(url):
    p = urllib.parse.urlsplit(url)
    return (p.scheme == 'https' and not p.username and not p.password and p.port in (None, 443)
            and (p.hostname == 'gamebanana.com' or (p.hostname or '').endswith('.gamebanana.com')))


class GameBananaRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not allowed_url(newurl):
            raise ModError('The download redirected outside GameBanana. Please use the mod page.')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Archive:
    def __init__(self, controller):
        self.spec = CATALOG[controller]
        self.url = 'https://gamebanana.com/dl/' + str(self.spec['id'])
        self.opener = urllib.request.build_opener(GameBananaRedirect())

    def open_range(self, start, size):
        if start < 0 or size <= 0 or start + size > self.spec['bytes']:
            raise ModError('Invalid archive range.')
        end = start + size - 1
        request = urllib.request.Request(self.url, headers={
            'User-Agent': 'OcarinaReborn-ClassicUI/1.0', 'Accept-Encoding': 'identity',
            'Range': f'bytes={start}-{end}'})
        response = self.opener.open(request, timeout=30)
        if (response.status != 206 or not allowed_url(response.url)
                or response.headers.get('Content-Range') != f'bytes {start}-{end}/{self.spec["bytes"]}'):
            response.close()
            raise ModError('GameBanana did not return the requested file part. Please retry later.')
        self.url = response.url
        return response

    def read_range(self, start, size):
        with self.open_range(start, size) as response:
            data = response.read(size + 1)
        if len(data) != size:
            raise ModError('Incomplete download. Please retry.')
        return data

    def entries(self):
        start = self.spec['bytes'] - TAIL
        tail = self.read_range(start, TAIL)
        if hashlib.sha256(tail).hexdigest() != self.spec['tail_sha256']:
            raise ModError('The mod archive has changed. This launcher needs an updated mod definition.')
        with zipfile.ZipFile(io.BytesIO(tail)) as archive:
            entries = archive.infolist()
        if len(entries) > 1000:
            raise ModError('Unexpected mod archive.')
        seen = set()
        for info in entries:
            safe_relative(info.filename.rstrip('/'))
            if info.filename.lower() in seen:
                raise ModError('Duplicate path in the mod archive.')
            seen.add(info.filename.lower())
            info.header_offset += start
            if (info.compress_type != zipfile.ZIP_STORED or info.flag_bits & 1
                    or info.file_size != info.compress_size or info.file_size > 128 * 1024 * 1024
                    or info.header_offset < 0 or info.header_offset + info.compress_size > self.spec['bytes']):
                raise ModError('Unsupported mod archive format.')
        return entries

    def fetch(self, info, cache, cancel, progress):
        cache = Path(cache) / str(self.spec['id'])
        cache.mkdir(parents=True, exist_ok=True)
        # Files shared by the archive's variants can be reused locally.
        target = cache / f'{info.CRC:08x}-{info.file_size}.bin'
        if target.is_file() and verify_member(target, info):
            progress(info.file_size)
            return target
        check_cancel(cancel)
        header = self.read_range(info.header_offset, 30)
        magic, _, flags, method, _, _, _, _, _, namesize, extrasize = struct.unpack('<4s5H3I2H', header)
        if magic != b'PK\x03\x04' or flags & 1 or method != zipfile.ZIP_STORED:
            raise ModError('Invalid ZIP file header.')
        begin = info.header_offset + 30
        fd, part = tempfile.mkstemp(prefix='.download-', dir=cache)
        part = Path(part)
        try:
            with os.fdopen(fd, 'wb') as output, self.open_range(begin, namesize + extrasize + info.file_size) as response:
                name = response.read(namesize)
                if name.decode('utf-8' if flags & 0x800 else 'cp437') != info.orig_filename:
                    raise ModError('Archive member does not match its directory.')
                if len(response.read(extrasize)) != extrasize:
                    raise ModError('Incomplete ZIP header.')
                left, count, crc = info.file_size, 0, 0
                while left:
                    check_cancel(cancel)
                    block = response.read(min(left, 256 * 1024))
                    if not block:
                        raise ModError('Incomplete download. Please retry.')
                    output.write(block)
                    crc = zlib.crc32(block, crc)
                    left -= len(block)
                    count += len(block)
                    progress(count)
                if crc != info.CRC:
                    raise ModError('Downloaded file checksum does not match. Please retry.')
            part.replace(target)
            return target
        finally:
            part.unlink(missing_ok=True)


def verify_member(path, info):
    if path.stat().st_size != info.file_size:
        return False
    crc = 0
    with path.open('rb') as stream:
        while block := stream.read(1024 * 1024):
            crc = zlib.crc32(block, crc)
    return crc == info.CRC


def selected_entries(entries, selection):
    if selection.get('controller') not in dict(CONTROLLERS):
        raise ModError('Choose a controller style.')
    try:
        logo = next(p for k, _, p in LOGOS if k == selection['logo'])
        style = next(p for k, _, p in STYLES if k == selection['style'])
    except (KeyError, StopIteration):
        raise ModError('Choose a logo and HUD style.') from None
    prefix = f'{logo}/{style}/'
    result = []
    for info in entries:
        if info.filename.startswith(prefix + 'romfs/') and not info.is_dir():
            rel = safe_relative(info.filename[len(prefix):])
            if rel.suffix not in ('.zs', '.bgyml'):
                raise ModError('Unexpected file in this HUD variant.')
            result.append((info, rel.as_posix()))
    if not 4 <= len(result) <= 30 or sum(i.file_size for i, _ in result) > 150 * 1024 * 1024:
        raise ModError('The selected HUD variant is missing or has an unexpected size.')
    return result


def state(game):
    root = Path(game) / 'mods'
    if is_link(root):
        raise ModError('The Mods folder must not be a link for managed installation.')
    candidates = [p for p in (root / NAME, root / ('_' + NAME)) if p.exists() or is_link(p)]
    if not candidates:
        return dict(installed=False, enabled=False, selection=dict(DEFAULT))
    if len(candidates) != 1:
        raise ModError('Both enabled and disabled Classic UI folders exist. Check the Mods folder first.')
    path = candidates[0]
    if is_link(path):
        raise ModError('The managed Classic UI folder must not be a link.')
    try:
        data = json.loads((path / MARKER).read_text(encoding='utf-8'))
        if data['mod_id'] != 737280 or data['version'] != VERSION:
            raise ValueError()
        selection = data['selection']
        if (selection['controller'] not in dict(CONTROLLERS) or selection['logo'] not in {k for k, _, _ in LOGOS}
                or selection['style'] not in {k for k, _, _ in STYLES}):
            raise ValueError()
        records = data['files']
        if not isinstance(records, list) or not 4 <= len(records) <= 30:
            raise ValueError()
        complete, seen = True, set()
        for record in records:
            rel = safe_relative(record['path'])
            if (rel.parts[0] != 'romfs' or rel.suffix not in ('.zs', '.bgyml')
                    or rel.as_posix().lower() in seen or not isinstance(record['bytes'], int)
                    or not 0 <= record['bytes'] <= 128 * 1024 * 1024
                    or not isinstance(record['crc'], int) or not 0 <= record['crc'] <= 0xffffffff):
                raise ValueError()
            seen.add(rel.as_posix().lower())
            member = path
            for part in rel.parts:
                member /= part
                if is_link(member):
                    raise ValueError()
            complete &= member.is_file() and member.stat().st_size == record['bytes']
    except (OSError, ValueError, KeyError, TypeError):
        raise ModError('The Classic UI folder has no valid launcher manifest. Existing files were left untouched.') from None
    return dict(installed=True, enabled=path.name == NAME, selection=selection, path=path, files=records, complete=complete)


@contextmanager
def edit_lock(game):
    """Same Windows lock as the game startup guard; scoped to this game folder."""
    path = Path(game) / '.ocarina-reborn.instance.lock'
    if os.name != 'nt':
        raise ModError('This launcher integration currently requires Windows.')
    from ctypes import wintypes
    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, ctypes.c_void_p,
                                   wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
    kernel.CreateFileW.restype = wintypes.HANDLE
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    handle = kernel.CreateFileW(str(path), 0xC0000000, 1, None, 4, 0x80, None)
    if handle == ctypes.c_void_p(-1).value:
        raise ModError('Close the game or any other operation using this game folder, then try again.')
    try:
        import save_manager
        if save_manager.game_running():
            raise ModError('Close the game before changing Classic UI.')
        yield
    finally:
        kernel.CloseHandle(handle)


def set_enabled(game, enabled):
    with edit_lock(game):
        old = state(game)
        if not old['installed']:
            raise ModError('Install a Classic UI variant first.')
        if enabled and not old['complete']:
            raise ModError('Some Classic UI files are missing. Choose "Install and enable" to repair them.')
        if old['enabled'] != bool(enabled):
            old['path'].rename(old['path'].with_name(NAME if enabled else '_' + NAME))
    return state(game)


def install(game, cache, selection, cancel=None, progress=lambda done, total: None, archive=None):
    game = Path(game)
    original = game / 'romfs/UI/Layout2Archive/Common.Product.100.Nin_Ounce_NVN2.blarc.zs'
    if not original.is_file():
        raise ModError('Build the game first. Its expected UI files were not found.')
    if selection.get('controller') not in dict(CONTROLLERS):
        raise ModError('Choose a controller style.')
    state(game)  # Refuse an unmanaged folder before downloading anything.
    archive = archive or Archive(selection['controller'])
    chosen = selected_entries(archive.entries(), selection)
    # Check the resource-table version before selecting a controller-specific pack.
    for _, rel in chosen:
        if '/ResourceSizeTable.' in rel and not (game / rel).is_file():
            raise ModError('This controller variant needs game data version 1.1.1. Its resource-size table was not found.')
    total, done, ready = sum(i.file_size for i, _ in chosen), 0, []
    for info, rel in chosen:
        check_cancel(cancel)
        blob = archive.fetch(info, cache, cancel, lambda count, base=done: progress(base + count, total))
        ready.append((blob, rel, info))
        done += info.file_size
    check_cancel(cancel)
    with edit_lock(game):
        old = state(game)
        root = game / 'mods'
        if is_link(root):
            raise ModError('The Mods folder must not be a link for managed installation.')
        root.mkdir(exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='_classic-ui-install-', dir=root) as tmp:
            staged = Path(tmp) / NAME
            staged.mkdir()
            records = []
            for blob, rel, info in ready:
                check_cancel(cancel)
                dest = staged / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(blob, dest)
                if not verify_member(dest, info):
                    raise ModError('Installed file verification failed. The previous HUD is unchanged.')
                records.append(dict(path=rel, bytes=info.file_size, crc=info.CRC))
            (staged / MARKER).write_text(json.dumps(dict(mod_id=737280, version=VERSION, author=AUTHOR,
                source=PAGE, license='CC BY-NC-ND 4.0', selection=selection, files=records), indent=2), encoding='utf-8')
            check_cancel(cancel)
            target = root / NAME
            backup = root / ('_classic-ui-backup-' + uuid.uuid4().hex)
            if old['installed']:
                old['path'].rename(backup)
            try:
                staged.rename(target)
            except OSError:
                if old['installed']:
                    backup.rename(old['path'])
                raise
            # Only the verified managed folder moved above is removed; other mods
            # and all original game files remain untouched. A failed cleanup is safe.
            if old['installed']:
                shutil.rmtree(backup, ignore_errors=True)
    return state(game)

"""Keep optional optimisation profiles from stopping a player's game build."""
from pathlib import Path


PROFILE_HELPER = '''def profile_use_flags(profile):
    """A missing optional profile must not turn a normal optimised build into a failure."""
    try:
        with open(profile, "rb") as f:
            digest = hashlib.sha1(f.read(), usedforsecurity=False).hexdigest()[:16]
    except OSError as e:
        print("WARNING: optional build profile is unavailable (%s); building without PGO." % e, flush=True)
        return []
    return ["-fprofile-instr-use=" + profile, "-DHOOKSHOT_PROFILE_SHA1=" + digest]


'''

OLD_USE = '''        with open(PGO, "rb") as f:
            hot_fl = hot_fl + ["-fprofile-instr-use=" + PGO, "-DHOOKSHOT_PROFILE_SHA1=" + hashlib.sha1(f.read(), usedforsecurity=False).hexdigest()[:16]]'''
NEW_USE = '''        hot_fl = hot_fl + profile_use_flags(PGO)'''
PGO_ANCHOR = 'PGO = os.environ.get("RX_PGO", "")\n\n\n'
ENV_ANCHOR = '    if os.path.exists(os.path.join(work, "hot_funcs.txt")):\n'
ENV_OVERRIDE = '''    # This builder selects its own compatible profile below. A stale RX_PGO inherited
    # from another installation must not leak through when no profile is shipped.
    env["RX_PGO"] = ""
'''


def replace_once(text, old, new):
    if new in text:
        return text
    if text.count(old) != 1:
        raise ValueError("Build-profile patch anchor changed; no files written: " + old[:80])
    return text.replace(old, new, 1)


def apply(root):
    root = Path(root)
    build = root / 'nx2/build.py'
    make = root / 'nx2/make_game.py'
    before_build = build.read_text(encoding='utf-8')
    before_make = make.read_text(encoding='utf-8')
    patched_build = replace_once(before_build, PGO_ANCHOR, PGO_ANCHOR + PROFILE_HELPER)
    patched_build = replace_once(patched_build, OLD_USE, NEW_USE)
    patched_make = replace_once(before_make, ENV_ANCHOR, ENV_OVERRIDE + ENV_ANCHOR)
    # Validate both scripts before changing either one; no game or user data involved.
    compile(patched_build, str(build), 'exec')
    compile(patched_make, str(make), 'exec')
    for path, before, after in ((build, before_build, patched_build), (make, before_make, patched_make)):
        if before != after:
            path.write_text(after, encoding='utf-8', newline='')


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('engine', type=Path)
    apply(parser.parse_args().engine)

"""Optional AmiiboMgr cooldown hooks. Fail closed on another game build.

0x8328c870 checks clock snapshots against 24 hours; 0x8328cd30 compares
the scanned model's saved date with today's year/month/day. The runtime helper
overrides their return values only while the explicit option is on, and only
from the verified AmiiboMgr callers. No saved timestamps or tag bytes are edited.
"""

BUILD = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
HOOKS = ((0x8328c870, 0), (0x8328cd30, 1))
CHECKS = (
    (0x8328c870, 0xd503237f),  # pacibsp: before the stack frame
    (0x8328c874, 0xd10443ff),  # sub sp, sp, #0x110
    (0x8328cd30, 0xd503237f),
    (0x8328cd34, 0xd10343ff),  # sub sp, sp, #0xd0
    (0x8328bde4, 0x940002a3),  # bl clock guard
    (0x8328bde8, 0x37000380),  # allowed when return bit 0 is set
    (0x8328be20, 0x94000294),
    (0x8328be24, 0x370004a0),
    (0x8328be60, 0x940003b4),  # bl used-today check
    (0x8328be64, 0x36000160),  # allowed when return bit 0 is clear
    (0x8328bebc, 0x9400039d),
    (0x8328bec0, 0x3607fb40),
)


def install(lifter, img, build_id):
    if build_id != BUILD or any(img.word(pc) != word for pc, word in CHECKS):
        print("ocarina reborn unlimited amiibo: other game build, left out")
        return 0
    for pc, rule in HOOKS:
        text = ("{ extern int ocr_amiibo_rule_override(Ctx *c, int rule); "
                f"if (ocr_amiibo_rule_override(c, {rule})) return; }}"
                "   /* (nx2/ocr_amiibo_rules.py) */")
        previous = lifter.after.get(pc, "")
        if text not in previous:
            lifter.after[pc] = previous + "\n" + text if previous else text
    print("ocarina reborn unlimited amiibo: hooked (off unless selected)")
    return 1

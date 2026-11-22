"""Scoped player Ocarina actor selection; no inventory/save changes.

Both native EquipmentUser entry points receive a caller-owned stack SafeString.
The helper changes only that string for the verified player caller/slot pair.
PACIBSP is a no-op in the lift, so these hooks run before the stack prologues.
"""

BUILD = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348"
HOOKS = ((0x81033f20, 0), (0x82e21a90, 1))
CHECKS = (
    (0x81033f20, 0xd503237f),
    (0x81033f24, 0xa9ba7bfd),
    (0x82e21a90, 0xd503237f),
    (0x82e21a94, 0xa9ba7bfd),
    (0x82e171c8, 0x7100369f),  # slot 13: playable Ocarina
    (0x82e171d0, 0x7100429f),  # slot 16: holder
    (0x82e173e0, 0x52800808),  # 64-byte caller-owned SafeString buffer
    (0x82e17a54, 0x9100a3e2),  # argument = sp + 0x28
    (0x82e17a64, 0x9788712f),
    (0x82e17a30, 0x94002818),
    (0x82e16c80, 0xd503237f),  # native update for one equipment slot
    (0x82e16c84, 0xd10503ff),
    (0x828104c8, 0x32050108),  # ExecutePlayerPlayMusic sets its full-lifecycle bit
    (0x828104cc, 0xb9002c08),
    (0x828116b0, 0x12047908),  # its native exit clears that bit
    (0x828116b4, 0xb9002e68),
    (0x80993044, 0xf941ad00),  # player-state component at components + 0x358
)


def install(lifter, img, build_id):
    if build_id != BUILD or any(img.word(pc) != word for pc, word in CHECKS):
        print("ocarina reborn instrument: other game build, left out")
        return 0
    for pc, path in HOOKS:
        text = ("{ extern void ocr_ocarina_equipment(Ctx *c, int path); "
                f"ocr_ocarina_equipment(c, {path}); }}"
                "   /* (nx2/ocr_ocarina.py) */")
        previous = lifter.after.get(pc, "")
        if text not in previous:
            lifter.after[pc] = previous + "\n" + text if previous else text
    print("ocarina reborn instrument: hooked (Original unless selected)")
    return 1

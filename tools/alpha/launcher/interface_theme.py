"""Shared launcher/F1 accent; game options are authoritative after playing."""
import re

KEYS = ('interface_red', 'interface_green', 'interface_blue')
DEFAULT = (46, 123, 255)
PRESETS = [('Reborn Blue', '#2e7bff'), ('Ocean', '#00b8b0'), ('Forest', '#42b86c'),
           ('Violet', '#a879ee'), ('Rose', '#ed76ae'), ('Amber', '#e8ad45'), ('Silver', '#bdc8da')]


def rgb(values):
    result = []
    for key, default in zip(KEYS, DEFAULT):
        try:
            result.append(max(0, min(255, int(values.get(key, default)))))
        except (ValueError, TypeError, OverflowError):
            result.append(default)
    return tuple(result)


def hex_color(values):
    return '#%02x%02x%02x' % rgb(values)


def from_hex(value):
    value = value.strip().lstrip('#')
    if not re.fullmatch(r'[0-9a-fA-F]{6}', value):
        raise ValueError('Expected six hexadecimal digits')
    return dict(zip(KEYS, (int(value[i:i+2], 16) for i in (0, 2, 4))))


def mix(a, b, percent):
    return tuple((x * (100 - percent) + y * percent + 50) // 100 for x, y in zip(a, b))


def luminance(color):
    channels = [v / 255 for v in color]
    channels = [v / 12.92 if v <= .04045 else ((v + .055) / 1.055) ** 2.4 for v in channels]
    return sum(v * weight for v, weight in zip(channels, (.2126, .7152, .0722)))


def tint(base, color):
    """Keep the original navy design exactly at Reborn Blue; recolor its shades."""
    span = max(base) - min(base)
    return tuple(max(0, min(255, b + ((a - d) * span + 104) // 209))
                 for b, a, d in zip(base, color, DEFAULT))


def palette(color):
    """Original launcher palette, with a shared customizable accent."""
    ink = (0, 0, 0) if luminance(color) > .179 else (255, 255, 255)
    original = {
        'BG_TOP': (13,27,54), 'BG_BOTTOM': (8,18,38), 'HEAD': (10,23,48),
        'PANEL': (16,34,74), 'PANEL_HI': (19,42,88), 'CELL': (12,26,58),
        'LINE': (34,66,126), 'LINE_HI': (55,104,200),
        'ACCENT_HI': (74,149,255), 'ACCENT_LO': (21,86,224),
        'BUTTON_TOP': (59,139,255), 'BUTTON_EDGE': (140,194,255),
    }
    colors = {key: tint(value,color) for key,value in original.items()}
    # The large primary labels keep the original white ink on blue gradients.
    # Very light custom colors need dark ink at both ends of the gradient.
    button_ink = (255,255,255) if luminance(colors['BUTTON_TOP']) <= .30 else (0,0,0)
    colors.update(ACCENT=color, GLOW=color, ON_ACCENT=ink, BUTTON_INK=button_ink,
                  TEXT=(242,246,255), SUB=(169,187,219), MUTED=(125,146,186),
                  LINK=mix(color,(255,255,255),60))
    return {key: '#%02x%02x%02x' % value for key, value in colors.items()}


# The launcher's own look since the forest redesign (2026-11-17): dark glass, gold frames, a glowing accent. palette() above
# stays the F1 menu's (the game draws the same navy shades: hud/ocr_interface_theme.h). In the launcher the chosen interface
# colour tints the whole look (the night, the glass, the light along fields and rows, the glows, the buttons, the icons);
# only the gold of the frames stays. The default colour (Reborn Blue, as the game's own default) is the design's forest
# green here.
FOREST_ACCENT = (66, 186, 96)


def launcher_palette(color):
    accent = FOREST_ACCENT if tuple(color) == DEFAULT else tuple(color)
    forest = accent == FOREST_ACCENT
    span = lambda base: max(base) - min(base)

    def shade(base):   # (a forest shade moved toward the accent as tint() moves the navy ones toward theirs)
        return tuple(max(0, min(255, b + ((a - f) * span(base) + 104) // 209)) for b, a, f in zip(base, accent, FOREST_ACCENT))
    ink = (0, 0, 0) if luminance(accent) > .179 else (255, 255, 255)
    top = mix(accent, (0, 0, 0), 8)
    colors = {
        'BG_TOP': shade((6, 30, 28)), 'BG_BOTTOM': shade((3, 17, 16)), 'HEAD': shade((3, 17, 17)),
        'PANEL': shade((7, 46, 41)), 'PANEL_HI': shade((11, 64, 56)), 'CELL': shade((4, 31, 28)),
        'GLASS_EDGE': shade((43, 106, 94)),
        'LINE': (150, 128, 62), 'LINE_HI': (232, 204, 108),   # (the gold of the frames: every colour)
        'EDGE': (196, 220, 88) if forest else mix(accent, (255, 255, 255), 38),   # (the light along fields and rows)
        'RULE': (110, 220, 200) if forest else mix(accent, (255, 255, 255), 50),  # (a panel title's rule)
        'ICON': (191, 244, 255) if forest else mix(accent, (255, 255, 255), 72),
        'ACCENT': accent, 'ACCENT_HI': mix(accent, (255, 255, 255), 28), 'ACCENT_LO': mix(accent, (0, 0, 0), 52),
        'GLOW': accent, 'BUTTON_TOP': top, 'BUTTON_EDGE': (240, 214, 124),
        'ON_ACCENT': ink,
        'TEXT': (240, 246, 240), 'SUB': shade((182, 206, 198)), 'MUTED': shade((132, 164, 156)),
        'LINK': mix(accent, (255, 255, 255), 60),
    }
    colors['BUTTON_INK'] = (255, 255, 255) if luminance(top) <= .30 else (0, 0, 0)
    return {key: '#%02x%02x%02x' % value for key, value in colors.items()}

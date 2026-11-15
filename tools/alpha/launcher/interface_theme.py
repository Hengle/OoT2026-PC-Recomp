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


def palette(color):
    """Integer blends match ocr_interface_theme.h; text on accents meets WCAG 4.5:1."""
    ink = (0, 0, 0) if luminance(color) > .179 else (255, 255, 255)
    colors = {
        'BG_TOP': mix((10, 17, 29), color, 9), 'BG_BOTTOM': mix((5, 9, 17), color, 4),
        'HEAD': mix((8, 15, 27), color, 8), 'PANEL': mix((12, 22, 39), color, 10),
        'PANEL_HI': mix((16, 29, 49), color, 18), 'CELL': mix((7, 14, 27), color, 7),
        'LINE': mix((30, 44, 65), color, 25), 'LINE_HI': mix((64, 80, 105), color, 45),
        'ACCENT': color, 'ACCENT_HI': mix(color, (255, 255, 255), 35),
        'ACCENT_LO': color, 'GLOW': color, 'ON_ACCENT': ink,
        'TEXT': (242, 246, 255), 'SUB': (184, 195, 213), 'MUTED': (145, 161, 185),
        'LINK': mix(color, (255, 255, 255), 60),
    }
    return {key: '#%02x%02x%02x' % value for key, value in colors.items()}

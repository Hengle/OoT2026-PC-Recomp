"""9:16 output: shared size validation, camera initialization and menu choices."""
from pathlib import Path
from engine_stability import replace_once

PORTRAIT_MOVIE = ('{ extern volatile float hos_wide_ratio; const float _r = hos_wide_ratio; '
    'if (_r > 0.0f && _r < 1.0f) { const uint64_t _vp = c->x[29] - 40; '
    'uint32_t _ua = (uint32_t)recomp_load32(c, _vp + 12), _ub = (uint32_t)recomp_load32(c, _vp + 20); '
    'float _a, _b; memcpy(&_a, &_ua, 4); memcpy(&_b, &_ub, 4); '
    'const float _in = (_b - _a) * (1.0f - _r / (16.0f / 9.0f)) * 0.5f; _a += _in; _b -= _in; '
    'memcpy(&_ua, &_a, 4); memcpy(&_ub, &_b, 4); recomp_store32(c, _vp + 12, _ua); '
    'recomp_store32(c, _vp + 20, _ub); } } /* Ocarina Reborn: portrait movie fit */')

CHANGES = (
    ('host/hos_wide_size.h',
     '(uint64_t)w * 4 >= (uint64_t)h * 5',
     '(uint64_t)w * 16 >= (uint64_t)h * 9'),
    ('host/hos_wide_size.h',
     'want < 5.0 / 4.0 ? 5.0 / 4.0 : want',
     'want < 9.0 / 16.0 ? 9.0 / 16.0 : want'),
    ('host/hos_wide_size.h', 'ratio as the picture takes it: 5:4 to 48:9.',
     'ratio as the picture takes it: 9:16 to 48:9.'),
    ('host/hos_main.c',
     '(want > 1.0f && want < game * 0.99)',
     '(want > 0.0f && want < game * 0.99)'),
    ('gpu/vk/vk_menu.cpp',
     '(want > 1.0 && want < game * 0.99)',
     '(want > 0.0 && want < game * 0.99)'),
    ('gpu/vk/display_modes.h',
     '    static const std::vector<Size> v = {\n',
     '    static const std::vector<Size> v = {\n'
     '        {720, 1280}, {1080, 1920}, {1440, 2560}, {2160, 3840}, // 9:16 portrait\n'),
    ('gpu/vk/display_modes.h',
     '} named[] = {{"5:4", 5.0 / 4}',
     '} named[] = {{"9:16", 9.0 / 16}, {"5:4", 5.0 / 4}'),
    ('gpu/vk/vk_menu.cpp',
     '        return o;\n    }();\n    return v;\n}',
     '        // Ocarina Reborn: offer portrait even on landscape displays. Keep the legacy fallback first.\n'
     '        for (dm::Size p : dm::common_sizes()) {\n'
     '            if (dm::ratio_name(p) != "9:16") continue;\n'
     '            if (std::none_of(o.begin(), o.end(), [&](Out v) { return v.w == p.w && v.h == p.h; }))\n'
     '                o.push_back({p.w, p.h});\n'
     '        }\n'
     '        return o;\n    }();\n    return v;\n}'),
    ('gpu/vk/vk_menu.cpp', 'c.s = ui::unit((float)h, opts.menu_size,',
     'c.s = ui::unit((float)std::min(w, h), opts.menu_size,'),
    ('gpu/vk/vk_menu.cpp', 'return ui::unit((float)h, opts.menu_size,',
     'return ui::unit((float)std::min(w, h), opts.menu_size,'),
    ('nx2/oot_wide.py',
     '"memcpy(c->vreg[1], _row, 16); } } } }',
     '"memcpy(c->vreg[1], _row, 16); "\n'
     '       "extern volatile float hos_wide_ratio; const float _r = hos_wide_ratio; "\n'
     '       "if (_r > 0.0f && _r < 1.0f) { memcpy(_row, c->vreg[4], 16); "\n'
     '       "for (int _k = 0; _k < 4; _k++) _row[_k] *= _r / (16.0f / 9.0f); "\n'
     '       "memcpy(c->vreg[4], _row, 16); } } } } }'),
    ('nx2/oot_wide.py', '# (main offset, the original instruction word there, the C after it)',
     'MOVIE += ' + repr(PORTRAIT_MOVIE) + '\n\n'
     '# (main offset, the original instruction word there, the C after it)'),
)


def apply(root):
    for rel, old, new in CHANGES:
        p = Path(root) / rel
        p.write_text(replace_once(p.read_text(encoding='utf-8'), old, new), encoding='utf-8', newline='\n')

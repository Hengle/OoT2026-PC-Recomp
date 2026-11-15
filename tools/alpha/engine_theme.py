"""Shared launcher/F1 appearance. UI-only files; translator/cache inputs stay intact."""
from pathlib import Path
import re
import shutil
from engine_stability import replace_once

HERE = Path(__file__).parent


def replace_function(text, start, replacement):
    pos = text.index(start)
    opening = text.index('{', pos)
    depth = 1
    end = opening + 1
    while depth:
        depth += (text[end] == '{') - (text[end] == '}')
        end += 1
    return text[:pos] + replacement + text[end:]


def apply(root):
    root = Path(root)
    vk = root / 'gpu/vk'
    shutil.copy2(HERE / 'hud/ocr_interface_theme.h', vk / 'ocr_interface_theme.h')
    ui = (vk / 'vk_ui.h').read_text(encoding='utf-8')
    ui = replace_once(ui, '#include "vk_imgui.h"', '#include "vk_imgui.h"\n#include "ocr_interface_theme.h"')
    ui = replace_once(ui, 'constexpr ImU32 kInk =', 'inline ImU32 kInk =')
    at = 'constexpr int kDimAlpha = 185;'
    ui = replace_once(ui, at, '''inline void update_theme() {
    using interface_theme::RGB;
    using interface_theme::mix;
    const RGB a{std::clamp(ocr_ui_r,0,255), std::clamp(ocr_ui_g,0,255), std::clamp(ocr_ui_b,0,255)};
    const int stamp = a.r | (a.g<<8) | (a.b<<16);
    static int previous = -1;
    if (previous == stamp) return;
    previous = stamp;
    const auto pack = [](RGB c, int alpha=255) { return rgba(c.r,c.g,c.b,alpha); };
    kInk = rgba(242,246,255); kSoft = rgba(184,195,213); kDim = rgba(145,161,185);
    kGold = kGoldHi = pack(a); kGoldInk = pack(interface_theme::foreground(a));
    kAccent = pack(mix(a,{255,255,255},60)); kEdge = pack(mix({30,44,65},a,25));
    kCellDark = pack(mix({7,14,27},a,7)); kCellName = pack(mix({12,22,39},a,10));
    kCellNameSel = kTabInset = pack(mix({16,29,49},a,18)); kBronze = kEdge;
    kColumn = pack(mix({5,9,17},a,4),248);
    kBannerTop = pack(mix({10,17,29},a,9)); kBanner = pack(mix({8,15,27},a,8));
    kBannerInk = kSoft; kBannerEdge = pack(mix({64,80,105},a,45));
    kBox = kCellDark; kBoxEdge = kEdge; kBar = kBanner; kListen = kCellNameSel;
}
''' + at)
    ui = replace_function(ui, 'inline void flourish(', '''inline void flourish(Ctx& c, float x0, float x1, float y, ImU32 col) {
    c.d->AddLine(ImVec2(x0,y), ImVec2(x1,y), alpha(col,.4f), std::max(1.0f,c.s));
}''')
    ui = replace_function(ui, 'inline void glow(', '''inline void glow(Ctx& c, ImVec2 a0, ImVec2 b0) {
    const float s = c.s;
    for (int i=3; i>=1; --i)
        c.d->AddRect(a0-ImVec2(i*s,i*s), b0+ImVec2(i*s,i*s), alpha(kAccent,.08f), 9*s, 0, 2*s);
    c.d->AddRect(a0,b0,kAccent,8*s,0,std::max(1.0f,s));
}''')
    ui = replace_function(ui, 'inline void gold(', '''inline void gold(Ctx& c, ImVec2 a0, ImVec2 b0) {
    c.d->AddRectFilled(a0,b0,kGold,7*c.s);
}''')
    ui = replace_function(ui, 'inline void banner(', '''inline void banner(Ctx& c, float hh) {
    c.d->AddRectFilledMultiColor(ImVec2(0,0), ImVec2(c.w,hh), kBannerTop,kBannerTop,kBanner,kBanner);
    c.d->AddLine(ImVec2(0,hh),ImVec2(c.w,hh),kEdge,std::max(1.0f,c.s));
}''')
    ui = replace_function(ui, 'inline void box(', '''inline void box(Ctx& c, ImVec2 a, ImVec2 b) {
    shadow(c,a,b,12*c.s,.45f,3*c.s);
    c.d->AddRectFilled(a,b,kBox,12*c.s);
    c.d->AddRect(a,b,kBoxEdge,12*c.s,0,std::max(1.0f,c.s));
}''')
    ui = replace_function(ui, 'inline void button(', '''inline void button(Ctx& c, ImVec2 a0, ImVec2 b0, const char* label, bool sel) {
    const float s=c.s;
    c.d->AddRectFilled(a0,b0,sel?kGold:kCellName,9*s);
    c.d->AddRect(a0,b0,sel?kAccent:kEdge,9*s,0,std::max(1.0f,s));
    text_mid_centre(c,c.f.strong,20*s,(a0.x+b0.x)*.5f,(a0.y+b0.y)*.5f,sel?kGoldInk:kInk,label);
}''')
    (vk / 'vk_ui.h').write_text(ui, encoding='utf-8')
    menu = (vk / 'vk_menu.cpp').read_text(encoding='utf-8')
    names = '"Reborn Blue", "Ocean", "Forest", "Violet", "Rose", "Amber", "Silver", "Custom"'
    menu = replace_once(menu, 'const char* tx_tunic_rgb(int v)',
        'const char* tx_interface_preset(int v) { static const char* names[] = {' + names + '}; return names[std::clamp(v,0,7)]; }\n'
        'const char* tx_tunic_rgb(int v)')
    help_text = 'Shared color for the launcher and F1 menu. Applies immediately and is saved automatically. The launcher adopts it when you return from the game.'
    rows = ('    {TAB_GAMEPLAY, "Interface color", &ocr_ui_preset, 0, 7, 1, tx_interface_preset,\n'
            f'     "{help_text}", nullptr, false, true}},\n')
    for label, short in [('red', 'r'), ('green', 'g'), ('blue', 'b')]:
        rows += (f'    {{TAB_GAMEPLAY, "Interface {label}", &ocr_ui_{short}, 0, 255, 1, tx_tunic_rgb,\n'
                 f'     "{help_text}", nullptr, false, true}},\n')
    menu = replace_once(menu, '    {TAB_GAMEPLAY, "Menu size",', rows + '    {TAB_GAMEPLAY, "Menu size",')
    for fn in ('is_slider', 'stops_at_ends'):
        menu = replace_once(menu, f'bool {fn}(const Row& r) {{ return ',
            f'bool {fn}(const Row& r) {{ return r.value == &ocr_ui_r || r.value == &ocr_ui_g || r.value == &ocr_ui_b || ')
    menu = replace_once(menu, '    prompts_at_once(r);',
        '    if (r.value == &ocr_ui_preset) interface_theme::select_preset(ocr_ui_preset);\n'
        '    ocr_ui_preset = interface_theme::preset_index();\n'
        '    prompts_at_once(r);')
    menu = replace_once(menu, 'void draw_menu(ui::Ctx& c) {',
        'void draw_menu(ui::Ctx& c) {\n    ui::update_theme();\n'
        '    ocr_ui_preset = interface_theme::preset_index();\n'
        '    c.f.heading = c.f.strong; // Launcher-like sans headings, including translated glyphs.')
    menu = replace_once(menu, 'ui::rgba(8, 5, 2, ui::kDimAlpha)', 'ui::rgba(3, 7, 15, ui::kDimAlpha)')
    menu = replace_once(menu,
        'c.d->AddRectFilled(ImVec2(x, 0), ImVec2(x + tw[i], hh - 3 * s), shown ? ui::kTabInset : ui::alpha(ui::kTabInset, 0.35f));',
        'c.d->AddRectFilled(ImVec2(x + 4*s, 8*s), ImVec2(x + tw[i] - 4*s, hh - 8*s), shown ? ui::kTabInset : ui::alpha(ui::kTabInset, 0.35f), 12*s);')
    menu = menu.replace('ui::rgba(0, 180, 255)', 'ui::kAccent')
    menu = menu.replace('ImVec2(x + 1, 0), ImVec2(x + 1, hh - 3 * s)', 'ImVec2(x + 18*s, hh - 8*s), ImVec2(x + tw[i] - 18*s, hh - 8*s)')
    # The rounded tab's lower rule replaces its two vertical separators.
    menu = menu.replace('                c.d->AddLine(ImVec2(x + tw[i] - 1, 0), ImVec2(x + tw[i] - 1, hh - 3 * s), ui::kAccent, std::max(1.0f, s));\n', '')
    menu = menu.replace('ui::rgba(114, 215, 234)', 'ui::kAccent')
    # Accent-filled selections have adaptive ink; headings on dark panels stay light.
    menu = menu.replace(', ui::kGold,', ', ui::kAccent,').replace(', ui::kGoldHi,', ', ui::kAccent,')
    menu = replace_function(menu, 'void column(', '''void column(ui::Ctx& c, float x0, float x1, float top) {
    const ImVec2 a(x0,top), b(x1,c.h-c.safe);
    c.d->AddRectFilled(a,b,ui::kColumn,12*c.s);
    c.d->AddRect(a,b,ui::kEdge,12*c.s,0,std::max(1.0f,c.s));
}''')
    menu = replace_once(menu, 'c.d->AddRectFilled(a, b, sel ? ui::kCellNameSel : ui::kCellName);',
                        'c.d->AddRectFilled(a, b, sel ? ui::kCellNameSel : ui::kCellName, 6*s);')
    # Headless UI snapshots have no animated present loop to advance scroll_rows.
    image_start = menu.index('void menu_record_image(')
    menu = menu[:image_start] + replace_once(menu[image_start:], '    ui::Ctx c = ui_ctx(w, h);',
        '    ease_step = 1; // Static UI snapshots show the selected row immediately.\n    ui::Ctx c = ui_ctx(w, h);')
    menu = replace_once(menu, '    if (r.value == &ocr_tunic) {',
        '    if (r.value == &ocr_ui_preset) {\n'
        '        c.d->AddRectFilled(ImVec2(va.x+4*s,va.y+9*s),ImVec2(va.x+27*s,vb.y-9*s),ui::rgba(ocr_ui_r,ocr_ui_g,ocr_ui_b),4*s);\n'
        '        va.x += 32*s;\n    }\n    if (r.value == &ocr_tunic) {')
    (vk / 'vk_menu.cpp').write_text(menu, encoding='utf-8')
    translations = (vk / 'menu_i18n.h').read_text(encoding='utf-8')
    de = [('Interface color', 'Menüfarbe'), ('Interface red', 'Menüfarbe: Rot'),
          ('Interface green', 'Menüfarbe: Grün'), ('Interface blue', 'Menüfarbe: Blau'),
          (help_text, 'Gemeinsame Farbe für Launcher und F1-Menü. Gilt sofort und wird automatisch gespeichert. Der Launcher übernimmt sie nach dem Spiel.')]
    entries = ''.join(f'    {{"{key}", "{value}"}},\n' for key, value in de)
    translations = replace_once(translations, 'inline constexpr Entry kde[] = {\n',
                                'inline constexpr Entry kde[] = {\n' + entries)
    translations, count = re.subn(r'(\{"de", "Deutsch", kde, )(\d+)(\})',
                                 lambda m: m[1] + str(int(m[2]) + len(de)) + m[3], translations)
    if count != 1:
        raise RuntimeError('German menu translation count anchor changed')
    (vk / 'menu_i18n.h').write_text(translations, encoding='utf-8')
    print('interface: shared RGB, presets and rounded launcher-style F1 panels (no shader changes)')

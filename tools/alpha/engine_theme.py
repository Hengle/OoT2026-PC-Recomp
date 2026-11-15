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


def launcher_style(ui, menu):
    """Paint the launcher's navy cards and luminous controls using the existing menu hit layout."""
    ui = replace_once(ui, 'inline void update_theme()',
        'inline ImU32 kButtonBottom, kButtonEdge, kBackdropTop, kBackdropBottom, kGlow;\ninline void update_theme()')
    ui = replace_function(ui, 'inline void update_theme()', '''inline void update_theme() {
    using namespace interface_theme;
    const RGB a{std::clamp(ocr_ui_r,0,255),std::clamp(ocr_ui_g,0,255),std::clamp(ocr_ui_b,0,255)};
    const int stamp=a.r|(a.g<<8)|(a.b<<16);
    static int previous=-1;
    if (previous==stamp) return;
    previous=stamp;
    const auto pack=[](RGB c) { return rgba(c.r,c.g,c.b); };
    const auto shade=[&](RGB c) { return pack(tint(c,a)); };
    kInk=rgba(242,246,255); kSoft=rgba(169,187,219); kDim=rgba(125,146,186);
    kGold=shade({59,139,255}); kGoldHi=shade({74,149,255});
    kGoldInk=pack(button_foreground(a)); kButtonBottom=shade({21,86,224});
    kButtonEdge=shade({140,194,255}); kGlow=pack(a);
    kAccent=pack(mix(a,{255,255,255},60)); kEdge=shade({34,66,126});
    kCellDark=shade({12,26,58}); kCellName=shade({16,34,74});
    kCellNameSel=kTabInset=shade({19,42,88}); kBronze=kCellNameSel;
    kColumn=kCellName; kBox=kCellName; kBoxEdge=kEdge;
    kBackdropTop=shade({13,27,54}); kBackdropBottom=shade({8,18,38});
    kBannerTop=shade({16,34,74}); kBanner=shade({10,23,48});
    kBannerInk=kSoft; kBannerEdge=shade({55,104,200}); kBar=kBanner; kListen=kCellNameSel;
}''')
    helpers = '''// Rounded gradients reuse ImGui geometry; no extra textures or pipelines.
inline void gradient(Ctx& c, ImVec2 a, ImVec2 b, ImU32 top, ImU32 bottom, float radius) {
    const int first=c.d->VtxBuffer.Size;
    c.d->AddRectFilled(a,b,IM_COL32_WHITE,radius);
    for (int i=first;i<c.d->VtxBuffer.Size;++i) {
        auto& v=c.d->VtxBuffer[i];
        const float t=std::clamp((v.pos.y-a.y)/std::max(1.f,b.y-a.y),0.f,1.f);
        ImU32 col=v.col&IM_COL32_A_MASK;
        for (int shift : {IM_COL32_R_SHIFT,IM_COL32_G_SHIFT,IM_COL32_B_SHIFT}) {
            const int x=(top>>shift)&255, y=(bottom>>shift)&255;
            col|=(ImU32)(x+(y-x)*t+.5f)<<shift;
        }
        v.col=col;
    }
}
inline void backdrop(Ctx& c) {
    // Small cached color mesh reproduces the launcher's upper glow and dark edges.
    constexpr int nx=24,ny=12;
    static ImU32 colors[ny+1][nx+1], stamp=0;
    if (stamp!=kGlow || !colors[0][0]) {
        stamp=kGlow;
        for (int y=0;y<=ny;++y) for (int x=0;x<=nx;++x) {
            const float yy=(float)y/ny, xx=2.f*x/nx-1.f;
            const float light=std::exp(-((xx/.9f)*(xx/.9f)+((yy-.05f)/.55f)*((yy-.05f)/.55f))*1.6f);
            const float edge=std::clamp((std::fabs(xx)-.55f)/.45f,0.f,1.f);
            ImU32 col=IM_COL32_A_MASK;
            for (int shift : {IM_COL32_R_SHIFT,IM_COL32_G_SHIFT,IM_COL32_B_SHIFT}) {
                float value=((kBackdropTop>>shift)&255)*(1-yy)+((kBackdropBottom>>shift)&255)*yy;
                value=(value+light*((kGlow>>shift)&255)*.16f)*(1-edge*edge*.35f);
                col|=(ImU32)std::clamp((int)value,0,255)<<shift;
            }
            colors[y][x]=col;
        }
    }
    for (int y=0;y<ny;++y) for (int x=0;x<nx;++x)
        c.d->AddRectFilledMultiColor(ImVec2(c.w*x/nx,c.h*y/ny),ImVec2(c.w*(x+1)/nx,c.h*(y+1)/ny),
            colors[y][x],colors[y][x+1],colors[y+1][x+1],colors[y+1][x]);
}
inline void ocarina(Ctx& c, ImVec2 p, float size) {
    const float s=size/40.f;
    auto at=[&](float x,float y) { return p+ImVec2(x*s,y*s); };
    c.d->PathLineTo(at(11,20)); c.d->PathLineTo(at(7,5));
    c.d->PathBezierCubicCurveTo(at(7,0),at(16,0),at(18,8)); c.d->PathLineTo(at(21,14));
    c.d->PathBezierCubicCurveTo(at(29,9),at(42,5),at(39,14));
    c.d->PathBezierCubicCurveTo(at(34,30),at(10,40),at(3,33));
    c.d->PathBezierCubicCurveTo(at(-2,28),at(5,23),at(11,20));
    c.d->PathFillConvex(kGold);
    for (ImVec2 hole : {at(10,29),at(19,24),at(27,19),at(33,13)}) {
        c.d->AddCircleFilled(hole,2.4f*s,kCellDark,12);
        c.d->AddCircle(hole,2.8f*s,kButtonEdge,12,std::max(1.f,s));
    }
    c.d->AddLine(at(10,14),at(18,10),kButtonEdge,2*s);
}
'''
    ui = replace_once(ui, 'inline void glow(', helpers+'\ninline void glow(')
    ui = replace_function(ui, 'inline void glow(', '''inline void glow(Ctx& c, ImVec2 a, ImVec2 b, float rounding=10) {
    for (int i=6;i>=1;--i) {
        const float e=i*2*c.s;
        c.d->AddRect(a-ImVec2(e,e),b+ImVec2(e,e),alpha(kGlow,.045f),rounding*c.s+e,0,2*c.s);
    }
    c.d->AddRect(a,b,kButtonEdge,rounding*c.s,0,std::max(1.f,c.s));
}''')
    ui = replace_function(ui, 'inline void gold(', '''inline void gold(Ctx& c, ImVec2 a, ImVec2 b, float rounding=9) {
    gradient(c,a,b,kGold,kButtonBottom,rounding*c.s);
    c.d->AddRect(a,b,kButtonEdge,rounding*c.s,0,std::max(1.f,c.s));
}''')
    ui = replace_function(ui, 'inline void box(', '''inline void box(Ctx& c, ImVec2 a, ImVec2 b) {
    shadow(c,a,b,12*c.s,.25f,3*c.s);
    gradient(c,a,b,kCellName,kCellDark,14*c.s);
    c.d->AddRect(a,b,kEdge,14*c.s,0,std::max(1.f,c.s));
}''')
    ui = replace_function(ui, 'inline void button(', '''inline void button(Ctx& c, ImVec2 a, ImVec2 b, const char* label, bool sel) {
    if (sel) { gold(c,a,b); glow(c,a,b); }
    else { gradient(c,a,b,kCellName,kCellDark,10*c.s); c.d->AddRect(a,b,kEdge,10*c.s,0,std::max(1.f,c.s)); }
    text_mid_centre(c,c.f.strong,20*c.s,(a.x+b.x)*.5f,(a.y+b.y)*.5f,sel?kGoldInk:kInk,label);
}''')
    # Prompts sit in the launcher's full-width dark footer, with outlined keycaps.
    start=ui.index('inline float prompt_bar(')
    part=ui[start:]
    a=part.index('    const float x0 ='); b=part.index('    const float kh =',a)
    part=part[:a]+'''    c.d->AddRectFilled(ImVec2(0,py-12*s),ImVec2(c.w,c.h),kBar);
    c.d->AddLine(ImVec2(c.safe,py-12*s),ImVec2(c.w-c.safe,py-12*s),kEdge,std::max(1.f,s));
'''+part[b:]
    ui=ui[:start]+part
    ui=ui.replace('const ImU32 cap = kInk, ink = rgba(10, 20, 45), dim = rgba(130, 145, 180);',
                  'const ImU32 cap = kCellNameSel, ink = kInk, dim = kDim;')
    menu=replace_once(menu,'c.d->AddRectFilled(ImVec2(0, 0), ImVec2(c.w, c.h), ui::rgba(3, 7, 15, ui::kDimAlpha))','ui::backdrop(c)')
    menu=replace_function(menu,'void column(','''void column(ui::Ctx& c, float x0, float x1, float top) {
    ui::box(c,ImVec2(x0,top+12*c.s),ImVec2(x1,ui::prompt_bar_top(c)-16*c.s));
}''')
    # Remove the spreadsheet-like name boxes; labels sit directly on the card.
    menu=replace_once(menu,'    c.d->AddRectFilled(a, b, sel ? ui::kCellNameSel : ui::kCellName, 6*s);\n'
        '    c.d->AddRect(a, b, ui::kEdge, 0, std::max(1.0f, s));\n'
        '    if (sel) c.d->AddRectFilled(a, ImVec2(a.x + 4 * s, b.y), ui::kGoldHi);',
        '    if (sel) c.d->AddRectFilled(ImVec2(a.x,a.y+10*s),ImVec2(a.x+3*s,b.y-10*s),ui::kGlow,1.5f*s);')
    # All choice/slider/toggle cells get a rounded outline, and a separate gap after their label.
    start=menu.index('void choice_cell('); end=menu.index('std::string restart_line(',start)
    cells=menu[start:end]
    cells=cells.replace('c.d->AddRectFilled(a, b, ui::kCellDark);','c.d->AddRectFilled(a, b, ui::kCellDark,10*s);')
    cells=cells.replace('c.d->AddRect(a, b, ui::kEdge, 0, std::max(1.0f, s));','c.d->AddRect(a, b, ui::kEdge,10*s,0,std::max(1.0f,s));')
    cells=cells.replace('c.d->AddRectFilled(fa, fb, ui::kBronze);','c.d->AddRectFilled(fa, fb, ui::kBronze,7*s);')
    cells=cells.replace('ui::diamond(c, ImVec2(xv, ty), 4.5f * s, done);','c.d->AddCircleFilled(ImVec2(xv,ty),4*s,done,16);')
    menu=menu[:start]+cells+menu[end:]
    start=menu.index('void draw_options('); end=menu.index('void draw_tune_bar(',start)
    part=menu[start:end]
    part=part.replace('23 * s','19 * s')
    part=replace_once(part,'    const float ty = hh * 0.5f + s;',
        '    c.d->AddRectFilled(ImVec2(x-6*s,6*s),ImVec2(x+total+6*s,hh-6*s),ui::kCellDark,24*s);\n'
        '    c.d->AddRect(ImVec2(x-6*s,6*s),ImVec2(x+total+6*s,hh-6*s),ui::kEdge,24*s,0,std::max(1.f,s));\n'
        '    const float ty = hh * 0.5f + s;')
    a=part.index('        if (shown || i == hover_tab)'); b=part.index('        hits.add(x,',a)
    part=part[:a]+'''        const ImVec2 ta(x+2*s,10*s),tb(x+tw[i]-2*s,hh-10*s);
        if (shown) { ui::gold(c,ta,tb,19); ui::glow(c,ta,tb,19); }
        else if (i==hover_tab) c.d->AddRectFilled(ta,tb,ui::kTabInset,18*s);
        ui::text_mid(c,c.f.heading,19*s,x+28*s,ty,shown?ui::kGoldInk:ui::kBannerInk,tab_titles[i]);
'''+part[b:]
    part=part.replace('"OCARINA REBORN"','"Ocarina Reborn"')
    a=part.index('            const ImVec2 centre('); b=part.index('            const float tx =',a)
    part=part[:a]+'''            ui::ocarina(c,ImVec2(x0,ty-18*s),36*s);
            c.d->AddLine(ImVec2(x0+tri+4*s,ty-14*s),ImVec2(x0+tri+4*s,ty+14*s),ui::kBannerEdge,std::max(1.f,s));
'''+part[b:]
    part=part.replace('tx, ty - 7 * s','tx, ty')
    part=part.replace('                ui::text_mid(c, c.f.body, std::max(10 * s, px * 0.55f), tx + s, ty + 11 * s, ui::kAccent, "Powered by Sorax");\n','')
    part=replace_once(part,'    column(c, cx0, cx1, hh);','''    const float content_top=hh+76*s;
    ui::text_mid(c,c.f.strong,28*s,cx0+6*s,hh+36*s,ui::kInkBright,"Settings");
    c.d->AddLine(ImVec2(cx0,content_top),ImVec2(hx1,content_top),ui::alpha(ui::kEdge,.65f),std::max(1.f,s));
    column(c,cx0,cx1,content_top);
''')
    part=part.replace('std::max(hh + 26 * s, c.h * 0.30f)','content_top+12*s')
    part=part.replace('after, hh + 18 * s, bar_top - 12 * s','after, content_top+12*s, bar_top-16*s')
    part=part.replace('top = hh + 24 * s, rx0 = cx0 + 44 * s, rx1 = cx1 - 44 * s',
                      'top = content_top + 36 * s, rx0 = cx0 + 30 * s, rx1 = cx1 - 24 * s')
    part=part.replace('pitch = 48 * s','pitch = 52 * s')
    part=part.replace('bar_top) - 10 * s','bar_top) - 32 * s')
    part=part.replace('y > bottom + 8 * s','y + rh > bottom')
    part=part.replace('ImVec2(split, y + rh)','ImVec2(split-10*s, y + rh)')
    menu=menu[:start]+part+menu[end:]
    return ui, menu


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
    ui, menu = launcher_style(ui, menu)
    (vk / 'vk_ui.h').write_text(ui, encoding='utf-8')
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

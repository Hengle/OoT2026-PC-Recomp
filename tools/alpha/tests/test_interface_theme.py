import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ALPHA = Path(__file__).resolve().parents[1]
ROOT = ALPHA.parents[1]
sys.path.insert(0, str(ALPHA / 'launcher'))
sys.path.insert(0, str(ALPHA))
import interface_theme as theme
import game_settings
import engine_theme


class InterfaceThemeTests(unittest.TestCase):
    def test_default_restores_original_launcher_style(self):
        p=theme.palette(theme.DEFAULT)
        self.assertEqual((p['BG_TOP'],p['PANEL'],p['CELL']),('#0d1b36','#10224a','#0c1a3a'))
        self.assertEqual((p['BUTTON_TOP'],p['ACCENT_LO'],p['BUTTON_INK']),('#3b8bff','#1556e0','#ffffff'))

    def test_rgb_validation_and_hex_roundtrip(self):
        self.assertEqual(theme.rgb({}), (46, 123, 255))
        self.assertEqual(theme.rgb(dict(interface_red=-30, interface_green='bad', interface_blue=999)), (0, 123, 255))
        for value in ('#000000', '#ffffff', '#12a3ef'):
            self.assertEqual(theme.hex_color(theme.from_hex(value)), value)
        for bad in ('abc', '#1234567', '#zzzzzz', '10,20,30', ''):
            with self.assertRaises(ValueError): theme.from_hex(bad)

    def test_accent_and_panel_contrast_across_color_cube(self):
        for r in range(0, 256, 17):
            for g in range(0, 256, 17):
                for b in range(0, 256, 17):
                    p = theme.palette((r,g,b))
                    for ink, bg in (('ON_ACCENT','ACCENT'), ('TEXT','PANEL'), ('SUB','BG_TOP'), ('LINK','CELL')):
                        a, c = (theme.luminance(theme.rgb(theme.from_hex(p[k]))) for k in (ink,bg))
                        self.assertGreaterEqual((max(a,c)+.05)/(min(a,c)+.05), 4.5, ((r,g,b),ink,bg))

    def test_colors_roundtrip_without_changing_game_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            game_settings.write(tmp, {'volume':55, 'resolution':4, 'interface_red':1, 'interface_green':2, 'interface_blue':3})
            # Launcher writes only RGB; F1 reads the same keys and writes the full options file.
            game_settings.write(tmp, theme.from_hex('#bc38a1'))
            saved = game_settings.read(tmp)
            self.assertEqual(theme.hex_color(saved), '#bc38a1')
            self.assertEqual((saved['volume'],saved['resolution']), ('55','4'))
            game_settings.reset(tmp)
            self.assertEqual(theme.hex_color(game_settings.read(tmp)), '#bc38a1')
            self.assertEqual(game_settings.read(tmp)['volume'], '55')

    def test_staging_patch_reproduces_authored_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp); vk=root/'gpu/vk'; vk.mkdir(parents=True)
            for name in ('vk_ui.h','vk_menu.cpp','menu_i18n.h'):
                baseline=subprocess.check_output(['git','show','6913f93:engine/gpu/vk/'+name],cwd=ROOT)
                (vk/name).write_bytes(baseline)
            engine_theme.apply(root)
            for name in ('vk_ui.h','vk_menu.cpp','menu_i18n.h','ocr_interface_theme.h'):
                self.assertEqual((vk/name).read_text(encoding='utf-8'),
                                 subprocess.check_output(['git','show','4ad4254:engine/gpu/vk/'+name],cwd=ROOT).decode('utf-8').replace('\r\n','\n'),name)

    def test_native_palette_and_presets_match_launcher(self):
        cxx=shutil.which('clang++')
        if not cxx: self.skipTest('clang++ not available')
        program=r'''
#include "ocr_interface_theme.h"
#include <iostream>
int main() {
    using namespace mkwvk; using namespace interface_theme;
    for (int i=0;i<7;++i) { select_preset(i); if(preset_index()!=i) return 1; }
    int r,g,b;
    while(std::cin>>r>>g>>b) {
        RGB a{r,g,b}, f=foreground(a), p=tint({16,34,74},a), l=mix(a,{255,255,255},60);
        std::cout<<f.r<<' '<<f.g<<' '<<f.b<<' '<<p.r<<' '<<p.g<<' '<<p.b<<' '<<l.r<<' '<<l.g<<' '<<l.b<<'\n';
    }
}'''
        colors = [theme.rgb(theme.from_hex(v)) for _,v in theme.PRESETS] + [(0,0,0),(255,255,255),(0,255,0),(255,0,0)]
        with tempfile.TemporaryDirectory() as tmp:
            src=Path(tmp)/'theme.cpp'; exe=Path(tmp)/('theme.exe' if os.name=='nt' else 'theme')
            src.write_text(program)
            subprocess.run([cxx,'-std=c++17','-Wall','-Wextra','-Werror',str(src),'-I'+str(ALPHA/'hud'),'-o',str(exe)],
                           check=True,capture_output=True)
            output=subprocess.check_output([str(exe)],input=''.join('%d %d %d\n'%v for v in colors),text=True)
        for color, line in zip(colors,output.splitlines()):
            palette=theme.palette(color)
            expected=tuple(v for key in ('ON_ACCENT','PANEL','LINK') for v in theme.rgb(theme.from_hex(palette[key])))
            self.assertEqual(tuple(map(int,line.split())),expected)


if __name__ == '__main__': unittest.main()

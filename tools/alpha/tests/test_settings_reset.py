from pathlib import Path
import ast, json, os, shutil, subprocess, sys, tempfile, unittest
from unittest.mock import patch
ALPHA=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ALPHA/'launcher'))
import settings_reset, game_settings

class SettingsResetTests(unittest.TestCase):
    def setup_files(self, root):
        game=root/'game';game.mkdir();config=root/'config';config.mkdir()
        settings=config/'settings.json'
        cfg=dict(game_dir=str(game),backup_dir='save backups',dlss_sdk='installed SDK',ram_guard=3,
                 cheats=True,audio='7',language='ja',interface_red=255,hide_reporting_tip=True)
        settings.write_text(json.dumps(cfg))
        (game/'ocarina_reborn_options.ini').write_text('volume=4\nkey_a=123\npad_a=8\nresolution=4\ntunic_custom=1\n')
        (game/'ocarina_reborn_env.txt').write_text('RX_VK_TEX_MAX_DIM=1024\n')
        (game/'language.txt').write_text('ja\n')
        for name in ('user/save.bin','romfs/original.bin','mods/custom/data.bin','mkw_vk_pipelines.bin','ready.json'):
            p=game/name;p.parent.mkdir(exist_ok=True,parents=True);p.write_bytes(b'unchanged')
        return game,settings,cfg

    def test_complete_reset_preserves_content_and_backup(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game,settings,cfg=self.setup_files(root)
            with patch.object(settings_reset.classic_voices,'status',return_value={'enabled':True}),patch.object(settings_reset.classic_voices,'set_enabled') as toggle:
                fresh,backup=settings_reset.reset_all(game,settings,cfg,dict(audio='default',language='en-US',navi_enabled=True))
            self.assertEqual(game_settings.read(game),{})
            self.assertNotIn('RX_VK_', (game/'ocarina_reborn_env.txt').read_text())
            self.assertEqual((game/'language.txt').read_text(),'en-US\n')
            self.assertEqual(fresh,dict(audio='default',language='en-US',navi_enabled=True,game_dir=str(game),backup_dir='save backups',dlss_sdk='installed SDK'))
            self.assertEqual(json.loads(settings.read_text()),fresh)
            self.assertEqual(json.loads((backup/'settings.json').read_text()),cfg)
            self.assertIn('key_a=123',(backup/'ocarina_reborn_options.ini').read_text())
            for name in ('user/save.bin','romfs/original.bin','mods/custom/data.bin','mkw_vk_pipelines.bin','ready.json'):
                self.assertEqual((game/name).read_bytes(),b'unchanged')
            self.assertEqual(toggle.call_count,2)

    def test_failure_rolls_back_preferences(self):
        with tempfile.TemporaryDirectory() as tmp:
            game,settings,cfg=self.setup_files(Path(tmp))
            before={p:p.read_bytes() for p in (settings,game/'ocarina_reborn_options.ini',game/'ocarina_reborn_env.txt')}
            real=settings_reset._write;count=0
            def fail_once(path,data):
                nonlocal count
                count+=1
                if count==2:raise OSError('write failure')
                real(path,data)
            with patch.object(settings_reset,'_write',side_effect=fail_once),patch.object(settings_reset.classic_voices,'status',return_value={'enabled':False}),patch.object(settings_reset.classic_voices,'set_enabled'):
                with self.assertRaises(OSError):settings_reset.reset_all(game,settings,cfg,{})
            self.assertEqual(before,{p:p.read_bytes() for p in before})

    def test_off_and_previous_values_map_to_engine(self):
        tree=ast.parse((ALPHA/'launcher/launcher.py').read_text(encoding='utf-8'));nodes=[]
        for n in tree.body:
            if isinstance(n,ast.Assign) and any(isinstance(t,ast.Name) and t.id=='LOW_END_DEFAULTS' for t in n.targets):nodes.append(n)
            if isinstance(n,ast.FunctionDef) and n.name=='low_end_env':nodes.append(n)
        scope={};exec(compile(ast.Module(body=nodes,type_ignores=[]),'settings','exec'),scope)
        for value,reserve in enumerate((512,1024,3072,0)):
            env=scope['low_end_env'](dict(ram_guard=value))
            self.assertEqual(env['OCR_RAM_RESERVE_MB'],str(reserve))
            self.assertEqual(env['OCR_RAM_GUARD'],'0' if value==3 else '1')
        self.assertEqual(scope['low_end_env'](dict(tex_max_dim=2))['RX_VK_TEX_MAX_DIM'],'0')
        self.assertEqual(scope['low_end_env'](dict(tex_max_dim=1))['RX_VK_TEX_MAX_DIM'],'1024')

    def test_off_disables_actual_renderer_reserve_eviction(self):
        # Execute the real renderer guard against deterministic memory snapshots.
        from test_memory_guard import HARNESS
        root=ALPHA.parents[1]
        text=(root/'engine/gpu/vk/vk_texture.cpp').read_text(encoding='utf-8')
        a=text.index('bool ocr_ram_limited = false, ocr_ram_urgent = false;')
        guard=text[a:text.index('#endif',a)+len('#endif')]
        code=HARNESS.replace('/* GUARD */',guard.replace('std::chrono::steady_clock::now()','fake_now()'))
        code=code[:code.index('int main(')]+'''int main() {
            manual_gb=12; memory.ullAvailPhys=128*MB; memory.ullAvailPageFile=128*MB;
            const auto budget=run(12*GB,6*GB,10);
            if (getenv("OCR_RAM_GUARD") && atoi(getenv("OCR_RAM_GUARD"))==0) assert(budget==12*GB);
            else assert(budget<6*GB);
        }'''
        code='#include "ocr_streaming_policy.h"\nconst char* vram_env=nullptr;\n'+code
        compiler=shutil.which('clang++');self.assertIsNotNone(compiler)
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp);(p/'test.cpp').write_text(code)
            build=subprocess.run([compiler,'-std=c++17','-O2','-static','-I'+str(root/'engine/gpu/vk'),str(p/'test.cpp'),'-o',str(p/'test.exe')],capture_output=True,text=True)
            self.assertEqual(build.returncode,0,build.stderr)
            for enabled in ('0','1'):
                run=subprocess.run([str(p/'test.exe')],env=dict(os.environ,OCR_RAM_GUARD=enabled),capture_output=True,text=True,timeout=10)
                self.assertEqual(run.returncode,0,run.stderr)

if __name__=='__main__':unittest.main()

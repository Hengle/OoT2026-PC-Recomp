from pathlib import Path
import sys, tempfile, unittest
ALPHA=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ALPHA/'launcher'))
import game_settings

class PortraitOptionsTests(unittest.TestCase):
    def test_launcher_roundtrip_keeps_portrait_and_other_preferences(self):
        row=next(row for _,_,rows in game_settings.SECTIONS for row in rows if row[0]=='output_res')
        choices=row[3]
        with tempfile.TemporaryDirectory() as tmp:
            game=Path(tmp)
            game_settings.write(game,{'volume':73,'key_a':123})
            for size in ('720x1280','1080x1920','1440x2560','2160x3840'):
                game_settings.write(game,{'output_res':size})
                vals=game_settings.read(game)
                self.assertEqual(game_settings.current(vals,'output_res',choices)[0],size)
                self.assertEqual(str(vals['volume']),'73')
                self.assertEqual(str(vals['key_a']),'123')
            game_settings.reset(game)
            self.assertNotIn('output_res',game_settings.read(game))
            self.assertEqual(str(game_settings.read(game)['volume']),'73')

if __name__=='__main__':unittest.main()

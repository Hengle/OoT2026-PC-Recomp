"""Optional reserve control and explicit unlimited texture dimensions."""
from pathlib import Path
from engine_stability import replace_once
CHANGES = [('gpu/vk/vk_texture.cpp',
  '        while (!x.sparse && astc && x.skip + 1 < x.levels && bytes_at(x.skip) > skip_from &&',
  '        while (max_dim && !x.sparse && astc && x.skip + 1 < x.levels && bytes_at(x.skip) > skip_from &&'),
 ('gpu/vk/vk_texture.cpp',
  '        static const uint64_t reserve = (uint64_t)(getenv("OCR_RAM_RESERVE_MB") ? std::max(512, '
  'atoi(getenv("OCR_RAM_RESERVE_MB"))) : 1024) << 20;',
  '        static const bool ram_guard_enabled = !getenv("OCR_RAM_GUARD") || atoi(getenv("OCR_RAM_GUARD")) != 0;\n'
  '        static const uint64_t reserve = ram_guard_enabled ? (uint64_t)(getenv("OCR_RAM_RESERVE_MB") ? std::max(512, '
  'atoi(getenv("OCR_RAM_RESERVE_MB"))) : 1024) << 20 : 0;'),
 ('gpu/vk/vk_texture.cpp',
  '            const uint64_t phys_reserve = std::max<uint64_t>(reserve, 1536ull << 20);',
  '            const uint64_t phys_reserve = ram_guard_enabled ? std::max<uint64_t>(reserve, 1536ull << 20) : 0;'),
 ('gpu/vk/vk_texture.cpp',
  '            const bool critical = ms.ullAvailPageFile < (256ull << 20) || ms.ullAvailPhys < (512ull << 20) ||\n'
  '                                  (vknown && vused > vallowed / 100 * 97);',
  '            const bool critical = (ram_guard_enabled && (ms.ullAvailPageFile < (256ull << 20) || ms.ullAvailPhys < '
  '(512ull << 20))) ||\n'
  '                                  (vknown && vused > vallowed / 100 * 97);')]
def apply(root):
    for rel, old, new in CHANGES:
        p=Path(root)/rel
        p.write_text(replace_once(p.read_text(encoding='utf-8'),old,new),encoding='utf-8',newline='\n')

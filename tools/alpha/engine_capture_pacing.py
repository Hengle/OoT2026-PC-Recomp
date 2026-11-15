"""Wait for completed write-back recordings without waiting for unrelated queues."""
from pathlib import Path
from engine_stability import replace_once

CAPTURE_PART_WAIT = r'''// Ocarina Reborn: a capture only needs the recording that copied its mirrored pages.
// Never wait for a missing mapping here: this can be the replay thread which must
// submit that recording. Unknown mappings and direct-memory hazards use the old path.
bool capture_wait_part(uint64_t value, uint64_t part, uint64_t whole) {
    static const bool enabled = !getenv("OCR_CAPTURE_PART_WAIT") || atoi(getenv("OCR_CAPTURE_PART_WAIT")) != 0;
    if (!enabled || !rec_timeline || async_on() || !sync_waits_on() || per_queue_fences_off() ||
        !part || whole > completed() || memory_in_place_part() > part) return false;
    uint64_t seq = 0;
    {
        std::lock_guard mk(rec_map_mu);
        const auto it = part_rec.find(part);
        if (it == part_rec.end()) return false;
        seq = it->second;
    }
    int ok = 0;
    wait_rec_seq(seq, 250000000ull, &ok);
    static std::atomic<uint64_t> calls{0}, timeouts{0};
    const uint64_t count = ++calls;
    if (!ok) {
        if (++timeouts <= 8) logf("vk: a capture's wait for write-back %llu timed out (recording %llu, done %llu)",
            (unsigned long long)value, (unsigned long long)seq, (unsigned long long)completed());
    }
    if (count == 1 || count % 3000 == 0)
        logf("[OcarinaReborn/PERF] capture recording waits: %llu, timed out: %llu (full submission retained for direct-memory hazards)",
            (unsigned long long)count, (unsigned long long)timeouts.load());
    // A timeout already consumed the same 250 ms budget as the original path.
    // Do not add another full-submission wait after it.
    return true;
}
'''

def apply(root):
    root = Path(root)
    memory = root/'gpu/vk/vk_memory.cpp'
    text = memory.read_text(encoding='utf-8')
    text = replace_once(text, '    uint64_t late_value = 0;\n',
        '    uint64_t late_value = 0;\n    uint64_t late_part = 0, late_whole = 0; // capture-time write-back dependencies\n')
    text = replace_once(text, 'c->late.clear(), c->late_value = 0;',
        'c->late.clear(), c->late_value = 0, c->late_part = 0, c->late_whole = 0;')
    text = replace_once(text, '                        v = std::max(v, pv);\n', '''                        v = std::max(v, pv);
                        const uint64_t pp = wb_parts.get(pages[i]);
                        if (pp) c->late_part = std::max(c->late_part, pp);
                        else c->late_whole = std::max(c->late_whole, pv);
''')
    text = replace_once(text, 'else if (v) vk_timeline_wait(v);',
        'else if (v) vk_timeline_wait(v, c->late_part, c->late_whole);')
    text = replace_once(text, 'vk_timeline_wait(c->late_value);',
        'vk_timeline_wait(c->late_value, c->late_part, c->late_whole);')
    memory.write_text(text, encoding='utf-8', newline='\n')
    internal = root/'gpu/vk/vk_internal.h'
    text = replace_once(internal.read_text(encoding='utf-8'), 'void vk_timeline_wait(uint64_t v);',
        'void vk_timeline_wait(uint64_t v, uint64_t part = 0, uint64_t whole = 0);')
    internal.write_text(text, encoding='utf-8', newline='\n')
    replay = root/'gpu/vk/vk_replay.cpp'
    text = replay.read_text(encoding='utf-8')
    text = replace_once(text, 'bool wait_recorded(uint64_t f, uint64_t timeout_ns, int* ok);',
        'bool wait_recorded(uint64_t f, uint64_t timeout_ns, int* ok);\nbool capture_wait_part(uint64_t value, uint64_t part, uint64_t whole);')
    text = replace_once(text, 'void vk_timeline_wait(uint64_t v) {',
        'void vk_timeline_wait(uint64_t v, uint64_t part, uint64_t whole) {')
    text = replace_once(text, '    if (!timeline || completed() >= v) return;\n',
        '    if (!timeline || completed() >= v) return;\n    if (capture_wait_part(v, part, whole)) return;\n')
    anchor = 'uint64_t fence();\n/// (hookshot) A fence of one queue'
    text = replace_once(text, anchor, CAPTURE_PART_WAIT+anchor)
    replay.write_text(text, encoding='utf-8', newline='\n')

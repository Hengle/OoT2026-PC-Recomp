/* Optional daily-limit override for the supported game's AmiiboMgr.
   nx2/ocr_amiibo_rules.py verifies the game build, entry instructions and all
   four callers before inserting these entry hooks, before the stack prologues.

   Only the cooldown answers change. The reader's UID/model, tag file, clocks,
   saved timestamps, supported-figure/location checks and reward creation remain
   the game's own. Turning this off resumes the original checks on the next scan. */
#include "hos.h"
#include "ocr_amiibo_rules.h"

int rx_option(int id, int otherwise);

int ocr_amiibo_rule_override(Ctx *c, int rule) {
    if (!c || rx_option(OCR_OPT_UNLIMITED_AMIIBO, 0) != 1) return 0;
    const uint64_t caller = c->x[30];
    if (rule == OCR_AMIIBO_CLOCK_ALLOWED &&
            (caller == 0x8328bde8ull || caller == 0x8328be24ull)) {
        c->x[0] = 1;  /* the 24-hour/clock-change guard permits this scan */
        return 1;
    }
    if (rule == OCR_AMIIBO_USED_TODAY &&
            (caller == 0x8328be64ull || caller == 0x8328bec0ull)) {
        c->x[0] = 0;  /* the model's recorded calendar date does not block it */
        return 1;
    }
    return 0;  /* unrelated calls retain the original game behavior */
}

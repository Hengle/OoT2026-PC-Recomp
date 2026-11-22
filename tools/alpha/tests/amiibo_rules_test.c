/* Invented guest context. The hook text and policy implementation are production code. */
#include <assert.h>
#include <string.h>
#include "ocr_amiibo_rules.c"

static int option, original_calls;
int rx_option(int id, int otherwise) {
    assert(id == OCR_OPT_UNLIMITED_AMIIBO && otherwise == 0);
    return option;
}

static void clock_guard(Ctx *c) {
    /* CLOCK_HOOK */
    ++original_calls;
    c->x[0] = 0; /* representative original answer: clock/24-hour check blocked */
}
static void used_today(Ctx *c) {
    /* DATE_HOOK */
    ++original_calls;
    c->x[0] = 1; /* representative original answer: this figure was used today */
}
static Ctx fresh(uint64_t caller) {
    Ctx c;
    memset(&c, 0xa5, sizeof c);
    c.x[30] = caller;
    return c;
}
int main(void) {
    const uint64_t callers[] = {0x8328bde8, 0x8328be24, 0x8328be64, 0x8328bec0};
    for (int i = 0; i < 4; ++i) {
        const int rule = i < 2 ? OCR_AMIIBO_CLOCK_ALLOWED : OCR_AMIIBO_USED_TODAY;
        void (*call)(Ctx *) = i < 2 ? clock_guard : used_today;
        /* OFF and malformed option values do not change even one byte. */
        const int disabled[] = {0, -1, 2};
        for (unsigned j = 0; j < sizeof disabled / sizeof disabled[0]; ++j) {
            option = disabled[j];
            Ctx c = fresh(callers[i]), expected = c;
            assert(!ocr_amiibo_rule_override(&c, rule));
            assert(!memcmp(&c, &expected, sizeof c));
            original_calls = 0;
            call(&c);
            expected.x[0] = i < 2 ? 0 : 1;
            assert(original_calls == 1 && !memcmp(&c, &expected, sizeof c));
        }
        /* ON returns before the guest prologue; no stack/register/flag side effects. */
        option = 1;
        Ctx c = fresh(callers[i]), expected = c;
        expected.x[0] = i < 2 ? 1 : 0;
        original_calls = 0;
        call(&c);
        assert(original_calls == 0 && !memcmp(&c, &expected, sizeof c));
        /* Turning OFF again resumes the real function immediately. */
        option = 0;
        call(&c);
        expected.x[0] = i < 2 ? 0 : 1;
        assert(original_calls == 1 && !memcmp(&c, &expected, sizeof c));
    }
    option = 1;
    Ctx c = fresh(0x12345678), expected = c;
    for (int rule = -1; rule <= 2; ++rule) {
        assert(!ocr_amiibo_rule_override(&c, rule));
        assert(!memcmp(&c, &expected, sizeof c));
    }
    c = fresh(callers[0]); expected = c;
    assert(!ocr_amiibo_rule_override(&c, OCR_AMIIBO_USED_TODAY));
    assert(!memcmp(&c, &expected, sizeof c));
    c = fresh(callers[2]); expected = c;
    assert(!ocr_amiibo_rule_override(&c, OCR_AMIIBO_CLOCK_ALLOWED));
    assert(!memcmp(&c, &expected, sizeof c));
    assert(!ocr_amiibo_rule_override(0, OCR_AMIIBO_CLOCK_ALLOWED));
    return 0;
}

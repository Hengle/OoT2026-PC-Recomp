/* The player's equipped Ocarina actor, not an inventory/save edit.

   Verified main e0f3ccfa: EquipmentUser::update slot (82e16c80) reads
   EquipOcarina into its own 64-byte stack SafeString. Slot 13 is the playable
   actor; slot 16 appends _Holder. Both native creation paths consume that name.
   Substitute only those names in that caller's temporary buffer, before native
   creation, so the selected actor brings its own OcarinaParam and model.

   A changed selection requests those two slots once on the existing serialized
   live-player update, outside events and F1. Native creation remains asynchronous.
   Inventory/story flags are never changed. */
#include "hos.h"
#include "ocr_ocarina.h"
#include <string.h>

int rx_option(int id, int otherwise);
int hos_oot_is_player(Ctx *c, uint64_t actor);

/* One refresh must use the same choice for the playable actor and its holder,
   even if the menu changes from another thread during native creation. */
static _Thread_local int refresh_choice = -1;
static int custom_equipment_seen;
static uint64_t refreshed_actor;
static int refreshed_choice;
static unsigned refreshed_slots, refresh_failures;
static int64_t refresh_retry_at;

static int ocarina_supported_image(Ctx *c) {
    /* Guard both the build identity and the instructions defining this ABI.
       Checking before each rare equipment call also fails closed if a mod
       rewrites the native caller. nx2/ocr_ocarina.py inserts the entry hooks. */
    return !strcmp(hos_main_build_id, "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348") &&
        recomp_load32(c, 0x81033f20ull) == 0xd503237fu &&
        recomp_load32(c, 0x82e21a90ull) == 0xd503237fu &&
        recomp_load32(c, 0x82e171c8ull) == 0x7100369fu &&
        recomp_load32(c, 0x82e171d0ull) == 0x7100429fu &&
        recomp_load32(c, 0x82e173e0ull) == 0x52800808u &&
        recomp_load32(c, 0x82e17a54ull) == 0x9100a3e2u &&
        recomp_load32(c, 0x82e17a64ull) == 0x9788712fu &&
        recomp_load32(c, 0x82e17a30ull) == 0x94002818u &&
        recomp_load32(c, 0x82e16c80ull) == 0xd503237fu &&
        recomp_load32(c, 0x82e16c84ull) == 0xd10503ffu &&
        recomp_load32(c, 0x828104c8ull) == 0x32050108u &&
        recomp_load32(c, 0x828104ccull) == 0xb9002c08u &&
        recomp_load32(c, 0x828116b0ull) == 0x12047908u &&
        recomp_load32(c, 0x828116b4ull) == 0xb9002e68u &&
        recomp_load32(c, 0x80993044ull) == 0xf941ad00u;
}

static uint64_t ocarina_player_owner(Ctx *c, uint64_t equipment) {
    if (!c || !hos_mem_region(equipment, 0x20)) return 0;
    /* EquipmentUser owns the actor wrapper. hos_oot_is_player expects the
       player component, as in hos_oot_lift_player's established identity chain. */
    const uint64_t actor = recomp_load64(c, equipment + 0x18);
    if (!actor || !hos_mem_region(actor, 0x278) || recomp_load64(c, actor) != 0x84b45e18ull) return 0;
    const uint64_t components = recomp_load64(c, actor + 0x270);
    if (!components || !hos_mem_region(components, 0x328) ||
        recomp_load64(c, components + 0x200) != equipment) return 0;
    const uint64_t movement = recomp_load64(c, components + 0x320);
    if (movement < HOS_HEAP_BASE + 0x1d50 || !hos_mem_region(movement, 0x20) ||
        recomp_load64(c, movement + 0x18) != actor) return 0;
    const uint64_t player = movement - 0x1d50;
    if (!hos_mem_region(player, 0x18)) return 0;
    const uint64_t resource = recomp_load64(c, player + 0x10);
    if (!resource || !hos_mem_region(resource, 95) || !hos_oot_is_player(c, player)) return 0;
    return actor;
}

static void ocarina_equipment_name(Ctx *c, uint64_t caller) {
    const int selected = refresh_choice >= 0 ? refresh_choice :
        rx_option(OCR_OPT_OCARINA_INSTRUMENT, OCR_OCARINA_ORIGINAL);
    if (!c || (selected != OCR_OCARINA_FAIRY && selected != OCR_OCARINA_TIME) ||
        c->x[30] != caller || (c->x[1] != 13 && c->x[1] != 16)) return;
    if (!ocarina_supported_image(c)) return;

    const uint64_t arg = c->x[2], sp = c->x[31];
    if (sp > HOS_SPACE_END - 0x100 || arg != sp + 0x28 ||
        !hos_mem_region(arg, 12 + 64) || !ocarina_player_owner(c, c->x[0])) return;
    if (recomp_load64(c, arg) != arg + 12 || recomp_load32(c, arg + 8) != 64) return;

    char previous[64];
    for (unsigned i = 0; i < sizeof previous; ++i)
        previous[i] = (char)recomp_load8(c, arg + 12 + i);
    if (!memchr(previous, 0, sizeof previous)) return;
    const int holder = c->x[1] == 16;
    const char *fairy = holder ? "Item_Ocarina_Fairy_Holder" : "Item_Ocarina_Fairy";
    const char *time = holder ? "Item_Ocarina_Time_Holder" : "Item_Ocarina_Time";
    /* Never turn an empty/unknown slot into an item or replace a modded item. */
    if (strcmp(previous, fairy) && strcmp(previous, time)) return;
    const char *name = selected == OCR_OCARINA_FAIRY ? fairy : time;
    if (!strcmp(previous, name)) return;
    __atomic_store_n(&custom_equipment_seen, 1, __ATOMIC_RELAXED);
    for (unsigned i = 0;; ++i) {
        recomp_store8(c, arg + 12 + i, (unsigned char)name[i]);
        if (!name[i]) break;
    }
}

/* Called only from hos_oot_lift_player's serialized cheat/update section. No
   captured guest pointer is later dereferenced: every refresh validates the
   current actor and equipment backlinks. Repeated frames make no native calls.
   Events, F1 and the complete native PlayMusic action defer a change until Link
   is free again. The action sets/clears bit 27 of PlayerComponent+0x2c; this is
   checked separately from note-input waits, which do not cover its animations. */
void ocr_ocarina_player_update(Ctx *c, uint64_t actor, uint64_t components, int can_refresh) {
    if (!c || !can_refresh || refresh_choice >= 0) return;
    int selected = rx_option(OCR_OPT_OCARINA_INSTRUMENT, OCR_OCARINA_ORIGINAL);
    if (selected < OCR_OCARINA_ORIGINAL || selected > OCR_OCARINA_TIME) selected = OCR_OCARINA_ORIGINAL;
    const int custom = __atomic_load_n(&custom_equipment_seen, __ATOMIC_RELAXED);
    if (selected == OCR_OCARINA_ORIGINAL && !custom && refreshed_choice == OCR_OCARINA_ORIGINAL) return;
    if (actor == refreshed_actor && selected == refreshed_choice && refreshed_slots == 3 &&
        (selected != OCR_OCARINA_ORIGINAL || !custom)) return;
    if (!ocarina_supported_image(c) || !hos_mem_region(components, 0x360)) return;
    const uint64_t equipment = recomp_load64(c, components + 0x200);
    if (ocarina_player_owner(c, equipment) != actor || !actor ||
        recomp_load64(c, actor + 0x270) != components) return;
    const uint64_t player_state = recomp_load64(c, components + 0x358);
    if (!player_state || !hos_mem_region(player_state, 0x30) ||
        (recomp_load32(c, player_state + 0x2c) & 0x08000000u)) return;
    A64Fn update = a64_lookup(0x82e16c80ull);
    if (!update) return;
    if (refreshed_actor != actor || refreshed_choice != selected ||
        (selected == OCR_OCARINA_ORIGINAL && custom && refreshed_slots == 3)) {
        refreshed_actor = actor;
        refreshed_choice = selected;
        refreshed_slots = refresh_failures = 0;
        refresh_retry_at = 0;
    }
    const int64_t now = hos_now_ns();
    if (now < refresh_retry_at) return;
    const Ctx saved = *c;
    refresh_choice = selected;
    for (unsigned slot = 0; slot < 2; ++slot) {
        if (refreshed_slots & (1u << slot)) continue;
        c->x[0] = equipment; c->x[1] = slot ? 16 : 13; c->x[30] = 0;
        update(c);
        const int accepted = (int)(c->x[0] & 1);
        *c = saved;
        if (accepted) refreshed_slots |= 1u << slot;
    }
    refresh_choice = -1;
    if (refreshed_slots != 3) {
        /* Retry only refused slots, at most twice a second, backing off to 2 s.
           Never repeatedly recreate a slot already accepted by the game. */
        if (refresh_failures < 3) ++refresh_failures;
        refresh_retry_at = now + (250000000LL << refresh_failures);
    } else if (selected == OCR_OCARINA_ORIGINAL) {
        __atomic_store_n(&custom_equipment_seen, 0, __ATOMIC_RELAXED);
    }
}

void ocr_ocarina_equipment(Ctx *c, int path) {
    if (path == 0) ocarina_equipment_name(c, 0x82e17a68ull);
    else if (path == 1) ocarina_equipment_name(c, 0x82e17a34ull);
    /* native equipment creation always runs with all registers intact */
}

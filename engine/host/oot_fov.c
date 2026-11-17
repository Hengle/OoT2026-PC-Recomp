/* The Insert menu's Field of view, as a percentage of the game's current vertical
   angle. nx2/oot_fov.py calls this after the angle load, before the game builds its
   projection (including the cached half-angle tangent used by CPU culling).

   Only camera zero's gameplay view is adjusted. Event cameras keep their authored
   angle. The source camera is never written: zooms still vary with the game, each
   update starts from its own angle, and 100% restores it on the next update.

   (Ocarina Reborn) A picture narrower than 16:9 (9:16 portrait, 4:3, 16:10): the game keeps its vertical angle whatever the
   shape, so the cameras that take the narrow ratio (nx2/oot_wide.py) saw less to each side, the view zoomed in and cut
   (a 9:16 picture showed a third of the 16:9 width). The gameplay view keeps the horizontal angle it has at 16:9 instead
   and gains height ("vert+"): tan(v'/2) = tan(v/2) * (16/9) / ratio. A wider picture is as before (its cameras already
   widen). HOS_VERT_PLUS=0: the game's vertical angle at every shape, as before. */
#include "hos.h"
#include "../gpu/vk/vk_api.h"
#include <math.h>
#include <stdlib.h>
#include <string.h>

int rx_option(int id, int otherwise);
extern volatile float hos_wide_ratio;   /* host/hos_main.c: the picture's width / height, 0 at 16:9 */

/* the factor on the half-angle's tangent that keeps 16:9's horizontal view at the picture's ratio: 1 at 16:9 and wider */
static float narrow_factor(void) {
    static int on = -1;
    if (on < 0) {
        const char *e = getenv("HOS_VERT_PLUS");
        on = !(e && e[0] == '0');
    }
    const float r = hos_wide_ratio;
    if (!on || !(r > 0.0f) || r >= 16.0f / 9.0f * 0.99f) return 1.0f;
    return (16.0f / 9.0f) / r;
}

void hos_oot_fov(Ctx *c, uint64_t camera) {
    int percent = rx_option(HOS_OPT_FOV, 100);
    if (percent < 50 || percent > 150) percent = 100;
    const float narrow = narrow_factor();
    if ((percent == 100 && narrow == 1.0f) || !camera) return;

    const uint64_t views = recomp_load64(c, camera + 0x18);
    const uint64_t view = views ? recomp_load64(c, views + 8) : 0;
    if (!view || recomp_load64(c, view) != 0x84c18a88ULL) return;   /* sead::LookAtCamera */

    /* CameraMgr's first camera supplies the gameplay view (hos_main.c's free view
       uses the same ownership check). Portraits, reflections and UI stay alone. */
    const uint64_t singleton = recomp_load64(c, 0x84ca6bc0ULL);
    const uint64_t manager = singleton ? recomp_load64(c, singleton) : 0;
    const uint64_t cameras = manager && recomp_load32(c, manager + 32) ? recomp_load64(c, manager + 40) : 0;
    const uint64_t main_camera = cameras ? recomp_load64(c, cameras) : 0;
    if (!main_camera || recomp_load64(c, main_camera + 120) != view) return;

    const uint64_t event_singleton = recomp_load64(c, 0x84c9e090ULL);
    const uint64_t events = event_singleton ? recomp_load64(c, event_singleton) : 0;
    if (events && recomp_load64(c, events + 104)) return;

    float angle;
    memcpy(&angle, c->vreg[0], sizeof angle);
    if (!isfinite(angle) || angle <= 0.0f || angle >= 3.141592654f) return;
    if (narrow != 1.0f) angle = 2.0f * atanf(tanf(angle * 0.5f) * narrow);   /* (16:9's horizontal view, the height grown) */
    /* Keep the vertical lens within 5..140 degrees even during an extreme zoom. */
    angle = fminf(2.443460953f, fmaxf(0.087266463f, angle * ((float)percent / 100.0f)));
    uint32_t bits;
    memcpy(&bits, &angle, sizeof bits);
    a64_vset64(c->vreg[0], bits);
}

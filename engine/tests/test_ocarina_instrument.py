"""Verify the production Ocarina helper changes only a native caller's stack name."""
import argparse
import importlib.util
import subprocess
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]

PRELUDE = r'''
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define CHECK(x) do { if (!(x)) { fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); exit(1); } } while (0)
#define HOS_SPACE_END 0x8000000000ULL
#define HOS_HEAP_BASE 0x1000000000ULL
typedef struct { uint64_t x[32]; uint8_t other[256]; } Ctx;
typedef void (*A64Fn)(Ctx*);
static void native_update(Ctx *c);
static int missing_update, update_calls, change_during_update;
static unsigned refused_slots, slot_calls[2];
static int64_t now_ns;
int64_t hos_now_ns(void) { return now_ns; }
static char created_names[2][64];
static A64Fn a64_lookup(uint64_t pc) { CHECK(pc==0x82e16c80ULL); return missing_update?NULL:native_update; }
static unsigned char memory[16384];
static const uint64_t base = HOS_HEAP_BASE + 0x100000;
static int selected, wrong_image;
char hos_main_build_id[41] = "e0f3ccfaf50065ae4ea01eb5aeb13b1a45da3348";
int hos_mem_region(uint64_t a, uint64_t n) { return a >= base && a - base <= sizeof memory && n <= sizeof memory - (a - base); }
static void *at(uint64_t a, unsigned n) { CHECK(hos_mem_region(a,n)); return memory + a - base; }
static uint64_t recomp_load64(Ctx *c, uint64_t a) { (void)c; uint64_t n; memcpy(&n,at(a,8),8); return n; }
static uint32_t recomp_load32(Ctx *c, uint64_t a) {
    (void)c;
    static const uint64_t addr[] = {0x81033f20,0x82e21a90,0x82e171c8,0x82e171d0,0x82e173e0,0x82e17a54,0x82e17a64,0x82e17a30,0x82e16c80,0x82e16c84,0x828104c8,0x828104cc,0x828116b0,0x828116b4,0x80993044};
    static const uint32_t word[] = {0xd503237f,0xd503237f,0x7100369f,0x7100429f,0x52800808,0x9100a3e2,0x9788712f,0x94002818,0xd503237f,0xd10503ff,0x32050108,0xb9002c08,0x12047908,0xb9002e68,0xf941ad00};
    for(unsigned i=0;i<sizeof addr/sizeof addr[0];i++) if(a==addr[i]) return word[i] ^ wrong_image;
    uint32_t n; memcpy(&n,at(a,4),4); return n;
}
static uint8_t recomp_load8(Ctx *c, uint64_t a) { (void)c; return *(uint8_t*)at(a,1); }
static void recomp_store8(Ctx *c, uint64_t a, uint8_t n) { (void)c; *(uint8_t*)at(a,1)=n; }
int rx_option(int id,int otherwise) { (void)otherwise; CHECK(id==4203); return selected; }
int hos_oot_is_player(Ctx *c,uint64_t actor) {
    const uint64_t r = recomp_load64(c, actor+16);
    return recomp_load64(c,actor)==0x84b6c460ULL && !memcmp(at(r+88,7),"Player",7);
}
static void put64(uint64_t a,uint64_t n) { memcpy(at(a,8),&n,8); }
static void put32(uint64_t a,uint32_t n) { memcpy(at(a,4),&n,4); }
'''

MAIN = r'''
/* Stand-in only for the native slot update. It feeds production name hooks,
   simulates clobbering every register and can race a menu selection change. */
static void native_update(Ctx *c) {
    CHECK(c->x[0]==base+0x400);
    CHECK(c->x[1]==13 || c->x[1]==16);
    CHECK(c->x[30]==0);
    const unsigned holder=c->x[1]==16;
    ++slot_calls[holder];
    c->x[31]=base+0x180; c->x[2]=c->x[31]+0x28;
    c->x[30]=0x82e17a68;
    put64(c->x[2],c->x[2]+12); put32(c->x[2]+8,64);
    strcpy(at(c->x[2]+12,64),holder?"Item_Ocarina_Time_Holder":"Item_Ocarina_Time");
    ocr_ocarina_equipment(c,0);
    strcpy(created_names[holder],at(c->x[2]+12,64));
    ++update_calls;
    if(change_during_update && !holder) selected=2;
    memset(c,0x69,sizeof *c);
    c->x[0]=(refused_slots & (1u<<holder))?0:1;
}
static void setup(Ctx *c,int kind,int path,const char *name) {
    memset(memory,0xa5,sizeof memory); memset(c,0x5a,sizeof *c);
    c->x[0]=base+0x400; c->x[1]=kind; c->x[31]=base+0x100;
    c->x[2]=c->x[31]+0x28; c->x[30]=path ? 0x82e17a34 : 0x82e17a68;
    put64(c->x[2],c->x[2]+12); put32(c->x[2]+8,64);
    memcpy(at(c->x[2]+12,(unsigned)strlen(name)+1),name,strlen(name)+1);
    put64(c->x[0]+0x18,base+0x500); put64(base+0x500,0x84b45e18ULL);
    put64(base+0x770,base+0x800); put64(base+0xa00,c->x[0]);
    put64(base+0xb20,base+0x2d50); put64(base+0x2d68,base+0x500);
    put64(base+0xb58,base+0x1000); put32(base+0x102c,0);
    put64(base+0x1000,0x84b6c460ULL);
    put64(base+0x1010,base+0x600); memcpy(at(base+0x658,7),"Player",7);
    selected=1; wrong_image=0; hos_main_build_id[0]='e';
    custom_equipment_seen=0; refreshed_actor=0; refreshed_choice=0; refresh_choice=-1;
    missing_update=0; update_calls=0; change_during_update=0;
    refreshed_slots=refresh_failures=0; refresh_retry_at=0;
    refused_slots=slot_calls[0]=slot_calls[1]=0; now_ns=1000000000LL;
}
static void verify(Ctx *c,int path,const char *expected) {
    Ctx before=*c; unsigned char bytes[sizeof memory]; memcpy(bytes,memory,sizeof bytes);
    if(expected) memcpy(bytes+c->x[2]+12-base,expected,strlen(expected)+1);
    ocr_ocarina_equipment(c,path);
    CHECK(!memcmp(&before,c,sizeof before));
    CHECK(!memcmp(bytes,memory,sizeof bytes)); /* includes simulated inventory/save bytes */
}
int main(void) {
    Ctx c;
    const char *fairy[2]={"Item_Ocarina_Fairy","Item_Ocarina_Fairy_Holder"};
    const char *time[2]={"Item_Ocarina_Time","Item_Ocarina_Time_Holder"};
    for(int path=0;path<2;path++) for(int h=0;h<2;h++) {
        int kind=h?16:13;
        setup(&c,kind,path,time[h]); verify(&c,path,fairy[h]);
        setup(&c,kind,path,fairy[h]); selected=2; verify(&c,path,time[h]);
        setup(&c,kind,path,time[h]); selected=0; verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); selected=3; verify(&c,path,NULL);
        setup(&c,kind,path,fairy[h]); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); c.x[30]++; verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); c.x[1]=12; verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); c.x[2]+=8; verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put32(c.x[2]+8,63); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put64(c.x[2],c.x[2]+13); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put64(c.x[0]+0x18,0); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); memory[0x658]='N'; verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put64(base+0x1010,0); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put64(base+0x500,0x84b6c460ULL); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put64(base+0xa00,base+0x480); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); put64(base+0x2d68,base+0x510); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); wrong_image=1; verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); hos_main_build_id[0]='f'; verify(&c,path,NULL);
        setup(&c,kind,path,"Custom_Ocarina"); verify(&c,path,NULL);
        setup(&c,kind,path,""); verify(&c,path,NULL);
        setup(&c,kind,path,time[h]); memset(at(c.x[2]+12,64),'X',64); verify(&c,path,NULL);
    }
    setup(&c,13,0,time[0]); verify(&c,2,NULL);
    ocr_ocarina_equipment(NULL,0);
    /* A menu choice must refresh a previously spawned actor, without repeatedly
       destroying/recreating it every frame. No calls before a safe player tick. */
    setup(&c,13,0,time[0]); selected=0;
    Ctx before=c;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==0);
    selected=1;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,0);
    CHECK(update_calls==0); /* F1/event defers, no request is consumed */
    put32(base+0x102c,0x08000000);
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==0); /* whole free-play action, even between note waits */
    put32(base+0x102c,0);
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==2 && !memcmp(&c,&before,sizeof c));
    CHECK(!strcmp(created_names[0],fairy[0]) && !strcmp(created_names[1],fairy[1]));
    for(int i=0;i<200;i++) ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==2);
    selected=2;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==4 && !memcmp(&c,&before,sizeof c));
    CHECK(!strcmp(created_names[0],time[0]) && !strcmp(created_names[1],time[1]));
    selected=0;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==6 && !memcmp(&c,&before,sizeof c));
    CHECK(!strcmp(created_names[0],time[0]) && !strcmp(created_names[1],time[1]));
    for(int i=0;i<200;i++) ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==6);
    for(unsigned i=0x3000;i<sizeof memory;i++) CHECK(memory[i]==0xa5); /* simulated save area */

    setup(&c,13,0,time[0]); change_during_update=1; before=c;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(selected==2 && update_calls==2 && !memcmp(&c,&before,sizeof c));
    CHECK(!strcmp(created_names[0],fairy[0]) && !strcmp(created_names[1],fairy[1]));
    change_during_update=0;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==4 && !strcmp(created_names[0],time[0]));

    setup(&c,13,0,time[0]); verify(&c,0,fairy[0]); selected=0; /* switched off before first player tick */
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==2 && !strcmp(created_names[0],time[0]));
    setup(&c,13,0,time[0]); missing_update=1;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1); CHECK(update_calls==0);
    missing_update=0; wrong_image=1;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1); CHECK(update_calls==0);
    wrong_image=0;
    ocr_ocarina_player_update(&c,base+0x510,base+0x800,1); CHECK(update_calls==0);
    ocr_ocarina_player_update(&c,base+0x500,base+0x810,1); CHECK(update_calls==0);
    ocr_ocarina_player_update(NULL,base+0x500,base+0x800,1);
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1); CHECK(update_calls==2);
    setup(&c,13,0,time[0]); refused_slots=2; before=c;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==2 && slot_calls[0]==1 && slot_calls[1]==1);
    for(int i=0;i<200;i++) ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==2); /* backoff, no repeated native creation per frame */
    now_ns+=500000000LL;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==3 && slot_calls[0]==1 && slot_calls[1]==2);
    refused_slots=0; now_ns+=1000000000LL;
    ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==4 && slot_calls[0]==1 && slot_calls[1]==3 && !memcmp(&c,&before,sizeof c));
    for(int i=0;i<200;i++) ocr_ocarina_player_update(&c,base+0x500,base+0x800,1);
    CHECK(update_calls==4);
    puts("PASS: Ocarina selection, guarded live refresh, no repeat recreation, deferred changes, paired choice, context/save isolation");
    return 0;
}
'''


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--cc", default="gcc")
    args = p.parse_args()
    spec = importlib.util.spec_from_file_location("ocr_ocarina", ROOT / "nx2/ocr_ocarina.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    words = dict(mod.CHECKS)
    lifter = SimpleNamespace(after={mod.HOOKS[0][0]: "existing hook"})
    image = SimpleNamespace(word=lambda pc: words.get(pc, 0))
    assert mod.install(lifter, image, "unsupported") == 0 and len(lifter.after) == 1
    assert mod.install(lifter, image, mod.BUILD) == 1
    previous = dict(lifter.after)
    assert mod.install(lifter, image, mod.BUILD) == 1 and lifter.after == previous
    for pc, _ in mod.CHECKS:
        words[pc] ^= 1
        rejected = SimpleNamespace(after={})
        assert mod.install(rejected, image, mod.BUILD) == 0 and not rejected.after
        words[pc] ^= 1
    text = (ROOT / "host/ocr_ocarina.c").read_text(encoding="utf-8")
    text = "\n".join(line for line in text.splitlines() if not line.startswith("#include"))
    header = (ROOT / "host/ocr_ocarina.h").read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="reborn-ocarina-") as folder:
        src, exe = Path(folder) / "t.c", Path(folder) / "t.exe"
        src.write_text(PRELUDE + header + text + MAIN, encoding="utf-8")
        subprocess.run([args.cc,"-std=c11","-Wall","-Wextra","-Werror","-o",str(exe),str(src)],check=True)
        subprocess.run([str(exe)],check=True,timeout=10)


if __name__ == "__main__":
    main()

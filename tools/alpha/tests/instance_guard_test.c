#include "ocr_instance.h"

int main(int argc, char **argv) {
    int result = ocr_instance_enter(argc, argv);
    if (result) return result;
    puts("acquired");
    fflush(stdout);
    if (argc > 1 && !strcmp(argv[1], "--hold")) getchar();
    return 0;
}

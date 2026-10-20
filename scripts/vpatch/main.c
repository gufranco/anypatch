#include "apply_patch.h"

int main(int argc, char **argv) {
  if (argc != 4) {
    fputs("usage: vpatch-apply SOURCE PATCH OUTPUT\n", stderr);
    return 64;
  }
  HANDLE source = fopen(argv[1], "rb");
  HANDLE patch = fopen(argv[2], "rb");
  HANDLE output = fopen(argv[3], "w+b");
  if (source == NULL || patch == NULL || output == NULL) {
    perror("vpatch-apply");
    return 66;
  }
  int result = DoPatch(patch, source, output);
  fclose(output);
  if (result != PATCH_SUCCESS) {
    fprintf(stderr, "vpatch-apply: DoPatch returned %d\n", result);
  }
  return result;
}

#ifndef VPATCH_POSIX_WINDOWS_H
#define VPATCH_POSIX_WINDOWS_H

#include <stdint.h>
#include <stdio.h>

typedef FILE *HANDLE;
typedef uint32_t DWORD;
typedef unsigned int UINT;
typedef unsigned char BYTE;
typedef int BOOL;
typedef struct {
  DWORD dwLowDateTime;
  DWORD dwHighDateTime;
} FILETIME;

#define TRUE 1
#define FALSE 0
#define FILE_BEGIN SEEK_SET
#define FILE_CURRENT SEEK_CUR
#define FILE_END SEEK_END

static inline BOOL ReadFile(HANDLE file, void *buffer, DWORD wanted, DWORD *got, void *unused) {
  (void)unused;
  *got = (DWORD)fread(buffer, 1, wanted, file);
  return !ferror(file);
}

static inline BOOL WriteFile(HANDLE file, const void *buffer, DWORD wanted, DWORD *put, void *unused) {
  (void)unused;
  *put = (DWORD)fwrite(buffer, 1, wanted, file);
  return !ferror(file);
}

static inline DWORD SetFilePointer(HANDLE file, int32_t distance, void *unused, int whence) {
  (void)unused;
  fseek(file, whence == SEEK_SET ? (long)(uint32_t)distance : (long)distance, whence);
  return (DWORD)ftell(file);
}

static inline void GetSystemTimeAsFileTime(FILETIME *time) {
  time->dwLowDateTime = 0;
  time->dwHighDateTime = 0;
}

static inline BOOL SetFileTime(HANDLE file, void *created, void *accessed, FILETIME *written) {
  (void)file;
  (void)created;
  (void)accessed;
  (void)written;
  return TRUE;
}

#ifndef min
#define min(a, b) ((a) < (b) ? (a) : (b))
#endif

#define long int

#endif

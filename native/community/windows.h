#ifndef DD_WINDOWS_H
#define DD_WINDOWS_H
#define _ACRTIMP
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0602
#include "core.h"
#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
size_t dd_strlen(const char *);
void *memcpy(void *, const void *, size_t);
void *memset(void *, int, size_t);
int memcmp(const void *, const void *, size_t);
int dd_connection_main(void);
int dd_sha(const unsigned char *, size_t, char[65]);
int dd_paths(WCHAR request[1024], WCHAR response[1024]);
int dd_recent(const WCHAR *, unsigned);
int dd_read(const WCHAR *, unsigned char *, DWORD, DWORD *);
int dd_write(const WCHAR *, const unsigned char *, DWORD);
void dd_log(const char *);
void dd_ascii_wide(const char *, WCHAR *, size_t);
int dd_restore_key(char[69]);
int dd_remember_key(const char *);
int dd_forget_key(void);
#endif

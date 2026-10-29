#ifndef DD_WINDOWS_H
#define DD_WINDOWS_H
#define _ACRTIMP
#define WIN32_LEAN_AND_MEAN
#define _WIN32_WINNT 0x0602
#include "core.h"
#include <windows.h>
#include <winhttp.h>
#include <bcrypt.h>
/* Test builds only (-DDD_FAULT_TEST): crash on purpose at a named point when
 * DD_TEST_FAULT names it, to prove the guards. Release builds compile it out. */
#ifdef DD_FAULT_TEST
void dd_test_point(const char *name);
#define DD_TEST_POINT(name) dd_test_point(name)
#else
#define DD_TEST_POINT(name) ((void)0)
#endif
#define DD_WIDEN(x) L##x
#define DD_WIDE(x) DD_WIDEN(x)
size_t dd_strlen(const char *);
void *memcpy(void *, const void *, size_t);
void *memset(void *, int, size_t);
int memcmp(const void *, const void *, size_t);
/* proxy.c: shared by the DLL's threads. Replies are checked and written while
 * holding dd_mailbox. */
#define DD_BROKEN_MESSAGE "HoloNet stopped after an internal error. Restart the game to use HoloNet."
extern CRITICAL_SECTION dd_mailbox;
extern volatile LONG dd_broken;
void dd_fault(const char *message);
HANDLE dd_thread(LPTHREAD_START_ROUTINE start, LPVOID parameter);
/* worker.c: browse, import and copy requests. A worker whose generation is
 * no longer current must not reply. */
extern volatile LONG dd_worker_generation;
int dd_worker_once(LONG generation);
/* connection.c: the key, My Shares and sharing. */
void dd_connection_start(void);
void dd_connection_poll(void);
void dd_connection_drop(void);
void dd_connection_wipe(void);
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

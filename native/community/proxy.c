#include "windows.h"
/* Forward version information APIs for the executable and all dependencies.
 * Resolve their implementation from System32, never search the game
 * directory. HoloNet runs on this DLL's own threads and has no Unreal/UE4SS
 * hooks or native ABI calls.
 */
static INIT_ONCE once = INIT_ONCE_STATIC_INIT;
static HMODULE real_version = 0;
static BOOL CALLBACK load_version(PINIT_ONCE init, PVOID parameter,
                                  PVOID *context) {
  WCHAR path[1024];
  UINT n = GetSystemDirectoryW(path, 990);
  const WCHAR *s = L"\\version.dll";
  size_t i;
  (void)init;
  (void)parameter;
  (void)context;
  if (!n || n >= 990)
    return FALSE;
  for (i = 0; s[i]; i++)
    path[n + i] = s[i];
  path[n + i] = 0;
  real_version = LoadLibraryExW(path, 0, LOAD_LIBRARY_SEARCH_SYSTEM32);
  return real_version != 0;
}
static FARPROC symbol(const char *name) {
  if (!InitOnceExecuteOnce(&once, load_version, 0, 0))
    return 0;
  return GetProcAddress(real_version, name);
}
/* Forward the complete public version API: graphics and other dependencies
 * can import functions beyond the executable's own import table. */
BOOL WINAPI DD_GetFileVersionInfoA(LPCSTR file, DWORD handle, DWORD len, LPVOID data) {
  typedef BOOL(WINAPI *fn)(LPCSTR, DWORD, DWORD, LPVOID);
  fn f = (fn)symbol("GetFileVersionInfoA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(file, handle, len, data);
}
DWORD WINAPI DD_GetFileVersionInfoSizeA(LPCSTR file, LPDWORD handle) {
  typedef DWORD(WINAPI *fn)(LPCSTR, LPDWORD);
  fn f = (fn)symbol("GetFileVersionInfoSizeA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(file, handle);
}
BOOL WINAPI DD_GetFileVersionInfoExA(DWORD flags, LPCSTR file, DWORD handle, DWORD len, LPVOID data) {
  typedef BOOL(WINAPI *fn)(DWORD, LPCSTR, DWORD, DWORD, LPVOID);
  fn f = (fn)symbol("GetFileVersionInfoExA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, file, handle, len, data);
}
DWORD WINAPI DD_GetFileVersionInfoSizeExA(DWORD flags, LPCSTR file, LPDWORD handle) {
  typedef DWORD(WINAPI *fn)(DWORD, LPCSTR, LPDWORD);
  fn f = (fn)symbol("GetFileVersionInfoSizeExA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, file, handle);
}
BOOL WINAPI DD_VerQueryValueA(LPCVOID block, LPCSTR sub, LPVOID * buffer, PUINT len) {
  typedef BOOL(WINAPI *fn)(LPCVOID, LPCSTR, LPVOID *, PUINT);
  fn f = (fn)symbol("VerQueryValueA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(block, sub, buffer, len);
}
DWORD WINAPI DD_VerLanguageNameA(DWORD language, LPSTR buffer, DWORD size) {
  typedef DWORD(WINAPI *fn)(DWORD, LPSTR, DWORD);
  fn f = (fn)symbol("VerLanguageNameA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(language, buffer, size);
}
DWORD WINAPI DD_VerFindFileA(DWORD flags, LPCSTR file, LPCSTR windows_dir, LPCSTR app_dir, LPSTR current_dir, PUINT current_len, LPSTR destination_dir, PUINT destination_len) {
  typedef DWORD(WINAPI *fn)(DWORD, LPCSTR, LPCSTR, LPCSTR, LPSTR, PUINT, LPSTR, PUINT);
  fn f = (fn)symbol("VerFindFileA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, file, windows_dir, app_dir, current_dir, current_len, destination_dir, destination_len);
}
DWORD WINAPI DD_VerInstallFileA(DWORD flags, LPCSTR source_file, LPCSTR destination_file, LPCSTR source_dir, LPCSTR destination_dir, LPCSTR current_dir, LPSTR temporary_file, PUINT temporary_len) {
  typedef DWORD(WINAPI *fn)(DWORD, LPCSTR, LPCSTR, LPCSTR, LPCSTR, LPCSTR, LPSTR, PUINT);
  fn f = (fn)symbol("VerInstallFileA");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, source_file, destination_file, source_dir, destination_dir, current_dir, temporary_file, temporary_len);
}
BOOL WINAPI DD_GetFileVersionInfoW(LPCWSTR file, DWORD handle, DWORD len, LPVOID data) {
  typedef BOOL(WINAPI *fn)(LPCWSTR, DWORD, DWORD, LPVOID);
  fn f = (fn)symbol("GetFileVersionInfoW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(file, handle, len, data);
}
DWORD WINAPI DD_GetFileVersionInfoSizeW(LPCWSTR file, LPDWORD handle) {
  typedef DWORD(WINAPI *fn)(LPCWSTR, LPDWORD);
  fn f = (fn)symbol("GetFileVersionInfoSizeW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(file, handle);
}
BOOL WINAPI DD_GetFileVersionInfoExW(DWORD flags, LPCWSTR file, DWORD handle, DWORD len, LPVOID data) {
  typedef BOOL(WINAPI *fn)(DWORD, LPCWSTR, DWORD, DWORD, LPVOID);
  fn f = (fn)symbol("GetFileVersionInfoExW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, file, handle, len, data);
}
DWORD WINAPI DD_GetFileVersionInfoSizeExW(DWORD flags, LPCWSTR file, LPDWORD handle) {
  typedef DWORD(WINAPI *fn)(DWORD, LPCWSTR, LPDWORD);
  fn f = (fn)symbol("GetFileVersionInfoSizeExW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, file, handle);
}
BOOL WINAPI DD_VerQueryValueW(LPCVOID block, LPCWSTR sub, LPVOID * buffer, PUINT len) {
  typedef BOOL(WINAPI *fn)(LPCVOID, LPCWSTR, LPVOID *, PUINT);
  fn f = (fn)symbol("VerQueryValueW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(block, sub, buffer, len);
}
DWORD WINAPI DD_VerLanguageNameW(DWORD language, LPWSTR buffer, DWORD size) {
  typedef DWORD(WINAPI *fn)(DWORD, LPWSTR, DWORD);
  fn f = (fn)symbol("VerLanguageNameW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(language, buffer, size);
}
DWORD WINAPI DD_VerFindFileW(DWORD flags, LPCWSTR file, LPCWSTR windows_dir, LPCWSTR app_dir, LPWSTR current_dir, PUINT current_len, LPWSTR destination_dir, PUINT destination_len) {
  typedef DWORD(WINAPI *fn)(DWORD, LPCWSTR, LPCWSTR, LPCWSTR, LPWSTR, PUINT, LPWSTR, PUINT);
  fn f = (fn)symbol("VerFindFileW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, file, windows_dir, app_dir, current_dir, current_len, destination_dir, destination_len);
}
DWORD WINAPI DD_VerInstallFileW(DWORD flags, LPCWSTR source_file, LPCWSTR destination_file, LPCWSTR source_dir, LPCWSTR destination_dir, LPCWSTR current_dir, LPWSTR temporary_file, PUINT temporary_len) {
  typedef DWORD(WINAPI *fn)(DWORD, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPCWSTR, LPWSTR, PUINT);
  fn f = (fn)symbol("VerInstallFileW");
  if (!f) { SetLastError(ERROR_PROC_NOT_FOUND); return 0; }
  return f(flags, source_file, destination_file, source_dir, destination_dir, current_dir, temporary_file, temporary_len);
}
/* Everything below runs on threads this DLL starts; the game's own threads
 * only ever enter the forwarders above. Each thread body runs inside a
 * structured exception guard: a fault in HoloNet code is caught, logged and
 * the key wiped, HoloNet answers every later request with DD_BROKEN_MESSAGE,
 * and the game keeps running. */
CRITICAL_SECTION dd_mailbox;
volatile LONG dd_broken;
static WCHAR request_path[1024], response_path[1024];
static unsigned char watched[DD_SAVE_MAX], fresh[DD_SAVE_MAX], reply[DD_SAVE_MAX];
static DWORD watched_size;
static ULONGLONG began;
static HANDLE worker;
static int worker_waiting, worker_active, broken_answered;
void dd_fault(const char *message) {
  if (InterlockedExchange(&dd_broken, 1))
    return;
  __try {
    dd_connection_wipe();
    dd_log(message);
  } __except (EXCEPTION_EXECUTE_HANDLER) {
  }
}
HANDLE dd_thread(LPTHREAD_START_ROUTINE start, LPVOID parameter) {
  /* Explicit stack: JSON parsing keeps a 256 KB token table on the stack, and
   * the game's default thread stack size is not ours to assume. */
  return CreateThread(0, 2u << 20, start, parameter,
                      STACK_SIZE_PARAM_IS_A_RESERVATION, 0);
}
/* Reply with a fixed message when the request is still exactly the one
 * watched. Same lock as every other reply, so a timeout and a late answer
 * never both land. */
static void answer(const char *message) {
  dd_save save;
  const char *error;
  char wire[512];
  size_t written;
  DWORD n;
  if (!dd_save_read(watched, watched_size, &save, &error) ||
      !dd_error_wire(wire, sizeof(wire), save.token, message))
    return;
  EnterCriticalSection(&dd_mailbox);
  __try {
    if (dd_read(request_path, fresh, sizeof(fresh), &n) && n == watched_size &&
        !memcmp(fresh, watched, n) &&
        dd_save_response(watched, watched_size, &save, wire, reply,
                         sizeof(reply), &written))
      dd_write(response_path, reply, (DWORD)written);
  } __finally {
    LeaveCriticalSection(&dd_mailbox);
  }
}
static DWORD WINAPI worker_main(LPVOID generation) {
  __try {
    dd_worker_once((LONG)(LONG_PTR)generation);
  } __except (EXCEPTION_EXECUTE_HANDLER) {
    dd_fault("HoloNet stopped after an internal error in a browse or import "
             "request. Restart the game to use HoloNet.");
  }
  return 0;
}
static int worker_running(void) {
  if (!worker)
    return 0;
  if (WaitForSingleObject(worker, 0) == WAIT_TIMEOUT)
    return 1;
  CloseHandle(worker);
  worker = 0;
  return 0;
}
/* A dropped worker can no longer reply (its generation is stale). It is never
 * terminated; it returns after its current network step. */
static void drop_worker(void) {
  InterlockedIncrement(&dd_worker_generation);
  worker_waiting = worker_active = 0;
}
static int is(const dd_save *save, const char *input) {
  return !memcmp(save->input, input, dd_strlen(input) + 1);
}
static void route(void) {
  dd_save control;
  const char *error;
  DD_TEST_POINT("mailbox");
  if (!dd_save_read(watched, watched_size, &control, &error)) {
    dd_log("Rejected unsupported or malformed mailbox SaveGame.");
    return;
  }
  if (dd_broken) {
    answer(DD_BROKEN_MESSAGE);
    return;
  }
  /* Requests that need the key belong to the connection (connection.c), which
   * reads them itself on the next poll. */
  if (is(&control, "FORGET")) {
    dd_connection_drop();
    answer(dd_forget_key() ? "Forgot connection. The saved key was removed "
                             "from this computer."
                           : "Could not remove the saved connection. Check "
                             "local file permissions and retry Forget "
                             "connection.");
  } else if (is(&control, "DISCONNECT")) {
    dd_connection_drop();
    answer("Disconnected for this session. Use Forget connection to remove a "
           "remembered key.");
  } else if (is(&control, "AUTH")) {
    dd_connection_drop(); /* A new key replaces any connection in progress. */
  } else if (!is(&control, "CONNECT") && !is(&control, "PUBLISH") &&
             memcmp(control.input, "MYSHARES/", 9)) {
    worker_waiting = worker_active = 1;
  }
}
static void tick(void) {
  DWORD count = 0;
  int exists = dd_recent(request_path, 45) &&
               dd_read(request_path, fresh, sizeof(fresh), &count);
  if (!exists) {
    if (watched_size) {
      drop_worker();
      SecureZeroMemory(watched, sizeof(watched));
      watched_size = 0;
    }
  } else if (count != watched_size || memcmp(fresh, watched, count)) {
    drop_worker();
    SecureZeroMemory(watched, sizeof(watched));
    memcpy(watched, fresh, count);
    watched_size = count;
    began = GetTickCount64();
    route();
  } else if (worker_active && GetTickCount64() - began >= 25000) {
    EnterCriticalSection(&dd_mailbox);
    __try {
      drop_worker();
      dd_log("HoloNet request timed out.");
    } __finally {
      LeaveCriticalSection(&dd_mailbox);
    }
    answer("HoloNet didn't answer in time. Try again when you're online.");
  }
  SecureZeroMemory(fresh, sizeof(fresh));
  if (dd_broken) {
    /* The request a crashed thread was working on is answered at once. */
    if (!broken_answered) {
      broken_answered = 1;
      drop_worker();
      if (watched_size)
        answer(DD_BROKEN_MESSAGE);
    }
    return;
  }
  /* One worker at a time: a new request waits for a dropped one to return. */
  if (worker_waiting && !worker_running()) {
    worker_waiting = 0;
    worker = dd_thread(worker_main, (LPVOID)(LONG_PTR)dd_worker_generation);
    if (!worker) {
      worker_active = 0;
      answer("Could not start the HoloNet request. Try again.");
    }
  } else if (worker_active && !worker_waiting && !worker_running())
    worker_active = 0;
  dd_connection_poll();
}
static int run(void) {
  dd_save stale;
  const char *error;
  DWORD bytes;
  if (!dd_paths(request_path, response_path))
    return 0;
  dd_log("HoloNet bridge " DD_VERSION " loaded (one DLL, no other programs). "
         "Requests have a 25-second deadline.");
  /* Remove an unfinished key-entry request from a prior game session. Only
   * connection.key is eligible for automatic reconnect. */
  if (dd_read(request_path, fresh, sizeof(fresh), &bytes) &&
      dd_save_read(fresh, bytes, &stale, &error) && is(&stale, "AUTH"))
    DeleteFileW(request_path);
  SecureZeroMemory(fresh, sizeof(fresh));
  dd_connection_start();
  for (;;) {
    tick();
    Sleep(100);
  }
}
static DWORD WINAPI monitor(PVOID ignored) {
  HMODULE pin;
  (void)ignored;
  /* Pin only our module for the process lifetime. Nothing is awaited in
   * DllMain. */
  GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_PIN |
                         GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,
                     (LPCWSTR)(const void *)&monitor, &pin);
  Sleep(500);
  InitializeCriticalSection(&dd_mailbox);
  __try {
    if (!run())
      return 0;
  } __except (EXCEPTION_EXECUTE_HANDLER) {
    dd_fault("HoloNet stopped after an internal error in the mailbox thread. "
             "Restart the game to use HoloNet.");
  }
  /* Keep answering, so the game shows why HoloNet stopped. A second fault
   * ends this thread quietly. */
  __try {
    for (;;) {
      tick();
      Sleep(100);
    }
  } __except (EXCEPTION_EXECUTE_HANDLER) {
  }
  return 0;
}
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
  (void)reserved;
  if (reason == DLL_PROCESS_ATTACH) {
    HANDLE thread;
    /* The thread starts only after the loader lock is released; nothing here
     * waits for it. */
    DisableThreadLibraryCalls(module);
    thread = dd_thread(monitor, 0);
    if (thread)
      CloseHandle(thread);
  }
  return TRUE;
}

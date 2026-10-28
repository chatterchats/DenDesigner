/* Native cancellation/deadline smoke harness, only for a disposable prefix.
 * Compile DD_HANG_WORKER for a harmless worker that waits without networking.
 */
#include "windows.h"
static WCHAR request[1024], response[1024], pidpath[1100];
static void paths(void) {
  size_t n, i;
  const WCHAR *s = L"child.pid";
  if (!dd_paths(request, response))
    ExitProcess(40);
  for (n = 0; response[n]; n++)
    pidpath[n] = response[n];
  pidpath[n] = 0;
  while (n && pidpath[n - 1] != '\\')
    n--;
  for (i = 0; s[i]; i++)
    pidpath[n + i] = s[i];
  pidpath[n + i] = 0;
}
#ifdef DD_HANG_WORKER
void mainCRTStartup(void) {
  DWORD pid = GetCurrentProcessId();
  paths();
  if (!dd_write(pidpath, (const unsigned char *)&pid, sizeof(pid)))
    ExitProcess(41);
  Sleep(60000);
  ExitProcess(0);
}
#else
void mainCRTStartup(void) {
  WCHAR path[1024], mode[32];
  DWORD n, pid = 0, size = 0;
  ULONGLONG start;
  HANDLE child;
  size_t i;
  paths();
  GetEnvironmentVariableW(L"DD_SMOKE_MODE", mode, 32);
  if (mode[0] == 'v') {
    if (!dd_read(pidpath, (unsigned char *)&pid, sizeof(pid), &size) ||
        size != sizeof(pid))
      ExitProcess(50);
    child = OpenProcess(SYNCHRONIZE, FALSE, pid);
    if (child) {
      if (WaitForSingleObject(child, 3000) != WAIT_OBJECT_0)
        ExitProcess(51);
      CloseHandle(child);
    } else if (GetLastError() != ERROR_INVALID_PARAMETER)
      ExitProcess(52);
    dd_log("LIFECYCLE_SMOKE: kill-on-close job removed worker on parent exit.");
    ExitProcess(0);
  }
  n = GetModuleFileNameW(0, path, 990);
  while (n && path[n - 1] != '\\')
    n--;
  {
    const WCHAR *s = L"version.dll";
    for (i = 0; s[i]; i++)
      path[n + i] = s[i];
    path[n + i] = 0;
  }
  if (!LoadLibraryExW(path, 0, LOAD_WITH_ALTERED_SEARCH_PATH))
    ExitProcess(42);
  start = GetTickCount64();
  while (GetTickCount64() - start < 5000) {
    if (dd_read(pidpath, (unsigned char *)&pid, sizeof(pid), &size) &&
        size == sizeof(pid))
      break;
    Sleep(50);
  }
  if (!pid)
    ExitProcess(43);
  child = OpenProcess(SYNCHRONIZE, FALSE, pid);
  if (!child)
    ExitProcess(44);
  if (mode[0] == 'c') {
    if (!DeleteFileW(request))
      ExitProcess(45);
    if (WaitForSingleObject(child, 3000) != WAIT_OBJECT_0)
      ExitProcess(46);
    if (GetFileAttributesW(response) != INVALID_FILE_ATTRIBUTES)
      ExitProcess(47);
    dd_log("LIFECYCLE_SMOKE: deleting request cancelled owned worker without "
           "response.");
    CloseHandle(child);
    ExitProcess(0);
  }
  if (mode[0] == 'd') {
    if (WaitForSingleObject(child, 28000) != WAIT_OBJECT_0)
      ExitProcess(48);
    Sleep(300);
    if (GetFileAttributesW(response) == INVALID_FILE_ATTRIBUTES)
      ExitProcess(49);
    dd_log("LIFECYCLE_SMOKE: total deadline terminated owned worker and "
           "returned error.");
    CloseHandle(child);
    ExitProcess(0);
  }
  /* mode exit: job handle belongs to this process; an external observer can
   * verify worker termination when the process exits. */
  dd_log("LIFECYCLE_SMOKE: parent exiting with pending owned worker.");
  ExitProcess(0);
}
#endif

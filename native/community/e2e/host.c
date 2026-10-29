/* Stands in for the game: loads version.dll from its folder, then idles until
 * a file named "quit" appears next to it (or 15 minutes pass). */
#define _ACRTIMP
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
void mainCRTStartup(void) {
  WCHAR path[1024], quit[1024]; DWORD n = GetModuleFileNameW(0, path, 990), i; ULONGLONG start = GetTickCount64();
  while (n && path[n - 1] != '\\') n--;
  for (i = 0; i < n; i++) quit[i] = path[i];
  lstrcpyW(path + n, L"version.dll"); lstrcpyW(quit + n, L"quit");
  if (!LoadLibraryW(path)) ExitProcess(10);
  while (GetTickCount64() - start < 900000) {
    if (GetFileAttributesW(quit) != INVALID_FILE_ATTRIBUTES) { DeleteFileW(quit); ExitProcess(0); }
    Sleep(100);
  }
  ExitProcess(0);
}

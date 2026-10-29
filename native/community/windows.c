#include "windows.h"
int _fltused = 0;
/* Link only Windows system APIs. Avoid both the MSVC and MinGW CRT. */
void *memcpy(void *d, const void *s, size_t n) {
  volatile unsigned char *a = d;
  const volatile unsigned char *b = s;
  size_t i;
  for (i = 0; i < n; i++)
    a[i] = b[i];
  return d;
}
void *memset(void *d, int v, size_t n) {
  volatile unsigned char *a = d;
  size_t i;
  for (i = 0; i < n; i++)
    a[i] = (unsigned char)v;
  return d;
}
int memcmp(const void *d, const void *s, size_t n) {
  const unsigned char *a = d, *b = s;
  size_t i;
  for (i = 0; i < n; i++)
    if (a[i] != b[i])
      return a[i] - b[i];
  return 0;
}
size_t dd_strlen(const char *s) {
  size_t n = 0;
  while (s[n])
    n++;
  return n;
}
void dd_ascii_wide(const char *s, WCHAR *out, size_t cap) {
  size_t i;
  for (i = 0; i + 1 < cap && s[i]; i++)
    out[i] = (WCHAR)(unsigned char)s[i];
  out[i] = 0;
}
static size_t wlen(const WCHAR *s) {
  size_t n = 0;
  while (s[n])
    n++;
  return n;
}
static int cat(WCHAR *s, size_t cap, const WCHAR *t) {
  size_t n = wlen(s), m = wlen(t);
  if (n + m >= cap)
    return 0;
  memcpy(s + n, t, (m + 1) * sizeof(WCHAR));
  return 1;
}
int dd_paths(WCHAR request[1024], WCHAR response[1024]) {
  DWORD n = GetEnvironmentVariableW(L"LOCALAPPDATA", request, 900);
  if (!n || n >= 900)
    return 0;
  if (!cat(request, 1024,
           L"\\SWZeroCompany\\Saved\\SaveGames\\ZComDen\\Community\\v1\\request"
           L".sav"))
    return 0;
  memcpy(response, request, (wlen(request) + 1) * sizeof(WCHAR));
  n = (DWORD)wlen(response);
  while (n && response[n - 1] != '\\')
    n--;
  response[n] = 0;
  return cat(response, 1024, L"response.sav");
}
/* Only the fixed private mailbox is accessed. Reject junction/symlink routes
 * in its path instead of allowing a local mailbox to redirect these writes. */
static int regular_path(const WCHAR *path) {
  WCHAR copy[1100];
  size_t i, n = wlen(path);
  DWORD attributes;
  if (n >= 1100 || n < 3 || path[1] != ':' || path[2] != '\\')
    return 0;
  memcpy(copy, path, (n + 1) * sizeof(WCHAR));
  for (i = 3; i <= n; i++)
    if (copy[i] == '\\' || copy[i] == 0) {
      WCHAR saved = copy[i];
      copy[i] = 0;
      attributes = GetFileAttributesW(copy);
      copy[i] = saved;
      if (attributes != INVALID_FILE_ATTRIBUTES &&
          (attributes & FILE_ATTRIBUTE_REPARSE_POINT))
        return 0;
    }
  return 1;
}
int dd_recent(const WCHAR *path, unsigned seconds) {
  WIN32_FILE_ATTRIBUTE_DATA info;
  FILETIME now;
  ULARGE_INTEGER a, b;
  if (!regular_path(path) ||
      !GetFileAttributesExW(path, GetFileExInfoStandard, &info))
    return 0;
  GetSystemTimeAsFileTime(&now);
  a.LowPart = now.dwLowDateTime;
  a.HighPart = now.dwHighDateTime;
  b.LowPart = info.ftLastWriteTime.dwLowDateTime;
  b.HighPart = info.ftLastWriteTime.dwHighDateTime;
  return a.QuadPart >= b.QuadPart &&
         a.QuadPart - b.QuadPart < (ULONGLONG)seconds * 10000000;
}
int dd_read(const WCHAR *path, unsigned char *out, DWORD capacity,
            DWORD *read) {
  LARGE_INTEGER size;
  HANDLE f;
  if (!regular_path(path))
    return 0;
  f = CreateFileW(path, GENERIC_READ,
                  FILE_SHARE_READ | FILE_SHARE_WRITE | FILE_SHARE_DELETE, 0,
                  OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, 0);
  DWORD actual = 0;
  int ok = 0;
  if (f == INVALID_HANDLE_VALUE)
    return 0;
  if (GetFileSizeEx(f, &size) && size.QuadPart > 0 &&
      size.QuadPart <= capacity &&
      ReadFile(f, out, (DWORD)size.QuadPart, &actual, 0) &&
      actual == size.QuadPart) {
    *read = actual;
    ok = 1;
  }
  CloseHandle(f);
  return ok;
}
int dd_write(const WCHAR *path, const unsigned char *data, DWORD n) {
  WCHAR tmp[1100];
  HANDLE f;
  DWORD actual = 0;
  int ok;
  size_t len = wlen(path);
  if (!regular_path(path) || len + 5 >= 1100)
    return 0;
  memcpy(tmp, path, (len + 1) * sizeof(WCHAR));
  cat(tmp, 1100, L".tmp");
  if (!regular_path(tmp))
    return 0;
  f = CreateFileW(tmp, GENERIC_WRITE, 0, 0, CREATE_ALWAYS,
                  FILE_ATTRIBUTE_NORMAL, 0);
  if (f == INVALID_HANDLE_VALUE)
    return 0;
  ok = WriteFile(f, data, n, &actual, 0) && actual == n && FlushFileBuffers(f);
  CloseHandle(f);
  if (ok)
    ok = MoveFileExW(tmp, path,
                     MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH);
  if (!ok)
    DeleteFileW(tmp);
  return ok;
}
int dd_sha(const unsigned char *data, size_t n, char output[65]) {
  BCRYPT_ALG_HANDLE alg = 0;
  BCRYPT_HASH_HANDLE hash = 0;
  unsigned char bytes[32];
  int ok = 0, i;
  const char *hex = "0123456789abcdef";
  if (n > 0xffffffffu)
    return 0;
  if (BCryptOpenAlgorithmProvider(&alg, BCRYPT_SHA256_ALGORITHM, 0, 0) < 0)
    return 0;
  if (BCryptCreateHash(alg, &hash, 0, 0, 0, 0, 0) >= 0 &&
      BCryptHashData(hash, (PUCHAR)data, (ULONG)n, 0) >= 0 &&
      BCryptFinishHash(hash, bytes, sizeof(bytes), 0) >= 0) {
    for (i = 0; i < 32; i++) {
      output[i * 2] = hex[bytes[i] >> 4];
      output[i * 2 + 1] = hex[bytes[i] & 15];
    }
    output[64] = 0;
    ok = 1;
  }
  if (hash)
    BCryptDestroyHash(hash);
  BCryptCloseAlgorithmProvider(alg, 0);
  return ok;
}
void dd_log(const char *message) {
  WCHAR req[1024], path[1024];
  HANDLE f;
  DWORD wrote;
  size_t n;
  if (!dd_paths(req, path))
    return;
  n = wlen(path);
  while (n && path[n - 1] != '\\')
    n--;
  path[n] = 0;
  if (!cat(path, 1024, L"native.log"))
    return;
  f = CreateFileW(path, FILE_APPEND_DATA, FILE_SHARE_READ | FILE_SHARE_WRITE, 0,
                  OPEN_ALWAYS, FILE_ATTRIBUTE_NORMAL, 0);
  if (f == INVALID_HANDLE_VALUE)
    return;
  WriteFile(f, message, (DWORD)dd_strlen(message), &wrote, 0);
  WriteFile(f, "\r\n", 2, &wrote, 0);
  CloseHandle(f);
}

/* Opt-in plain local credential file. It is deliberately separate from all
 * layout/composition slots and exports. This is not encrypted storage. */
static int connection_key_path(WCHAR path[1024]) {
 WCHAR response[1024];size_t n;
 if(!dd_paths(path,response))return 0;
 n=wlen(path);while(n&&path[n-1]!='\\')n--;path[n]=0;
 return cat(path,1024,L"connection.key")&&regular_path(path);
}
int dd_restore_key(char key[69]) {
 WCHAR path[1024];unsigned char bytes[69];DWORD n=0;int ok=0;
 SecureZeroMemory(key,69);
 if(connection_key_path(path)&&dd_read(path,bytes,sizeof(bytes),&n)&&n==68){bytes[68]=0;if(dd_key_valid((char *)bytes)){memcpy(key,bytes,69);ok=1;}}
 SecureZeroMemory(bytes,sizeof(bytes));return ok;
}
int dd_remember_key(const char *key) {
 WCHAR path[1024];
 return dd_key_valid(key)&&connection_key_path(path)&&dd_write(path,(const unsigned char *)key,68);
}
int dd_forget_key(void) {
 WCHAR path[1024];int ok;
 if(!connection_key_path(path))return 0;
 ok=DeleteFileW(path)||GetLastError()==ERROR_FILE_NOT_FOUND;
 if(!cat(path,1024,L".tmp")||!regular_path(path))return 0;
 return (DeleteFileW(path)||GetLastError()==ERROR_FILE_NOT_FOUND)&&ok;
}
#ifdef DD_FAULT_TEST
static int *volatile dd_test_null;
static volatile LONG dd_test_fired;
void dd_test_point(const char *name) {
  char want[64];
  size_t i;
  DWORD n = GetEnvironmentVariableA("DD_TEST_FAULT", want, sizeof(want));
  if (!n || n >= sizeof(want))
    return;
  for (i = 0; name[i] && name[i] == want[i]; i++)
    ;
  if (!name[i] && !want[i] && !InterlockedExchange(&dd_test_fired, 1))
    *dd_test_null = 1; /* Once: later requests show what players would see. */
}
#endif

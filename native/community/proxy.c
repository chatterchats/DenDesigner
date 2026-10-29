#include "windows.h"
/* Forward version information APIs for the executable and all dependencies.
 * Resolve their implementation from System32, never search the game
 * directory. The optional worker has no Unreal/UE4SS hooks or native ABI calls.
 */
static INIT_ONCE once = INIT_ONCE_STATIC_INIT;
static HMODULE real_version = 0, own_module = 0;
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
static unsigned char watched[DD_SAVE_MAX], latest[DD_SAVE_MAX], reply[DD_SAVE_MAX];
static void stop(PROCESS_INFORMATION *pi) {
  if (pi->hProcess) {
    if (WaitForSingleObject(pi->hProcess, 0) == WAIT_TIMEOUT)
      TerminateProcess(pi->hProcess, ERROR_CANCELLED);
    WaitForSingleObject(pi->hProcess, 2000);
    CloseHandle(pi->hProcess);
    pi->hProcess = 0;
  }
  if (pi->hThread) {
    CloseHandle(pi->hThread);
    pi->hThread = 0;
  }
}
static int start_connection(const WCHAR *exe,WCHAR *command,HANDLE job,STARTUPINFOW *startup,PROCESS_INFORMATION *connection) {
 stop(connection);
 if(!CreateProcessW(exe,command,0,0,FALSE,CREATE_NO_WINDOW|CREATE_SUSPENDED,0,0,startup,connection))return 0;
 if(!AssignProcessToJobObject(job,connection->hProcess)){stop(connection);return 0;}
 ResumeThread(connection->hThread);return 1;
}
static DWORD WINAPI monitor(PVOID ignored) {
  WCHAR exe[1024], command[1100], request[1024], response[1024];
  PROCESS_INFORMATION child, connection;
  WCHAR connect_command[1120];
  STARTUPINFOW startup;
  DWORD count = 0, prior = 0;
  ULONGLONG began = 0;
  size_t n, i;
  HMODULE pin;
  HANDLE job;
  JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits;
  (void)ignored;
  /* Pin only our module for the process lifetime. Nothing is awaited in
   * DllMain. */
  GetModuleHandleExW(GET_MODULE_HANDLE_EX_FLAG_PIN |
                         GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS,
                     (LPCWSTR)(const void *)&monitor, &pin);
  Sleep(500);
  if (!dd_paths(request, response))
    return 0;
  n = GetModuleFileNameW(own_module, exe, 1000);
  if (!n || n >= 1000)
    return 0;
  while (n && exe[n - 1] != '\\')
    n--;
  {
    const WCHAR *name = L"den-community.exe";
    for (i = 0; name[i]; i++)
      exe[n + i] = name[i];
    exe[n + i] = 0;
  }
  command[0] = '"';
  for (i = 0; exe[i]; i++)
    command[i + 1] = exe[i];
  command[i + 1] = '"';
  command[i + 2] = 0;
  memcpy(connect_command, command, (i+2)*sizeof(WCHAR));
  {const WCHAR *suffix=L" --connect";size_t j;for(j=0;suffix[j];j++)connect_command[i+2+j]=suffix[j];connect_command[i+2+j]=0;}
  memset(&connection, 0, sizeof(connection));
  memset(&child, 0, sizeof(child));
  memset(&startup, 0, sizeof(startup));
  startup.cb = sizeof(startup);
  job = CreateJobObjectW(0, 0);
  memset(&limits, 0, sizeof(limits));
  limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
  if (!job || !SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                                       &limits, sizeof(limits))) {
    if (job)
      CloseHandle(job);
    dd_log("Community child lifetime job unavailable; transport disabled.");
    return 0;
  }
  /* The game owns job's final handle. On game exit Windows closes it and kills
   * an outstanding worker, including a pending network operation. */
  dd_log("Standalone Community transport loaded; no UE4SS hooks. Requests have "
         "25-second total deadline.");
  /* Remove an unfinished key-entry request from a prior game session. Only
   * connection.key is eligible for automatic reconnect. */
  {dd_save stale;const char *error;DWORD bytes;
   if(dd_read(request,latest,sizeof(latest),&bytes)&&dd_save_read(latest,bytes,&stale,&error)&&!memcmp(stale.input,"AUTH",5))DeleteFileW(request);
   SecureZeroMemory(latest,sizeof(latest));}
  start_connection(exe,connect_command,job,&startup,&connection);
  for (;;) {
    SecureZeroMemory(latest,sizeof(latest));
    int exists = dd_recent(request, 45) &&
                 dd_read(request, latest, sizeof(latest), &count);
    if (!exists) {
      stop(&child);
      prior = 0;SecureZeroMemory(watched,sizeof(watched));
    } else if (count != prior || memcmp(latest, watched, count)) {
      stop(&child);
      SecureZeroMemory(watched,sizeof(watched));memcpy(watched, latest, count);
      prior = count;
      began = GetTickCount64();
      {
        dd_save control; const char *parse_error;
        if(dd_save_read(latest,count,&control,&parse_error) &&
           (!memcmp(control.input,"CONNECT",8)||!memcmp(control.input,"AUTH",5)||!memcmp(control.input,"FORGET",7)||!memcmp(control.input,"DISCONNECT",11)||!memcmp(control.input,"PUBLISH",8)||!memcmp(control.input,"MYSHARES/",9))) {
          /* Requests that need the key go to the long-lived connection process. */
          const char *message="HoloNet connection unavailable. Choose Connect to try again.";
          char wire[512];size_t written;
          if(!memcmp(control.input,"FORGET",7)){
            stop(&connection);message=dd_forget_key()?"Forgot connection. The saved key was removed from this computer.":"Could not remove the saved connection. Check local file permissions and retry Forget connection.";
          }else if(!memcmp(control.input,"DISCONNECT",11)){
            stop(&connection);message="Disconnected for this session. Use Forget connection to remove a remembered key.";
          }else{
            if(!memcmp(control.input,"AUTH",5))start_connection(exe,connect_command,job,&startup,&connection);
            else if(!connection.hProcess||WaitForSingleObject(connection.hProcess,0)!=WAIT_TIMEOUT)start_connection(exe,connect_command,job,&startup,&connection);
            if(connection.hProcess&&WaitForSingleObject(connection.hProcess,0)==WAIT_TIMEOUT){Sleep(100);continue;}
          }
          if(dd_error_wire(wire,sizeof(wire),control.token,message) && dd_save_response(latest,count,&control,wire,reply,sizeof(reply),&written))dd_write(response,reply,(DWORD)written);
          Sleep(100);continue;
        }
      }
      /* CreateProcess receives an absolute application path; no shell, user
       * arguments, remote binary, or downloaded content is ever executed. */
      if (!CreateProcessW(exe, command, 0, 0, FALSE,
                          CREATE_NO_WINDOW | CREATE_SUSPENDED, 0, 0, &startup,
                          &child))
        dd_log("Community worker could not start; verify den-community.exe "
               "installation.");
      else if (!AssignProcessToJobObject(job, child.hProcess)) {
        stop(&child);
        dd_log(
            "Community worker could not join lifetime job; request cancelled.");
      } else {
        ResumeThread(child.hThread);
      }
    } else if (child.hProcess) {
      if (WaitForSingleObject(child.hProcess, 0) != WAIT_TIMEOUT)
        stop(&child);
      else if (GetTickCount64() - began >= 25000) {
        dd_save save;
        const char *error;
        unsigned char *out;
        size_t written;
        char *wire;
        stop(&child);
        dd_log("Community request timed out; owned worker cancelled.");
        /* A timeout is a normal token-scoped error, not a late success. */
        out = HeapAlloc(GetProcessHeap(), 0, DD_SAVE_MAX);
        wire = HeapAlloc(GetProcessHeap(), 0, 2048);
        if (out && wire && dd_recent(request, 45) &&
            dd_read(request, latest, sizeof(latest), &count) &&
            count == prior && !memcmp(latest, watched, count) &&
            dd_save_read(watched, prior, &save, &error) &&
            dd_error_wire(
                wire, 2048, save.token,
                "HoloNet didn't answer in time. Try again when you're online.") &&
            dd_save_response(watched, prior, &save, wire, out, DD_SAVE_MAX,
                             &written))
          dd_write(response, out, (DWORD)written);
        if (out)
          HeapFree(GetProcessHeap(), 0, out);
        if (wire)
          HeapFree(GetProcessHeap(), 0, wire);
      }
    }
    Sleep(100);
  }
  return 0;
}
BOOL WINAPI DllMain(HINSTANCE module, DWORD reason, LPVOID reserved) {
  (void)reserved;
  if (reason == DLL_PROCESS_ATTACH) {
    own_module = module;
    DisableThreadLibraryCalls(module); /* Queue only. Worker starts after
                                          loader-lock initialization. */
    QueueUserWorkItem(monitor, 0, WT_EXECUTELONGFUNCTION);
  }
  return TRUE;
}

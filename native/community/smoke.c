/* Disposable-prefix smoke harness, never part of the player install. */
#include "windows.h"
void mainCRTStartup(void) {
  WCHAR path[1024], system[1024], request[1024], response[1024];
  HMODULE proxy, actual;
  typedef DWORD(WINAPI *size_fn)(LPCWSTR, LPDWORD);
  typedef BOOL(WINAPI *info_fn)(LPCWSTR, DWORD, DWORD, LPVOID);
  typedef BOOL(WINAPI *query_fn)(LPCVOID, LPCWSTR, LPVOID *, PUINT);
  size_fn a_size, p_size; info_fn a_info,p_info; query_fn a_query,p_query;
  DWORD n, direct_size, proxied_size, handle=0; size_t i; void *data;
  LPVOID direct_value=0,proxied_value=0; UINT direct_len=0,proxied_len=0;
  ULONGLONG start;
  const char *exports[] = {"GetFileVersionInfoA","GetFileVersionInfoExA","GetFileVersionInfoExW","GetFileVersionInfoSizeA","GetFileVersionInfoSizeExA","GetFileVersionInfoSizeExW","GetFileVersionInfoSizeW","GetFileVersionInfoW","VerFindFileA","VerFindFileW","VerInstallFileA","VerInstallFileW","VerLanguageNameA","VerLanguageNameW","VerQueryValueA","VerQueryValueW"};
  typedef BOOL(WINAPI *query_a_fn)(LPCVOID,LPCSTR,LPVOID *,PUINT);
  query_a_fn a_query_a,p_query_a;
  WCHAR graphics[2048]; HMODULE graphics_module;
  n=GetModuleFileNameW(0,path,990);while(n&&path[n-1]!='\\')n--;
  {const WCHAR*s=L"version.dll";for(i=0;s[i];i++)path[n+i]=s[i];path[n+i]=0;}
  proxy=LoadLibraryExW(path,0,LOAD_WITH_ALTERED_SEARCH_PATH);
  n=GetSystemDirectoryW(system,990);
  {const WCHAR*s=L"\\version.dll";for(i=0;s[i];i++)system[n+i]=s[i];system[n+i]=0;}
  actual=LoadLibraryExW(system,0,LOAD_LIBRARY_SEARCH_SYSTEM32);
  if(!proxy||!actual)ExitProcess(10);
  for(i=0;i<sizeof(exports)/sizeof(exports[0]);i++)
    if(!GetProcAddress(actual,exports[i])||!GetProcAddress(proxy,exports[i]))ExitProcess(17);
  a_query_a=(query_a_fn)GetProcAddress(actual,"VerQueryValueA");
  p_query_a=(query_a_fn)GetProcAddress(proxy,"VerQueryValueA");
  a_size=(size_fn)GetProcAddress(actual,"GetFileVersionInfoSizeW");
  p_size=(size_fn)GetProcAddress(proxy,"GetFileVersionInfoSizeW");
  a_info=(info_fn)GetProcAddress(actual,"GetFileVersionInfoW");
  p_info=(info_fn)GetProcAddress(proxy,"GetFileVersionInfoW");
  a_query=(query_fn)GetProcAddress(actual,"VerQueryValueW");
  p_query=(query_fn)GetProcAddress(proxy,"VerQueryValueW");
  if(!a_size||!p_size||!a_info||!p_info||!a_query||!p_query)ExitProcess(11);
  direct_size=a_size(system,&handle);proxied_size=p_size(system,&handle);
  if(!direct_size||direct_size!=proxied_size)ExitProcess(12);
  data=HeapAlloc(GetProcessHeap(),0,direct_size);
  if(!data||!p_info(system,0,direct_size,data)||!a_info(system,0,direct_size,data))ExitProcess(13);
  if(!a_query(data,L"\\",&direct_value,&direct_len)||!p_query(data,L"\\",&proxied_value,&proxied_len)||direct_len!=proxied_len||direct_value!=proxied_value)ExitProcess(14);
  if(!a_query_a(data,"\\",&direct_value,&direct_len)||!p_query_a(data,"\\",&proxied_value,&proxied_len)||direct_len!=proxied_len||direct_value!=proxied_value)ExitProcess(18);
  HeapFree(GetProcessHeap(),0,data);
  dd_log("SMOKE: all 16 version exports present; ANSI and Unicode VerQueryValue match System32.");
  if(GetEnvironmentVariableW(L"DD_GRAPHICS_DLL",graphics,2048)) {
    graphics_module=LoadLibraryExW(graphics,0,LOAD_WITH_ALTERED_SEARCH_PATH);
    if(!graphics_module)ExitProcess(19);
    dd_log("SMOKE: real game-prefix d3d12core.dll loads with the proxy present.");
    FreeLibrary(graphics_module);
  }
  dd_log("SMOKE: all three version.dll exports match System32 behavior.");
  if(!dd_paths(request,response))ExitProcess(15);
  start=GetTickCount64();
  while(GetTickCount64()-start<35000){
    if(GetFileAttributesW(response)!=INVALID_FILE_ATTRIBUTES){dd_log("SMOKE: native response file published.");ExitProcess(0);}
    Sleep(100);
  }
  dd_log("SMOKE: response deadline expired.");ExitProcess(16);
}

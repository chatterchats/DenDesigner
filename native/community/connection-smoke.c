/* Dedicated fake-transport test executable. This file is never linked into the
 * shipped worker. It cannot contact the service or use a player's credentials. */
#include "connection.c"
static volatile LONG attempts, publish_attempts;
static int fake_api(int publish,const unsigned char *body,DWORD n,char *response,DWORD cap) {
 const char *profile="{\"user_id\":\"11111111-1111-4111-8111-111111111111\",\"publishing\":\"beta-publishing\"}";
 (void)body;(void)n;(void)cap;
 if(publish){InterlockedIncrement(&publish_attempts);return api(1,body,n,response,cap);}
 InterlockedIncrement(&attempts);
 if(attempts==2)return -1;
 memcpy(response,profile,dd_strlen(profile)+1);return 1;
}
static int calls, finalized, deleted, fail_thumbnail, lose_reply, abandon, enforce_png;
static int fake_current(void){return !(abandon&&calls>=3);}
static int fake_http(const WCHAR *method,const WCHAR *path,const unsigned char *body,DWORD bytes,const WCHAR *headers,char *reply,DWORD cap){
 const char *staging="{\"upload\":{\"id\":\"11111111-1111-4111-8111-111111111111\",\"code\":\"PublishedTest01\",\"status\":\"staging\"}}";
 const char *published="{\"upload\":{\"id\":\"11111111-1111-4111-8111-111111111111\",\"code\":\"PublishedTest01\",\"status\":\"published\"}}";
 (void)body;(void)bytes;(void)headers;(void)cap;calls++;
 if(method[0]=='D'){deleted++;reply[0]=0;return 1;}
 if(path[dd_strlen("/api/v1/composition-uploads")]==0){memcpy(reply,finalized?published:staging,dd_strlen(finalized?published:staging)+1);return 1;}
 {size_t n=0;while(path[n])n++;
 if(n>9&&path[n-9]=='t'){size_t encoded;if(fail_thumbnail)return 0;if(enforce_png&&(!dd_cached_png(body,bytes,&encoded)||encoded!=bytes))ExitProcess(58);}
 if(n>8&&path[n-8]=='f'){finalized++;if(lose_reply){lose_reply=0;return 0;}}
 }
 reply[0]=0;return 1;
}
static void staged_checks(void){
 char reply[4096];int r;
 thumbnail_source_digest[0]=0;enforce_png=0;send_http=fake_http;request_current=fake_current;
 memcpy(publish_title,"Saved composition",18);publish_description[0]=0;update_code[0]=0;
 memcpy(original,"{}",2);payload_offset=0;payload_size=2;thumbnail[0]=1;thumbnail_size=1;
 calls=finalized=deleted=0;fail_thumbnail=1;r=api(1,0,0,reply,sizeof(reply));if(r!=0||calls!=3||finalized)ExitProcess(20);
 fail_thumbnail=0;lose_reply=1;calls=0;r=api(1,0,0,reply,sizeof(reply));if(r!=0||calls!=4||finalized!=1)ExitProcess(21);
 calls=0;r=api(1,0,0,reply,sizeof(reply));if(r!=1||calls!=1||finalized!=1)ExitProcess(22);
 calls=finalized=0;abandon=1;r=api(1,0,0,reply,sizeof(reply));if(r!=0||finalized||deleted!=1)ExitProcess(23);
}
static void add_directory(WCHAR *path,const WCHAR *part) {
 size_t n=0,i;while(path[n])n++;path[n++]='\\';for(i=0;part[i];i++)path[n++]=part[i];path[n]=0;
 if(!CreateDirectoryW(path,0)&&GetLastError()!=ERROR_ALREADY_EXISTS)ExitProcess(30);
}
static void remembered_checks(const char *key) {
 WCHAR temp[1024],base[1024],directory[1024],request[1024],response[1024];char restored[69];DWORD n;unsigned char raw[80];size_t i;ULONGLONG began;
 if(!GetTempPathW(900,temp)||!GetTempFileNameW(temp,L"ddc",0,base)||!DeleteFileW(base)||!CreateDirectoryW(base,0))ExitProcess(31);
 for(i=0;base[i];i++)directory[i]=base[i];directory[i]=0;
 SetEnvironmentVariableW(L"LOCALAPPDATA",base);
 add_directory(directory,L"SWZeroCompany");add_directory(directory,L"Saved");add_directory(directory,L"SaveGames");add_directory(directory,L"ZComDen");add_directory(directory,L"Community");add_directory(directory,L"v1");
 if(!dd_paths(request,response))ExitProcess(32);
 if(dd_restore_key(restored)||!dd_remember_key(key)||!dd_restore_key(restored)||memcmp(restored,key,69))ExitProcess(33);
 {size_t at=0;const WCHAR *name=L"connection.key";while(response[at])at++;while(at&&response[at-1]!='\\')at--;for(i=0;name[i];i++)response[at+i]=name[i];response[at+i]=0;}
 if(!dd_read(response,raw,sizeof(raw),&n)||n!=68||memcmp(raw,key,68))ExitProcess(34);
 if(!dd_forget_key()||dd_restore_key(restored))ExitProcess(35);
 // Ordinary validation without Remember must not create the credential file.
 memcpy(credential.key,key,69);authorize();attempts=0;reply_connection=0;want_remember=0;remembered_connection=0;perform(0);
 if(!connected||dd_restore_key(restored))ExitProcess(36);
 // A successful opt-in saves; reconnect loads the same key without UI entry.
 attempts=0;want_remember=1;perform(0);
 if(!dd_restore_key(restored)||memcmp(restored,key,69))ExitProcess(37);
 wipe();attempts=0;if(!restore_connection())ExitProcess(38);
 began=GetTickCount64();while(busy&&GetTickCount64()-began<5000)Sleep(20);
 if(busy||!connected||attempts!=1||!dd_restore_key(restored))ExitProcess(39);
 // Revoked/expired keys are removed instead of retrying forever on startup.
 perform(0);if(connected||dd_restore_key(restored))ExitProcess(40);
 if(!dd_write(response,(const unsigned char *)"malformed",9)||dd_restore_key(restored)||restored[0])ExitProcess(41);
 if(!dd_forget_key()||!dd_forget_key())ExitProcess(42);
 SecureZeroMemory(restored,sizeof(restored));SecureZeroMemory(raw,sizeof(raw));
}
static int reply_contains(const char *text){DWORD n;size_t i,k=dd_strlen(text);if(!dd_read(response_path,output,sizeof(output),&n))return 0;for(i=0;i+k<=n;i++)if(!memcmp(output+i,text,k))return 1;return 0;}
static const unsigned char test_png[]={137,80,78,71,13,10,26,10,0,0,0,13,73,72,68,82,0,0,0,1,0,0,0,1,8,6,0,0,0,31,21,196,137,0,0,0,13,73,68,65,84,120,156,99,248,223,224,240,31,0,7,0,2,191,43,215,199,226,0,0,0,0,73,69,78,68,174,66,96,130};
static void inpanel_checks(const char *key){
 WCHAR fixture[1024],thumbdir[1024],thumbpath[1024];DWORD n,root;size_t i,j;ULONGLONG began;char filename[25];const char *error;
 if(!GetEnvironmentVariableW(L"DD_INPANEL_FIXTURE",fixture,1024))return;
 if(!dd_paths(request_path,response_path)||!dd_read(fixture,original,sizeof(original),&n)||!dd_write(request_path,original,n))ExitProcess(50);
 Sleep(100); /* Wine wall-clock snapshots can lag the file timestamp immediately after write. */
 handled_token[0]=0;wipe();if(busy)ExitProcess(66);if(!dd_recent(request_path,45))ExitProcess(67);if(!dd_save_read(original,n,&pending,&error))ExitProcess(68);if(!equal(pending.input,"PUBLISH"))ExitProcess(69);procedure(window,WM_TIMER,0,0);
 if(publish_attempts)ExitProcess(51);if(!reply_contains("Not connected"))ExitProcess(65);
 memcpy(credential.key,key,69);authorize();connected=1;handled_token[0]=0;procedure(window,WM_TIMER,0,0);
 if(publish_attempts||!reply_contains("Thumbnail or saved snapshot unavailable"))ExitProcess(52);
 if(!dd_read(request_path,original,sizeof(original),&n)||!dd_save_read(original,n,&pending,&error))ExitProcess(53);
 memcpy(filename,original+pending.wire_value_offset,24);filename[24]=0;
 root=GetEnvironmentVariableW(L"LOCALAPPDATA",thumbdir,900);if(!root||root>=900)ExitProcess(54);
 add_directory(thumbdir,L"SWZeroCompany");add_directory(thumbdir,L"Saved");add_directory(thumbdir,L"ZComDen");add_directory(thumbdir,L"thumbs");
 for(i=0;thumbdir[i];i++)thumbpath[i]=thumbdir[i];thumbpath[i++]='\\';for(j=0;filename[j];j++)thumbpath[i++]=(WCHAR)filename[j];thumbpath[i]=0;
 {unsigned char cached[sizeof(test_png)+32];memcpy(cached,test_png,sizeof(test_png));memset(cached+sizeof(test_png),0xa5,32);if(!dd_write(thumbpath,cached,sizeof(cached)))ExitProcess(55);}
 send_http=fake_http;request_current=fake_current;calls=finalized=deleted=0;enforce_png=1;
 handled_token[0]=0;procedure(window,WM_TIMER,0,0);
 began=GetTickCount64();while(busy&&GetTickCount64()-began<5000)Sleep(20);
 if(busy||publish_attempts!=1||!equal(publish_title,"VM saved composition")||!equal(publish_description,"Retained after errors")||!reply_contains("Published: https://share.zcom.app/comp/PublishedTest01"))ExitProcess(56);
 if(thumbnail_size!=sizeof(test_png)||IsWindowVisible(window)||GetWindow(window,GW_CHILD))ExitProcess(57);
 for(i=thumbnail_size;i<thumbnail_size+32;i++)if(thumbnail[i])ExitProcess(59);
 DeleteFileW(request_path);DeleteFileW(response_path);DeleteFileW(thumbpath);wipe();
}
static int blocked_api(int publish,const unsigned char *body,DWORD n,char *response,DWORD cap){(void)publish;(void)body;(void)n;(void)response;(void)cap;Sleep(60000);return 0;}
static DWORD WINAPI open_window(LPVOID unused) {(void)unused;dd_connection_main();return 0;}
void mainCRTStartup(void) {
 HANDLE thread;size_t i;char key[69];ULONGLONG began;
 send_api=fake_api;
 thread=CreateThread(0,0,open_window,0,0,0);if(!thread)ExitProcess(10);
 began=GetTickCount64();while(!window&&GetTickCount64()-began<5000)Sleep(20);
 if(!window||IsWindowVisible(window)||GetWindow(window,GW_CHILD))ExitProcess(11);
 Sleep(150);KillTimer(window,1);if(SuspendThread(thread)==(DWORD)-1)ExitProcess(11); /* Deterministic manual pumps; no owner-thread timer races. */
 if(key_valid("not-a-key"))ExitProcess(12);
 memcpy(key,"zcu_",4);for(i=4;i<68;i++)key[i]='a';key[68]=0;
 if(!key_valid(key))ExitProcess(13);
 memcpy(credential.key,key,69);authorize();perform(0);
 if(!connected||attempts!=1||memcmp(credential.key,key,69))ExitProcess(14);
 if(!equal(status_text,"Connected: https://share.zcom.app/profile/11111111-1111-4111-8111-111111111111"))ExitProcess(15);
 perform(0);if(connected||attempts!=2)ExitProcess(16);
 for(i=0;i<sizeof(credential);i++)if(((unsigned char *)&credential)[i])ExitProcess(17);
 for(i=0;status_text[i];i++)if(!memcmp(status_text+i,"zcu_",4))ExitProcess(18);
 if(IsWindowVisible(window)||GetWindow(window,GW_CHILD))ExitProcess(19);
 remembered_checks(key);
 inpanel_checks(key);
 staged_checks();
 if(!equal(service_failure(400,"{\"error\":{\"code\":\"INVALID_THUMBNAIL\",\"message\":\"zcu_do_not_echo\"}}"),"Cached preview rejected by Community. Its PNG stream is invalid or unsupported. Regenerate the saved card preview and retry."))ExitProcess(63);
 if(!equal(service_failure(409,"{\"error\":{\"code\":\"REVISION_CONFLICT\"}}"),"Your publication changed. Check its current revision on the website before updating again."))ExitProcess(64);
 {WCHAR cancel[2];if(GetEnvironmentVariableW(L"DD_CANCEL_SMOKE",cancel,2)){
   send_api=blocked_api;memcpy(original,"{}",2);original_size=2;
   if(!dd_write(request_path,original,2))ExitProcess(60);
   start_task(1);if(!busy)ExitProcess(61);
   DeleteFileW(request_path);procedure(window,WM_TIMER,0,0);
   ExitProcess(62); /* Timer must terminate the entire blocked transport. */
 }}
 ExitProcess(0);
}

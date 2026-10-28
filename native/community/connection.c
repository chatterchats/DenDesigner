#include "windows.h"
/* The in-game masked connection form can opt in to a dedicated plain local key
 * file. Credentials never enter composition exports, logs or command lines. */
#define DD_RESULT (WM_APP + 1)
static HWND window; /* Message-only timer endpoint; no player-facing native UI. */
static int review_ready;
static char upload_id[37], published_code[33], publish_title[121], publish_description[4001], update_code[33], update_revision[10];
static unsigned char thumbnail[1048576];
static char requirements[65536];
static DWORD thumbnail_size, payload_offset, payload_size;
static char thumbnail_source_digest[65];

static volatile LONG busy;
static int connected;
static ULONGLONG started;
static struct { char key[69]; WCHAR authorization[100]; } credential;
static unsigned char original[DD_SAVE_MAX], current[DD_SAVE_MAX], output[DD_SAVE_MAX];
static DWORD original_size;
static dd_save pending;
static char status_text[256];
static WCHAR request_path[1024], response_path[1024];
static char handled_token[65];
static int equal(const char *a,const char *b) { return dd_strlen(a)==dd_strlen(b)&&!memcmp(a,b,dd_strlen(a)); }
static void wipe(void) { SecureZeroMemory(&credential,sizeof(credential)); connected=0; }
static int key_valid(const char *s) { return dd_key_valid(s); }
static int want_remember, reply_connection, remembered_connection;
static const char *safe_service_error, *upload_stage="checking connection";
static const char *service_failure(DWORD,const char *);
static int (*restore_key)(char[69])=dd_restore_key;
static int (*remember_key)(const char *)=dd_remember_key;
static int (*forget_key)(void)=dd_forget_key;
static void authorize(void) {
 const char *prefix="Authorization: Bearer ";size_t i,j;
 for(i=0;prefix[i];i++)credential.authorization[i]=prefix[i];
 for(j=0;credential.key[j];j++)credential.authorization[i+j]=credential.key[j];
 credential.authorization[i+j]='\r';credential.authorization[i+j+1]='\n';credential.authorization[i+j+2]=0;
}
static void connection_reply(const char *message) {
 DWORD n;size_t written;char wire[512];
 if(dd_read(request_path,current,sizeof(current),&n)&&n==original_size&&!memcmp(current,original,n)&&dd_error_wire(wire,sizeof(wire),pending.token,message)&&dd_save_response(original,original_size,&pending,wire,output,sizeof(output),&written)){
  if(dd_write(response_path,output,(DWORD)written)&&equal(pending.input,"AUTH"))DeleteFileW(request_path);
 }
}
static void progress(const char *stage) {
 char wire[512]="ZCOM-COMMUNITY\t1\t";size_t used=dd_strlen(wire),i,written;DWORD n;
 for(i=0;pending.token[i];i++)wire[used++]=pending.token[i];
 {const char *tag="\nprogress\t";for(i=0;tag[i];i++)wire[used++]=tag[i];}
 for(i=0;stage[i]&&used+5<sizeof(wire);i++)wire[used++]=stage[i];
 memcpy(wire+used,"\nend",5);
 if(dd_read(request_path,current,sizeof(current),&n)&&n==original_size&&!memcmp(current,original,n)&&dd_save_response(original,original_size,&pending,wire,output,sizeof(output),&written))dd_write(response_path,output,(DWORD)written);
}
static int http(const WCHAR *method,const WCHAR *path,const unsigned char *body,DWORD bytes,const WCHAR *extra,char *reply,DWORD capacity) {
 HINTERNET session=0,connection=0,request=0;
 DWORD disable=WINHTTP_DISABLE_REDIRECTS|WINHTTP_DISABLE_COOKIES|WINHTTP_DISABLE_AUTHENTICATION;
 DWORD policy=WINHTTP_OPTION_REDIRECT_POLICY_NEVER, code=0, size=sizeof(code), got=0, used=0;
 int result=0;
 reply[0]=0;safe_service_error=0;
 session=WinHttpOpen(L"DenDesignerCommunity/3",WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0);
 if(!session||!WinHttpSetTimeouts(session,4000,6000,6000,6000))goto done;
 connection=WinHttpConnect(session,L"share.zcom.app",INTERNET_DEFAULT_HTTPS_PORT,0);if(!connection)goto done;
 request=WinHttpOpenRequest(connection,method,path,0,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,WINHTTP_FLAG_SECURE);if(!request)goto done;
 if(!WinHttpSetOption(request,WINHTTP_OPTION_DISABLE_FEATURE,&disable,sizeof(disable))||!WinHttpSetOption(request,WINHTTP_OPTION_REDIRECT_POLICY,&policy,sizeof(policy)))goto done;
 if(!WinHttpAddRequestHeaders(request,credential.authorization,(DWORD)-1,WINHTTP_ADDREQ_FLAG_ADD|WINHTTP_ADDREQ_FLAG_REPLACE)||
 !WinHttpSendRequest(request,extra,(DWORD)-1,(LPVOID)body,bytes,bytes,0)||!WinHttpReceiveResponse(request,0))goto done;
 if(!WinHttpQueryHeaders(request,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,WINHTTP_HEADER_NAME_BY_INDEX,&code,&size,WINHTTP_NO_HEADER_INDEX))goto done;
 if(code==401){result=-1;goto done;}
 if(code==403){result=-2;goto done;}
 while(used+1<capacity){if(!WinHttpReadData(request,reply+used,capacity-used-1,&got))goto done;if(!got){reply[used]=0;if(code>=200&&code<300)result=1;else{safe_service_error=service_failure(code,reply);result=-3;}goto done;}used+=got;}
 done:if(request)WinHttpCloseHandle(request);if(connection)WinHttpCloseHandle(connection);if(session)WinHttpCloseHandle(session);return result;
}
static int (*send_http)(const WCHAR *,const WCHAR *,const unsigned char *,DWORD,const WCHAR *,char *,DWORD)=http;
static int append(char *out,size_t cap,const char *text){size_t n=dd_strlen(out),m=dd_strlen(text);if(n+m>=cap)return 0;memcpy(out+n,text,m+1);return 1;}
static int quote(char *out,size_t cap,const char *text){size_t i;if(!append(out,cap,"\""))return 0;for(i=0;text[i];i++){char b[3]={text[i],0,0};if((unsigned char)text[i]<32||(unsigned char)text[i]>=127)return 0;if(text[i]=='"'||text[i]=='\\'){b[0]='\\';b[1]=text[i];}if(!append(out,cap,b))return 0;}return append(out,cap,"\"");}
/* Parse fixed, bounded UUID/code response fields; never follow server URLs. */
static int response_field(const char *json,const char *name,char *out,size_t cap){
 char tag[64]="\"";size_t i,j,length=dd_strlen(json);if(!append(tag,sizeof(tag),name)||!append(tag,sizeof(tag),"\":\""))return 0;
 for(i=0;i+dd_strlen(tag)<=length;i++)if(!memcmp(json+i,tag,dd_strlen(tag))){i+=dd_strlen(tag);for(j=0;j+1<cap&&json[i+j]&&json[i+j]!='"';j++){char c=json[i+j];if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='-'||c=='_'))return 0;out[j]=c;}out[j]=0;return j>0&&json[i+j]=='"';}return 0;
}
/* Only fixed messages for known service codes are exposed. Never reflect a
 * server body (or arbitrary strings from it) into status, files or logs. */
static const char *service_failure(DWORD status,const char *reply){
 char code[64];size_t i;
 static const struct {const char *code,*message;} failures[]={
  {"INVALID_THUMBNAIL","Cached preview rejected by Community. Its PNG stream is invalid or unsupported. Regenerate the saved card preview and retry."},
  {"INVALID_PAYLOAD","Saved composition rejected. Review part transforms, mesh/material paths and supported limits, then retry."},
  {"INVALID_METADATA","Title or description rejected. Enter a nonblank title of up to 120 characters and a description up to 4000 characters."},
  {"INVALID_REVISION","Update revision is invalid. Use your share code and its current positive revision, or leave both update fields empty."},
  {"REVISION_CONFLICT","Your publication changed. Check its current revision on the website before updating again."},
  {"REVISION_OR_GRANT_CHANGED","Publication revision or publishing permission changed. Check your account and current revision before retrying."},
  {"IDEMPOTENCY_CONFLICT","This retry does not match its staged metadata. Review the saved snapshot and metadata before retrying."},
  {"ACCOUNT_UPLOAD_LIMIT_OR_GRANT_CHANGED","Account upload limit reached or permission changed. Retry the same snapshot; cancelled staging expires after an hour."},
  {"FILE_ALREADY_UPLOADED","A staged file differs from this retry. Restore the original saved snapshot or start a new publication with changed metadata."},
  {"UPLOAD_CLOSED","Staged upload expired or was cancelled. Retry to start a fresh staged upload."},
  {"UPLOAD_CLOSED_OR_GRANT_CHANGED","Staged upload closed or publishing permission changed. Reconnect, check your account and retry."},
  {"LISTING_NOT_FOUND","Update listing was not found in your account. Check its code, or clear both update fields to create a new publication."},
  {"INCOMPLETE_UPLOAD","Staged upload is incomplete. Retry the same saved snapshot to finish its files."},
  {"STORAGE_UNAVAILABLE","Community file storage is temporarily unavailable. Your form is kept; retry later."},
  {"FILE_STORAGE_UNAVAILABLE","Community file storage is temporarily unavailable. Your form is kept; retry later."},
  {"RATE_LIMITED","Community request rate limit reached. Wait before retrying; your form has been kept."},
  {"INVALID_UPLOADED_BYTES","Community could not validate the staged snapshot and preview. Review the saved card and retry."},
  {"PAYLOAD_LIMIT","Published composition exceeds the service size limit. Publish a smaller saved composition."}
 };
 if(response_field(reply,"code",code,sizeof(code)))for(i=0;i<sizeof(failures)/sizeof(failures[0]);i++)if(equal(code,failures[i].code))return failures[i].message;
 if(status==429)return "Community request rate limit reached. Wait before retrying.";
 if(status>=500)return "Community service is temporarily unavailable. Your form is kept; retry later.";
 return "Community rejected this upload step. Check metadata, revision and account limits; your form has been kept.";
}
static int still_current(void){DWORD n;return dd_read(request_path,current,sizeof(current),&n)&&n==original_size&&!memcmp(current,original,n);}
static int (*request_current)(void)=still_current;
static int stage_path(WCHAR *wide,const char *part){char path[160]="/api/v1/composition-uploads/";if(dd_strlen(upload_id)!=36||!append(path,sizeof(path),upload_id)||!append(path,sizeof(path),part))return 0;dd_ascii_wide(path,wide,160);return 1;}
static int api(int publish,const unsigned char *body,DWORD bytes,char *reply,DWORD capacity) {
 WCHAR path[160],headers[300];char json[25000]="{\"title\":",idempotency[65],raw_headers[300]="Accept: application/json\r\nContent-Type: application/json\r\nIdempotency-Key: ";int result;
 (void)body;(void)bytes;safe_service_error=0;upload_stage="checking connection";
 if(!publish)return send_http(L"GET",L"/api/v1/game/profile",0,0,L"Accept: application/json\r\n",reply,capacity);
 if(!request_current())return 0;
 if(!quote(json,sizeof(json),publish_title)||!append(json,sizeof(json),",\"description\":")||!quote(json,sizeof(json),publish_description))return 0;
 if(update_code[0]){if(!append(json,sizeof(json),",\"code\":")||!quote(json,sizeof(json),update_code)||!append(json,sizeof(json),",\"base_revision\":")||!append(json,sizeof(json),update_revision))return 0;}
 if(!append(json,sizeof(json),"}"))return 0;
 /* Same metadata, thumbnail and document have the same retry key, including
  * after selecting the card again. Metadata changes start a fresh upload. */
 {char digest[65],thumb_hash[65];if(!dd_sha(original+payload_offset,payload_size,digest)||!(thumbnail_source_digest[0]?(memcpy(thumb_hash,thumbnail_source_digest,65),1):dd_sha(thumbnail,thumbnail_size,thumb_hash))||!append(json,sizeof(json),digest)||!append(json,sizeof(json),thumb_hash)||!dd_sha((unsigned char *)json,dd_strlen(json),idempotency))return 0;json[dd_strlen(json)-128]=0;}
 if(!append(raw_headers,sizeof(raw_headers),idempotency)||!append(raw_headers,sizeof(raw_headers),"\r\n"))return 0;dd_ascii_wide(raw_headers,headers,300);
 upload_stage="creating or recovering the staged upload";progress("Creating or recovering staged upload...");
 result=send_http(L"POST",L"/api/v1/composition-uploads",(unsigned char *)json,(DWORD)dd_strlen(json),headers,reply,capacity);
 if(result!=1)return result;
 {char status[20];if(response_field(reply,"status",status,sizeof(status))&&(equal(status,"expired")||equal(status,"cancelled"))){
  char retry[140]="";append(retry,sizeof(retry),idempotency);append(retry,sizeof(retry),pending.token);if(!dd_sha((unsigned char *)retry,dd_strlen(retry),idempotency))return 0;
  raw_headers[0]=0;append(raw_headers,sizeof(raw_headers),"Accept: application/json\r\nContent-Type: application/json\r\nIdempotency-Key: ");append(raw_headers,sizeof(raw_headers),idempotency);append(raw_headers,sizeof(raw_headers),"\r\n");dd_ascii_wide(raw_headers,headers,300);
  result=send_http(L"POST",L"/api/v1/composition-uploads",(unsigned char *)json,(DWORD)dd_strlen(json),headers,reply,capacity);if(result!=1)return result;
 }}
 if(!response_field(reply,"id",upload_id,sizeof(upload_id))||dd_strlen(upload_id)!=36||!response_field(reply,"code",published_code,sizeof(published_code)))return 0;
 {char status[20];if(response_field(reply,"status",status,sizeof(status))&&equal(status,"published"))return 1;}
 if(!request_current())goto cancel;
 upload_stage="uploading the saved snapshot";progress("Uploading saved snapshot...");stage_path(path,"/payload");result=send_http(L"PUT",path,original+payload_offset,payload_size,L"Content-Type: application/json\r\n",reply,capacity);if(result!=1)return result;
 if(!request_current())goto cancel;
 upload_stage="uploading the cached preview";progress("Uploading cached preview...");stage_path(path,"/thumbnail");result=send_http(L"PUT",path,thumbnail,thumbnail_size,L"Content-Type: image/png\r\n",reply,capacity);if(result!=1)return result;
 if(!request_current())goto cancel;
 upload_stage="finalizing the immutable revision";progress("Validating dependencies and committing immutable revision...");stage_path(path,"/finalize");return send_http(L"POST",path,0,0,L"Accept: application/json\r\n",reply,capacity);
 cancel:stage_path(path,"");send_http(L"DELETE",path,0,0,L"Accept: application/json\r\n",reply,capacity);return 0;
}
static int (*send_api)(int,const unsigned char *,DWORD,char *,DWORD)=api;
static DWORD WINAPI perform(LPVOID parameter) {
 int publish=parameter!=0, result; char reply[4096];
 const char *message="Community unavailable or upload rejected. Check title, ownership, revision and account limits; retry Publish. Offline editing is still available.";
 result=send_api(publish,publish?original+pending.wire_value_offset:0,publish?(DWORD)(pending.wire_end-pending.wire_value_offset-1):0,reply,sizeof(reply));
 if(result==-3&&safe_service_error)message=safe_service_error;
 else if(result==0){status_text[0]=0;append(status_text,sizeof(status_text),"Community request failed while ");append(status_text,sizeof(status_text),upload_stage);append(status_text,sizeof(status_text),". Retry the same saved snapshot; your form has been kept.");message=status_text;}
 else if(result==-1){forget_key();remembered_connection=0;wipe();message="Key invalid, expired, revoked, or publishing unavailable. Generate a replacement on the website.";}
 else if(result==-2){message="Publishing is unavailable for this account. Approved beta access may be required. Your remembered connection has been kept.";}
 else if(result==1&&publish){status_text[0]=0;append(status_text,sizeof(status_text),"Published: https://share.zcom.app/comp/");append(status_text,sizeof(status_text),published_code);message=status_text;review_ready=0;}
 else if(result==1){
  const char *tag="\"user_id\":\"";size_t i,j;int found=0;
  for(i=0;i+dd_strlen(tag)<dd_strlen(reply);i++)if(!memcmp(reply+i,tag,dd_strlen(tag))){
   i+=dd_strlen(tag);for(j=0;j<36&&reply[i+j];j++)if(!((reply[i+j]>='a'&&reply[i+j]<='f')||(reply[i+j]>='0'&&reply[i+j]<='9')||reply[i+j]=='-'))break;
   if(j==36&&reply[i+j]=='"'){const char *prefix="Connected: https://share.zcom.app/profile/";size_t n=dd_strlen(prefix);memcpy(status_text,prefix,n);memcpy(status_text+n,reply+i,36);status_text[n+36]=0;found=1;connected=1;}break;
  }
  if(found){
   if(reply_connection&&!still_current()){wipe();want_remember=0;message="Connection cancelled.";}
   else {
    if(want_remember){remembered_connection=remember_key(credential.key);if(!remembered_connection)append(status_text,sizeof(status_text)," - Could not save connection; connected for this session only.");}
    if(remembered_connection)append(status_text,sizeof(status_text)," - Remembered connection.");message=status_text;
   }
  }else{wipe();message="Invalid Community profile response. Disconnected.";}
 }
 if(message!=status_text){size_t n=dd_strlen(message);if(n>=sizeof(status_text))n=sizeof(status_text)-1;memcpy(status_text,message,n);status_text[n]=0;}
 SecureZeroMemory(reply,sizeof(reply));
 if(publish||reply_connection)connection_reply(status_text);
 if(!publish){reply_connection=0;want_remember=0;SecureZeroMemory(original,sizeof(original));SecureZeroMemory(current,sizeof(current));SecureZeroMemory(output,sizeof(output));}
 InterlockedExchange(&busy,0);return 0;
}
static void start_task(int publish) {
 HANDLE thread;if(InterlockedCompareExchange(&busy,1,0))return;
 started=GetTickCount64();
 thread=CreateThread(0,0,perform,(LPVOID)(size_t)publish,0,0);
 if(thread)CloseHandle(thread);else{connection_reply("Could not start Community request. Retry.");InterlockedExchange(&busy,0);}
}
static int restore_connection(void) {
 if(!restore_key(credential.key))return 0;
 remembered_connection=1;authorize();start_task(0);return 1;
}
static LRESULT CALLBACK procedure(HWND hwnd,UINT message,WPARAM w,LPARAM l) {
 if(message==WM_CLOSE){wipe();DestroyWindow(hwnd);return 0;}
 if(message==WM_DESTROY){wipe();ExitProcess(0);}
 if(message==WM_TIMER&&busy&&GetTickCount64()-started>25000){wipe();ExitProcess(ERROR_TIMEOUT);}
 if(message==WM_TIMER&&busy&&!still_current()&&original_size){wipe();ExitProcess(ERROR_CANCELLED);}
 if(message==WM_TIMER&&!busy){
  const char *error;DWORD n;dd_save incoming;
  if(dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&incoming,&error)&&!equal(incoming.token,handled_token)&&(equal(incoming.input,"AUTH")||equal(incoming.input,"CONNECT"))){
   pending=incoming;memcpy(handled_token,pending.token,65);memcpy(original,current,n);original_size=n;reply_connection=1;want_remember=0;
   if(equal(pending.input,"AUTH")){
    wipe();want_remember=original[pending.wire_value_offset]=='1';memcpy(credential.key,original+pending.wire_value_offset+2,68);credential.key[68]=0;
    if(!want_remember){remembered_connection=0;}
    if(!want_remember&&!forget_key()){connection_reply("Could not remove the previous remembered connection. Use Forget connection and retry.");wipe();reply_connection=0;return 0;}
   }else if(!key_valid(credential.key)&&!restore_key(credential.key)){
    connection_reply("No remembered connection. Enter your game upload key and choose Connect.");reply_connection=0;SecureZeroMemory(original,sizeof(original));SecureZeroMemory(current,sizeof(current));return 0;
   }
   if(equal(pending.input,"CONNECT")){char saved[69];remembered_connection=restore_key(saved);SecureZeroMemory(saved,sizeof(saved));}
   authorize();start_task(0);return 0;
  }
 }
 if(message==WM_TIMER&&!busy){
  const char *error;DWORD n;
  if(dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&pending,&error)&&equal(pending.input,"PUBLISH")&&!equal(pending.token,handled_token)){
   WCHAR thumb_path[1024];char filename[40];size_t i,j;DWORD root;
   memcpy(handled_token,pending.token,65);memcpy(original,current,n);original_size=n;upload_id[0]=0;review_ready=0;thumbnail_source_digest[0]=0;
   if(!connected){connection_reply("Not connected. Enter a key or use Connect to retry your remembered connection.");return 0;}
   for(i=0;i<sizeof(filename)-1&&pending.wire_value_offset+i<pending.wire_end-1&&original[pending.wire_value_offset+i]!='\n';i++)filename[i]=(char)original[pending.wire_value_offset+i];filename[i]=0;
   if(pending.wire_value_offset+i>=pending.wire_end-1||original[pending.wire_value_offset+i]!='\n')goto bad_thumbnail;
   if(i!=24||memcmp(filename,"Composition_",12)||memcmp(filename+20,".png",4))goto bad_thumbnail;
   for(j=12;j<20;j++)if(!((filename[j]>='0'&&filename[j]<='9')||(filename[j]>='a'&&filename[j]<='f')))goto bad_thumbnail;
   root=GetEnvironmentVariableW(L"LOCALAPPDATA",thumb_path,800);if(!root||root>=800)goto bad_thumbnail;
   {WCHAR suffix[128];dd_ascii_wide("\\SWZeroCompany\\Saved\\ZComDen\\thumbs\\",suffix,128);for(j=0;suffix[j];j++)thumb_path[root++]=suffix[j];for(j=0;filename[j];j++)thumb_path[root++]=(WCHAR)filename[j];thumb_path[root]=0;}
   if(!dd_read(thumb_path,thumbnail,sizeof(thumbnail),&thumbnail_size))goto bad_thumbnail;
   {size_t encoded;
    /* Keep the pre-fix retry identity: a rejected padded thumbnail never reached
     * immutable storage. Its existing staged payload can now finish normally. */
    if(!dd_sha(thumbnail,thumbnail_size,thumbnail_source_digest)||!dd_cached_png(thumbnail,thumbnail_size,&encoded))goto bad_thumbnail;
    SecureZeroMemory(thumbnail+encoded,thumbnail_size-encoded);thumbnail_size=(DWORD)encoded;
   }
   payload_offset=(DWORD)(pending.wire_value_offset+i+1);
   {char *fields[]={publish_title,publish_description,update_code,update_revision};size_t caps[]={sizeof(publish_title),sizeof(publish_description),sizeof(update_code),sizeof(update_revision)};size_t f,k;
    for(f=0;f<4;f++){
     for(k=0;payload_offset<pending.wire_end-1&&original[payload_offset]!='\n';payload_offset++){
      unsigned char c=original[payload_offset];if(c<32||c>=127||k+1>=caps[f])goto bad_metadata;fields[f][k++]=(char)c;
     }
     fields[f][k]=0;if(payload_offset>=pending.wire_end-1)goto bad_metadata;payload_offset++;
     for(k=0;k+4<=dd_strlen(fields[f]);k++)if(!memcmp(fields[f]+k,"zcu_",4))goto bad_metadata;
    }
    if(!publish_title[0])goto bad_metadata;
    if(update_code[0]){char checked[33];if(!dd_code(update_code,checked)||!equal(checked,update_code)||!update_revision[0]||update_revision[0]=='0')goto bad_metadata;for(k=0;update_revision[k];k++)if(update_revision[k]<'0'||update_revision[k]>'9')goto bad_metadata;}
    else if(update_revision[0])goto bad_metadata;
   }
   if(payload_offset>=pending.wire_end-1)goto bad_metadata;payload_size=(DWORD)(pending.wire_end-1-payload_offset);
   if(!dd_publish_review(original+payload_offset,payload_size,requirements,sizeof(requirements)))goto bad_thumbnail;
   review_ready=1;start_task(1);return 0;
   bad_metadata:connection_reply("Invalid metadata. Use a title of 1-120 printable ASCII characters and description up to 4000. Updates require a share code and positive revision. Upload keys are not metadata.");return 0;
   bad_thumbnail:connection_reply("Thumbnail or saved snapshot unavailable. Wait for the cached card preview, review again, then retry.");

  }
 }
 return DefWindowProcW(hwnd,message,w,l);
}
static LONG WINAPI crash_filter(EXCEPTION_POINTERS *exception) {
 (void)exception;wipe();ExitProcess(ERROR_PROCESS_ABORTED);return EXCEPTION_EXECUTE_HANDLER;
}
int dd_connection_main(void) {
 WNDCLASSW wc;MSG message;HMODULE instance=GetModuleHandleW(0);
 /* Optional persistence is plain local storage, explicitly chosen in-game. */
 if(!VirtualLock(&credential,sizeof(credential)))return 2;
 SetErrorMode(SEM_FAILCRITICALERRORS|SEM_NOGPFAULTERRORBOX);
 SetUnhandledExceptionFilter(crash_filter);
 {typedef HRESULT(WINAPI *exclude_fn)(const void *,DWORD);exclude_fn exclude=(exclude_fn)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"WerRegisterExcludedMemoryBlock");if(exclude)exclude(&credential,sizeof(credential));}
 if(!dd_paths(request_path,response_path))return 2;
 memset(&wc,0,sizeof(wc));wc.lpfnWndProc=procedure;wc.hInstance=instance;wc.lpszClassName=L"ZComCommunityConnection";wc.hCursor=LoadCursorW(0,MAKEINTRESOURCEW(32512));
 if(!RegisterClassW(&wc))return 2;
 window=CreateWindowExW(0,wc.lpszClassName,L"",0,0,0,0,0,HWND_MESSAGE,0,instance,0);if(!window)return 2;
 SetTimer(window,1,100,0);
 {dd_save incoming;const char *error;DWORD n;int auth_waiting=dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&incoming,&error)&&equal(incoming.input,"AUTH");
 if(!auth_waiting)restore_connection();}
 while(GetMessageW(&message,0,0,0)>0){TranslateMessage(&message);DispatchMessageW(&message);}wipe();return 0;
}

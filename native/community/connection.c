#include "windows.h"
/* The key, My Shares and sharing. The mailbox thread (proxy.c) calls
 * dd_connection_poll every 100 ms; network work runs on one task thread at a
 * time. A task that times out or whose request is replaced is dropped: it is
 * never terminated, stops at its next network step, and its result is
 * discarded. The in-game masked connection form can opt in to a dedicated plain
 * local key file. Credentials never enter composition exports, logs or command
 * lines. */
static int review_ready;
/* Publish text is UTF-8: up to 120, 4000 and 500 characters. */
static char upload_id[37], published_code[33], publish_title[481], publish_description[16001], publish_changelog[2001], update_code[33], update_revision[10];
static char publish_wire[DD_WIRE_UTF8_MAX];
static char reply_buffer[DD_METADATA_MAX];
static char shares_page[5];
static unsigned char thumbnail[1048576];
static char requirements[65536];
static DWORD thumbnail_size, payload_offset, payload_size;
static char thumbnail_source_digest[65];

static volatile LONG busy, task_generation;
static LONG task_mine;
static int task_kind;
static int stale(void) { return task_mine != task_generation; }
static int connected;
static ULONGLONG started;
static struct { char key[69]; WCHAR authorization[100]; } credential;
static unsigned char original[DD_SAVE_MAX], current[DD_SAVE_MAX], output[DD_SAVE_MAX];
static DWORD original_size;
static dd_save pending;
static char status_text[512];
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
static void reply_wire(const char *wire) {
 DWORD n;size_t written;
 EnterCriticalSection(&dd_mailbox);
 __try{
  if(dd_read(request_path,current,sizeof(current),&n)&&n==original_size&&!memcmp(current,original,n)&&dd_save_response(original,original_size,&pending,wire,output,sizeof(output),&written)){
   if(dd_write(response_path,output,(DWORD)written)&&equal(pending.input,"AUTH"))DeleteFileW(request_path);
  }
 }__finally{LeaveCriticalSection(&dd_mailbox);}
}
static void connection_reply(const char *message) {
 char wire[1024];
 if(dd_error_wire(wire,sizeof(wire),pending.token,message))reply_wire(wire);
}
static void progress(const char *stage) {
 char wire[512]="ZCOM-COMMUNITY\t1\t";size_t used=dd_strlen(wire),i,written;DWORD n;
 for(i=0;pending.token[i];i++)wire[used++]=pending.token[i];
 {const char *tag="\nprogress\t";for(i=0;tag[i];i++)wire[used++]=tag[i];}
 for(i=0;stage[i]&&used+5<sizeof(wire);i++)wire[used++]=stage[i];
 memcpy(wire+used,"\nend",5);
 EnterCriticalSection(&dd_mailbox);
 __try{
  if(!stale()&&dd_read(request_path,current,sizeof(current),&n)&&n==original_size&&!memcmp(current,original,n)&&dd_save_response(original,original_size,&pending,wire,output,sizeof(output),&written))dd_write(response_path,output,(DWORD)written);
 }__finally{LeaveCriticalSection(&dd_mailbox);}
}
static int http(const WCHAR *method,const WCHAR *path,const unsigned char *body,DWORD bytes,const WCHAR *extra,char *reply,DWORD capacity) {
 /* Paths are fixed API routes plus validated codes, ids and page numbers. */
 HINTERNET session=0,connection=0,request=0;
 DWORD disable=WINHTTP_DISABLE_REDIRECTS|WINHTTP_DISABLE_COOKIES|WINHTTP_DISABLE_AUTHENTICATION;
 DWORD policy=WINHTTP_OPTION_REDIRECT_POLICY_NEVER, response_timeout=6000, code=0, size=sizeof(code), got=0, used=0;
 int result=0;
 reply[0]=0;safe_service_error=0;
 if(stale()&&method[0]!='D')return 0; /* A dropped share still cancels its upload. */
 session=WinHttpOpen(L"DenDesignerHoloNet/" DD_WIDE(DD_VERSION),WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,WINHTTP_NO_PROXY_NAME,WINHTTP_NO_PROXY_BYPASS,0);
 if(!session||!WinHttpSetTimeouts(session,4000,6000,6000,6000))goto done;
 connection=WinHttpConnect(session,DD_WIDE(DD_SERVICE_HOST),DD_SERVICE_PORT,0);if(!connection)goto done;
 request=WinHttpOpenRequest(connection,method,path,0,WINHTTP_NO_REFERER,WINHTTP_DEFAULT_ACCEPT_TYPES,DD_SERVICE_SECURE?WINHTTP_FLAG_SECURE:0);if(!request)goto done;
 /* Wine (Proton) needs the response-header timeout set explicitly. */
 if(!WinHttpSetOption(request,WINHTTP_OPTION_DISABLE_FEATURE,&disable,sizeof(disable))||!WinHttpSetOption(request,WINHTTP_OPTION_REDIRECT_POLICY,&policy,sizeof(policy))||!WinHttpSetOption(request,WINHTTP_OPTION_RECEIVE_RESPONSE_TIMEOUT,&response_timeout,sizeof(response_timeout)))goto done;
 if(!WinHttpAddRequestHeaders(request,credential.authorization,(DWORD)-1,WINHTTP_ADDREQ_FLAG_ADD|WINHTTP_ADDREQ_FLAG_REPLACE)||
 !WinHttpSendRequest(request,extra,(DWORD)-1,(LPVOID)body,bytes,bytes,0)||!WinHttpReceiveResponse(request,0))goto done;
 if(!WinHttpQueryHeaders(request,WINHTTP_QUERY_STATUS_CODE|WINHTTP_QUERY_FLAG_NUMBER,WINHTTP_HEADER_NAME_BY_INDEX,&code,&size,WINHTTP_NO_HEADER_INDEX))goto done;
 if(code==401){result=-1;goto done;}
 if(code==403){result=-2;goto done;}
 /* Read only what has arrived, so a dropped task stops between reads. */
 for(;;){DWORD available=0;
  if((stale()&&method[0]!='D')||!WinHttpQueryDataAvailable(request,&available))goto done;
  if(available&&used+1>=capacity)goto done;
  if(available>capacity-used-1)available=capacity-used-1;
  if(available&&!WinHttpReadData(request,reply+used,available,&got))goto done;
  if(!available||!got){reply[used]=0;if(code>=200&&code<300)result=1;else{safe_service_error=service_failure(code,reply);result=-3;}goto done;}
  used+=got;}
 done:if(request)WinHttpCloseHandle(request);if(connection)WinHttpCloseHandle(connection);if(session)WinHttpCloseHandle(session);return result;
}
static int (*send_http)(const WCHAR *,const WCHAR *,const unsigned char *,DWORD,const WCHAR *,char *,DWORD)=http;
static int append(char *out,size_t cap,const char *text){size_t n=dd_strlen(out),m=dd_strlen(text);if(n+m>=cap)return 0;memcpy(out+n,text,m+1);return 1;}
/* JSON string from validated UTF-8 (dd_publish_text): UTF-8 passes through;
 * quotes, backslashes and line breaks are escaped. */
static int quote(char *out,size_t cap,const char *text){size_t i;if(!append(out,cap,"\""))return 0;for(i=0;text[i];i++){char b[3]={text[i],0,0};if(text[i]=='\n'){b[0]='\\';b[1]='n';}else if((unsigned char)text[i]<32||text[i]==127)return 0;else if(text[i]=='"'||text[i]=='\\'){b[0]='\\';b[1]=text[i];}if(!append(out,cap,b))return 0;}return append(out,cap,"\"");}
/* Fixed, bounded UUID/code/status fields only; never follow server URLs. */
static int response_field(const char *json,const char *name,char *out,size_t cap){
 return dd_json_word((const unsigned char *)json,dd_strlen(json),name,out,cap);
}
/* Only fixed messages for known service codes are exposed. Never reflect a
 * server body (or arbitrary strings from it) into status, files or logs. */
static const char *service_failure(DWORD status,const char *reply){
 char code[64];size_t i;
 static const struct {const char *code,*message;} failures[]={
  {"INVALID_THUMBNAIL","HoloNet couldn't read the preview image. Let the card preview render again, then share."},
  {"INVALID_PAYLOAD","HoloNet couldn't accept this composition. Check that every part is still valid, save it, then share again."},
  {"INVALID_METADATA","HoloNet didn't accept the text. Use a title of up to 120 characters, a description up to 4000 and What changed up to 500."},
  {"INVALID_REVISION","This share has changed on HoloNet since you picked it. Pick it again from My Shares, then share."},
  {"REVISION_CONFLICT","This share has changed on HoloNet since you picked it. Pick it again from My Shares, then share."},
  {"REVISION_OR_GRANT_CHANGED","This share or your sharing access changed. Check your account on zcom.app, then try again."},
  {"IDEMPOTENCY_CONFLICT","This retry doesn't match the share that was started. Save the composition again, then share."},
  {"ACCOUNT_UPLOAD_LIMIT_OR_GRANT_CHANGED","You've reached your sharing limit, or your access changed. Unfinished shares are cleared after an hour."},
  {"FILE_ALREADY_UPLOADED","A file in this share differs from the retry. Save the composition again, then share."},
  {"UPLOAD_CLOSED","The share expired or was cancelled. Share again to start over."},
  {"UPLOAD_CLOSED_OR_GRANT_CHANGED","The share was closed or your access changed. Reconnect, then try again."},
  {"LISTING_NOT_FOUND","That share isn't in your account any more. Pick another from My Shares, or share as a new build."},
  {"INCOMPLETE_UPLOAD","The share didn't finish uploading. Share again to complete it."},
  {"STORAGE_UNAVAILABLE","HoloNet's file storage is unavailable right now. Your text is kept; try again later."},
  {"FILE_STORAGE_UNAVAILABLE","HoloNet's file storage is unavailable right now. Your text is kept; try again later."},
  {"RATE_LIMITED","HoloNet is busy. Wait a moment, then try again; your text is kept."},
  {"INVALID_UPLOADED_BYTES","HoloNet couldn't check the uploaded composition and preview. Save it again, then share."},
  {"PAYLOAD_LIMIT","This composition is too large for HoloNet. Share a smaller one."}
 };
 if(response_field(reply,"code",code,sizeof(code)))for(i=0;i<sizeof(failures)/sizeof(failures[0]);i++)if(equal(code,failures[i].code))return failures[i].message;
 if(status==429)return "HoloNet is busy. Wait a moment, then try again.";
 if(status>=500)return "HoloNet is having trouble right now. Your text is kept; try again later.";
 return "HoloNet refused this step. Check the text, the share you're updating and your account; your text is kept.";
}
static int still_current(void){DWORD n;return dd_read(request_path,current,sizeof(current),&n)&&n==original_size&&!memcmp(current,original,n);}
static int (*request_current)(void)=still_current;
static int stage_path(WCHAR *wide,const char *part){char path[160]="/api/v1/composition-uploads/";if(dd_strlen(upload_id)!=36||!append(path,sizeof(path),upload_id)||!append(path,sizeof(path),part))return 0;dd_ascii_wide(path,wide,160);return 1;}
/* kind 0: profile, 1: publish, 2: one page of My Shares. */
static int api(int kind,const unsigned char *body,DWORD bytes,char *reply,DWORD capacity) {
 WCHAR path[160],headers[300];static char json[32768];char idempotency[65],raw_headers[300]="Accept: application/json\r\nContent-Type: application/json\r\nIdempotency-Key: ";int result;
 (void)body;(void)bytes;safe_service_error=0;upload_stage="checking the connection";
 if(kind==0)return send_http(L"GET",L"/api/v1/game/profile",0,0,L"Accept: application/json\r\n",reply,capacity);
 if(kind==2){
  char route[80]="/api/v1/my/listings?page=";char number[8];size_t k=0;int page=0,j;
  for(j=0;shares_page[j];j++)page=page*10+shares_page[j]-'0';
  page++;do{number[k++]=(char)('0'+page%10);page/=10;}while(page);
  {size_t at=dd_strlen(route);while(k)route[at++]=number[--k];route[at]=0;}
  append(route,sizeof(route),"&per_page=8");upload_stage="loading My Shares";dd_ascii_wide(route,path,160);
  return send_http(L"GET",path,0,0,L"Accept: application/json\r\n",reply,capacity);
 }
 if(!request_current())return 0;
 json[0]=0;
 if(!append(json,sizeof(json),"{\"title\":")||!quote(json,sizeof(json),publish_title)||!append(json,sizeof(json),",\"description\":")||!quote(json,sizeof(json),publish_description))return 0;
 if(update_code[0]){if(!append(json,sizeof(json),",\"code\":")||!quote(json,sizeof(json),update_code)||!append(json,sizeof(json),",\"base_revision\":")||!append(json,sizeof(json),update_revision))return 0;
  if(publish_changelog[0]&&(!append(json,sizeof(json),",\"changelog\":")||!quote(json,sizeof(json),publish_changelog)))return 0;}
 if(!append(json,sizeof(json),"}"))return 0;
 /* Same metadata, thumbnail and document have the same retry key, including
  * after selecting the card again. Metadata changes start a fresh upload. */
 {char digest[65],thumb_hash[65];if(!dd_sha((const unsigned char *)publish_wire+payload_offset,payload_size,digest)||!(thumbnail_source_digest[0]?(memcpy(thumb_hash,thumbnail_source_digest,65),1):dd_sha(thumbnail,thumbnail_size,thumb_hash))||!append(json,sizeof(json),digest)||!append(json,sizeof(json),thumb_hash)||!dd_sha((unsigned char *)json,dd_strlen(json),idempotency))return 0;json[dd_strlen(json)-128]=0;}
 if(!append(raw_headers,sizeof(raw_headers),idempotency)||!append(raw_headers,sizeof(raw_headers),"\r\n"))return 0;dd_ascii_wide(raw_headers,headers,300);
 upload_stage="starting the share";progress("Starting the share...");
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
 upload_stage="uploading the composition";progress("Uploading the composition...");stage_path(path,"/payload");result=send_http(L"PUT",path,(const unsigned char *)publish_wire+payload_offset,payload_size,L"Content-Type: application/json\r\n",reply,capacity);if(result!=1){if(stale())goto cancel;return result;}
 if(!request_current())goto cancel;
 upload_stage="uploading the preview";progress("Uploading the preview...");stage_path(path,"/thumbnail");result=send_http(L"PUT",path,thumbnail,thumbnail_size,L"Content-Type: image/png\r\n",reply,capacity);if(result!=1){if(stale())goto cancel;return result;}
 if(!request_current())goto cancel;
 upload_stage="finishing the share";progress("HoloNet is checking the build...");stage_path(path,"/finalize");return send_http(L"POST",path,0,0,L"Accept: application/json\r\n",reply,capacity);
 /* Replaced, deleted or timed out mid-upload: cancel the unfinished share. */
 cancel:stage_path(path,"");send_http(L"DELETE",path,0,0,L"Accept: application/json\r\n",reply,capacity);return 0;
}
static int (*send_api)(int,const unsigned char *,DWORD,char *,DWORD)=api;
/* Apply a finished task's result; called holding dd_mailbox, only while the
 * task is current. */
static void apply(int kind,int result) {
 char *reply=reply_buffer;
 const char *message="HoloNet is unavailable or refused the share. Your text is kept; try again. Editing offline still works.";
 if(result==-3&&safe_service_error)message=safe_service_error;
 else if(result==0){status_text[0]=0;append(status_text,sizeof(status_text),"HoloNet stopped responding while ");append(status_text,sizeof(status_text),upload_stage);append(status_text,sizeof(status_text),". Try again; your text is kept.");message=status_text;}
 else if(result==-1){forget_key();remembered_connection=0;wipe();message="Key invalid, expired or revoked. Get a new key at " DD_SERVICE_HOST "/account.";}
 else if(result==-2){message="Sharing isn't available for this account yet. Your remembered connection has been kept.";}
 else if(result==1&&kind==1){status_text[0]=0;append(status_text,sizeof(status_text),"Published: " DD_SERVICE_URL "/comp/");append(status_text,sizeof(status_text),published_code);message=status_text;review_ready=0;}
 else if(result==1&&kind==2){
  /* My Shares is a value page, not a status message. */
  static char wire[DD_WIRE_MAX];size_t k=0,j;const char *head="ZCOM-COMMUNITY\t1\t";int page=0;
  for(j=0;shares_page[j];j++)page=page*10+shares_page[j]-'0';
  for(j=0;head[j];j++)wire[k++]=head[j];for(j=0;pending.token[j];j++)wire[k++]=pending.token[j];wire[k++]='\n';
  if(dd_shares_page((const unsigned char *)reply,dd_strlen(reply),page,wire+k,sizeof(wire)-k-4)){k=dd_strlen(wire);memcpy(wire+k,"end",4);reply_wire(wire);return;}
  message="HoloNet sent a My Shares page this Den Designer could not read.";
 }
 else if(result==1){
  char name[260];
  if(dd_profile((const unsigned char *)reply,dd_strlen(reply),name,sizeof(name))){
   status_text[0]=0;append(status_text,sizeof(status_text),name[0]?"Connected as ":"Connected to HoloNet");append(status_text,sizeof(status_text),name);connected=1;
   if(reply_connection&&!still_current()){wipe();want_remember=0;message="Connection cancelled.";}
   else {
    if(want_remember){remembered_connection=remember_key(credential.key);if(!remembered_connection)append(status_text,sizeof(status_text)," - Could not save connection; connected for this session only.");}
    if(remembered_connection)append(status_text,sizeof(status_text)," - Remembered connection.");message=status_text;
   }
  }else{wipe();message="HoloNet sent a profile this Den Designer could not read. Disconnected.";}
 }
 if(message!=status_text){size_t n=dd_strlen(message);if(n>=sizeof(status_text))n=sizeof(status_text)-1;memcpy(status_text,message,n);status_text[n]=0;}
 if(kind||reply_connection)connection_reply(status_text);
 if(!kind){reply_connection=0;want_remember=0;SecureZeroMemory(original,sizeof(original));SecureZeroMemory(current,sizeof(current));SecureZeroMemory(output,sizeof(output));}
}
static DWORD WINAPI perform(LPVOID parameter) {
 int kind=(int)(size_t)parameter,result;
 DD_TEST_POINT("task");
 result=send_api(kind,0,0,reply_buffer,sizeof(reply_buffer));
 EnterCriticalSection(&dd_mailbox);
 __try{if(!stale())apply(kind,result);}
 __finally{SecureZeroMemory(reply_buffer,sizeof(reply_buffer));LeaveCriticalSection(&dd_mailbox);}
 InterlockedExchange(&busy,0);return 0;
}
static DWORD WINAPI task_main(LPVOID parameter) {
 __try{perform(parameter);}
 __except(EXCEPTION_EXECUTE_HANDLER){dd_fault("HoloNet stopped after an internal error while connecting or sharing. Restart the game to use HoloNet.");}
 return 0;
}

static void start_task(int kind) {
 HANDLE thread;if(InterlockedCompareExchange(&busy,1,0))return;
 started=GetTickCount64();task_kind=kind;task_mine=task_generation;
 thread=dd_thread(task_main,(LPVOID)(size_t)kind);
 if(thread)CloseHandle(thread);else{connection_reply("Could not start the HoloNet request. Try again.");InterlockedExchange(&busy,0);}
}
static int restore_connection(void) {
 if(!restore_key(credential.key))return 0;
 remembered_connection=1;authorize();start_task(0);return 1;
}
/* Drop the running task: on timeout (answering the request), or when its
 * request was replaced or deleted. An unfinished connection check also drops
 * the key it was checking. */
static void drop_task(int timed_out) {
 EnterCriticalSection(&dd_mailbox);
 __try{
  InterlockedIncrement(&task_generation);
  if(timed_out&&(task_kind||reply_connection)){
   if(!task_kind)connection_reply("HoloNet didn't answer in time. Try again when you're online.");
   else{status_text[0]=0;append(status_text,sizeof(status_text),"HoloNet stopped responding while ");append(status_text,sizeof(status_text),upload_stage);append(status_text,sizeof(status_text),". Try again; your text is kept.");connection_reply(status_text);}
  }
  if(!task_kind)wipe();
  reply_connection=0;want_remember=0;
 }__finally{LeaveCriticalSection(&dd_mailbox);}
}
void dd_connection_wipe(void) { wipe(); }
/* Disconnect, Forget or a new key: drop any running task and the key. */
void dd_connection_drop(void) {
 EnterCriticalSection(&dd_mailbox);
 __try{InterlockedIncrement(&task_generation);wipe();remembered_connection=0;reply_connection=0;want_remember=0;}
 __finally{LeaveCriticalSection(&dd_mailbox);}
}
void dd_connection_poll(void) {
 if(busy&&!stale()){
  if(GetTickCount64()-started>25000)drop_task(1);
  else if(original_size&&!still_current())drop_task(0);
 }
 if(!busy){
  const char *error;DWORD n;dd_save incoming;
  if(dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&incoming,&error)&&!equal(incoming.token,handled_token)&&(equal(incoming.input,"AUTH")||equal(incoming.input,"CONNECT"))){
   pending=incoming;memcpy(handled_token,pending.token,65);memcpy(original,current,n);original_size=n;reply_connection=1;want_remember=0;
   if(equal(pending.input,"AUTH")){
    wipe();want_remember=original[pending.wire_value_offset]=='1';memcpy(credential.key,original+pending.wire_value_offset+2,68);credential.key[68]=0;
    if(!want_remember){remembered_connection=0;}
    if(!want_remember&&!forget_key()){connection_reply("Could not remove the previous remembered connection. Use Forget connection and retry.");wipe();reply_connection=0;return;}
   }else if(!key_valid(credential.key)&&!restore_key(credential.key)){
    connection_reply("No remembered connection. Enter your game upload key and choose Connect.");reply_connection=0;SecureZeroMemory(original,sizeof(original));SecureZeroMemory(current,sizeof(current));return;
   }
   if(equal(pending.input,"CONNECT")){char saved[69];remembered_connection=restore_key(saved);SecureZeroMemory(saved,sizeof(saved));}
   authorize();start_task(0);return;
  }
 }
 if(!busy){
  const char *error;DWORD n;
  if(dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&pending,&error)&&!memcmp(pending.input,"MYSHARES/",9)&&!equal(pending.token,handled_token)){
   memcpy(handled_token,pending.token,65);memcpy(original,current,n);original_size=n;
   if(!connected){connection_reply("Not connected. Enter a key or use Connect to retry your remembered connection.");return;}
   memcpy(shares_page,pending.input+9,dd_strlen(pending.input+9)+1);start_task(2);return;
  }
 }
 if(!busy){
  const char *error;DWORD n;
  if(dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&pending,&error)&&equal(pending.input,"PUBLISH")&&!equal(pending.token,handled_token)){
   WCHAR thumb_path[1024];char filename[40];size_t i,j,size,at;DWORD root;
   DD_TEST_POINT("poll");
   memcpy(handled_token,pending.token,65);memcpy(original,current,n);original_size=n;upload_id[0]=0;review_ready=0;thumbnail_source_digest[0]=0;
   if(!connected){connection_reply("Not connected. Enter a key or use Connect to retry your remembered connection.");return;}
   if(!dd_save_wire(original,n,&pending,publish_wire,sizeof(publish_wire),&size))goto bad_thumbnail;
   i=dd_thumbnail_name((const unsigned char *)publish_wire,size<64?size:64);if(!i)goto bad_thumbnail;
   memcpy(filename,publish_wire,i);filename[i]=0;
   root=GetEnvironmentVariableW(L"LOCALAPPDATA",thumb_path,800);if(!root||root>=800)goto bad_thumbnail;
   {WCHAR suffix[128];dd_ascii_wide("\\SWZeroCompany\\Saved\\ZComDen\\thumbs\\",suffix,128);for(j=0;suffix[j];j++)thumb_path[root++]=suffix[j];for(j=0;filename[j];j++)thumb_path[root++]=(WCHAR)filename[j];thumb_path[root]=0;}
   if(!dd_read(thumb_path,thumbnail,sizeof(thumbnail),&thumbnail_size))goto bad_thumbnail;
   {size_t encoded;
    /* Keep the pre-fix retry identity: a rejected padded thumbnail never reached
     * immutable storage. Its existing staged payload can now finish normally. */
    if(!dd_sha(thumbnail,thumbnail_size,thumbnail_source_digest)||!dd_cached_png(thumbnail,thumbnail_size,&encoded))goto bad_thumbnail;
    SecureZeroMemory(thumbnail+encoded,thumbnail_size-encoded);thumbnail_size=(DWORD)encoded;
   }
   publish_title[0]=publish_description[0]=publish_changelog[0]=update_code[0]=update_revision[0]=0;
   at=i+1;
   if(size-at>6&&!memcmp(publish_wire+at,"title\t",6)){
    /* HoloNet window: "key<TAB>value" lines (title, description, changelog,
     * update<TAB>code<TAB>revision), then a line "payload" and the JSON. */
    for(;;){
     size_t end=at,tab;while(end<size&&publish_wire[end]!='\n')end++;
     if(end>=size)goto bad_metadata;
     if(end-at==7&&!memcmp(publish_wire+at,"payload",7)){at=end+1;break;}
     for(tab=at;tab<end&&publish_wire[tab]!='\t';tab++);
     if(tab>=end)goto bad_metadata;
     if(tab-at==5&&!memcmp(publish_wire+at,"title",5)){if(!dd_publish_text(publish_wire+tab+1,end-tab-1,120,0,publish_title,sizeof(publish_title)))goto bad_metadata;}
     else if(tab-at==11&&!memcmp(publish_wire+at,"description",11)){if(!dd_publish_text(publish_wire+tab+1,end-tab-1,4000,1,publish_description,sizeof(publish_description)))goto bad_metadata;}
     else if(tab-at==9&&!memcmp(publish_wire+at,"changelog",9)){if(!dd_publish_text(publish_wire+tab+1,end-tab-1,500,1,publish_changelog,sizeof(publish_changelog)))goto bad_metadata;}
     else if(tab-at==6&&!memcmp(publish_wire+at,"update",6)){
      size_t second=tab+1;while(second<end&&publish_wire[second]!='\t')second++;
      if(second>=end||second-tab-1>=sizeof(update_code)||end-second-1>=sizeof(update_revision))goto bad_metadata;
      memcpy(update_code,publish_wire+tab+1,second-tab-1);update_code[second-tab-1]=0;
      memcpy(update_revision,publish_wire+second+1,end-second-1);update_revision[end-second-1]=0;
      if(!update_code[0])goto bad_metadata;
     }else goto bad_metadata;
     at=end+1;
    }
   }else{
    /* preview.22 panel: four printable ASCII lines (title, description, code,
     * revision), then the JSON. */
    char *fields[]={publish_title,publish_description,update_code,update_revision};size_t caps[]={121,4001,sizeof(update_code),sizeof(update_revision)};size_t f,k;
    for(f=0;f<4;f++){
     for(k=0;at<size&&publish_wire[at]!='\n';at++){unsigned char c=(unsigned char)publish_wire[at];if(c<32||c>=127||k+1>=caps[f])goto bad_metadata;fields[f][k++]=(char)c;}
     fields[f][k]=0;if(at>=size)goto bad_metadata;at++;
     for(k=0;k+4<=dd_strlen(fields[f]);k++)if(!memcmp(fields[f]+k,"zcu_",4))goto bad_metadata;
    }
   }
   {size_t k;int visible=0;
    for(k=0;publish_title[k];k++)if(publish_title[k]!=' ')visible=1;
    if(!visible)goto bad_metadata;
    if(update_code[0]){char checked[33];if(!dd_code(update_code,checked)||!equal(checked,update_code)||!update_revision[0]||update_revision[0]=='0')goto bad_metadata;for(k=0;update_revision[k];k++)if(update_revision[k]<'0'||update_revision[k]>'9')goto bad_metadata;}
    else if(update_revision[0])goto bad_metadata;
   }
   if(at>=size)goto bad_metadata;payload_offset=(DWORD)at;payload_size=(DWORD)(size-at);
   if(!dd_publish_review((const unsigned char *)publish_wire+payload_offset,payload_size,requirements,sizeof(requirements)))goto bad_thumbnail;
   review_ready=1;start_task(1);return;
   bad_metadata:connection_reply("Check the text: a title of 1-120 characters, a description up to 4000 and What changed up to 500. An update needs the share's code and revision. Upload keys can't go in the text.");return;
   bad_thumbnail:connection_reply("The preview image or saved composition isn't ready. Wait for the card preview, then share again.");
  }
 }
}
void dd_connection_start(void) {
 dd_save incoming;const char *error;DWORD n;
 /* Optional persistence is plain local storage, explicitly chosen in-game. */
 if(!VirtualLock(&credential,sizeof(credential)))dd_log("Could not lock the key's memory page; continuing without.");
 {typedef HRESULT(WINAPI *exclude_fn)(const void *,DWORD);exclude_fn exclude=(exclude_fn)GetProcAddress(GetModuleHandleW(L"kernel32.dll"),"WerRegisterExcludedMemoryBlock");if(exclude)exclude(&credential,sizeof(credential));}
 if(!dd_paths(request_path,response_path))return;
 if(!(dd_recent(request_path,45)&&dd_read(request_path,current,sizeof(current),&n)&&dd_save_read(current,n,&incoming,&error)&&equal(incoming.input,"AUTH")))restore_connection();
}

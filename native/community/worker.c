#include "windows.h"
/* HTTP is isolated behind this value transport. Parsing/import callers never
 * depend on WinHTTP handle types. Cancelling terminates this owned worker
 * process, including DNS, TLS, response reads and parsing. */
typedef struct {
  int (*get)(const char *, int, unsigned char *, size_t, size_t *,
             const char **);
} transport;
static int header(HINTERNET request, DWORD query, WCHAR *out, DWORD chars) {
  DWORD bytes = chars * sizeof(WCHAR), index = 0;
  return WinHttpQueryHeaders(request, query, WINHTTP_HEADER_NAME_BY_INDEX, out,
                             &bytes, &index);
}
static int weq(const WCHAR *a, const WCHAR *b) {
  while (*a && *a == *b) {
    a++;
    b++;
  }
  return *a == *b;
}
static int pinned_revision;
static int http_get(const char *code, int document, unsigned char *out,
                    size_t cap, size_t *size, const char **error) {
  HINTERNET session = 0, connection = 0, request = 0;
  WCHAR path[128], type[256], encoding[256], location[1024], length[64];
  char narrow[128];
  DWORD status = 0, statusbytes = sizeof(status),
        disable = WINHTTP_DISABLE_REDIRECTS | WINHTTP_DISABLE_COOKIES |
                  WINHTTP_DISABLE_AUTHENTICATION;
  DWORD policy = WINHTTP_OPTION_REDIRECT_POLICY_NEVER;
  DWORD got = 0;
  size_t n = 0, i, j;
  int ok = 0;
  *error = "Community is offline or HTTPS failed.";
  /* Construct both URLs from a validated opaque code; downloaded URLs never
   * enter this interface and redirects/authentication/cookies are disabled. */
  if (document!=-1 && (!dd_code(code, narrow) || dd_strlen(narrow) != dd_strlen(code) ||
      memcmp(narrow, code, dd_strlen(code))))
    return 0;
  if(document==-1){memcpy(narrow,"/api/v1/compositions",21);}
  else {
    const char *prefix = "/api/v1/comp/";
    i = dd_strlen(prefix);
    memcpy(narrow, prefix, i);
    j = dd_strlen(code);
    memcpy(narrow + i, code, j);
    i += j;
    if (document) {
      memcpy(narrow + i, "/document", 9);
      i += 9;
    }
      if(pinned_revision>0){char digits[16];size_t k=0;int value=pinned_revision;memcpy(narrow+i,"?revision=",10);i+=10;do{digits[k++]=(char)('0'+value%10);value/=10;}while(value);while(k)narrow[i++]=digits[--k];}
    narrow[i] = 0;
  }
  dd_ascii_wide(narrow, path, 128);
  session = WinHttpOpen(L"DenDesignerCommunity/1",
                        WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
                        WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
  if (!session)
    goto done;
  if (!WinHttpSetTimeouts(session, 4000, 6000, 6000, 6000))
    goto done;
  connection = WinHttpConnect(session, L"share.zcom.app",
                              INTERNET_DEFAULT_HTTPS_PORT, 0);
  if (!connection)
    goto done;
  request =
      WinHttpOpenRequest(connection, L"GET", path, 0, WINHTTP_NO_REFERER,
                         WINHTTP_DEFAULT_ACCEPT_TYPES, WINHTTP_FLAG_SECURE);
  if (!request)
    goto done;
  if (!WinHttpSetOption(request, WINHTTP_OPTION_DISABLE_FEATURE, &disable,
                        sizeof(disable)) ||
      !WinHttpSetOption(request, WINHTTP_OPTION_REDIRECT_POLICY, &policy,
                        sizeof(policy)))
    goto done;
  if (!WinHttpSendRequest(
          request, L"Accept: application/json\r\nAccept-Encoding: identity\r\n",
          (DWORD)-1, WINHTTP_NO_REQUEST_DATA, 0, 0, 0) ||
      !WinHttpReceiveResponse(request, 0))
    goto done;
  if (!WinHttpQueryHeaders(
          request, WINHTTP_QUERY_STATUS_CODE | WINHTTP_QUERY_FLAG_NUMBER,
          WINHTTP_HEADER_NAME_BY_INDEX, &status, &statusbytes,
          WINHTTP_NO_HEADER_INDEX))
    goto done;
  if (status != 200) {
    *error = status == 404 ? "Share code is missing or unpublished."
                           : "Community returned an unsupported HTTP status.";
    goto done;
  }
  if (header(request, WINHTTP_QUERY_LOCATION, location, 1024)) {
    *error = "Redirect responses are not accepted.";
    goto done;
  }
  if (!header(request, WINHTTP_QUERY_CONTENT_TYPE, type, 256) ||
      (!weq(type, L"application/json") &&
       !weq(type, L"application/json; charset=utf-8"))) {
    *error = "Community did not return JSON.";
    goto done;
  }
  if (header(request, WINHTTP_QUERY_CONTENT_ENCODING, encoding, 256) &&
      !weq(encoding, L"identity")) {
    *error = "Compressed responses are not accepted.";
    goto done;
  }
  /* WinHTTP validates HTTP framing; enforce an independent byte limit
   * regardless of Content-Length or chunking. Never allocate from remote sizes.
   */
  if (header(request, WINHTTP_QUERY_CONTENT_LENGTH, length, 64)) {
    size_t value = 0;
    for (i = 0; length[i]; i++) {
      if (length[i] < '0' || length[i] > '9' || value > cap) {
        *error = "Invalid or oversized Content-Length.";
        goto done;
      }
      value = value * 10 + length[i] - '0';
    }
    if (value > cap) {
      *error = "Community response exceeds byte limit.";
      goto done;
    }
  }
  for (;;) {
    DWORD wanted = (DWORD)(cap - n);
    if (wanted > 8192)
      wanted = 8192;
    if (!wanted) {
      unsigned char extra;
      if (!WinHttpReadData(request, &extra, 1, &got))
        goto done;
      if (got) {
        *error = "Community response exceeds byte limit.";
        goto done;
      }
      break;
    }
    if (!WinHttpReadData(request, out + n, wanted, &got))
      goto done;
    if (!got)
      break;
    n += got;
  }
  if (!n) {
    *error = "Community returned an empty response.";
    goto done;
  }
  *size = n;
  ok = 1;
done:
  if (request)
    WinHttpCloseHandle(request);
  if (connection)
    WinHttpCloseHandle(connection);
  if (session)
    WinHttpCloseHandle(session);
  return ok;
}
static unsigned char original[DD_SAVE_MAX], fresh[DD_SAVE_MAX],
    metadata[DD_METADATA_MAX], document[DD_DOCUMENT_MAX], response[DD_SAVE_MAX];
static char wire[DD_WIRE_MAX];
static int once(void) {
  WCHAR request_path[1024], response_path[1024];
  DWORD request_size = 0, fresh_size = 0;
  size_t metadata_size = 0, document_size = 0, expected_size = 0,
         response_size = 0;
  char code[33], expected_digest[65], digest[65];
  const char *error = "Native Community request failed.";
  dd_save save;
  transport net = {http_get};
  int valid = 0;
  if (!dd_paths(request_path, response_path) || !dd_recent(request_path, 45) ||
      !dd_read(request_path, original, sizeof(original), &request_size) ||
      !dd_save_read(original, request_size, &save, &error)) {
    dd_log("Rejected unsupported or malformed mailbox SaveGame.");
    return 2;
  }
  if(!memcmp(save.input,"COPYURL/",8)||!memcmp(save.input,"COPYCODE/",9)){
    int url=save.input[4]=='U';char checked[33],text[128]="";size_t k=0,j;HGLOBAL memory;char *value;
    if(!dd_code(save.input+(url?8:9),checked))goto complete;
    if(url){const char *prefix="https://share.zcom.app/comp/";for(j=0;prefix[j];j++)text[k++]=prefix[j];}
    for(j=0;checked[j];j++)text[k++]=checked[j];text[k]=0;
    memory=GlobalAlloc(GMEM_MOVEABLE,k+1);if(!memory)goto complete;
    value=GlobalLock(memory);if(!value){GlobalFree(memory);goto complete;}memcpy(value,text,k+1);GlobalUnlock(memory);
    if(!OpenClipboard(0)){GlobalFree(memory);goto complete;}
    EmptyClipboard();if(!SetClipboardData(CF_TEXT,memory))GlobalFree(memory);CloseClipboard();
    error="Copied publication link/code.";goto complete;
  }
  if(!memcmp(save.input,"CATALOG/",8)){
    char codes[6][33],query[81],row[8192];int page=0,pages,total,selected,r;size_t used;
    for(r=8;save.input[r];r++){if(save.input[r]<'0'||save.input[r]>'9'||page>7)goto complete;page=page*10+save.input[r]-'0';}
    if(page>7)goto complete;
    used=save.wire_end-save.wire_value_offset-1;memcpy(query,original+save.wire_value_offset,used);query[used]=0;if(used==1&&query[0]==' ')query[0]=0;
    if(!net.get("",-1,metadata,sizeof(metadata),&metadata_size,&error))goto complete;
    selected=dd_gallery_select(metadata,metadata_size,query,page,codes,&pages,&total);if(selected<0){error="Invalid public catalogue response.";goto complete;}
    {size_t j,k=0;const char *head="ZCOM-COMMUNITY\t1\t";for(j=0;head[j];j++)wire[k++]=head[j];for(j=0;save.token[j];j++)wire[k++]=save.token[j];wire[k]=0;}
    {char number[16];size_t j;int values[]={page,pages,total};const char *head="\ngallery";used=dd_strlen(wire);for(j=0;head[j];j++)wire[used++]=head[j];for(r=0;r<3;r++){int n=values[r],k=0;wire[used++]='\t';do{number[k++]=(char)('0'+n%10);n/=10;}while(n);while(k)wire[used++]=number[--k];}wire[used++]='\n';wire[used]=0;}
    for(r=0;r<selected;r++){
      if(!net.get(codes[r],0,metadata,sizeof(metadata),&metadata_size,&error)||!dd_gallery_row(metadata,metadata_size,codes[r],row,sizeof(row)))goto complete;
      if(!dd_read(request_path,fresh,sizeof(fresh),&fresh_size)||fresh_size!=request_size||memcmp(original,fresh,request_size))return 4;
      used=dd_strlen(wire);if(used+dd_strlen(row)+5>=sizeof(wire)){error="Public catalogue page exceeds the transport limit.";goto complete;}memcpy(wire+used,row,dd_strlen(row)+1);
    }
    used=dd_strlen(wire);memcpy(wire+used,"end",4);valid=1;goto complete;
  }
  if(!memcmp(save.input,"PREVIEW/",8)||!memcmp(save.input,"DOWNLOAD/",9)){
    size_t j;int revision=0;for(j=save.wire_value_offset;j<save.wire_end-1;j++)revision=revision*10+original[j]-'0';pinned_revision=revision;
  }
  if (!dd_code(!memcmp(save.input,"PREVIEW/",8)?save.input+8:!memcmp(save.input,"DOWNLOAD/",9)?save.input+9:save.input, code)) {
    error = "Enter a share code or HTTPS zcom.app composition link.";
    goto complete;
  }
  if (!net.get(code, 0, metadata, sizeof(metadata), &metadata_size, &error) ||
      !dd_listing(metadata, metadata_size, code, &expected_size,
                  expected_digest, &error))
    goto complete;
  pinned_revision=dd_listing_revision(metadata,metadata_size);
  if (!net.get(code, 1, document, sizeof(document), &document_size, &error))
    goto complete;
  if (document_size != expected_size ||
      !dd_sha(document, document_size, digest) ||
      memcmp(digest, expected_digest, 65)) {
    error = "Downloaded composition does not match listing size or SHA-256.";
    goto complete;
  }
  if (!dd_document(document, document_size, code, save.token, dd_sha, wire,
                   sizeof(wire), &error))
    goto complete;
  valid = 1;
complete:
  if (!valid && !dd_error_wire(wire, sizeof(wire), save.token, error))
    return 3;
  /* Recheck exact original bytes immediately before publishing; token
   * replacement and deletion cannot cause a stale response to be imported. BP
   * also checks token. */
  if (!dd_read(request_path, fresh, sizeof(fresh), &fresh_size) ||
      fresh_size != request_size || memcmp(original, fresh, request_size))
    return 4;
  if (!dd_save_response(original, request_size, &save, wire, response,
                        sizeof(response), &response_size) ||
      !dd_write(response_path, response, (DWORD)response_size)) {
    dd_log("Could not publish Community response SaveGame.");
    return 5;
  }
  dd_log(valid ? "Community composition fetched and validated; awaiting native "
                 "import."
               : error);
  return valid ? 0 : 1;
}
void mainCRTStartup(void) {
 const WCHAR *command=GetCommandLineW(); size_t i;
 for(i=0;command[i];i++) if(command[i]=='-' && command[i+1]=='-' && command[i+2]=='c') ExitProcess((UINT)dd_connection_main());
 ExitProcess((UINT)once());
}

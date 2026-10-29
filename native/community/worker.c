#include "windows.h"
/* Browse, import and copy requests, one at a time on a worker thread
 * (proxy.c). HTTP is isolated behind this value transport. Parsing/import
 * callers never depend on WinHTTP handle types. A dropped request (replaced,
 * deleted or timed out) is never terminated: it stops at its next network step
 * and cannot reply. */
typedef struct {
  int (*get)(const char *, unsigned char *, size_t, size_t *, const char **);
} transport;
static int header(HINTERNET request, DWORD query, WCHAR *out, DWORD chars) {
  DWORD bytes = chars * sizeof(WCHAR), index = 0;
  return WinHttpQueryHeaders(request, query, WINHTTP_HEADER_NAME_BY_INDEX, out,
                             &bytes, &index);
}
/* application/json, any case, optionally followed by parameters. */
static int json_type(const WCHAR *type) {
  const char *want = "application/json";
  size_t i;
  for (i = 0; want[i]; i++) {
    WCHAR c = type[i];
    if (c >= 'A' && c <= 'Z')
      c += 32;
    if (c != (WCHAR)want[i])
      return 0;
  }
  return type[i] == 0 || type[i] == ';' || type[i] == ' ';
}
volatile LONG dd_worker_generation;
static LONG mine;
static int dropped(void) { return mine != dd_worker_generation; }
static int weq(const WCHAR *a, const WCHAR *b) {
  while (*a && *a == *b) {
    a++;
    b++;
  }
  return *a == *b;
}
/* Only paths built here from validated codes, page numbers and encoded search
 * text reach this function; server-supplied URLs never do. */
static int http_get(const char *narrow, unsigned char *out, size_t cap,
                    size_t *size, const char **error) {
  HINTERNET session = 0, connection = 0, request = 0;
  WCHAR path[512], type[256], encoding[256], location[1024], length[64];
  DWORD status = 0, statusbytes = sizeof(status),
        disable = WINHTTP_DISABLE_REDIRECTS | WINHTTP_DISABLE_COOKIES |
                  WINHTTP_DISABLE_AUTHENTICATION;
  DWORD policy = WINHTTP_OPTION_REDIRECT_POLICY_NEVER, response_timeout = 6000;
  DWORD got = 0;
  size_t n = 0, i;
  int ok = 0;
  *error = "HoloNet is offline or the secure connection failed.";
  if (dd_strlen(narrow) >= 512 || memcmp(narrow, "/api/v1/", 8) || dropped())
    return 0;
  dd_ascii_wide(narrow, path, 512);
  session = WinHttpOpen(L"DenDesignerHoloNet/" DD_WIDE(DD_VERSION),
                        WINHTTP_ACCESS_TYPE_AUTOMATIC_PROXY,
                        WINHTTP_NO_PROXY_NAME, WINHTTP_NO_PROXY_BYPASS, 0);
  if (!session)
    goto done;
  if (!WinHttpSetTimeouts(session, 4000, 6000, 6000, 6000))
    goto done;
  connection = WinHttpConnect(session, DD_WIDE(DD_SERVICE_HOST), DD_SERVICE_PORT, 0);
  if (!connection)
    goto done;
  request =
      WinHttpOpenRequest(connection, L"GET", path, 0, WINHTTP_NO_REFERER,
                         WINHTTP_DEFAULT_ACCEPT_TYPES,
                         DD_SERVICE_SECURE ? WINHTTP_FLAG_SECURE : 0);
  if (!request)
    goto done;
  /* The wait for response headers has its own timeout. Windows takes it from
   * WinHttpSetTimeouts; Wine (Proton) needs it set, or it waits forever. */
  if (!WinHttpSetOption(request, WINHTTP_OPTION_DISABLE_FEATURE, &disable,
                        sizeof(disable)) ||
      !WinHttpSetOption(request, WINHTTP_OPTION_REDIRECT_POLICY, &policy,
                        sizeof(policy)) ||
      !WinHttpSetOption(request, WINHTTP_OPTION_RECEIVE_RESPONSE_TIMEOUT,
                        &response_timeout, sizeof(response_timeout)))
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
    *error = status == 404   ? "No HoloNet build has that code, or it is hidden."
             : status == 429 ? "HoloNet is busy. Wait a moment, then try again."
             : status >= 500 ? "HoloNet is having trouble right now. Try again later."
                             : "HoloNet refused the request.";
    goto done;
  }
  if (header(request, WINHTTP_QUERY_LOCATION, location, 1024)) {
    *error = "Redirect responses are not accepted.";
    goto done;
  }
  if (!header(request, WINHTTP_QUERY_CONTENT_TYPE, type, 256) || !json_type(type)) {
    *error = "HoloNet sent something other than JSON.";
    goto done;
  }
  if (header(request, WINHTTP_QUERY_CONTENT_ENCODING, encoding, 256) &&
      !weq(encoding, L"identity")) {
    *error = "HoloNet sent a compressed reply, which the bridge does not accept.";
    goto done;
  }
  /* WinHTTP validates HTTP framing; enforce an independent byte limit
   * regardless of Content-Length or chunking. Never allocate from remote sizes.
   */
  if (header(request, WINHTTP_QUERY_CONTENT_LENGTH, length, 64)) {
    size_t value = 0;
    for (i = 0; length[i]; i++) {
      if (length[i] < '0' || length[i] > '9' || value > cap) {
        *error = "HoloNet sent a reply that is too large.";
        goto done;
      }
      value = value * 10 + length[i] - '0';
    }
    if (value > cap) {
      *error = "HoloNet sent a reply that is too large.";
      goto done;
    }
  }
  /* Read only what has arrived, so a slow reply still comes back here between
   * reads and a dropped request stops. No data available means the end. */
  for (;;) {
    DWORD available = 0;
    if (dropped() || !WinHttpQueryDataAvailable(request, &available))
      goto done;
    if (!available)
      break;
    if (n == cap) {
      *error = "HoloNet sent a reply that is too large.";
      goto done;
    }
    if (available > cap - n)
      available = (DWORD)(cap - n);
    if (available > 8192)
      available = 8192;
    if (!WinHttpReadData(request, out + n, available, &got))
      goto done;
    if (!got)
      break;
    n += got;
  }
  if (!n) {
    *error = "HoloNet sent an empty reply.";
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
/* /api/v1/comp/<code>[/document][?revision=N] from a validated code. */
static int listing_path(char *out, const char *code, int document, int revision) {
  const char *prefix = "/api/v1/comp/";
  char digits[16];
  size_t i = 0, j, k = 0;
  for (j = 0; prefix[j]; j++)
    out[i++] = prefix[j];
  for (j = 0; code[j] && j < 32; j++)
    out[i++] = code[j];
  if (document)
    for (j = 0; "/document"[j]; j++)
      out[i++] = "/document"[j];
  if (revision > 0) {
    for (j = 0; "?revision="[j]; j++)
      out[i++] = "?revision="[j];
    do {
      digits[k++] = (char)('0' + revision % 10);
      revision /= 10;
    } while (revision);
    while (k)
      out[i++] = digits[--k];
  }
  out[i] = 0;
  return 1;
}
static unsigned char original[DD_SAVE_MAX], fresh[DD_SAVE_MAX],
    metadata[DD_METADATA_MAX], document[DD_DOCUMENT_MAX], response[DD_SAVE_MAX];
static char request_wire[DD_WIRE_UTF8_MAX];
static char wire[DD_WIRE_MAX];
int dd_worker_once(LONG generation) {
  WCHAR request_path[1024], response_path[1024];
  DWORD request_size = 0, fresh_size = 0;
  size_t metadata_size = 0, document_size = 0, expected_size = 0,
         response_size = 0, used = 0;
  char code[33], expected_digest[65], digest[65], path[512];
  const char *error = "The HoloNet request failed.";
  dd_save save;
  transport net = {http_get};
  int valid = 0, revision = 0, result = 4;
  mine = generation;
  DD_TEST_POINT("worker");
  if (!dd_paths(request_path, response_path) || !dd_recent(request_path, 45) ||
      !dd_read(request_path, original, sizeof(original), &request_size) ||
      !dd_save_read(original, request_size, &save, &error) ||
      !dd_save_wire(original, request_size, &save, request_wire, sizeof(request_wire), &used)) {
    dd_log("Rejected unsupported or malformed mailbox SaveGame.");
    return 2;
  }
  if(!memcmp(save.input,"COPYURL/",8)||!memcmp(save.input,"COPYCODE/",9)){
    int url=save.input[4]=='U';char checked[33],text[128]="";size_t k=0,j;HGLOBAL memory;char *value;
    if(!dd_code(save.input+(url?8:9),checked))goto complete;
    if(url){const char *prefix=DD_SERVICE_URL "/comp/";for(j=0;prefix[j];j++)text[k++]=prefix[j];}
    for(j=0;checked[j];j++)text[k++]=checked[j];text[k]=0;
    memory=GlobalAlloc(GMEM_MOVEABLE,k+1);if(!memory)goto complete;
    value=GlobalLock(memory);if(!value){GlobalFree(memory);goto complete;}memcpy(value,text,k+1);GlobalUnlock(memory);
    if(!OpenClipboard(0)){GlobalFree(memory);goto complete;}
    EmptyClipboard();if(!SetClipboardData(CF_TEXT,memory))GlobalFree(memory);CloseClipboard();
    error=url?"Copied the HoloNet link.":"Copied the share code.";goto complete;
  }
  if(!memcmp(save.input,"CATALOG/",8)){
    /* One request per page: the server pages and searches. */
    int page=0,legacy,r;size_t k=0,j;const char *head="ZCOM-COMMUNITY\t1\t";
    for(r=8;save.input[r];r++)page=page*10+save.input[r]-'0';
    if(!dd_catalog_request(request_wire,used,&legacy,path,sizeof(path),page))goto complete;
    if(!net.get(path,metadata,sizeof(metadata),&metadata_size,&error))goto complete;
    for(j=0;head[j];j++)wire[k++]=head[j];for(j=0;save.token[j];j++)wire[k++]=save.token[j];wire[k++]='\n';
    if(!dd_gallery_page(metadata,metadata_size,legacy,page,wire+k,sizeof(wire)-k-4)){error="HoloNet sent a page of builds this Den Designer could not read.";goto complete;}
    k=dd_strlen(wire);memcpy(wire+k,"end",4);valid=1;goto complete;
  }
  if(!memcmp(save.input,"PREVIEW/",8)||!memcmp(save.input,"DOWNLOAD/",9)){
    size_t j;for(j=0;j<used;j++)revision=revision*10+request_wire[j]-'0';
  }
  if (!dd_code(!memcmp(save.input,"PREVIEW/",8)?save.input+8:!memcmp(save.input,"DOWNLOAD/",9)?save.input+9:save.input, code)) {
    error = "Enter a share code or a zcom.app composition link.";
    goto complete;
  }
  /* The listing names the exact revision and digest; the document request is
   * pinned to that revision so both describe the same immutable file. */
  if (!listing_path(path, code, 0, revision) ||
      !net.get(path, metadata, sizeof(metadata), &metadata_size, &error) ||
      !dd_listing(metadata, metadata_size, code, &expected_size,
                  expected_digest, &error))
    goto complete;
  revision=dd_listing_revision(metadata,metadata_size);
  if (!listing_path(path, code, 1, revision) ||
      !net.get(path, document, sizeof(document), &document_size, &error))
    goto complete;
  if (document_size != expected_size ||
      !dd_sha(document, document_size, digest) ||
      memcmp(digest, expected_digest, 65)) {
    error = "The downloaded build doesn't match its HoloNet listing. Try again.";
    goto complete;
  }
  if (!dd_document(document, document_size, code, save.token, dd_sha, wire,
                   sizeof(wire), &error))
    goto complete;
  valid = 1;
complete:
  if (!valid && !dd_error_wire(wire, sizeof(wire), save.token, error))
    return 3;
  /* Recheck exact original bytes immediately before publishing, under the
   * reply lock; token replacement, deletion and timeouts cannot cause a stale
   * response to be imported. BP also checks token. */
  EnterCriticalSection(&dd_mailbox);
  __try {
    if (dropped() || !dd_read(request_path, fresh, sizeof(fresh), &fresh_size) ||
        fresh_size != request_size || memcmp(original, fresh, request_size))
      result = 4;
    else if (!dd_save_response(original, request_size, &save, wire, response,
                               sizeof(response), &response_size) ||
             !dd_write(response_path, response, (DWORD)response_size))
      result = 5;
    else
      result = valid ? 0 : 1;
  } __finally {
    LeaveCriticalSection(&dd_mailbox);
  }
  if (result == 5)
    dd_log("Could not publish Community response SaveGame.");
  else if (result < 2)
    dd_log(valid ? "HoloNet request answered; awaiting the game." : error);
  return result;
}

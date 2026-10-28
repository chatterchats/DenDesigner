#include "core.h"
/* No CRT calls. All indices and output writes are checked before access. */
static size_t slen(const char *s) {
  size_t n = 0;
  while (s[n])
    n++;
  return n;
}
static int eqn(const void *a, const void *b, size_t n) {
  const unsigned char *x = a, *y = b;
  size_t i;
  for (i = 0; i < n; i++)
    if (x[i] != y[i])
      return 0;
  return 1;
}
static int eq(const char *a, const char *b) {
  size_t n = slen(a);
  return n == slen(b) && eqn(a, b, n);
}
static void cp(void *a, const void *b, size_t n) {
  unsigned char *x = a;
  const unsigned char *y = b;
  size_t i;
  for (i = 0; i < n; i++)
    x[i] = y[i];
}
static int ascii_code(char c) {
  return (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') ||
         (c >= '0' && c <= '9') || c == '_' || c == '-';
}
static int hex(char c) {
  return (c >= '0' && c <= '9') || (c >= 'a' && c <= 'f');
}
int dd_key_valid(const char *s) {
 size_t i;if(slen(s)!=68||!eqn(s,"zcu_",4))return 0;
 for(i=4;i<68;i++)if(!hex(s[i]))return 0;
 return 1;
}
int dd_code(const char *input, char out[33]) {
  const char *p = input;
  size_t n = slen(input), i;
  const char *a = "https://share.zcom.app/comp/", *b = "https://zcom.app/comp/";
  if (n >= slen(a) && eqn(p, a, slen(a))) {
    p += slen(a);
    n -= slen(a);
  } else if (n >= slen(b) && eqn(p, b, slen(b))) {
    p += slen(b);
    n -= slen(b);
  } else {
    for (i = 0; i < n; i++)
      if (!ascii_code(p[i]))
        return 0;
  }
  if (n && p[n - 1] == '/')
    n--;
  if (n < 6 || n > 32)
    return 0;
  for (i = 0; i < n; i++)
    if (!ascii_code(p[i]))
      return 0;
  cp(out, p, n);
  out[n] = 0;
  return 1;
}

typedef struct {
  size_t start, end;
  int next, count;
  char kind;
} tok;
typedef struct {
  const unsigned char *s;
  size_t n, p;
  int used, depth;
  tok t[8192];
} parser;
static int ws(unsigned char c) {
  return c == ' ' || c == '\t' || c == '\r' || c == '\n';
}
static void skip(parser *p) {
  while (p->p < p->n && ws(p->s[p->p]))
    p->p++;
}
static int val(parser *p);
static int add(parser *p, char kind) {
  int id;
  if (p->used >= 8192)
    return -1;
  id = p->used++;
  p->t[id].start = p->p;
  p->t[id].end = p->p;
  p->t[id].next = id + 1;
  p->t[id].count = 0;
  p->t[id].kind = kind;
  return id;
}
/* General ASCII JSON strings, with escape syntax checked. Wire values use the
 * stricter unescaped subset; metadata may contain standard JSON escapes. */
static int str(parser *p) {
  int id = add(p, 's');
  if (id < 0)
    return -1;
  p->p++;
  while (p->p < p->n) {
    unsigned c = p->s[p->p++];
    if (c == '"') {
      p->t[id].end = p->p;
      return id;
    }
    if (c < 32 || c >= 127)
      return -1;
    if (c == '\\') {
      unsigned e;
      if (p->p >= p->n)
        return -1;
      e = p->s[p->p++];
      if (e == 'u') {
        int i;
        for (i = 0; i < 4; i++) {
          if (p->p >= p->n)
            return -1;
          c = p->s[p->p++];
          if (!((c >= '0' && c <= '9') || (c >= 'a' && c <= 'f') ||
                (c >= 'A' && c <= 'F')))
            return -1;
        }
      } else if (e != '"' && e != '\\' && e != '/' && e != 'b' && e != 'f' &&
                 e != 'n' && e != 'r' && e != 't')
        return -1;
    }
  }
  return -1;
}
static int val(parser *p) {
  int id, k, n = 0;
  size_t q;
  unsigned c;
  skip(p);
  if (p->p >= p->n || p->depth++ >= 32)
    return -1;
  c = p->s[p->p];
  if (c == '"') {
    id = str(p);
    p->depth--;
    return id;
  }
  if (c == '{' || c == '[') {
    id = add(p, (char)c);
    if (id < 0)
      return -1;
    p->p++;
    skip(p);
    if (p->p < p->n && p->s[p->p] == (c == '{' ? '}' : ']')) {
      p->p++;
      p->t[id].end = p->p;
      p->depth--;
      return id;
    }
    for (;;) {
      if (c == '{') {
        if (p->p >= p->n || p->s[p->p] != '"')
          return -1;
        k = str(p);
        if (k < 0)
          return -1;
        skip(p);
        if (p->p >= p->n || p->s[p->p++] != ':')
          return -1;
      }
      if (val(p) < 0)
        return -1;
      n++;
      skip(p);
      if (p->p >= p->n)
        return -1;
      if (p->s[p->p] == (c == '{' ? '}' : ']')) {
        p->p++;
        break;
      }
      if (p->s[p->p++] != ',')
        return -1;
      skip(p);
    }
    p->t[id].count = n;
    p->t[id].next = p->used;
    p->t[id].end = p->p;
    p->depth--;
    return id;
  }
  id = add(p, 'v');
  if (id < 0)
    return -1;
  q = p->p;
  while (p->p < p->n && !ws(p->s[p->p]) && p->s[p->p] != ',' &&
         p->s[p->p] != ']' && p->s[p->p] != '}')
    p->p++;
  p->t[id].end = p->p;
  p->depth--;
  return p->p > q ? id : -1;
}
static int raw(parser *p, int id, const char *s) {
  size_t n = slen(s);
  return id >= 0 && p->t[id].end - p->t[id].start == n &&
         eqn(p->s + p->t[id].start, s, n);
}
static int text(parser *p, int id, char *out, size_t cap) {
  size_t start, n, i;
  if (id < 0 || p->t[id].kind != 's')
    return 0;
  start = p->t[id].start + 1;
  n = p->t[id].end - start - 1;
  {size_t used=0;
  for (i = 0; i < n; i++) {
    unsigned c = p->s[start + i];
    if(c=='\\'){if(++i>=n)return 0;c=p->s[start+i];if(c!='"'&&c!='\\'&&c!='/')return 0;}
    if (c < 32 || c >= 127) return 0;
    if(used+1>=cap)return 0;
    out[used++] = (char)c;
  }
  out[used] = 0;}

  return 1;
}
static int istext(parser *p, int id, const char *s) {
  size_t n = slen(s);
  return id >= 0 && p->t[id].kind == 's' &&
         p->t[id].end - p->t[id].start == n + 2 &&
         eqn(p->s + p->t[id].start + 1, s, n);
}
static int member(parser *p, int obj, const char *key) {
  int i, found = -1;
  if (obj < 0 || p->t[obj].kind != '{')
    return -1;
  for (i = obj + 1; i < p->t[obj].next;) {
    int v = i + 1;
    if (istext(p, i, key)) {
      if (found >= 0)
        return -2;
      found = v;
    }
    i = p->t[v].next;
  }
  return found;
}
static int object(parser *p, int id, const char *const *keys, int n) {
  int i, j, seen[24] = {0};
  if (id < 0 || n > 24 || p->t[id].kind != '{' || p->t[id].count != n)
    return 0;
  for (i = id + 1; i < p->t[id].next;) {
    int v = i + 1;
    for (j = 0; j < n; j++)
      if (istext(p, i, keys[j]))
        break;
    if (j == n || seen[j])
      return 0;
    seen[j] = 1;
    i = p->t[v].next;
  }
  return 1;
}
static int integer(parser *p, int id, int *value) {
  size_t i, end;
  int sign = 1;
  uint32_t x = 0;
  if (id < 0 || p->t[id].kind != 'v')
    return 0;
  i = p->t[id].start;
  end = p->t[id].end;
  if (i < end && p->s[i] == '-') {
    sign = -1;
    i++;
  }
  if (i >= end)
    return 0;
  if (p->s[i] == '0' && (end - i > 1 || sign == -1))
    return 0;
  for (; i < end; i++) {
    unsigned c = p->s[i];
    if (c < '0' || c > '9' || x > 100000000)
      return 0;
    x = x * 10 + c - '0';
  }
  if (x > 10000000)
    return 0;
  *value = (int)x * sign;
  return 1;
}
static int vector(parser *p, int id, int values[3], int positive) {
  int i, k = 0;
  if (id < 0 || p->t[id].kind != '[' || p->t[id].count != 3)
    return 0;
  for (i = id + 1; i < p->t[id].next; i = p->t[i].next) {
    if (!integer(p, i, &values[k]) || (positive && values[k] <= 0))
      return 0;
    k++;
  }
  return 1;
}
static int decimal(parser *,int,int);
static int init(parser *p, const unsigned char *s, size_t n) {
  int i;
  p->s = s;
  p->n = n;
  p->p = 0;
  p->used = 0;
  p->depth = 0;
  if (!n || val(p) != 0)
    return 0;
  skip(p);
  if (p->p != n)
    return 0;
  for (i = 0; i < p->used; i++)
    if (p->t[i].kind == 'v' && !raw(p, i, "true") && !raw(p, i, "false") &&
        !raw(p, i, "null") && !decimal(p, i, -1))
      return 0;
  return 1;
}
/* No duplicate keys anywhere, including objects not consumed by this slice. */
static int unique(parser *p) {
  int o, a, b;
  char key[1025];
  for (o = 0; o < p->used; o++)
    if (p->t[o].kind == '{')
      for (a = o + 1; a < p->t[o].next; a = p->t[a + 1].next) {
        size_t n = p->t[a].end - p->t[a].start;
        if (!text(p, a, key, sizeof(key)))
          return 0;
        for (b = p->t[a + 1].next; b < p->t[o].next; b = p->t[b + 1].next)
          if (n == p->t[b].end - p->t[b].start &&
              eqn(p->s + p->t[a].start, p->s + p->t[b].start, n))
            return 0;
      }
  return 1;
}
/* Canonical payload: printable ASCII strings and finite decimal values,
 * lexicographically sorted object keys, and no insignificant whitespace. This
 * is an explicit subset of Python contract.canonical, never an alternate float
 * hash scheme. */
static int decimal(parser *p,int id,int positive) {
 size_t i,end;double value=0,divisor=1;int sign=1,expsign=1,exponent=0,digits=0;
 if(id<0||p->t[id].kind!='v'||p->t[id].end-p->t[id].start>64)return 0;
 i=p->t[id].start;end=p->t[id].end;
 if(i<end&&p->s[i]=='-'){sign=-1;i++;}
 if(i>=end||p->s[i]<'0'||p->s[i]>'9')return 0;
 if(p->s[i]=='0'&&i+1<end&&p->s[i+1]>='0'&&p->s[i+1]<='9')return 0;
 while(i<end&&p->s[i]>='0'&&p->s[i]<='9'){value=value*10+p->s[i++]-'0';digits++;}
 if(!digits)return 0;
 if(i<end&&p->s[i]=='.'){i++;digits=0;while(i<end&&p->s[i]>='0'&&p->s[i]<='9'){divisor*=10;value+=(p->s[i++]-'0')/divisor;digits++;}if(!digits)return 0;}
 if(i<end&&(p->s[i]=='e'||p->s[i]=='E')){i++;if(i<end&&(p->s[i]=='-'||p->s[i]=='+')){if(p->s[i]=='-')expsign=-1;i++;}digits=0;while(i<end&&p->s[i]>='0'&&p->s[i]<='9'){exponent=exponent*10+p->s[i++]-'0';digits++;if(exponent>308)return 0;}if(!digits)return 0;}
 if(i!=end)return 0;
 while(exponent--){if(expsign>0)value*=10;else value/=10;}value*=sign;
 return positive<0?(value>=-1e308&&value<=1e308):positive?(value>0&&value<=100):(value>=-1e7&&value<=1e7);
}
static int decimal_vector(parser *p,int id,int positive) {
 int i;if(id<0||p->t[id].kind!='['||p->t[id].count!=3)return 0;
 for(i=id+1;i<p->t[id].next;i=p->t[i].next)if(!decimal(p,i,positive))return 0;
 return 1;
}
static int asset_path(const char *path) {
 size_t i,n=slen(path),slash=0,dot=0;if(n<6||n>1023||path[0]!='/')return 0;
 for(i=1;i<n;i++){if(path[i]=='/'){if(i==1||path[i-1]=='/'||dot)return 0;slash=i;}else if(path[i]=='.'){if(dot||i==slash+1)return 0;dot=i;}else if(!ascii_code(path[i]))return 0;}
 return slash>0&&dot>slash+1&&n-dot-1==dot-slash-1&&eqn(path+slash+1,path+dot+1,n-dot-1);
}
static int dependency_has(parser *p,int deps,const char *path,const char *kind) {
 const char *lists[]={"assets","unknown_assets"};int l,i,found=0;char candidate[1024];
 for(l=0;l<2;l++){int a=member(p,deps,lists[l]);if(a<0||p->t[a].kind!='[')return 0;
 for(i=a+1;i<p->t[a].next;i=p->t[i].next)if(text(p,member(p,i,"path"),candidate,sizeof(candidate))&&eq(candidate,path)){if(!istext(p,member(p,i,"kind"),kind))return 0;found++;}}
 return found==1;
}
static int canonical_payload(parser *p, int root) {
  int i, a, b;
  size_t j;
  char x[1025], y[1025];
  for (j = p->t[root].start; j < p->t[root].end; j++)
    if (ws(p->s[j])) { /* Spaces inside strings are allowed; checked by token
                          scan below. */
      break;
    }
  for (i = root; i < p->t[root].next; i++) {
    tok *t = &p->t[i];
    if (t->kind == 's') {
      if (!text(p, i, x, sizeof(x)))
        return 0;
    } else if (t->kind == 'v') {
      if (!raw(p, i, "true") && !raw(p, i, "false") && !raw(p, i, "null") &&
          !decimal(p, i, 0))
        return 0;
    }
    if (t->kind == '{') {
      for (a = i + 1; a < t->next; a = p->t[a + 1].next) {
        b = p->t[a + 1].next;
        if (b < t->next) {
          size_t k = 0;
          if (!text(p, a, x, sizeof(x)) || !text(p, b, y, sizeof(y)))
            return 0;
          while (x[k] && x[k] == y[k])
            k++;
          if ((unsigned char)x[k] >= (unsigned char)y[k])
            return 0;
        }
      }
    }
  }
  /* Skip precisely each string region to reject only external whitespace. */
  for (j = p->t[root].start; j < p->t[root].end;) {
    if (p->s[j] == '"') {
      j++;
      while (j < p->t[root].end && p->s[j] != '"')
        j++;
      j++;
    } else {
      if (ws(p->s[j]))
        return 0;
      j++;
    }
  }
  return 1;
}

static int trimmed(const char *s) {
  size_t n = slen(s);
  return !n || (s[0] != ' ' && s[n - 1] != ' ');
}

int dd_listing(const unsigned char *json, size_t size, const char *code,
               size_t *bytes, char digest[65], const char **error) {
  parser p;
  int item, v, n;
  char expected[65];
  *error = "Malformed listing response.";
  if (size > DD_METADATA_MAX || !init(&p, json, size) || !unique(&p))
    return 0;
  if (!istext(&p, member(&p, 0, "api_version"), "v1")) {
    *error = "Unsupported Community API version.";
    return 0;
  }
  item = member(&p, 0, "item");
  if (item < 0 || p.t[item].kind != '{' ||
      !istext(&p, member(&p, item, "code"), code) ||
      !istext(&p, member(&p, item, "kind"), "comp"))
    return 0;
  if (!integer(&p, member(&p, item, "schema_version"), &n) || n != 1) {
    *error = "Unsupported composition schema; update Den Designer.";
    return 0;
  }
  v = member(&p, item, "document_bytes");
  if (!integer(&p, v, &n) || n <= 0 || (size_t)n > DD_DOCUMENT_MAX) {
    *error = "Listing has no bounded downloadable document.";
    return 0;
  }
  if (!text(&p, member(&p, item, "document_sha256"), expected,
            sizeof(expected)) ||
      slen(expected) != 64)
    return 0;
  for (v = 0; v < 64; v++)
    if (!hex(expected[v]))
      return 0;
  *bytes = (size_t)n;
  cp(digest, expected, 65);
  return 1;
}

typedef struct {
  char *out;
  size_t n, cap;
  int ok;
} writer;
static void put(writer *w, const char *s) {
  size_t n = slen(s);
  if (!w->ok || n >= w->cap - w->n) {
    w->ok = 0;
    return;
  }
  cp(w->out + w->n, s, n);
  w->n += n;
  w->out[w->n] = 0;
}
static void num(writer *w, int n) {
  char b[16];
  int i = 0, j;
  if (n < 0) {
    put(w, "-");
    n = -n;
  }
  do {
    b[i++] = (char)('0' + n % 10);
    n /= 10;
  } while (n);
  for (j = i - 1; j >= 0; j--) {
    char s[2] = {b[j], 0};
    put(w, s);
  }
}
static void vector_wire(writer *w, const int n[3]) {
  int i;
  for (i = 0; i < 3; i++) {
    put(w, "\t");
    num(w, n[i]);
  }
}
size_t dd_error_wire(char *wire, size_t cap, const char *token,
                     const char *error) {
  writer w = {wire, 0, cap, 1};
  put(&w, "ZCOM-COMMUNITY\t1\t");
  put(&w, token);
  put(&w, "\nerror\t");
  put(&w, error);
  put(&w, "\nend");
  return w.ok ? w.n : 0;
}
int dd_document(const unsigned char *json, size_t size, const char *code,
                const char *token, dd_hash_fn hash, char *wire, size_t capacity,
                const char **error) {
  parser p;
  int c, d, m, author, payload, entries, anchor, deps, assets, entry, asset, k,
      n, count, xyz[3], rot[3], scale[3], collision, published=0;
  char digest[65], expected[65], title[121], key[97], oldkeys[128][97];
  writer w = {wire, 0, capacity, 1};
  const char *rootkeys[] = {"format",   "schema_version", "content_type",
                            "metadata", "compatibility",  "dependencies",
                            "payload",  "integrity"};
  const char *compatkeys[] = {"game_id", "game_version", "mod_id",
                              "mod_version", "native_fingerprint"};
  const char *metakeys[] = {"title", "description", "author", "media"};
  const char *authorkeys[] = {"id", "display_name"};
  const char *depkeys[] = {"assets", "packs", "unknown_assets"};
  const char *assetkeys[] = {"path", "kind", "owner", "asset_id"};
  const char *payloadkeys[] = {"anchor", "entries"};
  const char *anchorkeys[] = {"position", "convention"};
  const char *integritykeys[] = {"algorithm", "payload_sha256"};
  const char *entrykeys[] = {"Kind",
                             "Key",
                             "Mesh",
                             "Position",
                             "Rotation",
                             "Scale",
                             "HasPosition",
                             "HasRotation",
                             "HasScale",
                             "Hidden",
                             "CollisionMode",
                             "Materials",
                             "HasFingerprint",
                             "FingerprintMesh",
                             "FingerprintPosition"};
  *error = "Malformed or unsupported composition JSON.";
  if (size > DD_DOCUMENT_MAX || !init(&p, json, size) || !unique(&p) ||
      !object(&p, 0, rootkeys, 8))
    return 0;
  if (!istext(&p, member(&p, 0, "format"), "zcom-share") ||
      !integer(&p, member(&p, 0, "schema_version"), &n) || n != 1 ||
      !istext(&p, member(&p, 0, "content_type"), "composition")) {
    *error = "Unsupported composition schema or content type.";
    return 0;
  }
  c = member(&p, 0, "compatibility");
  if (!object(&p, c, compatkeys, 5))
    return 0;
  if (!istext(&p, member(&p, c, "game_id"), "steam:2075800") ||
      !istext(&p, member(&p, c, "game_version"), "25898267") ||
      !istext(&p, member(&p, c, "mod_id"), "community.den-designer") ||
      !istext(&p, member(&p, c, "mod_version"), "1.1.0-preview.19") ||
      !istext(&p, member(&p, c, "native_fingerprint"), "")) {
    *error = "Composition requires a different game or Den Designer version.";
    return 0;
  }
  m = member(&p, 0, "metadata");
  if (!object(&p, m, metakeys, 4) ||
      !text(&p, member(&p, m, "title"), title, sizeof(title)) || !title[0] ||
      !trimmed(title))
    return 0;
  {
    char desc[4001], authorid[129], display[97];
    if (!text(&p, member(&p, m, "description"), desc, sizeof(desc)) ||
        !trimmed(desc))
      return 0;
    author = member(&p, m, "author");
    if (!object(&p, author, authorkeys, 2) ||
        !text(&p, member(&p, author, "id"), authorid, sizeof(authorid)) ||
        !authorid[0] || !trimmed(authorid) ||
        !text(&p, member(&p, author, "display_name"), display,
              sizeof(display)) ||
        !display[0] || !trimmed(display))
      return 0;
  }
  k = member(&p, m, "media");
  if (k < 0 || p.t[k].kind != '[' || p.t[k].count > 1) return 0;
  if (p.t[k].count) {
    const char *keys[] = {"id","mime","width","height","bytes","sha256","alt"};
    int image=k+1,width,height,bytes;char digest[65],alt[513];
    if(!object(&p,image,keys,7)||!istext(&p,member(&p,image,"id"),"thumbnail")||
       !istext(&p,member(&p,image,"mime"),"image/png")||
       !integer(&p,member(&p,image,"width"),&width)||width<1||width>1024||
       !integer(&p,member(&p,image,"height"),&height)||height<1||height>1024||
       !integer(&p,member(&p,image,"bytes"),&bytes)||bytes<1||bytes>1048576||
       !text(&p,member(&p,image,"sha256"),digest,sizeof(digest))||slen(digest)!=64||
       !text(&p,member(&p,image,"alt"),alt,sizeof(alt)))return 0;
    published=1;
    /* Descriptive image metadata is never fetched or used as a local path. */
  }
  deps = member(&p, 0, "dependencies");
  if (!object(&p, deps, depkeys, 3))
    return 0;
  k = member(&p, deps, "packs");
  if (k < 0 || p.t[k].kind != '[' || p.t[k].count) {
    *error = "Dependencies: prop packs unsupported by this native test slice. "
             "Import blocked.";
    return 0;
  }
  k = member(&p, deps, "unknown_assets");
  if (k < 0 || p.t[k].kind != '[' || (!published&&p.t[k].count)) {
    *error = "Dependencies: unknown asset ownership. Import blocked.";
    return 0;
  }
  assets = member(&p, deps, "assets");
  if (assets < 0 || p.t[assets].kind != '[' || (!published&&p.t[assets].count != 1)) {
    *error = "Dependencies: only the reviewed base-game control monitor is "
             "supported.";
    return 0;
  }
  asset = assets + 1;
  if (!published&&(!object(&p, asset, assetkeys, 4) ||
      !istext(&p, member(&p, asset, "path"), DD_MESH) ||
      !istext(&p, member(&p, asset, "kind"), "mesh") ||
      !istext(&p, member(&p, asset, "owner"), "game") ||
      !istext(&p, member(&p, asset, "asset_id"), "den-control-monitor-a"))) {
    *error =
        "Dependencies: asset is outside the reviewed native slice inventory.";
    return 0;
  }
  payload = member(&p, 0, "payload");
  if (!object(&p, payload, payloadkeys, 2) || !canonical_payload(&p, payload)) {
    *error = "Import requires canonical ASCII JSON with bounded "
             "transforms.";
    return 0;
  }
  d = member(&p, 0, "integrity");
  if (!object(&p, d, integritykeys, 2) ||
      !istext(&p, member(&p, d, "algorithm"), "sha256") ||
      !text(&p, member(&p, d, "payload_sha256"), expected, sizeof(expected)) ||
      slen(expected) != 64 ||
      !hash(json + p.t[payload].start, p.t[payload].end - p.t[payload].start,
            digest) ||
      !eq(expected, digest)) {
    *error = "Composition payload integrity check failed.";
    return 0;
  }
  anchor = member(&p, payload, "anchor");
  if (!object(&p, anchor, anchorkeys, 2) ||
      !istext(&p, member(&p, anchor, "convention"), "bounds-bottom-center") ||
      !(published?decimal_vector(&p, member(&p, anchor, "position"),0):vector(&p, member(&p, anchor, "position"), xyz, 0)))
    return 0;
  entries = member(&p, payload, "entries");
  if (entries < 0 || p.t[entries].kind != '[' || p.t[entries].count < 1 ||
      p.t[entries].count > 128) {
    *error = "Composition must have 1 to 128 parts.";
    return 0;
  }
  count = p.t[entries].count;
  put(&w, "ZCOM-COMMUNITY\t1\t");
  put(&w, token);
  put(&w, "\nok\nname\t");
  title[27] = 0;
  put(&w, title);
  put(&w, " ");
  n = (int)slen(code);
  put(&w, code + (n > 12 ? n - 12 : 0));
  put(&w,published?"\nreport\tPublished asset requirements detected; every mesh and material is checked locally before placement.\nanchor":"\nreport\tDependencies: 1 reviewed base-game mesh; packs: none. Local thumbnail follows import.\nanchor");
  if(published){int v=member(&p,anchor,"position"),a;for(a=v+1;a<p.t[v].next;a=p.t[a].next){char number[65];size_t len=p.t[a].end-p.t[a].start;cp(number,json+p.t[a].start,len);number[len]=0;put(&w,"\t");put(&w,number);}}
  else vector_wire(&w, xyz);
  put(&w, "\ncount\t");
  num(&w, count);
  n = 0;
  for (entry = entries + 1; entry < p.t[entries].next;
       entry = p.t[entry].next) {
    int z[3];char mesh[1024];
    if (!object(&p, entry, entrykeys, 15) ||
        !integer(&p, member(&p, entry, "Kind"), &k) || k != 0 ||
        !text(&p, member(&p, entry, "Key"), key, sizeof(key)) || !key[0] ||
        !text(&p, member(&p, entry, "Mesh"),mesh,sizeof(mesh))||!asset_path(mesh)||(!published&&!eq(mesh,DD_MESH))||(published&&!dependency_has(&p,deps,mesh,"mesh"))) {
      *error = "Composition has unsupported entries or dependencies.";
      return 0;
    }
    for (k = 0; key[k]; k++)
      if (!ascii_code(key[k]))
        return 0;
    for (k = 0; k < n; k++)
      if (eq(oldkeys[k], key)) {
        *error = "Composition has duplicate part identities.";
        return 0;
      }
    cp(oldkeys[n++], key, slen(key) + 1);
    if (!raw(&p, member(&p, entry, "HasPosition"), "true") ||
        !raw(&p, member(&p, entry, "HasRotation"), "true") ||
        !raw(&p, member(&p, entry, "HasScale"), "true") ||
        !raw(&p, member(&p, entry, "Hidden"), "false") ||
        !raw(&p, member(&p, entry, "HasFingerprint"), "false") ||
        !istext(&p, member(&p, entry, "FingerprintMesh"), "") ||
        !vector(&p, member(&p, entry, "FingerprintPosition"), z, 0) || z[0] ||
        z[1] || z[2])
      return 0;
    k = member(&p, entry, "Materials");
    if (k < 0 || p.t[k].kind != '[' || p.t[k].count>64||(!published&&p.t[k].count)) {
      *error = "Dependencies: material overrides unsupported by the reviewed "
               "native slice.";
      return 0;
    }
    if(published){
      const char *fields[]={"Position","Rotation","Scale"};int f;
      put(&w,"\npart\t");put(&w,mesh);
      for(f=0;f<3;f++){int v=member(&p,entry,fields[f]),a;if(!decimal_vector(&p,v,f==2))return 0;
       for(a=v+1;a<p.t[v].next;a=p.t[a].next){char number[65];size_t len=p.t[a].end-p.t[a].start;cp(number,json+p.t[a].start,len);number[len]=0;put(&w,"\t");put(&w,number);}}
      if(!integer(&p,member(&p,entry,"CollisionMode"),&collision)||collision<0||collision>2)return 0;
    }else{
    if (!vector(&p, member(&p, entry, "Position"), xyz, 0) ||
        !vector(&p, member(&p, entry, "Rotation"), rot, 0) ||
        !vector(&p, member(&p, entry, "Scale"), scale, 1) ||
        !integer(&p, member(&p, entry, "CollisionMode"), &collision) ||
        collision < 0 || collision > 2)
      return 0;
    put(&w, "\npart\t" DD_MESH);
    vector_wire(&w, xyz);
    vector_wire(&w, rot);
    vector_wire(&w, scale);
    }
    put(&w, "\t");
    num(&w, collision);
    if(published){int m=member(&p,entry,"Materials"),a;for(a=m+1;a<p.t[m].next;a=p.t[a].next){char material[1024];if(!text(&p,a,material,sizeof(material))||(material[0]&&(!asset_path(material)||!dependency_has(&p,deps,material,"material"))))return 0;put(&w,"\nmaterial\t");put(&w,material);}}
  }
  put(&w, "\nend");
  if (!w.ok) {
    *error = "Validated composition exceeds native wire limit.";
    return 0;
  }
  return 1;
}

static uint32_t u32(const unsigned char *p) {
  return (uint32_t)p[0] | ((uint32_t)p[1] << 8) | ((uint32_t)p[2] << 16) |
         ((uint32_t)p[3] << 24);
}
static void set32(unsigned char *p, uint32_t n) {
  p[0] = (unsigned char)n;
  p[1] = (unsigned char)(n >> 8);
  p[2] = (unsigned char)(n >> 16);
  p[3] = (unsigned char)(n >> 24);
}
static int fstr(const unsigned char *b, size_t n, size_t *pos,
                const unsigned char **text, size_t *len) {
  uint32_t size;
  if (*pos > n || n - *pos < 4)
    return 0;
  size = u32(b + *pos);
  *pos += 4;
  if (!size || size > n - *pos || b[*pos + size - 1] != 0)
    return 0;
  *text = b + *pos;
  *len = size - 1;
  *pos += size;
  return 1;
}
static int fmatch(const unsigned char *b, size_t n, size_t *pos,
                  const char *match) {
  const unsigned char *s;
  size_t len;
  return fstr(b, n, pos, &s, &len) && len == slen(match) && eqn(s, match, len);
}
int dd_save_read(const unsigned char *b, size_t n, dd_save *out,
                 const char **error) {
  size_t p = 0, len, start, i;
  const unsigned char *s;
  uint32_t count;
  int seen = 0;
  *error = "Unsupported Community mailbox SaveGame.";
  if (n > DD_SAVE_MAX || n < 50 || !eqn(b, "GVAS", 4) || u32(b + 4) != 3 ||
      u32(b + 8) != 522 || u32(b + 12) != 1017 || b[16] != 5 || b[17] != 0 ||
      b[18] != 6 || b[19] != 0 || b[20] != 1 || b[21] != 0)
    return 0;
  p = 26;
  if (!fstr(b, n, &p, &s, &len) || p > n || n - p < 8 || u32(b + p) != 3)
    return 0;
  count = u32(b + p + 4);
  p += 8;
  if (count > 256 || count > (n - p) / 20)
    return 0;
  p += (size_t)count * 20;
  if (!fmatch(b, n, &p,
              "/DenDesignerGF/Runtime/"
              "BP_DenCommunityWireSave.BP_DenCommunityWireSave_C"))
    return 0;
  /* UE5.6 tagged SaveGame terminator/version flag precedes tagged properties.
   */
  if (p >= n || b[p++] != 0)
    return 0;
  for (;;) {
    const unsigned char *name;
    size_t namesize, sizeoff, valueoff, end, payloadsize;
    int which = -1;
    if (!fstr(b, n, &p, &name, &namesize))
      return 0;
    if (namesize == 4 && eqn(name, "None", 4)) {
      if (n - p != 4 || u32(b + p) != 0 || seen != 7)
        return 0;
      break;
    }
    if (namesize == 5 && eqn(name, "Token", 5))
      which = 0;
    if (namesize == 5 && eqn(name, "Input", 5))
      which = 1;
    if (namesize == 4 && eqn(name, "Wire", 4))
      which = 2;
    if (which < 0 || (seen & (1 << which)))
      return 0;
    seen |= 1 << which;
    if (!fmatch(b, n, &p, "StrProperty") || n - p < 9 || u32(b + p) != 0)
      return 0;
    p += 4;
    sizeoff = p;
    payloadsize = u32(b + p);
    p += 4;
    /* The editor includes a property GUID (flag 2); the shipped game strips
     * it (flag 0). Preserve the measured local tag layout in the response. */
    {
      unsigned flags = b[p++];
      if (flags != 0 && flags != 2)
        return 0;
      if (flags == 2) {
        if (n - p < 16)
          return 0;
        p += 16;
      }
    }
    valueoff = p;
    if (!fstr(b, n, &p, &s, &len) || p - valueoff != payloadsize)
      return 0;
    end = p;
    /* FString payload is literal UTF-8/ANSI; reject wide strings for this ASCII
     * wire. */
    for (i = 0; i < len; i++)
      if ((s[i] < 32 && !(which==2&&(s[i]=='\n'||s[i]=='\t')))||s[i]>=127)
        return 0;
    if (which == 0) {
      if (len != 32)
        return 0;
      for (i = 0; i < len; i++)
        if (!hex((char)s[i]))
          return 0;
      cp(out->token, s, len);
      out->token[len] = 0;
    }
    if (which == 1) {
      if (len > 256)
        return 0;
      cp(out->input, s, len);
      out->input[len] = 0;
    }
    if (which == 2) {
      if (len > DD_WIRE_MAX)
        return 0;
      out->wire_size_offset = sizeoff;
      out->wire_length_offset = valueoff;
      out->wire_value_offset = valueoff + 4;
      out->wire_end = end;
    }
  }
  /* Only explicitly typed operations may carry bounded outgoing values. */
  {
    size_t bytes=out->wire_end-out->wire_value_offset-1;
    const unsigned char *wire=b+out->wire_value_offset;
    if(eq(out->input,"AUTH")){
      char key[69];
      if(bytes!=70||(wire[0]!='0'&&wire[0]!='1')||wire[1]!='\t')return 0;
      cp(key,wire+2,68);key[68]=0;
      if(!dd_key_valid(key))return 0;
    }else if(eqn(out->input,"PREVIEW/",8)||eqn(out->input,"DOWNLOAD/",9)){
      size_t j;if(!bytes||bytes>9)return 0;for(j=0;j<bytes;j++)if(wire[j]<'0'||wire[j]>'9')return 0;
    }else if(eqn(out->input,"CATALOG/",8)){
      size_t j;if(bytes>80)return 0;for(j=0;j<bytes;j++)if(wire[j]<32||wire[j]>=127)return 0;
      for(j=0;j+4<=bytes;j++)if(eqn(wire+j,"zcu_",4))return 0;
    }else if(eq(out->input,"PUBLISH")){
      if(bytes<2||bytes>DD_WIRE_MAX)return 0;
      if(wire[0]!='{'){
        size_t j;if(bytes<26||!eqn(wire,"Composition_",12)||!eqn(wire+20,".png\n",5))return 0;
        for(j=12;j<20;j++)if(!hex((char)wire[j]))return 0;
      }
    }else if(bytes!=7||!eqn(wire,"request",7))return 0;
  }
  (void)start;
  return 1;
}
int dd_save_response(const unsigned char *b, size_t n, const dd_save *s,
                     const char *wire, unsigned char *out, size_t cap,
                     size_t *written) {
  size_t len = slen(wire), prefix = s->wire_value_offset, end = s->wire_end,
         total;
  if (prefix > n || end > n || end < prefix || len > DD_WIRE_MAX)
    return 0;
  total = prefix + len + 1 + n - end;
  if (total > cap)
    return 0;
  cp(out, b, prefix);
  cp(out + prefix, wire, len);
  out[prefix + len] = 0;
  cp(out + prefix + len + 1, b + end, n - end);
  set32(out + s->wire_size_offset, (uint32_t)(len + 5));
  set32(out + s->wire_length_offset, (uint32_t)(len + 1));
  *written = total;
  return 1;
}

/* Local review only; the server revalidates the actual uploaded bytes. Every
 * mesh and ordered material override is shown, including unreviewed paths. */
int dd_publish_review(const unsigned char *json,size_t size,char *out,size_t cap) {
 parser p;writer w={out,0,cap,1};int payload,entries,entry,k,m;char path[1024];
 if(!init(&p,json,size)||!unique(&p))return 0;
 payload=member(&p,0,"payload");entries=member(&p,payload,"entries");
 if(entries<0||p.t[entries].kind!='['||p.t[entries].count<1||p.t[entries].count>128)return 0;
 put(&w,"Parts: ");num(&w,p.t[entries].count);put(&w,"\r\nRequirements detected from saved values:\r\n");
 for(entry=entries+1;entry<p.t[entries].next;entry=p.t[entry].next){
  if(!text(&p,member(&p,entry,"Mesh"),path,sizeof(path)))return 0;
  put(&w,eq(path,DD_MESH)?"Reviewed base game mesh: ":"Unreviewed mesh (local availability required): ");put(&w,path);put(&w,"\r\n");
  m=member(&p,entry,"Materials");if(m<0||p.t[m].kind!='['||p.t[m].count>64)return 0;
  for(k=m+1;k<p.t[m].next;k=p.t[k].next){if(!text(&p,k,path,sizeof(path)))return 0;if(path[0]){put(&w,"Unreviewed material: ");put(&w,path);put(&w,"\r\n");}}
 }
 return w.ok;
}

int dd_listing_revision(const unsigned char *json,size_t size) {
 parser p;int item,n;if(!init(&p,json,size))return 0;item=member(&p,0,"item");
 return integer(&p,member(&p,item,"revision"),&n)&&n>0?n:0;
}

/* Only for the fixed local render cache. UE 5.6's PNG export serializes
 * GetAllocatedSize() rather than Num(), appending allocator slack after IEND.
 * Validate the complete encoded stream before dropping that local suffix.
 * Remote images and the service continue to reject every trailing byte. */
static unsigned png_u32(const unsigned char *p){return ((unsigned)p[0]<<24)|((unsigned)p[1]<<16)|((unsigned)p[2]<<8)|p[3];}
static unsigned png_crc(const unsigned char *p,size_t n){unsigned c=0xffffffffu;size_t i;unsigned k;for(i=0;i<n;i++){c^=p[i];for(k=0;k<8;k++)c=(c>>1)^((c&1)?0xedb88320u:0);}return c^0xffffffffu;}
int dd_cached_png(const unsigned char *data,size_t size,size_t *encoded){
 static const unsigned char signature[8]={137,80,78,71,13,10,26,10};
 size_t at=8,n;int idat=0,idat_end=0;unsigned w,h;const unsigned char *type,*body;
 *encoded=0;if(size<57||size>1048576||!eqn(data,signature,8))return 0;
 while(at+12<=size){
  n=png_u32(data+at);if(n>size-at-12)return 0;
  type=data+at+4;body=data+at+8;
  if(png_crc(type,n+4)!=png_u32(body+n))return 0;
  if(at==8){
   if(!eqn(type,"IHDR",4)||n!=13)return 0;
   w=png_u32(body);h=png_u32(body+4);
   if(!w||!h||w>1024||h>1024||w*h>1048576||body[8]!=8||(body[9]!=2&&body[9]!=6)||body[10]||body[11]||body[12])return 0;
  }else if(eqn(type,"IDAT",4)){if(idat_end)return 0;idat=1;}
  else{
   if(idat)idat_end=1;
   if(eqn(type,"IEND",4)){if(n||!idat)return 0;*encoded=at+12;return 1;}
   if(eqn(type,"IHDR",4)||eqn(type,"acTL",4)||eqn(type,"fcTL",4)||eqn(type,"fdAT",4)||!(type[0]&32))return 0;
  }
  at+=n+12;
 }
 return 0;
}

/* Public catalogue transport is values only. Six rows per UI page; the deployed
 * v1 catalogue currently bounds its public feed to the latest 24 listings. */
static int gallery_contains(const char *hay,const char *needle){size_t i,j;for(i=0;hay[i];i++){for(j=0;needle[j]&&hay[i+j];j++){char a=hay[i+j],b=needle[j];if(a>='A'&&a<='Z')a+=32;if(b>='A'&&b<='Z')b+=32;if(a!=b)break;}if(!needle[j])return 1;}return !needle[0];}
static void gallery_text(parser *p,int id,char *out,size_t cap){size_t i,end,k=0;out[0]=0;if(id<0||p->t[id].kind!='s')return;i=p->t[id].start+1;end=p->t[id].end-1;for(;i<end&&k+1<cap;i++){unsigned c=p->s[i];if(c=='\\'&&i+1<end){c=p->s[++i];if(c=='u'&&i+4<end){i+=4;c='?';}else if(c=='n'||c=='r'||c=='t')c=' ';}out[k++]=(char)(c>=32&&c<127?c:'?');}out[k]=0;}
int dd_gallery_select(const unsigned char *json,size_t size,const char *query,int page,char codes[6][33],int *pages,int *total){
 parser p;int items,row,n=0,k=0,revision;char title[121],description[4001],code[33],checked[33];
 if(size>DD_METADATA_MAX||page<0||page>7||slen(query)>80||!init(&p,json,size)||!unique(&p)||!istext(&p,member(&p,0,"api_version"),"v1")||raw(&p,member(&p,0,"fixture"),"true"))return -1;
 items=member(&p,0,"items");if(items<0||p.t[items].kind!='['||p.t[items].count>48)return -1;
 for(row=items+1;row<p.t[items].next;row=p.t[row].next){
  if(!text(&p,member(&p,row,"code"),code,sizeof(code))||!dd_code(code,checked)||!eq(code,checked))return -1;
  if(!integer(&p,member(&p,row,"revision"),&revision)||revision<1)continue;
  gallery_text(&p,member(&p,row,"title"),title,sizeof(title));gallery_text(&p,member(&p,row,"description"),description,sizeof(description));
  if(!gallery_contains(title,query)&&!gallery_contains(description,query)&&!gallery_contains(code,query))continue;
  if(n>=page*6&&k<6){cp(codes[k++],code,slen(code)+1);}
  n++;
 }
 *total=n;*pages=(n+5)/6;return k;
}
int dd_gallery_row(const unsigned char *json,size_t size,const char *expected,char *out,size_t cap){
 parser p;writer w={out,0,cap,1};int item,creator,count=0,revision=0,requirements,unknown,packs,asset;char title[121],description[2001],author[97],code[33],path[1024];
 if(size>DD_METADATA_MAX||!init(&p,json,size)||!unique(&p)||!istext(&p,member(&p,0,"api_version"),"v1"))return 0;
 item=member(&p,0,"item");if(!text(&p,member(&p,item,"code"),code,sizeof(code))||!eq(expected,code))return 0;
 gallery_text(&p,member(&p,item,"title"),title,sizeof(title));gallery_text(&p,member(&p,item,"description"),description,sizeof(description));
 creator=member(&p,item,"creator");gallery_text(&p,member(&p,creator,"display_name"),author,sizeof(author));if(!author[0])gallery_text(&p,member(&p,creator,"id"),author,sizeof(author));if(!author[0])cp(author,"Creator not provided",21);
 integer(&p,member(&p,item,"part_count"),&count);integer(&p,member(&p,item,"revision"),&revision);
 if(count<0||count>128||revision<0)return 0;
 put(&w,"listing\t");put(&w,code);put(&w,"\t");put(&w,title);put(&w,"\t");put(&w,description);put(&w,"\t");put(&w,author);put(&w,"\t");num(&w,count);put(&w,"\t");num(&w,revision);put(&w,"\t");
 requirements=member(&p,item,"requirements");unknown=member(&p,requirements,"unknown_assets");packs=member(&p,requirements,"packs");
 if(requirements<0){put(&w,"Requirements pending validated local preview\n");return w.ok;}
 put(&w,"Declared packs: ");num(&w,packs>=0?p.t[packs].count:0);put(&w,"; unknown dependencies: ");num(&w,unknown>=0?p.t[unknown].count:0);
 {int known=member(&p,requirements,"assets");
 if(known>=0)for(asset=known+1;asset<p.t[known].next&&w.n+1100<cap;asset=p.t[asset].next){gallery_text(&p,member(&p,asset,"path"),path,sizeof(path));put(&w," | Reviewed asset: ");put(&w,path);}
 if(packs>=0)for(asset=packs+1;asset<p.t[packs].next&&w.n+1100<cap;asset=p.t[asset].next){gallery_text(&p,member(&p,asset,"id"),path,sizeof(path));put(&w," | Pack: ");put(&w,path);gallery_text(&p,member(&p,asset,"version"),path,sizeof(path));put(&w," ");put(&w,path);}
 }
 if(unknown>=0)for(asset=unknown+1;asset<p.t[unknown].next&&w.n+1100<cap;asset=p.t[asset].next){gallery_text(&p,member(&p,asset,"path"),path,sizeof(path));put(&w," | UNKNOWN: ");put(&w,path);}
 put(&w,"\n");return w.ok;
}

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
/* A bare code or a HoloNet composition link, with or without https://. The old
 * share. host still appears in links people posted before the move. */
int dd_code(const char *input, char out[33]) {
  static const char *const links[] = {
      "https://" DD_SERVICE_HOST "/comp/", "https://share." DD_SERVICE_HOST "/comp/",
      "https://www." DD_SERVICE_HOST "/comp/", DD_SERVICE_HOST "/comp/",
      "share." DD_SERVICE_HOST "/comp/", "www." DD_SERVICE_HOST "/comp/"};
  const char *p = input;
  size_t n = slen(input), i, k, alnum = 1;
  for (k = 0; k < sizeof(links) / sizeof(links[0]); k++)
    if (n >= slen(links[k]) && eqn(p, links[k], slen(links[k]))) {
      p += slen(links[k]);
      n -= slen(links[k]);
      break;
    }
  if (k == sizeof(links) / sizeof(links[0]))
    for (i = 0; i < n; i++)
      if (!ascii_code(p[i]))
        return 0;
  if (n && p[n - 1] == '/')
    n--;
  if (n < 6 || n > 32)
    return 0;
  for (i = 0; i < n; i++) {
    if (!ascii_code(p[i]))
      return 0;
    if (p[i] == '_' || p[i] == '-')
      alnum = 0;
  }
  /* HoloNet codes are 8 Crockford base32 characters, case-insensitive. Older
   * test codes of other lengths keep their case. */
  for (i = 0; i < n; i++)
    out[i] = (char)(n == 8 && alnum && p[i] >= 'a' && p[i] <= 'z' ? p[i] - 32 : p[i]);
  out[n] = 0;
  return 1;
}
/* One well-formed UTF-8 sequence: its length, or 0 (overlong, surrogate,
 * truncated or out of range). */
static size_t utf8(const unsigned char *s, size_t n, unsigned *u) {
  unsigned c = s[0], v;
  size_t k, i;
  if (c < 128) {
    *u = c;
    return 1;
  }
  if (c >= 0xc2 && c <= 0xdf) {
    k = 2;
    v = c & 31;
  } else if (c >= 0xe0 && c <= 0xef) {
    k = 3;
    v = c & 15;
  } else if (c >= 0xf0 && c <= 0xf4) {
    k = 4;
    v = c & 7;
  } else
    return 0;
  if (n < k)
    return 0;
  for (i = 1; i < k; i++) {
    if ((s[i] & 0xc0) != 0x80)
      return 0;
    v = (v << 6) | (s[i] & 63);
  }
  if ((k == 3 && v < 0x800) || (k == 4 && (v < 0x10000 || v > 0x10ffff)) ||
      (v >= 0xd800 && v <= 0xdfff))
    return 0;
  *u = v;
  return k;
}
static size_t encode(unsigned u, char *b) {
  if (u < 0x80) {
    b[0] = (char)u;
    return 1;
  }
  if (u < 0x800) {
    b[0] = (char)(0xc0 | (u >> 6));
    b[1] = (char)(0x80 | (u & 63));
    return 2;
  }
  if (u < 0x10000) {
    b[0] = (char)(0xe0 | (u >> 12));
    b[1] = (char)(0x80 | ((u >> 6) & 63));
    b[2] = (char)(0x80 | (u & 63));
    return 3;
  }
  b[0] = (char)(0xf0 | (u >> 18));
  b[1] = (char)(0x80 | ((u >> 12) & 63));
  b[2] = (char)(0x80 | ((u >> 6) & 63));
  b[3] = (char)(0x80 | (u & 63));
  return 4;
}
static int hex4(const unsigned char *s, unsigned *u) {
  int i;
  *u = 0;
  for (i = 0; i < 4; i++) {
    unsigned c = s[i];
    *u <<= 4;
    if (c >= '0' && c <= '9')
      *u |= c - '0';
    else if (c >= 'a' && c <= 'f')
      *u |= c - 'a' + 10;
    else if (c >= 'A' && c <= 'F')
      *u |= c - 'A' + 10;
    else
      return 0;
  }
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
/* JSON strings: escape syntax checked, raw bytes must be well-formed UTF-8.
 * The canonical payload keeps to the stricter unescaped ASCII subset (text);
 * metadata is decoded with jstr. */
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
    if (c < 32)
      return -1;
    if (c >= 128) {
      unsigned u;
      size_t k = utf8(p->s + p->p - 1, p->n - p->p + 1, &u);
      if (!k)
        return -1;
      p->p += k - 1;
      continue;
    }
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
/* Decode any JSON string to UTF-8: escapes, surrogate pairs and raw UTF-8.
 * Returns its length in characters, or -1 if it is not a string, contains NUL
 * or an unpaired surrogate, or does not fit. Control characters are kept;
 * put_text decides how they reach the wire. */
static long jstr(parser *p, int id, char *out, size_t cap) {
  size_t i, end, used = 0, k, m;
  long chars = 0;
  char b[4];
  if (id < 0 || p->t[id].kind != 's' || !cap)
    return -1;
  i = p->t[id].start + 1;
  end = p->t[id].end - 1;
  while (i < end) {
    unsigned u = p->s[i];
    k = 1;
    if (u == '\\') {
      unsigned e = p->s[i + 1];
      k = 2;
      if (e == 'u') {
        if (!hex4(p->s + i + 2, &u) || (u >= 0xdc00 && u <= 0xdfff))
          return -1;
        k = 6;
        if (u >= 0xd800 && u <= 0xdbff) {
          unsigned low;
          if (i + 12 > end || p->s[i + 6] != '\\' || p->s[i + 7] != 'u' ||
              !hex4(p->s + i + 8, &low) || low < 0xdc00 || low > 0xdfff)
            return -1;
          u = 0x10000 + ((u - 0xd800) << 10) + (low - 0xdc00);
          k = 12;
        }
      } else
        u = e == 'b' ? 8 : e == 'f' ? 12 : e == 'n' ? 10 : e == 'r' ? 13 : e == 't' ? 9 : e;
    } else if (u >= 128 && !(k = utf8(p->s + i, end - i, &u)))
      return -1;
    if (!u)
      return -1;
    m = encode(u, b);
    if (used + m >= cap)
      return -1;
    cp(out + used, b, m);
    used += m;
    chars++;
    i += k;
  }
  out[used] = 0;
  return chars;
}
static int blank(const char *s) {
  for (; *s; s++)
    if (*s != ' ' && *s != '\t' && *s != '\n' && *s != '\r')
      return 0;
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

int dd_listing(const unsigned char *json, size_t size, const char *code,
               size_t *bytes, char digest[65], const char **error) {
  parser p;
  int item, v, n;
  char expected[65];
  *error = "HoloNet sent a listing this Den Designer could not read.";
  if (size > DD_METADATA_MAX || !init(&p, json, size) || !unique(&p))
    return 0;
  if (!istext(&p, member(&p, 0, "api_version"), "v1")) {
    *error = "HoloNet answered in a format this Den Designer doesn't know. Update Den Designer.";
    return 0;
  }
  item = member(&p, 0, "item");
  if (item < 0 || p.t[item].kind != '{' ||
      !istext(&p, member(&p, item, "code"), code) ||
      !istext(&p, member(&p, item, "kind"), "comp"))
    return 0;
  if (!integer(&p, member(&p, item, "schema_version"), &n) || n < 1)
    return 0;
  if (n > 1) {
    *error = "This build needs a newer Den Designer. Update Den Designer, then import it again.";
    return 0;
  }
  v = member(&p, item, "document_bytes");
  if (!integer(&p, v, &n) || n <= 0 || (size_t)n > DD_DOCUMENT_MAX) {
    *error = "This listing has no build file to download.";
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
/* Free text inside a tab- and line-framed wire field, cut at max characters.
 * Tabs and other control characters become spaces. With escape, a line break
 * is written as \n and a backslash as \\ so the game can restore paragraphs;
 * without it, line breaks become spaces too. */
static void put_text(writer *w, const char *s, long max, int escape) {
  size_t i = 0, n = slen(s), k;
  long chars = 0;
  while (i < n && chars < max) {
    unsigned char c = (unsigned char)s[i];
    char b[5] = {0};
    unsigned u;
    k = 1;
    if (c >= 128) {
      if (!(k = utf8((const unsigned char *)s + i, n - i, &u))) {
        w->ok = 0;
        return;
      }
      cp(b, s + i, k);
    } else if (escape && c == '\r') {
      i++;
      continue;
    } else if (escape && (c == '\\' || c == '\n')) {
      b[0] = '\\';
      b[1] = c == '\n' ? 'n' : '\\';
    } else
      b[0] = (char)(c < 32 || c == 127 ? ' ' : c);
    put(w, b);
    i += k;
    chars++;
  }
}
/* Percent-encode UTF-8 for a URL query value. */
static void put_query(writer *w, const char *s) {
  const char *digits = "0123456789ABCDEF";
  for (; *s; s++) {
    unsigned char c = (unsigned char)*s;
    char b[4] = {(char)c, 0, 0, 0};
    if (!((c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || (c >= '0' && c <= '9') ||
          c == '-' || c == '.' || c == '_' || c == '~')) {
      b[0] = '%';
      b[1] = digits[c >> 4];
      b[2] = digits[c & 15];
    }
    put(w, b);
  }
}
/* Decimal tokens are copied as written; they were validated by decimal(). */
static void put_numbers(writer *w, parser *p, int vector) {
  int a;
  for (a = vector + 1; a < p->t[vector].next; a = p->t[a].next) {
    char number[65];
    size_t len = p->t[a].end - p->t[a].start;
    cp(number, p->s + p->t[a].start, len);
    number[len] = 0;
    put(w, "\t");
    put(w, number);
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
static int mount_ok(const char *s) {
  size_t i, n = slen(s);
  if (!n || n > 64)
    return 0;
  for (i = 0; i < n; i++)
    if (!ascii_code(s[i]))
      return 0;
  return 1;
}
/* Where a mesh or material may come from: the base game, a declared prop
 * pack's mount, or the build's own unknown_assets list. The game still checks
 * that each asset exists locally before placing anything. */
static int asset_allowed(parser *p, int packs, int unknown, const char *path,
                         const char *kind) {
  int i;
  char buffer[1024];
  size_t n;
  if (!asset_path(path))
    return 0;
  if (eqn(path, "/Game/", 6))
    return 1;
  for (i = packs + 1; i < p->t[packs].next; i = p->t[i].next)
    if (text(p, member(p, i, "mount"), buffer, 66) && (n = slen(buffer)) &&
        eqn(path + 1, buffer, n) && path[n + 1] == '/')
      return 1;
  for (i = unknown + 1; i < p->t[unknown].next; i = p->t[i].next)
    if (text(p, member(p, i, "path"), buffer, sizeof(buffer)) && eq(buffer, path) &&
        istext(p, member(p, i, "kind"), kind))
      return 1;
  return 0;
}
static int is_string(parser *p, int id) { return id >= 0 && p->t[id].kind == 's'; }
/* HoloNet build file, schema 1 (format zcom-share). Outside the payload,
 * fields this version doesn't use are ignored so the server can add metadata
 * without breaking imports. The payload is the game's own format: exact keys,
 * canonical bytes, and its SHA-256 must match. */
int dd_document(const unsigned char *json, size_t size, const char *code,
                const char *token, dd_hash_fn hash, char *wire, size_t capacity,
                const char **error) {
  parser p;
  int c, m, deps, packs, unknown, payload, entries, anchor, d, k, n, entry,
      collision, i;
  long chars;
  char digest[65], expected[65], title[481], key[97], oldkeys[128][97],
      mesh[1024], buffer[1024];
  writer w = {wire, 0, capacity, 1};
  const char *payloadkeys[] = {"anchor", "entries"};
  const char *anchorkeys[] = {"position", "convention"};
  const char *entrykeys[] = {"Kind",          "Key",            "Mesh",
                             "Position",      "Rotation",       "Scale",
                             "HasPosition",   "HasRotation",    "HasScale",
                             "Hidden",        "CollisionMode",  "Materials",
                             "HasFingerprint", "FingerprintMesh", "FingerprintPosition"};
  *error = "This build's file is damaged or isn't a Den Designer composition.";
  if (size > DD_DOCUMENT_MAX || !init(&p, json, size) || !unique(&p) ||
      p.t[0].kind != '{' || !istext(&p, member(&p, 0, "format"), "zcom-share") ||
      !istext(&p, member(&p, 0, "content_type"), "composition") ||
      !integer(&p, member(&p, 0, "schema_version"), &n) || n < 1)
    return 0;
  if (n > 1) {
    *error = "This build needs a newer Den Designer. Update Den Designer, then import it again.";
    return 0;
  }
  c = member(&p, 0, "compatibility");
  if (c < 0 || p.t[c].kind != '{' ||
      !istext(&p, member(&p, c, "game_id"), "steam:2075800") ||
      !istext(&p, member(&p, c, "mod_id"), "community.den-designer") ||
      !is_string(&p, member(&p, c, "game_version")) ||
      !is_string(&p, member(&p, c, "mod_version"))) {
    *error = "This build was made for a different game or mod.";
    return 0;
  }
  m = member(&p, 0, "metadata");
  if (m < 0 || p.t[m].kind != '{')
    return 0;
  chars = jstr(&p, member(&p, m, "title"), title, sizeof(title));
  if (chars < 1 || chars > 120 || blank(title))
    return 0;
  {
    char description[16004];
    int author = member(&p, m, "author"), footprint = member(&p, m, "footprint_cm");
    chars = jstr(&p, member(&p, m, "description"), description, sizeof(description));
    if (chars < 0 || chars > 4000 || author < 0 || p.t[author].kind != '{' ||
        !is_string(&p, member(&p, author, "id")))
      return 0;
    if (footprint >= 0 && !raw(&p, footprint, "null") &&
        !decimal_vector(&p, footprint, 0))
      return 0;
  }
  deps = member(&p, 0, "dependencies");
  packs = member(&p, deps, "packs");
  unknown = member(&p, deps, "unknown_assets");
  if (deps < 0 || p.t[deps].kind != '{' || packs < 0 || p.t[packs].kind != '[' ||
      p.t[packs].count > 32 || unknown < 0 || p.t[unknown].kind != '[' ||
      p.t[unknown].count > 256) {
    *error = "This build's list of prop packs and mods is damaged.";
    return 0;
  }
  for (i = packs + 1; i < p.t[packs].next; i = p.t[i].next)
    if (!text(&p, member(&p, i, "mount"), buffer, 66) || !mount_ok(buffer) ||
        jstr(&p, member(&p, i, "title"), buffer, sizeof(buffer)) < 1 ||
        jstr(&p, member(&p, i, "version"), buffer, sizeof(buffer)) < 0 ||
        jstr(&p, member(&p, i, "id"), buffer, sizeof(buffer)) < 1) {
      *error = "This build's list of prop packs and mods is damaged.";
      return 0;
    }
  for (i = unknown + 1; i < p.t[unknown].next; i = p.t[i].next)
    if (!text(&p, member(&p, i, "path"), buffer, sizeof(buffer)) ||
        !asset_path(buffer) ||
        (!istext(&p, member(&p, i, "kind"), "mesh") &&
         !istext(&p, member(&p, i, "kind"), "material"))) {
      *error = "This build's list of prop packs and mods is damaged.";
      return 0;
    }
  payload = member(&p, 0, "payload");
  if (!object(&p, payload, payloadkeys, 2) || !canonical_payload(&p, payload))
    return 0;
  d = member(&p, 0, "integrity");
  if (d < 0 || p.t[d].kind != '{' ||
      !istext(&p, member(&p, d, "algorithm"), "sha256") ||
      !text(&p, member(&p, d, "payload_sha256"), expected, sizeof(expected)) ||
      slen(expected) != 64 ||
      !hash(json + p.t[payload].start, p.t[payload].end - p.t[payload].start,
            digest) ||
      !eq(expected, digest)) {
    *error = "This build's file failed its integrity check. Try importing it again.";
    return 0;
  }
  anchor = member(&p, payload, "anchor");
  if (!object(&p, anchor, anchorkeys, 2) ||
      !istext(&p, member(&p, anchor, "convention"), "bounds-bottom-center") ||
      !decimal_vector(&p, member(&p, anchor, "position"), 0))
    return 0;
  entries = member(&p, payload, "entries");
  if (entries < 0 || p.t[entries].kind != '[' || p.t[entries].count < 1 ||
      p.t[entries].count > 128) {
    *error = "A composition has 1 to 128 parts.";
    return 0;
  }
  put(&w, "ZCOM-COMMUNITY\t1\t");
  put(&w, token);
  put(&w, "\nok\nname\t");
  put_text(&w, title, 27, 0);
  put(&w, " ");
  n = (int)slen(code);
  put(&w, code + (n > 12 ? n - 12 : 0));
  put(&w, "\nreport\t");
  if (!p.t[packs].count && !p.t[unknown].count)
    put(&w, "Base game only.");
  if (p.t[packs].count) {
    put(&w, "Uses prop packs: ");
    for (i = packs + 1; i < p.t[packs].next; i = p.t[i].next) {
      if (i != packs + 1)
        put(&w, ", ");
      jstr(&p, member(&p, i, "title"), buffer, sizeof(buffer));
      put_text(&w, buffer, 60, 0);
      if (jstr(&p, member(&p, i, "version"), buffer, sizeof(buffer)) > 0) {
        put(&w, " ");
        put_text(&w, buffer, 20, 0);
      }
    }
    put(&w, ".");
  }
  if (p.t[unknown].count) {
    put(&w, p.t[packs].count ? " Also uses " : "Uses ");
    num(&w, p.t[unknown].count);
    put(&w, p.t[unknown].count == 1 ? " asset from a mod HoloNet doesn't list."
                                    : " assets from mods HoloNet doesn't list.");
  }
  put(&w, "\nanchor");
  put_numbers(&w, &p, member(&p, anchor, "position"));
  put(&w, "\ncount\t");
  num(&w, p.t[entries].count);
  n = 0;
  for (entry = entries + 1; entry < p.t[entries].next; entry = p.t[entry].next) {
    int z[3], materials;
    const char *fields[] = {"Position", "Rotation", "Scale"};
    if (!object(&p, entry, entrykeys, 15) ||
        !integer(&p, member(&p, entry, "Kind"), &k) || k != 0 ||
        !text(&p, member(&p, entry, "Key"), key, sizeof(key)) || !key[0] ||
        !text(&p, member(&p, entry, "Mesh"), mesh, sizeof(mesh)) ||
        !asset_allowed(&p, packs, unknown, mesh, "mesh")) {
      *error = "This build has a part from a source it doesn't declare.";
      return 0;
    }
    for (k = 0; key[k]; k++)
      if (!ascii_code(key[k]))
        return 0;
    for (k = 0; k < n; k++)
      if (eq(oldkeys[k], key)) {
        *error = "This build lists the same part twice.";
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
    materials = member(&p, entry, "Materials");
    if (materials < 0 || p.t[materials].kind != '[' || p.t[materials].count > 64 ||
        !integer(&p, member(&p, entry, "CollisionMode"), &collision) ||
        collision < 0 || collision > 2)
      return 0;
    put(&w, "\npart\t");
    put(&w, mesh);
    for (k = 0; k < 3; k++) {
      int v = member(&p, entry, fields[k]);
      if (!decimal_vector(&p, v, k == 2))
        return 0;
      put_numbers(&w, &p, v);
    }
    put(&w, "\t");
    num(&w, collision);
    for (k = materials + 1; k < p.t[materials].next; k = p.t[k].next) {
      if (!text(&p, k, buffer, sizeof(buffer)) ||
          (buffer[0] && !asset_allowed(&p, packs, unknown, buffer, "material"))) {
        *error = "This build has a material from a source it doesn't declare.";
        return 0;
      }
      put(&w, "\nmaterial\t");
      put(&w, buffer);
    }
  }
  put(&w, "\nend");
  if (!w.ok) {
    *error = "This build is too large for the game's import message.";
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
/* The PUBLISH thumbnail line: Composition_<8 hex>.png is the library card
 * render, Composition_<8 hex>_512.png the larger share render. Returns the
 * name's length when it is followed by a line break, else 0. */
size_t dd_thumbnail_name(const unsigned char *w, size_t n) {
  size_t j;
  if (n < 21 || !eqn(w, "Composition_", 12))
    return 0;
  for (j = 12; j < 20; j++)
    if (!hex((char)w[j]))
      return 0;
  if (n >= 25 && eqn(w + 20, ".png\n", 5))
    return 24;
  if (n >= 29 && eqn(w + 20, "_512.png\n", 9))
    return 28;
  return 0;
}
/* UTF-16LE units to UTF-8, as far as whole characters fit (already
 * validated by dd_save_read). Returns the bytes written, without NUL. */
static size_t wide_prefix(const unsigned char *w, size_t units, unsigned char *out,
                          size_t cap) {
  size_t i, used = 0, m;
  char b[4];
  for (i = 0; i < units; i++) {
    unsigned u = w[2 * i] | (unsigned)w[2 * i + 1] << 8;
    if (u >= 0xd800 && u <= 0xdbff && i + 1 < units)
      u = 0x10000 + ((u - 0xd800) << 10) + ((w[2 * i + 2] | (unsigned)w[2 * i + 3] << 8) - 0xdc00), i++;
    m = encode(u, b);
    if (used + m > cap)
      break;
    cp(out + used, b, m);
    used += m;
  }
  return used;
}
int dd_save_wire(const unsigned char *b, size_t n, const dd_save *s, char *out,
                 size_t cap, size_t *written) {
  size_t start = s->wire_value_offset, end = s->wire_end, len;
  if (start > n || end > n || end <= start || !cap)
    return 0;
  if (!s->wire_wide) {
    len = end - start - 1;
    if (len + 1 > cap)
      return 0;
    cp(out, b + start, len);
  } else {
    size_t units = (end - start) / 2 - 1, i, need = 0;
    /* Every character must fit; a partial decode is never a valid value. */
    for (i = 0; i < units; i++) {
      unsigned u = b[start + 2 * i] | (unsigned)b[start + 2 * i + 1] << 8;
      need += u < 0x80 ? 1 : u < 0x800 ? 2 : (u >= 0xd800 && u <= 0xdbff) ? (i++, 4) : 3;
    }
    if (need + 1 > cap)
      return 0;
    len = wide_prefix(b + start, units, (unsigned char *)out, cap - 1);
  }
  out[len] = 0;
  *written = len;
  return 1;
}
/* Mailbox page numbers: 0-based, 1 to 4 digits. */
static int page_number(const char *s) {
  size_t i, n = slen(s);
  if (!n || n > 4 || (s[0] == '0' && n > 1))
    return 0;
  for (i = 0; i < n; i++)
    if (s[i] < '0' || s[i] > '9')
      return 0;
  return 1;
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
    /* UE writes an FString as ANSI when every character fits, otherwise as
     * UTF-16 with a negative length. Token and Input are always ASCII; Wire
     * may be UTF-16 (player-typed titles and descriptions). */
    if (which == 2 && n - p >= 4 && (int32_t)u32(b + p) < 0) {
      int32_t units = (int32_t)u32(b + p);
      size_t chars;
      if (units == INT32_MIN)
        return 0;
      chars = (size_t)-units;
      p += 4;
      if (chars < 1 || chars > (n - p) / 2 || b[p + 2 * chars - 2] ||
          b[p + 2 * chars - 1])
        return 0;
      for (i = 0; i + 1 < chars; i++) {
        unsigned u = b[p + 2 * i] | (unsigned)b[p + 2 * i + 1] << 8;
        if ((u < 32 && u != '\n' && u != '\t') || u == 127 ||
            (u >= 0xdc00 && u <= 0xdfff))
          return 0;
        if (u >= 0xd800 && u <= 0xdbff) {
          unsigned low;
          if (i + 2 >= chars)
            return 0;
          low = b[p + 2 * i + 2] | (unsigned)b[p + 2 * i + 3] << 8;
          if (low < 0xdc00 || low > 0xdfff)
            return 0;
          i++;
        }
      }
      p += 2 * chars;
      if (p - valueoff != payloadsize || chars - 1 > DD_WIRE_MAX)
        return 0;
      out->wire_size_offset = sizeoff;
      out->wire_length_offset = valueoff;
      out->wire_value_offset = valueoff + 4;
      out->wire_end = p;
      out->wire_wide = 1;
      continue;
    }
    if (!fstr(b, n, &p, &s, &len) || p - valueoff != payloadsize)
      return 0;
    end = p;
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
      out->wire_wide = 0;
    }
  }
  /* Only explicitly typed operations may carry bounded outgoing values. Only
   * search text and PUBLISH carry free text, so only they may arrive as
   * UTF-16. A PUBLISH check reads just its first (ASCII) line. */
  {
    size_t bytes=out->wire_end-out->wire_value_offset-1;
    const unsigned char *wire=b+out->wire_value_offset;
    unsigned char head[512];
    if(out->wire_wide){
      size_t units=(out->wire_end-out->wire_value_offset)/2-1;
      if(!eq(out->input,"PUBLISH")&&(!eqn(out->input,"CATALOG/",8)||units>120))return 0;
      bytes=wide_prefix(wire,units,head,sizeof(head));
      if(eq(out->input,"PUBLISH")&&units>bytes)bytes=units; /* length check only */
      wire=head;
    }
    if(eq(out->input,"AUTH")){
      char key[69];
      if(bytes!=70||(wire[0]!='0'&&wire[0]!='1')||wire[1]!='\t')return 0;
      cp(key,wire+2,68);key[68]=0;
      if(!dd_key_valid(key))return 0;
    }else if(eqn(out->input,"PREVIEW/",8)||eqn(out->input,"DOWNLOAD/",9)){
      size_t j;if(!bytes||bytes>9)return 0;for(j=0;j<bytes;j++)if(wire[j]<'0'||wire[j]>'9')return 0;
    }else if(eqn(out->input,"CATALOG/",8)){
      char path[512];int legacy;
      if(!page_number(out->input+8)||!dd_catalog_request((const char *)wire,bytes,&legacy,path,sizeof(path),0))return 0;
    }else if(eq(out->input,"PUBLISH")){
      if(bytes<2||bytes>DD_WIRE_MAX)return 0;
      if(wire[0]!='{'&&(bytes<26||!dd_thumbnail_name(wire,bytes<64?bytes:64)))return 0;
    }else if(eqn(out->input,"MYSHARES/",9)){
      if(!page_number(out->input+9)||bytes!=7||!eqn(wire,"request",7))return 0;
    }else if(bytes!=7||!eqn(wire,"request",7))return 0;
  }
  (void)start;
  return 1;
}
/* Writes wire (UTF-8) into the response copy of the request SaveGame: as an
 * ANSI FString when it is ASCII, otherwise as UTF-16 with a negative length,
 * exactly as UE would have saved it. */
int dd_save_response(const unsigned char *b, size_t n, const dd_save *s,
                     const char *wire, unsigned char *out, size_t cap,
                     size_t *written) {
  size_t len = slen(wire), prefix = s->wire_value_offset, end = s->wire_end,
         total, units = 0, body, i, k, at;
  int wide = 0;
  unsigned u;
  if (prefix > n || end > n || end < prefix)
    return 0;
  for (i = 0; i < len; i += k) {
    if (!(k = utf8((const unsigned char *)wire + i, len - i, &u)))
      return 0;
    wide |= u >= 128;
    units += u >= 0x10000 ? 2 : 1;
  }
  if (units > DD_WIRE_MAX)
    return 0;
  body = wide ? 2 * (units + 1) : len + 1;
  total = prefix + body + n - end;
  if (total > cap)
    return 0;
  cp(out, b, prefix);
  at = prefix;
  if (!wide) {
    cp(out + at, wire, len);
    at += len;
    out[at++] = 0;
  } else {
    for (i = 0; i < len; i += k) {
      k = utf8((const unsigned char *)wire + i, len - i, &u);
      if (u >= 0x10000) {
        unsigned high = 0xd800 + ((u - 0x10000) >> 10);
        out[at++] = (unsigned char)high;
        out[at++] = (unsigned char)(high >> 8);
        u = 0xdc00 + ((u - 0x10000) & 0x3ff);
      }
      out[at++] = (unsigned char)u;
      out[at++] = (unsigned char)(u >> 8);
    }
    out[at++] = 0;
    out[at++] = 0;
  }
  cp(out + at, b + end, n - end);
  set32(out + s->wire_size_offset, (uint32_t)(body + 4));
  set32(out + s->wire_length_offset,
        wide ? (uint32_t)(-(int32_t)(units + 1)) : (uint32_t)(len + 1));
  *written = total;
  return 1;
}

/* Local review only; the server revalidates the actual uploaded bytes. Every
 * mesh and ordered material override is shown. */
int dd_publish_review(const unsigned char *json,size_t size,char *out,size_t cap) {
 parser p;writer w={out,0,cap,1};int payload,entries,entry,k,m;char path[1024];
 if(!init(&p,json,size)||!unique(&p))return 0;
 payload=member(&p,0,"payload");entries=member(&p,payload,"entries");
 if(entries<0||p.t[entries].kind!='['||p.t[entries].count<1||p.t[entries].count>128)return 0;
 put(&w,"Parts: ");num(&w,p.t[entries].count);put(&w,"\r\nRequirements detected from saved values:\r\n");
 for(entry=entries+1;entry<p.t[entries].next;entry=p.t[entry].next){
  if(!text(&p,member(&p,entry,"Mesh"),path,sizeof(path)))return 0;
  put(&w,eqn(path,"/Game/",6)?"Base game mesh: ":"Mesh from a prop pack or mod: ");put(&w,path);put(&w,"\r\n");
  m=member(&p,entry,"Materials");if(m<0||p.t[m].kind!='['||p.t[m].count>64)return 0;
  for(k=m+1;k<p.t[m].next;k=p.t[k].next){if(!text(&p,k,path,sizeof(path)))return 0;if(path[0]){put(&w,eqn(path,"/Game/",6)?"Base game material: ":"Material from a prop pack or mod: ");put(&w,path);put(&w,"\r\n");}}
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

/* CATALOG/<page> wire: the preview.22 panel sends only its search text
 * (newest first, six per page); HoloNet sends "<newest|imports>\t<all|base>\t
 * <search>". Search is up to 80 characters without control characters. Builds
 * the API path for 0-based page into path. */
int dd_catalog_request(const char *wire,size_t size,int *legacy,char *path,size_t cap,int page){
 writer w={path,0,cap,1};size_t i,start=0,end=size,k;char query[512];const char *sort="newest";int base=0,chars=0;unsigned u;
 if(size>480||page<0||page>9999||!cap)return 0;
 for(i=0;i<size&&wire[i]!='\t';i++);
 *legacy=i==size;
 if(!*legacy){
  size_t j;
  for(j=i+1;j<size&&wire[j]!='\t';j++);
  if(j>=size)return 0;
  if(i==6&&eqn(wire,"newest",6))sort="newest";else if(i==7&&eqn(wire,"imports",7))sort="imports";else return 0;
  if(j-i-1==4&&eqn(wire+i+1,"base",4))base=1;else if(!(j-i-1==3&&eqn(wire+i+1,"all",3)))return 0;
  start=j+1;
 }
 while(start<end&&wire[start]==' ')start++;
 while(end>start&&wire[end-1]==' ')end--;
 for(i=start;i<end;i+=k){
  if(!(k=utf8((const unsigned char *)wire+i,end-i,&u))||u<32||u==127||++chars>80)return 0;
  if(i+4<=end&&eqn(wire+i,"zcu_",4))return 0;
 }
 cp(query,wire+start,end-start);query[end-start]=0;
 put(&w,"/api/v1/compositions?page=");num(&w,page+1);put(&w,"&per_page=");num(&w,*legacy?6:8);
 put(&w,"&sort=");put(&w,sort);if(base)put(&w,"&base_game=1");
 if(query[0]){put(&w,"&q=");put_query(&w,query);}
 return w.ok;
}
static int number_or(parser *p,int id,int fallback){int n;return integer(p,id,&n)&&n>=0?n:fallback;}
static void put_date(writer *w,parser *p,int item){
 char date[41];size_t i;int id=member(p,item,"updated_at");
 if(id<0)id=member(p,item,"published_at");
 if(!text(p,id,date,sizeof(date)))return;
 for(i=0;date[i];i++)if(!((date[i]>='0'&&date[i]<='9')||date[i]=='-'||date[i]==':'||date[i]=='.'||date[i]=='T'||date[i]=='Z'||date[i]=='+'))return;
 put(w,date);
}
/* footprint_cm [x,y,z] as metres to one decimal, "2.4 × 0.8 × 2.1 m". */
static void put_footprint(writer *w,parser *p,int vector){
 int a,k=0,cm[3];char digit[2]={0,0};
 if(vector<0||p->t[vector].kind!='['||p->t[vector].count!=3)return;
 for(a=vector+1;a<p->t[vector].next;a=p->t[a].next){
  size_t i=p->t[a].start,end=p->t[a].end;long whole=0;int tenth=-1;
  if(!decimal(p,a,0)||p->s[i]=='-')return;
  for(;i<end&&p->s[i]>='0'&&p->s[i]<='9';i++)if((whole=whole*10+p->s[i]-'0')>1000000)return;
  if(i<end&&p->s[i]=='.'&&i+1<end&&p->s[i+1]>='0'&&p->s[i+1]<='9')tenth=p->s[i+1]-'0';
  if(i<end&&p->s[i]!='.')return; /* no exponents in a footprint */
  cm[k++]=(int)whole+(tenth>=5);
 }
 for(k=0;k<3;k++){
  int tenths=(cm[k]+5)/10;
  if(k)put(w," \xc3\x97 ");
  num(w,tenths/10);put(w,".");digit[0]=(char)('0'+tenths%10);put(w,digit);
 }
 put(w," m");
}
/* A pack's Nexus link is used only if it's an HTTPS Nexus Mods page for this
 * game; otherwise (or with none) link to a Nexus search for the pack title.
 * The server applies the same rule; this keeps the game safe regardless. */
static void put_nexus(writer *w,parser *p,int pack,const char *title){
 static const char *const prefixes[]={"https://www.nexusmods.com/games/starwarszerocompany/","https://www.nexusmods.com/starwarszerocompany/"};
 char url[301];size_t i,k;int ok=0;
 if(text(p,member(p,pack,"url"),url,sizeof(url)))
  for(k=0;k<2&&!ok;k++)if(slen(url)>slen(prefixes[k])&&eqn(url,prefixes[k],slen(prefixes[k]))){
   ok=1;for(i=slen(prefixes[k]);url[i];i++){char c=url[i];if(!((c>='A'&&c<='Z')||(c>='a'&&c<='z')||(c>='0'&&c<='9')||c=='-'||c=='.'||c=='_'||c=='~'||c=='/'||c=='?'||c=='='||c=='&'||c=='%'||c=='+'||c=='#'))ok=0;}
  }
 if(ok){put(w,url);return;}
 put(w,"https://www.nexusmods.com/games/starwarszerocompany/mods?title=");put_query(w,title);
}
/* One listing as wire rows. Rows without a valid code or revision are left
 * out rather than failing the page. HoloNet rows:
 *   card\tcode\ttitle\tcreator\tparts\trevision\timports\tbase_game_only\t
 *     unknown_assets\tupdated\tfootprint\tdescription (escaped, first 1000
 *     characters). footprint is display text in metres ("2.4 × 0.8 × 2.1 m"),
 *     empty when the build has none.
 *   pack\tcode\tid\ttitle\tversion\tparts\tnexus_url   (one per prop pack)
 * The preview.22 panel's row stays: listing\tcode\ttitle\tdescription\t
 * creator\tparts\trevision\trequirements. */
static void listing_rows(parser *p,int item,writer *w,int legacy){
 char code[33],checked[33],title[481],creator[385],buffer[16004],id[129];int revision,requirements,packs,unknown,pack,creatorobj;
 if(!text(p,member(p,item,"code"),code,sizeof(code))||!dd_code(code,checked)||!eq(code,checked)||!integer(p,member(p,item,"revision"),&revision)||revision<1)return;
 if(jstr(p,member(p,item,"title"),title,sizeof(title))<1)cp(title,"Untitled",9);
 creatorobj=member(p,item,"creator");
 if(jstr(p,member(p,creatorobj,"display_name"),creator,sizeof(creator))<1||blank(creator))cp(creator,"Unknown creator",16);
 requirements=member(p,item,"requirements");packs=member(p,requirements,"packs");unknown=member(p,requirements,"unknown_assets");
 if(packs>=0&&(p->t[packs].kind!='['||p->t[packs].count>32))packs=-1;
 if(unknown>=0&&p->t[unknown].kind!='[')unknown=-1;
 if(jstr(p,member(p,item,"description"),buffer,sizeof(buffer))<0)buffer[0]=0;
 if(legacy){
  put(w,"listing\t");put(w,code);put(w,"\t");put_text(w,title,120,0);put(w,"\t");put_text(w,buffer,2000,0);put(w,"\t");put_text(w,creator,64,0);
  put(w,"\t");num(w,number_or(p,member(p,item,"part_count"),0));put(w,"\t");num(w,revision);put(w,"\t");
  if((packs<0||!p->t[packs].count)&&(unknown<0||!p->t[unknown].count))put(w,"Base game only");
  if(packs>=0)for(pack=packs+1;pack<p->t[packs].next;pack=p->t[pack].next){
   put(w,pack!=packs+1?" | Pack: ":"Pack: ");if(jstr(p,member(p,pack,"title"),buffer,sizeof(buffer))>0)put_text(w,buffer,60,0);
   if(jstr(p,member(p,pack,"version"),buffer,sizeof(buffer))>0){put(w," ");put_text(w,buffer,20,0);}
  }
  if(unknown>=0)for(pack=unknown+1;pack<p->t[unknown].next&&w->n+1100<w->cap;pack=p->t[pack].next)if(text(p,member(p,pack,"path"),buffer,1024)){put(w," | UNKNOWN: ");put(w,buffer);}
  put(w,"\n");return;
 }
 put(w,"card\t");put(w,code);put(w,"\t");put_text(w,title,120,0);put(w,"\t");put_text(w,creator,64,0);
 put(w,"\t");num(w,number_or(p,member(p,item,"part_count"),0));put(w,"\t");num(w,revision);
 put(w,"\t");num(w,number_or(p,member(p,item,"import_count"),0));
 put(w,raw(p,member(p,item,"base_game_only"),"true")?"\t1\t":"\t0\t");num(w,unknown>=0?p->t[unknown].count:0);
 put(w,"\t");put_date(w,p,item);put(w,"\t");put_footprint(w,p,member(p,item,"footprint_cm"));put(w,"\t");put_text(w,buffer,1000,1);put(w,"\n");
 if(packs>=0)for(pack=packs+1;pack<p->t[packs].next;pack=p->t[pack].next){
  if(!text(p,member(p,pack,"id"),id,sizeof(id)))id[0]=0;
  if(jstr(p,member(p,pack,"title"),title,sizeof(title))<1)cp(title,id,slen(id)+1);
  put(w,"pack\t");put(w,code);put(w,"\t");put_text(w,id,64,0);put(w,"\t");put_text(w,title,120,0);put(w,"\t");
  if(jstr(p,member(p,pack,"version"),buffer,sizeof(buffer))>0)put_text(w,buffer,32,0);
  put(w,"\t");num(w,number_or(p,member(p,pack,"parts"),0));put(w,"\t");put_nexus(w,p,pack,title);put(w,"\n");
 }
}
/* Shared page header: "<tag>\t<page>\t<pages>\t<total>". The server's page is
 * 1-based; the game's is 0-based. */
static int page_header(parser *p,writer *w,const char *tag,int page,int per,int *items){
 int total,pages;
 *items=member(p,0,"items");
 if(*items<0||p->t[*items].kind!='['||p->t[*items].count>per)return 0;
 total=number_or(p,member(p,0,"total"),-1);if(total<0)total=p->t[*items].count;
 pages=number_or(p,member(p,0,"pages"),-1);if(pages<0)pages=(total+per-1)/per;
 put(w,tag);put(w,"\t");num(w,page);put(w,"\t");num(w,pages);put(w,"\t");num(w,total);put(w,"\n");
 return 1;
}
/* One page of /api/v1/compositions as a "gallery" header and listing rows.
 * The preview.22 panel can't show more than eight pages. */
int dd_gallery_page(const unsigned char *json,size_t size,int legacy,int page,char *out,size_t cap){
 parser p;writer w={out,0,cap,1};int items,row;
 if(!cap||size>DD_METADATA_MAX||!init(&p,json,size)||!unique(&p)||p.t[0].kind!='{'||!istext(&p,member(&p,0,"api_version"),"v1"))return 0;
 if(legacy){
  int total=number_or(&p,member(&p,0,"total"),0),pages=number_or(&p,member(&p,0,"pages"),(total+5)/6);items=member(&p,0,"items");
  if(items<0||p.t[items].kind!='['||p.t[items].count>6)return 0;
  if(pages>8){pages=8;total=48;}
  put(&w,"gallery\t");num(&w,page);put(&w,"\t");num(&w,pages);put(&w,"\t");num(&w,total);put(&w,"\n");
 }else if(!page_header(&p,&w,"gallery",page,8,&items))return 0;
 for(row=items+1;row<p.t[items].next;row=p.t[row].next)listing_rows(&p,row,&w,legacy);
 return w.ok;
}
/* One page of /api/v1/my/listings:
 *   shares\tpage\tpages\ttotal
 *   share\tcode\ttitle\tlatest_revision\timports\tpublic|hidden\tupdated */
int dd_shares_page(const unsigned char *json,size_t size,int page,char *out,size_t cap){
 parser p;writer w={out,0,cap,1};int items,row,revision;char code[33],checked[33],title[481];
 if(!cap||size>DD_METADATA_MAX||!init(&p,json,size)||!unique(&p)||p.t[0].kind!='{'||!page_header(&p,&w,"shares",page,8,&items))return 0;
 for(row=items+1;row<p.t[items].next;row=p.t[row].next){
  revision=number_or(&p,member(&p,row,"latest_revision"),0);if(revision<1)revision=number_or(&p,member(&p,row,"revision"),0);
  if(!text(&p,member(&p,row,"code"),code,sizeof(code))||!dd_code(code,checked)||!eq(code,checked)||revision<1)continue;
  if(jstr(&p,member(&p,row,"title"),title,sizeof(title))<1)cp(title,"Untitled",9);
  put(&w,"share\t");put(&w,code);put(&w,"\t");put_text(&w,title,120,0);put(&w,"\t");num(&w,revision);put(&w,"\t");num(&w,number_or(&p,member(&p,row,"import_count"),0));
  put(&w,raw(&p,member(&p,row,"hidden"),"true")||istext(&p,member(&p,row,"visibility"),"hidden")?"\thidden\t":"\tpublic\t");put_date(&w,&p,row);put(&w,"\n");
 }
 return w.ok;
}
/* /api/v1/game/profile: a valid user_id is required; display_name is shown as
 * "Connected as <name>" and may be missing (name is then empty). */
int dd_profile(const unsigned char *json,size_t size,char *name,size_t cap){
 parser p;writer w={name,0,cap,1};char id[64],display[385];size_t i;
 if(!cap)return 0;
 name[0]=0;
 if(size>DD_METADATA_MAX||!init(&p,json,size)||!unique(&p)||p.t[0].kind!='{'||!text(&p,member(&p,0,"user_id"),id,sizeof(id))||slen(id)!=36)return 0;
 for(i=0;i<36;i++)if(!(hex(id[i])||(id[i]=='-'&&(i==8||i==13||i==18||i==23)))||(id[i]=='-')!=(i==8||i==13||i==18||i==23))return 0;
 if(jstr(&p,member(&p,0,"display_name"),display,sizeof(display))>0&&!blank(display))put_text(&w,display,64,0);
 if(!w.ok)name[0]=0;
 return 1;
}
/* PUBLISH text values (title, description, changelog) arrive one per line
 * with \n for a line break and \\ for a backslash. Decodes into out; checks
 * UTF-8, at most max_chars characters, no control characters (line breaks
 * only when multiline) and no upload key. */
int dd_publish_text(const char *in,size_t size,int max_chars,int multiline,char *out,size_t cap){
 size_t i,used=0,k;int chars=0;unsigned u;
 for(i=0;i<size;i+=k){
  k=1;
  if(in[i]=='\\'){if(i+1>=size||(in[i+1]!='n'&&in[i+1]!='\\'))return 0;u=in[i+1]=='n'?'\n':'\\';k=2;}
  else if(!(k=utf8((const unsigned char *)in+i,size-i,&u)))return 0;
  if((u<32&&!(multiline&&u=='\n'))||u==127||++chars>max_chars)return 0;
  if(i+4<=size&&eqn(in+i,"zcu_",4))return 0;
  {char b[4];size_t m=encode(u,b);if(used+m>=cap)return 0;cp(out+used,b,m);used+=m;}
 }
 out[used]=0;return 1;
}

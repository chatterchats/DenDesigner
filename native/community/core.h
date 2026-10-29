#ifndef DEN_COMMUNITY_CORE_H
#define DEN_COMMUNITY_CORE_H
#include <stddef.h>
#include <stdint.h>
/* The one HoloNet server setting. Release builds use the defaults; a local
 * development build may pass -DDD_SERVICE_HOST=... (see build.sh). */
#ifndef DD_SERVICE_HOST
#define DD_SERVICE_HOST "zcom.app"
#endif
#ifndef DD_SERVICE_PORT
#define DD_SERVICE_PORT 443
#endif
#ifndef DD_SERVICE_SECURE
#define DD_SERVICE_SECURE 1
#endif
#define DD_SERVICE_URL "https://" DD_SERVICE_HOST
#define DD_VERSION "0.9.20"
#define DD_DOCUMENT_MAX (4u * 1024u * 1024u)
#define DD_METADATA_MAX (64u * 1024u)
/* Wire values are UTF-8 here. The SaveGame stores them as ANSI when ASCII and
 * as UTF-16 otherwise, so a mailbox file holds at most two bytes per unit. */
#define DD_WIRE_MAX (48u * 1024u)
#define DD_WIRE_UTF8_MAX (3u * DD_WIRE_MAX)
#define DD_SAVE_MAX (2u * DD_WIRE_MAX + 16u * 1024u)
#define DD_PAGE_MAX 24
typedef int (*dd_hash_fn)(const unsigned char *, size_t, char[65]);
typedef struct {
  char token[65], input[257];
  size_t wire_size_offset, wire_length_offset, wire_value_offset, wire_end;
  int wire_wide;
} dd_save;
int dd_code(const char *input, char code[33]);
int dd_listing(const unsigned char *json, size_t size, const char *code,
               size_t *bytes, char digest[65], const char **error);
int dd_document(const unsigned char *json, size_t size, const char *code,
                const char *token, dd_hash_fn hash, char *wire, size_t capacity,
                const char **error);
int dd_save_read(const unsigned char *data, size_t size, dd_save *save,
                 const char **error);
int dd_save_wire(const unsigned char *data, size_t size, const dd_save *save,
                 char *out, size_t capacity, size_t *written);
int dd_save_response(const unsigned char *data, size_t size,
                     const dd_save *save, const char *wire,
                     unsigned char *output, size_t capacity, size_t *written);
size_t dd_error_wire(char *wire, size_t capacity, const char *token,
                     const char *error);
int dd_publish_review(const unsigned char *,size_t,char *,size_t);
int dd_listing_revision(const unsigned char *,size_t);
int dd_key_valid(const char *);
int dd_cached_png(const unsigned char *,size_t,size_t *);
int dd_catalog_request(const char *wire,size_t size,int *legacy,char *path,size_t capacity,int page);
int dd_gallery_page(const unsigned char *json,size_t size,int legacy,int page,char *out,size_t capacity);
int dd_shares_page(const unsigned char *json,size_t size,int page,char *out,size_t capacity);
int dd_profile(const unsigned char *json,size_t size,char *name,size_t capacity);
size_t dd_thumbnail_name(const unsigned char *,size_t);
int dd_publish_text(const char *in,size_t size,int max_chars,int multiline,char *out,size_t capacity);
#endif

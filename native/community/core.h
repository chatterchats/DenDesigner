#ifndef DEN_COMMUNITY_CORE_H
#define DEN_COMMUNITY_CORE_H
#include <stddef.h>
#include <stdint.h>
#define DD_DOCUMENT_MAX (4u * 1024u * 1024u)
#define DD_METADATA_MAX (64u * 1024u)
#define DD_SAVE_MAX (64u * 1024u)
#define DD_WIRE_MAX (48u * 1024u)
#define DD_MESH                                                                \
  "/Game/Game/Environments/Strategy/HQ/Props/Control/"                         \
  "Control_Monitor_A.Control_Monitor_A"
/* Legacy fixture imports retain their reviewed subset. Validated published
 * documents additionally support decimal transforms and covered asset paths;
 * the engine checks local mesh/material availability before placement. */
typedef int (*dd_hash_fn)(const unsigned char *, size_t, char[65]);
typedef struct {
  char token[65], input[257];
  size_t wire_size_offset, wire_length_offset, wire_value_offset, wire_end;
} dd_save;
int dd_code(const char *input, char code[33]);
int dd_listing(const unsigned char *json, size_t size, const char *code,
               size_t *bytes, char digest[65], const char **error);
int dd_document(const unsigned char *json, size_t size, const char *code,
                const char *token, dd_hash_fn hash, char *wire, size_t capacity,
                const char **error);
int dd_save_read(const unsigned char *data, size_t size, dd_save *save,
                 const char **error);
int dd_save_response(const unsigned char *data, size_t size,
                     const dd_save *save, const char *wire,
                     unsigned char *output, size_t capacity, size_t *written);
size_t dd_error_wire(char *wire, size_t capacity, const char *token,
                     const char *error);
int dd_publish_review(const unsigned char *,size_t,char *,size_t);
int dd_listing_revision(const unsigned char *,size_t);
int dd_key_valid(const char *);
int dd_cached_png(const unsigned char *,size_t,size_t *);
int dd_gallery_select(const unsigned char *,size_t,const char *,int,char [6][33],int *,int *);
int dd_gallery_row(const unsigned char *,size_t,const char *,char *,size_t);
#endif

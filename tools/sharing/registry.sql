-- Offline reference schema. No HTTP routes or public upload surface.
PRAGMA foreign_keys = ON;
CREATE TABLE IF NOT EXISTS listings (
    id TEXT PRIMARY KEY,
    content_type TEXT NOT NULL CHECK(content_type IN ('den','composition','character')),
    author_id TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now'))
);
CREATE TABLE IF NOT EXISTS revisions (
    id TEXT PRIMARY KEY,
    listing_id TEXT NOT NULL REFERENCES listings(id),
    revision INTEGER NOT NULL CHECK(revision > 0),
    -- One global, case-sensitive namespace across all content types.
    share_code TEXT NOT NULL COLLATE BINARY UNIQUE
        CHECK(length(share_code)=32 AND share_code NOT GLOB '*[^A-Za-z0-9]*'),
    schema_version INTEGER NOT NULL CHECK(schema_version > 0),
    document TEXT NOT NULL,
    document_sha256 TEXT NOT NULL,
    published_at TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%fZ','now')),
    UNIQUE(listing_id, revision)
);
CREATE TRIGGER IF NOT EXISTS immutable_revision_update BEFORE UPDATE ON revisions
BEGIN SELECT RAISE(ABORT, 'Published revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS immutable_revision_delete BEFORE DELETE ON revisions
BEGIN SELECT RAISE(ABORT, 'Published revisions are immutable'); END;
CREATE TRIGGER IF NOT EXISTS stable_listing_identity BEFORE UPDATE ON listings
BEGIN SELECT RAISE(ABORT, 'Listing identity is immutable'); END;
PRAGMA user_version = 1;

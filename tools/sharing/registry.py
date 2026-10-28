"""Offline reference Community registry; intentionally no public upload transport."""
import json
from pathlib import Path
import secrets
import sqlite3
import string
import uuid

from .contract import canonical, digest, require, validate


def share_code():
    # secrets.choice uses rejection sampling, avoiding modulo bias. ~190 bits.
    return ''.join(secrets.choice(string.ascii_letters + string.digits) for _ in range(32))


class Registry:
    def __init__(self, connection):
        self.db = connection
        version = self.db.execute('PRAGMA user_version').fetchone()[0]
        require(version in (0, 1), 'Unsupported registry schema')
        self.db.executescript(Path(__file__).with_name('registry.sql').read_text())

    def create_listing(self, content_type, author_id):
        require(content_type in ('den', 'composition'), 'Character support is reserved')
        require(type(author_id) is str and 0 < len(author_id) <= 128, 'Invalid author ID')
        ident = uuid.uuid4().hex
        with self.db:
            self.db.execute('INSERT INTO listings(id,content_type,author_id) VALUES(?,?,?)',
                            (ident, content_type, author_id))
        return ident

    def publish(self, listing_id, doc):
        """Internal/offline only. A future service must authorize the listing owner."""
        validate(doc)
        with self.db:
            # Serializes revision allocation across connections, including empty listings.
            self.db.execute('BEGIN IMMEDIATE')
            row = self.db.execute('SELECT content_type,author_id FROM listings WHERE id=?', (listing_id,)).fetchone()
            require(row == (doc['content_type'], doc['metadata']['author']['id']), 'Listing identity mismatch')
            revision = self.db.execute('SELECT COALESCE(MAX(revision),0)+1 FROM revisions WHERE listing_id=?',
                                       (listing_id,)).fetchone()[0]
            ident = uuid.uuid4().hex
            for _ in range(8):
                code = share_code()
                try:
                    self.db.execute('INSERT INTO revisions(id,listing_id,revision,share_code,schema_version,document,document_sha256) VALUES(?,?,?,?,?,?,?)',
                                    (ident, listing_id, revision, code, doc['schema_version'], canonical(doc).decode(), digest(doc)))
                    return dict(listing_id=listing_id, revision_id=ident, revision=revision, share_code=code)
                except sqlite3.IntegrityError:
                    # Retry only a code collision. Do not swallow other constraints.
                    if self.db.execute('SELECT 1 FROM revisions WHERE share_code=?', (code,)).fetchone() is None:
                        raise
            raise ValueError('Share code collision retry limit reached')

    def resolve(self, code):
        require(type(code) is str and len(code) == 32 and code.isascii() and code.isalnum(), 'Invalid share code')
        row = self.db.execute('SELECT listing_id,id,revision,document,document_sha256 FROM revisions WHERE share_code=?', (code,)).fetchone()
        if row is None: return None
        doc = json.loads(row[3])
        require(digest(doc) == row[4], 'Revision integrity mismatch')
        validate(doc)
        return dict(listing_id=row[0], revision_id=row[1], revision=row[2], share_code=code, document=doc)

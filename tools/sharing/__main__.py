"""Offline validation only: python3 -m tools.sharing FILE.json"""
import argparse
from pathlib import Path
from .contract import loads, MAX_BYTES


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('file', type=Path)
    args = parser.parse_args()
    try:
        with args.file.open('rb') as source:
            doc = loads(source.read(MAX_BYTES + 1))
        print(f"Valid {doc['content_type']} sharing schema {doc['schema_version']}: {doc['metadata']['title']}")
    except (ValueError, OSError) as exc:
        parser.exit(1, str(exc) + '\n')

if __name__ == '__main__': main()

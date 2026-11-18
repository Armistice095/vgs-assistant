"""Command line helper for the master key.

    python -m vgs.crypto.keytool generate v2     # new key: store it in the password manager
    python -m vgs.crypto.keytool fingerprint     # check value of MASTER_KEY_B64 (environment)
    python -m vgs.crypto.keytool verify <copy>   # does the backup copy match the key in use?

``generate`` prints the key once on stdout: nothing is written to disk or to the logs.
"""

from __future__ import annotations

import argparse
import hmac
import os
import sys

from vgs.crypto.envelope import generate_master_key_b64
from vgs.crypto.keys import KeyConfigError, fingerprint


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="keytool")
    sub = parser.add_subparsers(dest="command", required=True)
    gen = sub.add_parser("generate", help="create a new master key")
    gen.add_argument("key_id", help="identifier of the new key, e.g. v2")
    sub.add_parser("fingerprint", help="check value of MASTER_KEY_B64 from the environment")
    ver = sub.add_parser("verify", help="compare a backup copy with MASTER_KEY_B64")
    ver.add_argument("backup_copy")
    args = parser.parse_args(argv)

    try:
        if args.command == "generate":
            key = generate_master_key_b64()
            print(f"MASTER_KEY_ID={args.key_id}")
            print(f"MASTER_KEY_B64={key}")
            print(f"fingerprint={fingerprint(key)}", file=sys.stderr)
            return 0
        current = os.environ.get("MASTER_KEY_B64", "")
        if not current:
            print("MASTER_KEY_B64 is not set", file=sys.stderr)
            return 2
        if args.command == "fingerprint":
            print(fingerprint(current))
            return 0
        same = hmac.compare_digest(fingerprint(current), fingerprint(args.backup_copy))
        print("MATCH" if same else "DIFFERENT")
        return 0 if same else 1
    except KeyConfigError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

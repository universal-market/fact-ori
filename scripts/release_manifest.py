#!/usr/bin/env python3
"""Describe an immutable committed source tree; never attest a deployment/review."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path, PurePosixPath


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def git(root, *args):
    # A replacement ref must never reinterpret the object named by our identity.
    return subprocess.check_output(
        ["git", "--no-replace-objects", "-C", str(root), *args], stderr=subprocess.PIPE
    )


def public_path(path):
    """Refuse sensitive tracked paths before reading their blob contents."""
    parts = PurePosixPath(path).parts
    return bool(parts) and not path.startswith("/") and not any(
        part in {"..", ".aws", ".codex", ".agents", ".convex", "node_modules",
                 ".npmrc", ".netrc", ".git-credentials", "id_rsa", "id_ed25519"}
        or (part.startswith(".env") and part != ".env.example")
        or part.endswith((".key", ".pem")) for part in parts
    )


def build_manifest(root, revision="HEAD"):
    root = Path(root)
    commit = git(root, "rev-parse", "--verify", "--end-of-options", revision + "^{commit}").decode().strip()
    # cat-file can return corrupt blob bytes without checking their object ID.
    # Delegate object-format-aware integrity checks to Git before hashing inputs.
    git(root, "fsck", "--strict", "--no-dangling", commit)
    tree = git(root, "rev-parse", commit + "^{tree}").decode().strip()
    entries = git(root, "ls-tree", "-rz", "--full-tree", commit).split(b"\0")
    files = []
    for entry in entries:
        if not entry:
            continue
        metadata, raw_path = entry.split(b"\t", 1)
        mode, kind, oid = metadata.decode().split()
        path = raw_path.decode("utf8")
        if not public_path(path):
            raise ValueError(f"Refusing sensitive source path: {path}")
        if kind != "blob" or mode not in {"100644", "100755"}:
            raise ValueError(f"Unsupported source entry: {path}")
        blob = git(root, "cat-file", "blob", oid)
        files.append({"path": path, "mode": mode, "sha256": hashlib.sha256(blob).hexdigest()})
    subject = {"schema_version": 1, "kind": "committed_source_tree",
               "source_commit": commit, "source_tree": tree,
               "files": sorted(files, key=lambda item: item["path"])}
    return {**subject, "manifest_sha256": hashlib.sha256(canonical(subject)).hexdigest(),
            "limits": ["Committed Git bytes only; working-tree edits and untracked files are not described.",
                       "Not a built-artifact or deployed-code attestation.",
                       "No review authenticity, acceptance, factual truth or source freshness is established."]}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--revision", default="HEAD")
    args = parser.parse_args()
    print(json.dumps(build_manifest(args.root, args.revision), indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()

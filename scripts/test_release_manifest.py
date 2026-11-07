import hashlib
import json
import subprocess
import tempfile
import unittest
import zlib
from pathlib import Path

from release_manifest import build_manifest, canonical, public_path


class ReleaseManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.git("init", "-q")
        self.git("config", "user.name", "Manifest fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("convex/checks.ts", "export const scope = 'current';\n")
        self.write("package-lock.json", "{}\n")
        self.commit()

    def git(self, *args):
        return subprocess.check_output(["git", "-C", str(self.root), *args], stderr=subprocess.PIPE)

    def write(self, name, text):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)

    def commit(self):
        self.git("add", ".")
        self.git("commit", "-qm", "fixture")
        return self.git("rev-parse", "HEAD").decode().strip()

    def test_exact_bytes_deterministic_sorted_and_self_digest(self):
        a = build_manifest(self.root)
        self.assertEqual(a, build_manifest(self.root))
        self.assertEqual([x["path"] for x in a["files"]], ["convex/checks.ts", "package-lock.json"])
        self.assertEqual(a["files"][0]["sha256"], hashlib.sha256(b"export const scope = 'current';\n").hexdigest())
        self.assertEqual(a["files"][0]["mode"], "100644")
        subject = {k: v for k, v in a.items() if k not in {"manifest_sha256", "limits"}}
        self.assertEqual(a["manifest_sha256"], hashlib.sha256(canonical(subject)).hexdigest())
        self.assertEqual(a["kind"], "committed_source_tree")
        self.assertNotIn("accepted", json.dumps(a))

    def test_worktree_and_untracked_are_not_misrepresented_as_commit(self):
        before = build_manifest(self.root)
        self.write("convex/checks.ts", "uncommitted drift")
        self.write(".env.local", "PRIVATE_FIXTURE_NOT_A_REAL_CREDENTIAL")
        self.assertEqual(build_manifest(self.root), before)
        self.assertIn("working-tree edits", before["limits"][0])

    def test_new_committed_file_and_change_both_invalidate_old_identity(self):
        before = build_manifest(self.root)
        self.write("convex/checks.ts", "changed scope")
        self.write("convex/new function.ts", "new runtime path")
        self.commit()
        after = build_manifest(self.root)
        self.assertNotEqual(before["manifest_sha256"], after["manifest_sha256"])
        self.assertNotEqual(before["source_tree"], after["source_tree"])
        self.assertIn("convex/new function.ts", [x["path"] for x in after["files"]])

    def test_merge_style_same_tree_different_commit_keeps_distinction(self):
        before = build_manifest(self.root)
        self.git("commit", "--allow-empty", "-qm", "metadata-only commit")
        after = build_manifest(self.root)
        self.assertEqual(before["source_tree"], after["source_tree"])
        self.assertEqual(before["files"], after["files"])
        self.assertNotEqual(before["source_commit"], after["source_commit"])
        self.assertNotEqual(before["manifest_sha256"], after["manifest_sha256"])

    def test_replaced_blob_does_not_change_committed_source_identity(self):
        before = build_manifest(self.root)
        original = self.git("rev-parse", "HEAD:convex/checks.ts").decode().strip()
        self.write("replacement.txt", "replacement bytes, never committed")
        replacement = self.git("hash-object", "-w", "replacement.txt").decode().strip()
        self.git("replace", original, replacement)
        # Prove the fixture changes ordinary Git reads before testing isolation.
        self.assertEqual(self.git("cat-file", "blob", original), b"replacement bytes, never committed")
        self.assertEqual(build_manifest(self.root), before)

    def test_replaced_commit_does_not_change_selected_tree(self):
        before = build_manifest(self.root)
        self.write("convex/checks.ts", "a different committed tree")
        replacement = self.commit()
        self.git("replace", before["source_commit"], replacement)
        self.assertNotEqual(
            self.git("rev-parse", before["source_commit"] + "^{tree}").decode().strip(),
            before["source_tree"],
        )
        self.assertEqual(build_manifest(self.root, before["source_commit"]), before)

    def corrupt_object(self, oid, kind, data):
        # Disposable fixture repository only: valid encoding, wrong object ID.
        path = self.root / ".git" / "objects" / oid[:2] / oid[2:]
        path.chmod(0o644)
        path.write_bytes(zlib.compress(kind.encode() + b" " + str(len(data)).encode() + b"\0" + data))

    def test_corrupt_blob_is_refused(self):
        oid = self.git("rev-parse", "HEAD:convex/checks.ts").decode().strip()
        self.corrupt_object(oid, "blob", b"tampered bytes\n")
        self.assertEqual(self.git("cat-file", "blob", oid), b"tampered bytes\n")
        with self.assertRaises(subprocess.CalledProcessError):
            build_manifest(self.root)

    def test_corrupt_tree_is_refused(self):
        oid = self.git("rev-parse", "HEAD^{tree}").decode().strip()
        data = self.git("cat-file", "tree", oid).replace(b"package-lock.json", b"zackage-lock.json")
        self.corrupt_object(oid, "tree", data)
        with self.assertRaises(subprocess.CalledProcessError):
            build_manifest(self.root)

    def test_corrupt_commit_is_refused(self):
        oid = self.git("rev-parse", "HEAD").decode().strip()
        data = self.git("cat-file", "commit", oid).replace(b"fixture\n", b"tampered\n")
        self.corrupt_object(oid, "commit", data)
        self.assertIn(b"tampered\n", self.git("cat-file", "commit", oid))
        with self.assertRaises(subprocess.CalledProcessError):
            build_manifest(self.root)

    def test_sha256_repository_integrity_is_checked_by_git(self):
        self.root = self.root / "sha256"
        self.root.mkdir()
        self.git("init", "-q", "--object-format=sha256")
        self.git("config", "user.name", "Manifest fixture")
        self.git("config", "user.email", "fixture@example.invalid")
        self.write("a.txt", "original\n")
        self.commit()
        manifest = build_manifest(self.root)
        self.assertEqual(len(manifest["source_commit"]), 64)
        self.assertEqual(manifest["files"][0]["sha256"], hashlib.sha256(b"original\n").hexdigest())
        oid = self.git("rev-parse", "HEAD:a.txt").decode().strip()
        self.corrupt_object(oid, "blob", b"tampered\n")
        with self.assertRaises(subprocess.CalledProcessError):
            build_manifest(self.root)

    def test_historical_revision_uses_old_bytes_and_option_like_revision_fails(self):
        old = self.git("rev-parse", "HEAD").decode().strip()
        before = build_manifest(self.root, old)
        self.write("convex/checks.ts", "new")
        self.commit()
        self.assertEqual(build_manifest(self.root, old), before)
        with self.assertRaises(subprocess.CalledProcessError):
            build_manifest(self.root, "--help")

    def test_sensitive_tracked_path_is_rejected_without_blob_publication(self):
        self.write(".env.local", "PRIVATE_FIXTURE_NOT_A_REAL_CREDENTIAL")
        self.commit()
        with self.assertRaisesRegex(ValueError, "Refusing sensitive source path"):
            build_manifest(self.root)
        for path in [".aws/config", "nested/key.pem", "token.key", ".codex/settings", ".npmrc", ".netrc"]:
            self.assertFalse(public_path(path))

    def test_symlink_is_rejected_without_following_target(self):
        (self.root / "link").symlink_to("/unreadable/fixture")
        self.commit()
        with self.assertRaisesRegex(ValueError, "Unsupported source entry"):
            build_manifest(self.root)


if __name__ == "__main__":
    unittest.main()

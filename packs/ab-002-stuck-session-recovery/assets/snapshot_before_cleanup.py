#!/usr/bin/env python3
"""Evidence snapshot before cleaning up a stuck task/worker session (pack ab-002).

Read-only on the source: it never edits the worktree, the branch or the database.
It writes a new evidence directory containing:
  - git status / log / worktree list output
  - a binary patch of tracked changes (staged + unstaged) against HEAD
  - a tarball of untracked files (respecting .gitignore)
  - a git bundle of the branch (all commits reachable from HEAD)
  - optional: a consistent SQLite copy made with VACUUM INTO, plus integrity_check
  - MANIFEST.sha256 over everything written

Usage:
  snapshot_before_cleanup.py --worktree PATH --out DIR [--db PATH] [--note TEXT]
"""
import argparse, datetime, hashlib, json, os, sqlite3, subprocess, sys, tarfile


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True)
    return p.returncode, p.stdout, p.stderr


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--worktree", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--db")
    ap.add_argument("--note", default="")
    a = ap.parse_args()

    wt = os.path.abspath(a.worktree)
    out = os.path.abspath(a.out)
    if os.path.exists(out) and os.listdir(out):
        sys.exit(f"refusing to write into non-empty {out}")
    os.makedirs(out, exist_ok=True)

    meta = {"taken_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
            "worktree": wt, "note": a.note, "steps": []}

    def save(name, data):
        with open(os.path.join(out, name), "wb") as f:
            f.write(data)

    for name, cmd in [
        ("git-status.txt", ["git", "status", "--porcelain=v1", "--branch", "--untracked-files=all"]),
        ("git-log.txt", ["git", "log", "--oneline", "--decorate", "-n", "50"]),
        ("git-worktree-list.txt", ["git", "worktree", "list", "--porcelain"]),
        ("git-head.txt", ["git", "rev-parse", "HEAD", "--abbrev-ref", "HEAD"]),
    ]:
        rc, so, se = run(cmd, wt)
        save(name, so + (b"\n# stderr\n" + se if se else b""))
        meta["steps"].append({"file": name, "rc": rc})

    rc, patch, se = run(["git", "diff", "--binary", "HEAD"], wt)
    if rc != 0:
        sys.exit("git diff failed: " + se.decode())
    save("tracked-changes.patch", patch)
    meta["steps"].append({"file": "tracked-changes.patch", "rc": rc, "bytes": len(patch)})

    rc, so, _ = run(["git", "ls-files", "--others", "--exclude-standard", "-z"], wt)
    untracked = [p for p in so.decode().split("\0") if p]
    with tarfile.open(os.path.join(out, "untracked.tar.gz"), "w:gz") as tf:
        for rel in untracked:
            tf.add(os.path.join(wt, rel), arcname=rel)
    meta["steps"].append({"file": "untracked.tar.gz", "count": len(untracked)})

    rc, _, se = run(["git", "bundle", "create", os.path.join(out, "branch.bundle"), "HEAD", "--branches"], wt)
    if rc != 0:
        sys.exit("git bundle failed: " + se.decode())
    rc, so, se = run(["git", "bundle", "verify", os.path.join(out, "branch.bundle")], wt)
    meta["steps"].append({"file": "branch.bundle", "verify_rc": rc})
    if rc != 0:
        sys.exit("bundle verify failed: " + se.decode())

    if a.db:
        src = os.path.abspath(a.db)
        dst = os.path.join(out, "db-backup.sqlite")
        # Open the source read-only so this tool cannot write to it.
        con = sqlite3.connect(f"file:{src}?mode=ro", uri=True)
        con.execute("VACUUM INTO ?", (dst,))
        con.close()
        bcon = sqlite3.connect(f"file:{dst}?mode=ro", uri=True)
        ok = bcon.execute("PRAGMA integrity_check").fetchone()[0]
        tables = [r[0] for r in bcon.execute("select name from sqlite_master where type='table' order by name")]
        counts = {t: bcon.execute(f'select count(*) from "{t}"').fetchone()[0] for t in tables}
        bcon.close()
        meta["db"] = {"source": src, "integrity_check": ok, "row_counts": counts}
        if ok != "ok":
            sys.exit("backup integrity_check failed: " + ok)

    with open(os.path.join(out, "snapshot.json"), "w") as f:
        json.dump(meta, f, indent=2)

    lines = []
    for root, _, files in os.walk(out):
        for fn in sorted(files):
            if fn == "MANIFEST.sha256":
                continue
            p = os.path.join(root, fn)
            lines.append(f"{sha256(p)}  {os.path.relpath(p, out)}")
    with open(os.path.join(out, "MANIFEST.sha256"), "w") as f:
        f.write("\n".join(sorted(lines, key=lambda l: l.split('  ')[1])) + "\n")
    print(f"snapshot written to {out} ({len(lines)} files)")


if __name__ == "__main__":
    main()

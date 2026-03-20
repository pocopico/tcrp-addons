#!/usr/bin/env python3
"""
update_addons.py — TCRP addons.json + rpext-index.json new-release inserter
============================================================================

For each addon, finds every model that already has at least one release entry
and inserts a new entry for the new build number pointing to the same release
URL as that model's most recent existing build.

Updates TWO sets of files:
  1. addons.json              — the combined index (NDJSON or JSON array)
  2. <addon>/rpext-index.json — each addon's own index, in a sibling directory

Directory layout expected:
  /root/addons/
    addons.json
    9p/
      rpext-index.json
    acpid/
      rpext-index.json
    ...

Usage
-----
  # Dry-run: show what would change, touch nothing
  python3 update_addons.py --build 72806

  # Apply changes (both addons.json and every rpext-index.json)
  python3 update_addons.py --build 72806 --apply

  # Scope to specific models only
  python3 update_addons.py --build 72806 --models rs4021xsp ds3622xsp --apply

  # Use a non-default addons.json location
  python3 update_addons.py --build 72806 --file /root/addons/addons.json --apply

  # Override the release URL for a specific model (new platform family)
  python3 update_addons.py --build 72806 --override ds923p=https://.../newplatform.json --apply

  # Save a report of what was done
  python3 update_addons.py --build 72806 --apply --report /tmp/update_72806.txt

  # Show all models and supported build versions per addon (no --build needed)
  python3 update_addons.py --verify

  # Verify a specific addon only
  python3 update_addons.py --verify --addon acpid

  # Verify and check which models are missing a specific build
  python3 update_addons.py --verify --build 72806
"""

import argparse
import json
import re
import shutil
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

# ── Default paths ──────────────────────────────────────────────────────────────
DEFAULT_LOCAL  = Path("/root/addons/addons.json")
DEFAULT_CACHED = Path("/root/tcrp-node/addons.json")

SENTINEL_KEY = "zendofmodel"
SENTINEL_VAL = "endofurls"


# ── NDJSON / JSON helpers ──────────────────────────────────────────────────────

def parse_addons(text):
    t = text.strip()
    if t.startswith("["):
        return json.loads(t)
    parts = re.split(r'(?<=\})\s*(?=\{)', t)
    out = []
    for part in parts:
        part = part.strip()
        if part:
            try:
                out.append(json.loads(part))
            except json.JSONDecodeError as e:
                print(f"  WARNING: skipping malformed entry: {e}", file=sys.stderr)
    return out


def serialize_addons(items, original_was_array):
    if original_was_array:
        return json.dumps(items, indent=2, ensure_ascii=False) + "\n"
    return "\n".join(json.dumps(item, ensure_ascii=False) for item in items) + "\n"


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"  WARNING: cannot read {path}: {e}", file=sys.stderr)
        return None


def save_json(path, data, no_backup):
    if not no_backup and path.exists():
        shutil.copy2(path, path.with_suffix(".json.bak"))
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                    encoding="utf-8")


# ── Core logic ─────────────────────────────────────────────────────────────────

def build_model_entries(releases):
    """Return {model: [(build_int, url), ...]} from a releases dict."""
    me = defaultdict(list)
    for key, url in releases.items():
        if key == SENTINEL_KEY:
            continue
        m = re.match(r'^(.+)_(\d+)$', key)
        if m:
            me[m.group(1)].append((int(m.group(2)), url))
    return me


def compute_new_entries(releases, new_build, model_filter, overrides):
    """Return (to_add dict, skipped list)."""
    model_entries = build_model_entries(releases)
    to_add = {}
    skipped = []
    for model, builds in sorted(model_entries.items()):
        if model_filter and model not in model_filter:
            continue
        new_key = f"{model}_{new_build}"
        if new_key in releases:
            skipped.append(f"    SKIP  {new_key}  (already present)")
            continue
        url = overrides.get(model) or max(builds, key=lambda x: x[0])[1]
        to_add[new_key] = url
    return to_add, skipped


def apply_to_releases(releases, to_add):
    """Append to_add entries, keeping sentinel last."""
    has_sentinel = SENTINEL_KEY in releases
    if has_sentinel:
        del releases[SENTINEL_KEY]
    releases.update(to_add)
    if has_sentinel:
        releases[SENTINEL_KEY] = SENTINEL_VAL


def format_logs(to_add, skipped, label, model_entries, overrides, dry_run):
    if not to_add and not skipped:
        return []
    action = "DRY-RUN" if dry_run else "ADD"
    lines = [f"  {label}"]
    for key, url in sorted(to_add.items()):
        model = key.rsplit("_", 1)[0]
        src = "override" if model in overrides else f"from _{max(b for b,_ in model_entries[model])}"
        short = url.split("/tcrp-addons/")[1] if "/tcrp-addons/" in url else url
        lines.append(f"    {action:7s}  {key:<30s}  {short}  ({src})")
    lines.extend(skipped)
    return lines


# ── Locate an addon's rpext-index.json ────────────────────────────────────────

def find_rpext(addon, addons_dir):
    """
    Try to locate the rpext-index.json for this addon under addons_dir.
    Strategy: addon["id"] as folder name, falling back to the path embedded
    in addon["url"].
    """
    # 1. Direct id match
    p = addons_dir / addon.get("id", "") / "rpext-index.json"
    if p.exists():
        return p

    # 2. Derive folder from the url field
    url = addon.get("url", "")
    m = re.search(r'/([^/]+)/rpext-index\.json', url)
    if m:
        p2 = addons_dir / m.group(1) / "rpext-index.json"
        if p2.exists():
            return p2

    return None


# ── Per-addon processing ───────────────────────────────────────────────────────

def process_addon(addon, new_build, model_filter, overrides,
                  addons_dir, dry_run, no_backup):
    """
    Returns (addons_json_additions, rpext_additions, log_lines).
    Modifies addon dict and rpext file in-place when not dry_run.
    """
    addon_id = addon.get("id", "?")
    all_logs = []

    # ── addons.json entry ─────────────────────────────────────────────────────
    releases = addon.get("releases", {})
    if not isinstance(releases, dict):
        return 0, 0, []

    me = build_model_entries(releases)
    to_add, skipped = compute_new_entries(releases, new_build, model_filter, overrides)
    logs = format_logs(to_add, skipped, f"[addons.json]  {addon_id}", me, overrides, dry_run)
    if logs:
        all_logs.extend(logs)

    if to_add and not dry_run:
        apply_to_releases(releases, to_add)
        addon["releases"] = releases

    aj_count = len(to_add)

    # ── rpext-index.json ──────────────────────────────────────────────────────
    rpext_count = 0
    rpext_path = find_rpext(addon, addons_dir)

    if rpext_path:
        rpext = load_json(rpext_path)
        if rpext and isinstance(rpext.get("releases"), dict):
            rr = rpext["releases"]
            rme = build_model_entries(rr)
            r_to_add, r_skipped = compute_new_entries(rr, new_build, model_filter, overrides)
            r_logs = format_logs(
                r_to_add, r_skipped,
                f"[rpext-index]  {rpext_path.relative_to(addons_dir)}",
                rme, overrides, dry_run
            )
            if r_logs:
                all_logs.extend(r_logs)

            if r_to_add and not dry_run:
                apply_to_releases(rr, r_to_add)
                rpext["releases"] = rr
                save_json(rpext_path, rpext, no_backup)

            rpext_count = len(r_to_add)
    else:
        if to_add or skipped:
            all_logs.append(
                f"  [rpext-index]  WARNING: no rpext-index.json found for '{addon_id}' "
                f"under {addons_dir}"
            )

    return aj_count, rpext_count, all_logs


# ── Verify / matrix display ───────────────────────────────────────────────────

def verify_addons(items, addons_dir, addon_filter, build_filter):
    """
    Print a matrix of model → supported build versions for every addon.
    If build_filter is set, also flags models missing that build.
    """
    # Derive a short platform name from a release URL
    # e.g. ".../9p/releases/apollolake.json" -> "apollolake"
    #      ".../acpid/recipes/universal.json" -> "universal"
    def platform(url):
        m = re.search(r'/([^/]+)\.json$', url or "")
        return m.group(1) if m else "?"

    print(f"{'─'*72}")
    print(f"  VERIFY  —  {len(items)} addons   "
          f"{'  filter: ' + addon_filter if addon_filter else ''}"
          f"{'  check-build: ' + build_filter if build_filter else ''}")
    print(f"{'─'*72}")

    total_models = 0
    total_missing = 0

    for addon in items:
        addon_id = addon.get("id", "?")
        if addon_filter and addon_id != addon_filter:
            continue

        releases = addon.get("releases", {})
        if not isinstance(releases, dict):
            continue

        me = build_model_entries(releases)
        if not me:
            continue

        # Collect all unique build numbers across all models (sorted)
        all_builds = sorted({b for builds in me.values() for b, _ in builds})

        desc = (addon.get("info") or {}).get("description", "")
        print(f"\n  ┌─ {addon_id}  —  {desc}")

        col_model = max(len(m) for m in me) + 2
        col_build = 8   # each build number column width

        # Header row: build numbers
        build_header = "".join(f"{str(b):>{col_build}}" for b in all_builds)
        print(f"  │  {'model':<{col_model}}  {build_header}  platform")
        print(f"  │  {'─'*col_model}  {'─'*(col_build*len(all_builds))}  ────────────")

        for model in sorted(me):
            builds_dict = {b: url for b, url in me[model]}
            # Mark each build slot: ✓ present, · missing
            row_builds = ""
            for b in all_builds:
                if b in builds_dict:
                    row_builds += f"{'✓':>{col_build}}"
                else:
                    row_builds += f"{'·':>{col_build}}"

            # Platform from the most recent build URL
            latest_url = max(me[model], key=lambda x: x[0])[1]
            plat = platform(latest_url)

            # Flag if the requested build is missing for this model
            missing_flag = ""
            if build_filter and int(build_filter) not in builds_dict:
                missing_flag = f"  ← missing {build_filter}"
                total_missing += 1

            print(f"  │  {model:<{col_model}}  {row_builds}  {plat}{missing_flag}")
            total_models += 1

        # Totals line
        model_count = len(me)
        build_count = len(all_builds)
        latest_build = max(all_builds)
        print(f"  └─ {model_count} models  ·  {build_count} build versions  ·  latest: {latest_build}")

    print(f"\n{'─'*72}")
    print(f"  Total models scanned : {total_models}")
    if build_filter:
        ok = total_models - total_missing
        print(f"  Have build {build_filter:<8}: {ok}")
        print(f"  Missing build {build_filter:<5}: {total_missing}"
              + ("  ✓ all covered" if total_missing == 0 else "  ← run --build to add"))
    print()


# ── Entry point ────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(
        description="Insert a new DSM build into addons.json + every rpext-index.json",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    ap.add_argument("--build",     default=None, help="New DSM build number, e.g. 72806")
    ap.add_argument("--file",      default=None,  help=f"Path to addons.json (default: {DEFAULT_LOCAL})")
    ap.add_argument("--apply",     action="store_true", help="Write changes (default is dry-run)")
    ap.add_argument("--verify",    action="store_true",
                    help="Display model/version matrix for every addon (read-only)")
    ap.add_argument("--addon",     default=None,
                    help="Limit --verify to a single addon id, e.g. acpid")
    ap.add_argument("--models",    nargs="+", default=None,
                    help="Limit to specific model names, e.g. rs4021xsp ds3622xsp")
    ap.add_argument("--override",  nargs="+", default=[], metavar="MODEL=URL",
                    help="Override URL for a model, e.g. ds923p=https://.../new.json")
    ap.add_argument("--report",    default=None, help="Write a change report to this file")
    ap.add_argument("--no-backup", action="store_true", help="Skip .bak backups before writing")
    args = ap.parse_args()

    # --verify doesn't need --build; --build without --verify triggers update mode
    if not args.verify and not args.build:
        ap.error("--build is required unless --verify is specified")

    if args.build and not re.match(r'^\d+$', args.build):
        ap.error(f"--build must be numeric, got: {args.build!r}")
    new_build = args.build

    # Resolve addons.json
    if args.file:
        addons_path = Path(args.file)
    elif DEFAULT_LOCAL.exists():
        addons_path = DEFAULT_LOCAL
    elif DEFAULT_CACHED.exists():
        addons_path = DEFAULT_CACHED
    else:
        ap.error(f"Cannot find addons.json. Use --file to specify its location.")

    if not addons_path.exists():
        ap.error(f"File not found: {addons_path}")

    addons_dir = addons_path.parent   # sibling directories are the addon folders

    # Parse overrides
    overrides = {}
    for o in args.override:
        if "=" not in o:
            ap.error(f"--override must be MODEL=URL, got: {o!r}")
        model, url = o.split("=", 1)
        overrides[model.strip()] = url.strip()

    model_filter = set(args.models) if args.models else None

    # Load addons.json
    raw = addons_path.read_text(encoding="utf-8")
    original_was_array = raw.strip().startswith("[")
    items = parse_addons(raw)
    if not items:
        print("ERROR: addons.json is empty or unparseable.", file=sys.stderr)
        sys.exit(1)

    # ── Verify mode (read-only, exits here) ──────────────────────────────────
    if args.verify:
        verify_addons(items, addons_dir,
                      addon_filter=args.addon,
                      build_filter=new_build)
        sys.exit(0)

    # Header
    mode = "APPLY" if args.apply else "DRY-RUN"
    header = (
        f"update_addons.py  —  build={new_build}  mode={mode}\n"
        f"addons.json : {addons_path}\n"
        f"addons dir  : {addons_dir}\n"
        f"addons      : {len(items)}\n"
        f"models      : {', '.join(sorted(model_filter)) if model_filter else '(all)'}\n"
        f"time        : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
        + ("─" * 72)
    )
    print(header)

    total_aj = total_rx = 0
    all_logs = []

    for addon in items:
        aj, rx, logs = process_addon(
            addon, new_build, model_filter, overrides,
            addons_dir, dry_run=not args.apply, no_backup=args.no_backup
        )
        total_aj += aj
        total_rx += rx
        if logs:
            print()
            for line in logs:
                print(line)
            all_logs.extend(logs)

    # Summary
    verb = "Added" if args.apply else "Would add"
    summary = (
        "\n" + ("─" * 72) + "\n"
        f"{verb}:  {total_aj} entries in addons.json\n"
        f"{verb}:  {total_rx} entries across rpext-index.json files\n"
    )
    if not args.apply:
        summary += "Re-run with --apply to write changes.\n"
    print(summary)

    # Write addons.json
    if args.apply and total_aj > 0:
        if not args.no_backup:
            bak = addons_path.with_suffix(".json.bak")
            shutil.copy2(addons_path, bak)
            print(f"Backup  : {bak}")
        addons_path.write_text(serialize_addons(items, original_was_array), encoding="utf-8")
        print(f"Updated : {addons_path}")
    elif args.apply and total_aj == 0:
        print("addons.json — nothing to write.")

    # Report
    if args.report:
        Path(args.report).write_text(
            header + "\n" + "\n".join(all_logs) + summary, encoding="utf-8"
        )
        print(f"Report  : {args.report}")


if __name__ == "__main__":
    main()

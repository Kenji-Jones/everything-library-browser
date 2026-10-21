#!/usr/bin/env python3
"""Build the per-format library zips published as GitHub Release assets.

The site can already zip a selection in the browser, but doing that for the
whole library pulls every file through the host. These prebuilt archives are
the same thing, made once, so "download everything" costs the site nothing.

The layout matches what the browser's zip builder produces, so a release zip
and a select-all zip are interchangeable:

    EverythingLibrary/<Category>/<Subcategory>/<file>
    EverythingLibrary/LICENSE.txt
    EverythingLibrary/CREDITS.txt

Usage: python3 tools/build_release_zips.py [outdir]
"""

import json
import pathlib
import re
import sys
import zipfile

SITE = pathlib.Path(__file__).resolve().parent.parent / "EverythingLibraryBrowser"
ROOT = "EverythingLibrary/"
BAD = re.compile(r'[:*?"<>|]')


def js_number(x):
    """Format like JavaScript's Number#toString, which these factors rely on."""
    s = f"{x:.10f}".rstrip("0").rstrip(".")
    return s or "0"


def load():
    catalog = json.loads((SITE / "data" / "catalog.json").read_text())
    labels = {c["id"]: c["label"] for c in catalog["categories"]}
    for i, item in enumerate(catalog["items"]):
        item["_i"] = i
    return catalog, labels


def files_for(catalog, fmt):
    """Mirror selectedFiles() in assets/app.js for a whole-library selection."""
    out = []
    for item in catalog["items"]:
        if fmt == "blend":
            # One .blend per object holds every variant.
            out.append({"it": item, "v": item["variants"][0], "url": item["blend"]})
        else:
            for v in item["variants"]:
                out.append({"it": item, "v": v, "url": v[fmt]})
    return out


def credits(files, fmt, labels):
    canvas_cats = []
    for item in files:
        if item["it"].get("source"):
            label = labels.get(item["it"]["category"], item["it"]["category"])
            if label not in canvas_cats:
                canvas_cats.append(label)
    lines = [
        "Everything Library (c) David OReilly - http://davidoreilly.com/library",
        "Licensed CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/). "
        "Credit the author when you use these models.",
        "",
        f"{', '.join(canvas_cats)} models were sourced from Everything Canvas "
        "(https://everythingcanvas.vercel.app/)",
        "by Vince McKelvie. Their names and sizes are estimates.",
        "",
        f"{len(files)} {fmt.upper()} files:",
        "",
    ]
    for f in files:
        it, v = f["it"], f["v"]
        cat = labels.get(it["category"], it["category"])
        parts = [f["url"].split("/")[-1], it["name"], f"{cat} > {it['subcategoryLabel']}"]
        if it.get("source"):
            parts.append(f"from {it['source']} {', '.join(it['sourceFiles'])}")
        if v.get("magnified"):
            parts.append(
                f"scaled up {v['magnified']}x, multiply by "
                f"{js_number(1 / v['magnified'])} for real size"
            )
        lines.append("  |  ".join(parts))
    return "\n".join(lines) + "\n"


def build(fmt, outdir, catalog, labels):
    files = files_for(catalog, fmt)
    out = outdir / f"EverythingLibrary-{fmt}.zip"
    # .blend files are already compressed; GLB and FBX shrink a lot with deflate.
    mode = zipfile.ZIP_STORED if fmt == "blend" else zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(out, "w", allowZip64=True) as z:
        for f in files:
            cat = labels.get(f["it"]["category"], f["it"]["category"])
            name = f["url"].split("/")[-1]
            path = BAD.sub("", f"{cat}/{f['it']['subcategoryLabel']}/{name}")
            z.write(SITE / f["url"], ROOT + path, compress_type=mode)
        # Read as bytes: LICENSE.txt has CRLF endings, and the browser's
        # fetch().text() preserves them. read_text() would silently strip them.
        z.writestr(ROOT + "LICENSE.txt", (SITE / "LICENSE.txt").read_bytes(),
                   compress_type=zipfile.ZIP_DEFLATED)
        z.writestr(ROOT + "CREDITS.txt", credits(files, fmt, labels),
                   compress_type=zipfile.ZIP_DEFLATED)
    return out, len(files)


def main():
    outdir = pathlib.Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    outdir.mkdir(parents=True, exist_ok=True)
    catalog, labels = load()
    for fmt in ("glb", "fbx", "blend"):
        out, n = build(fmt, outdir, catalog, labels)
        print(f"{out.name}: {n} files, {out.stat().st_size / 1048576:.1f} MB")


if __name__ == "__main__":
    main()

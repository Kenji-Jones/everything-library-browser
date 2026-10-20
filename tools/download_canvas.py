"""Download the Everything Library categories that aren't in itchSourceFiles from Everything Canvas
(https://everythingcanvas.vercel.app, a drawing tool by Vince McKelvie that hosts the models as numbered GLBs).

    python3 download_canvas.py

Resumable: files already on disk are skipped. Downloads a few files at a time to go easy on the host.
"""
import os, sys, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

BASE = "https://everythingcanvas.vercel.app/extras/models/"
CATEGORIES = {  # display name: (site folder, model count from the site's main.js)
    "Microscopic": ("everything-microscopic", 226),
    "Plants": ("everything-plants", 486),
    "Underwater": ("everything-underwater", 107),
    "Trees": ("everything-trees", 273),
    "Human": ("everything-human", 330),
    "Vehicles": ("everything-vehicles", 83),
    "Zeometry": ("everything-geo", 297),
    "Space": ("everything-space", 265),
}
OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "canvasSourceFiles")


def fetch(job):
    url, path = job
    if os.path.exists(path) and os.path.getsize(path) > 0:
        return 0
    for attempt in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "EverythingLibraryBrowser/1.0 (personal archive)"})
            with urllib.request.urlopen(req, timeout=60) as r:
                data = r.read()
            if data[:4] != b"glTF":
                raise ValueError("not a GLB")
            with open(path + ".part", "wb") as f:
                f.write(data)
            os.replace(path + ".part", path)
            time.sleep(0.05)
            return len(data)
        except Exception as e:
            if attempt == 3:
                print("FAILED", url, e, flush=True)
                return -1
            time.sleep(2 * (attempt + 1))


jobs = []
for name, (folder, count) in CATEGORIES.items():
    os.makedirs(os.path.join(OUT, name), exist_ok=True)
    jobs += [(f"{BASE}{folder}/{i}.glb", os.path.join(OUT, name, f"{i}.glb")) for i in range(count)]

total, failed = 0, 0
with ThreadPoolExecutor(max_workers=4) as pool:
    for n, size in enumerate(pool.map(fetch, jobs), 1):
        if size < 0:
            failed += 1
        else:
            total += size
        if n % 200 == 0 or n == len(jobs):
            print(f"{n}/{len(jobs)} files, {total / 1e6:.1f} MB downloaded, {failed} failed", flush=True)
sys.exit(1 if failed else 0)

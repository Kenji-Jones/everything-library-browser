# Everything Library browser

A searchable, categorized site for David OReilly's Everything Library, with every object split into its own file.
The models are licensed CC BY 4.0, so credit "Everything Library © David OReilly" when you use them.

## Use it

Double-click `EverythingLibraryBrowser/Open Library.command`. It serves the folder at `http://localhost:8765` and
opens your browser. Close the Terminal window to stop it.

Opening `index.html` directly also works for browsing, searching and downloading. The 3D viewer needs the
local server, because browsers block loading model files from `file://`. The viewer loads three.js from
jsDelivr, so it needs an internet connection.

## Hosting

The site is live at <https://kenji-jones.github.io/everything-library-browser/>.

`.github/workflows/pages.yml` redeploys it on every push to `main`. Pages' branch deploy can only
serve the repository root or `/docs`, so the workflow publishes the `EverythingLibraryBrowser`
folder as the Pages artifact instead. Only that folder is served: `tools/` and the source packs
aren't reachable from the site.

It's about 525 MB, against GitHub Pages' 1 GB site limit and 100 GB/month soft bandwidth limit.
To host it elsewhere, publish the same folder on any static host; `netlify.toml` is kept as a
Netlify fallback.

## Downloading models

- **One file:** open any object to download it as GLB, FBX or .blend.
- **Several files:** tick the checkbox on each card, or use **Select all** to select everything currently
  shown: a category, a subcategory or a search. Shift-click a checkbox to select a range.
- **The selection:** it's kept across searches and reloads. The bar at the bottom picks the format and
  downloads everything as one zip, built in the browser, with folders per category and subcategory plus
  `LICENSE.txt` and `CREDITS.txt`.
- **Large selections:** in Chrome and Edge, selections over 150 MB stream straight to a file you choose, so
  even the whole library works. Other browsers build the zip in memory.
- **The whole library:** selecting everything hands over a prebuilt zip from the
  [latest release](https://github.com/Kenji-Jones/everything-library-browser/releases/latest) rather than
  rebuilding it in the browser — one fast download, and it costs the site no bandwidth. Same contents and
  layout as a select-all zip: 60 MB of GLB, 109 MB of FBX or 194 MB of .blend.

## What's in it

1,323 objects and 3,344 variants in 13 categories.

| Source | Categories |
|---|---|
| `itchSourceFiles/`: the original .blend packs, with authored names and sizes | Animals, Buildings, Consumables, Furnishings, Geology |
| `canvasSourceFiles/`: numbered GLBs downloaded from [Everything Canvas](https://everythingcanvas.vercel.app/) (Vince McKelvie) | Human-Made, Microscopic, Plants, Space, Trees, Underwater, Vehicles, Zeometry |

Each download contains:

- **Per variant:** a `.glb` and an `.fbx`, centered with the base at the origin, at scale 1.
- **Per object:** a `.blend` with all variants side by side.

### About the Everything Canvas categories

- **Names:** the canvas files had lost their names. Every model was named by eye from its thumbnail, and
  the names live in `canvasSourceFiles/<Category>/names.json`. Models with the same name and subcategory
  become variants of one object. Edit the JSON and rebuild to fix a name.
- **Simplified names:** `tools/simplify_names.py` swaps overly technical names for simple ones
  (Staphylococcus becomes Cluster Bacterium). The old name stays searchable.
- **Sizes:** the canvas had normalized every model to the same size. Sizes are now estimated real-world
  sizes, marked "≈" on the site. Abstract shapes, planets, nebulae and galaxies have no size.
- **Magnified models:** anything with a real size under 1 cm is exported scaled up by a power of ten, so it
  lands between 10 cm and 1 m. A bacterium is ×100,000 and a virus is ×1,000,000. The site shows the true size
  and the factor. Each exported object also carries `magnified` and `scale_to_real_size` custom properties
  (glTF extras, FBX and Blender custom props).
- **The "Human" category** is human-made objects (tools, toys, electronics, clothing), so the site labels it
  "Human-Made".

## Rebuild after changing anything

The source packs aren't in the repository (see `.gitignore`), only the hand-made `canvasSourceFiles/*/names.json`.
To rebuild, first restore them:

- `itchSourceFiles/`: the five category packs from https://itch.io/c/1250195/everything-library
  (Animals 002, Buildings 001, Consumables 002, Furnishings 001, Geology 001), one folder each.
- `canvasSourceFiles/`: run `python3 tools/download_canvas.py`.

Then:

```bash
tools/rebuild.sh
```

This takes about 3.5 minutes and needs Blender at `/Applications/Blender.app`, or set `BLENDER=/path/to/Blender`.

- `tools/export_library.py` splits a category `.blend` or a folder of canvas GLBs into objects. It fixes
  light and glass materials so vertex-alpha fades work, and renders EEVEE thumbnails.
- `tools/finalize_blends.py` links each per-object `.blend`'s collection into its scene. This works around a
  Blender 5.2 crash.
- `tools/build_catalog.py` builds the readable names, search keywords and the catalog.
- `tools/download_canvas.py` re-downloads the canvas categories. It's resumable and skips existing files.
- `tools/naming_sheets.py` makes numbered contact sheets for naming canvas models.
- `tools/build_release_zips.py` builds the per-format library zips published as release assets. Upload them
  with `gh release upload`, and update `RELEASE_ZIP` in `assets/app.js` if the sizes change.

## Known source quirks

- **Original-library sizes:** these are as authored, and some aren't realistic (e.g. Cricket 5.7 m).
- **Consumables units:** nine Consumables objects are in meters while the rest of that file is in
  centimeters. `SCALE_EXCEPTIONS` in `export_library.py` lists them.
- **Light beams:** they fade via vertex-color alpha. glTF can't store vertex-color emission, so in GLB/FBX
  they're faded but not glowing. The site's viewer and the `.blend` files render them glowing.

"""Second pass over the per-item .blend files written by export_library.py:
open each, link its collection into the scene, and save, so the model shows up when the file is opened.

    Blender -b --factory-startup --python finalize_blends.py -- <out_dir>
"""
import bpy, sys, glob, os

out = sys.argv[sys.argv.index("--") + 1]
files = sorted(glob.glob(os.path.join(out, "models", "*", "*", "*.blend")))
bpy.context.preferences.filepaths.save_version = 0  # don't leave .blend1 backups next to every file
for i, f in enumerate(files, 1):
    bpy.ops.wm.open_mainfile(filepath=f, load_ui=False)
    scene = bpy.context.scene
    for o in list(bpy.data.objects):
        if o.users_collection == () and o.type in {"CAMERA", "LIGHT"}:
            bpy.data.objects.remove(o)
    for coll in bpy.data.collections:
        if coll.name not in scene.collection.children:
            scene.collection.children.link(coll)
        coll.use_fake_user = False
    scene.name = os.path.splitext(os.path.basename(f))[0]
    bpy.ops.wm.save_mainfile(filepath=f, compress=True)
    if i % 50 == 0 or i == len(files):
        print(f"[finalize] {i}/{len(files)}", flush=True)

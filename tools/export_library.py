"""Split an Everything Library category .blend into individual models.

Run headless, one category file per process:
    Blender -b <Category>.blend --python export_library.py -- <out_dir> <Category> [scale]
or, for a folder of numbered GLBs (the Everything Canvas downloads), from an empty file:
    CANVAS_DIR=<folder> Blender -b --factory-startup --python export_library.py -- <out_dir> <Category>
CANVAS_DIR/names.json ({"<index>": {"name", "subcategory"}}) supplies names; models that share a
subcategory and name become variants of one object. Unnamed models are called "<Category> <n>".

For every object it writes, per variant:
    models/<category>/<item_id>/<item_id>_vN.glb   (web viewer + download)
    models/<category>/<item_id>/<item_id>_vN.fbx
    thumbs/<item_id>_vN.webp
and per item a .blend containing all variants laid out side by side.
Metadata goes to data/parts/<category>.json and is merged by build_catalog.py.
"""
import bpy, sys, os, re, json, math, time
from mathutils import Vector, Matrix

argv = sys.argv[sys.argv.index("--") + 1:]
OUT = os.path.abspath(argv[0])
CATEGORY = argv[1]
SCALE = float(argv[2]) if len(argv) > 2 else 1.0  # corrects files authored at a different unit scale
# Objects in a file that were authored in meters while the rest of that file is in centimeters.
SCALE_EXCEPTIONS = {
    "Consumables": {"ApplePie", "Baguette", "BananaBunch", "Cake", "MarketStand", "Pineapple",
                    "ProduceCrate", "Pumpkin", "WatermelonSlice"},
}
ONLY = os.environ.get("ONLY")
CANVAS_DIR = os.environ.get("CANVAS_DIR")  # optional comma list of item names, for testing

THUMB_SIZE = 384
ALT_RE = re.compile(r"^alt\d*", re.I)


def slug(s):
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


def log(*a):
    print(f"[{CATEGORY}]", *a, flush=True)


scene = bpy.context.scene
view_layer = bpy.context.view_layer

# ---------------------------------------------------------------- collect items
# item = {name, subcategory, tags, variants: [[mesh objects]]}
items = []


def meshes_in(o):
    return ([o] if o.type == "MESH" else []) + [c for c in o.children_recursive if c.type == "MESH"]


def variants_of(node):
    alts = [c for c in node.children if ALT_RE.match(c.name)]
    if len(alts) >= 2:
        shared = ([node] if node.type == "MESH" else []) + [
            m for c in node.children if not ALT_RE.match(c.name) for m in meshes_in(c)]
        out = [shared + meshes_in(a) for a in sorted(alts, key=lambda a: a.name)]
        return [v for v in out if v]
    v = meshes_in(node)
    return [v] if v else []


if CANVAS_DIR:
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    names_path = os.path.join(CANVAS_DIR, "names.json")
    names = json.load(open(names_path)) if os.path.exists(names_path) else {}
    files = sorted((f for f in os.listdir(CANVAS_DIR) if f.endswith(".glb")), key=lambda f: int(f[:-4]))
    groups = {}
    for f in files:
        idx = int(f[:-4])
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=os.path.join(CANVAS_DIR, f))
        meshes = [o for o in bpy.data.objects if o not in before and o.type == "MESH"]
        if not meshes:
            continue
        info = names.get(str(idx)) or {"name": f"{CATEGORY} {idx + 1}", "subcategory": "Unsorted"}
        # Everything Canvas normalised every model to the same size; rescale to an estimated real size.
        scale = 1.0
        if info.get("size_m"):
            pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
            extent = max(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3))
            scale = info["size_m"] / max(extent, 1e-9)
        key = (info["subcategory"], info["name"])
        groups.setdefault(key, []).append((idx, meshes, scale, bool(info.get("size_m")), info.get("aka"), info.get("size_m")))
    for (sub, name), members in groups.items():
        members.sort(key=lambda m: m[0])
        aka = sorted({m[4] for m in members if m[4]})  # names replaced by simplify_names.py stay searchable
        # Anything under 1 cm is scaled up by a power of ten (shared by all variants) so it lands between
        # 10 cm and 1 m: usable in a scene, and exactly reversible.
        real = max((m[5] for m in members if m[5]), default=None)
        magnify = 10 ** math.ceil(math.log10(0.1 / real)) if real and real < 0.01 else 1
        items.append({"name": name, "subcategory": sub, "tags": aka, "variants": [m[1] for m in members],
                      "scales": [m[2] * magnify for m in members], "sizeKnown": [m[3] for m in members],
                      "magnify": magnify,
                      "sourceFiles": [f"{m[0]}.glb" for m in members]})
elif CATEGORY == "Geology":
    # Geology is organised by collections; group objects by base name inside each leaf collection.
    seen = set()

    # Deepest collections first so objects linked to several collections land in the most specific one.
    def walk_deep_first(coll, top, path):
        for c in coll.children:
            walk_deep_first(c, top or c.name, path + [c.name])
        if coll is not scene.collection:
            walk_leaf(coll, top or coll.name, path)

    def walk_leaf(coll, top, path):
        groups = {}
        for o in coll.objects:
            if o.type != "MESH" or o.name in seen:
                continue
            seen.add(o.name)
            base = re.sub(r"_anim.*$", "", o.name)
            base = re.sub(r"(\.\d+)+$", "", base).rstrip(".")
            groups.setdefault(base, []).append(o)
        for base, objs in groups.items():
            items.append({
                "name": base,
                "subcategory": top,
                "tags": path[1:],
                "variants": [[o] for o in sorted(objs, key=lambda o: o.name)],
            })

    walk_deep_first(scene.collection, None, [])
else:
    roots = [o for o in bpy.data.objects if o.parent is None and o.type == "EMPTY"]
    if len(roots) == 1 and roots[0].name.upper() == roots[0].name:
        subcats = list(roots[0].children)  # e.g. ANIMALS -> Amphibians, Birds...
    else:
        subcats = roots  # Furnishings: roots are the subcategories
    for sub in sorted(subcats, key=lambda o: o.name):
        for node in sorted(sub.children, key=lambda o: o.name):
            vs = variants_of(node)
            if vs:
                items.append({"name": node.name, "subcategory": sub.name, "tags": [], "variants": vs})

if ONLY:
    keep = set(ONLY.split(","))
    items = [i for i in items if i["name"] in keep]
log(f"{len(items)} items, {sum(len(i['variants']) for i in items)} variants")

# ---------------------------------------------------------------- scene setup
for o in bpy.data.objects:
    o.hide_render = True

work = bpy.data.collections.new("__export")
scene.collection.children.link(work)

cam_data = bpy.data.cameras.new("__thumbcam")
cam_data.lens = 50
cam = bpy.data.objects.new("__thumbcam", cam_data)
work.objects.link(cam)
scene.camera = cam

r = scene.render
r.engine = "BLENDER_EEVEE"
r.resolution_x = r.resolution_y = THUMB_SIZE
r.resolution_percentage = 100
r.film_transparent = True
r.image_settings.file_format = "WEBP"
r.image_settings.color_mode = "RGBA"
r.image_settings.quality = 88
scene.eevee.taa_render_samples = 32
scene.view_settings.view_transform = "Standard"

# Soft grey sky for fill plus a key light from the front-left, so thumbnails read like a studio shot.
world = bpy.data.worlds.new("__thumbworld")
world.use_nodes = True
bg = world.node_tree.nodes.get("Background")
bg.inputs["Color"].default_value = (0.62, 0.64, 0.68, 1)
bg.inputs["Strength"].default_value = 1.0
scene.world = world
sun_data = bpy.data.lights.new("__thumbsun", "SUN")
sun_data.energy = 2.6
sun_data.angle = math.radians(12)
sun = bpy.data.objects.new("__thumbsun", sun_data)
sun.rotation_euler = (math.radians(50), 0, math.radians(-35))
work.objects.link(sun)

# ---------------------------------------------------------------- material fixes
# The library stores light-beam fades and transparency in vertex-colour alpha, but only some files wire it up.
# Normalise every light/transparent material so the alpha (and light emission) is used everywhere.
FADE_RE = re.compile(r"Light|Transp|WaterFountain", re.I)


def fading_material_names():
    """Material names where a mesh actually varies vertex-colour alpha.

    Names promise transparency far more often than meshes use it: every Canvas model is
    Mat_ParticleTransp while being fully opaque. Marking those BLENDED exports them as
    glTF alphaMode BLEND, and viewers then draw their double-sided triangles unsorted,
    which reads as inverted normals. This is the same trap the opaque branch below warns
    about, so decide from the alpha actually stored, not from the name.
    """
    names = set()
    for mesh in bpy.data.meshes:
        attr = mesh.color_attributes.active_color
        if not attr or not mesh.materials:
            continue
        for poly in mesh.polygons:
            if poly.material_index >= len(mesh.materials):
                continue
            mat = mesh.materials[poly.material_index]
            if not mat or mat.name in names:
                continue
            for li in poly.loop_indices:
                idx = li if attr.domain == "CORNER" else mesh.loops[li].vertex_index
                if attr.data[idx].color[3] < 0.999:
                    names.add(mat.name)
                    break
    return names


def fix_material(mat):
    if not mat.use_nodes or not mat.node_tree:
        return
    nt = mat.node_tree
    bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
    if not bsdf:
        return
    vc = next((n for n in nt.nodes if n.type == "VERTEX_COLOR"), None)
    if not vc:
        vc = nt.nodes.new("ShaderNodeVertexColor")
        vc.location = (bsdf.location.x - 300, bsdf.location.y)
    if not bsdf.inputs["Base Color"].is_linked:
        nt.links.new(vc.outputs["Color"], bsdf.inputs["Base Color"])
    if FADE_RE.search(mat.name) and ("light" in mat.name.lower() or mat.name in FADES):
        if not bsdf.inputs["Alpha"].is_linked:
            nt.links.new(vc.outputs["Alpha"], bsdf.inputs["Alpha"])
        mat.surface_render_method = "BLENDED"
        mat.use_transparency_overlap = True
        if "light" in mat.name.lower():
            if not bsdf.inputs["Emission Color"].is_linked:
                nt.links.new(vc.outputs["Color"], bsdf.inputs["Emission Color"])
            mat.use_backface_culling = False
            LIGHT_SOCKETS.append(bsdf.inputs["Emission Strength"])
            return
    else:
        # Opaque materials: some files mark them Blended, which makes glTF viewers depth-sort them badly.
        for l in list(bsdf.inputs["Alpha"].links):
            nt.links.remove(l)
        bsdf.inputs["Alpha"].default_value = 1.0
        mat.surface_render_method = "DITHERED"
    # Stray emission settings would export as a flat white glow.
    for l in list(bsdf.inputs["Emission Color"].links):
        nt.links.remove(l)
    bsdf.inputs["Emission Strength"].default_value = 0.0


def set_light_emission(on):
    """Light materials glow via vertex colour -> Emission. glTF/FBX can't express that and would write a
    flat white glow, so emission is switched off while exporting and on for thumbnails and .blend files."""
    for sock in LIGHT_SOCKETS:
        sock.default_value = 1.0 if on else 0.0


LIGHT_SOCKETS = []
TRANSP_MATS = set()
FADES = fading_material_names()
for mat in bpy.data.materials:
    fix_material(mat)
    if FADE_RE.search(mat.name) and "light" not in mat.name.lower():
        TRANSP_MATS.add(mat.name)

MIN_GLASS_ALPHA = 0.3  # some glass is authored nearly invisible (alpha ~0.05); keep it readable


def clean_color_attributes(mesh):
    """Keep only the colour layer that was actually painted.

    A few source meshes carry a half-filled duplicate layer: wherever nobody painted
    it, it stays pure white with alpha 1. Blender renders the active one, but glTF
    writes every layer in order, so the blank one can land in COLOR_0 — the only slot
    most viewers read — and the model arrives white. Score by how little pure white a
    layer holds, then by whether it carries real alpha.
    """
    if len(mesh.color_attributes) < 2:
        return
    best, best_score = None, None
    for a in mesh.color_attributes:
        white = sum(1 for d in a.data if min(d.color[:3]) > 0.97)
        has_alpha = 1 if any(d.color[3] < 0.999 for d in a.data) else 0
        score = (-white / max(len(a.data), 1), has_alpha)
        if best_score is None or score > best_score:
            best, best_score = a.name, score
    for a in list(mesh.color_attributes):
        if a.name != best:
            mesh.color_attributes.remove(a)
    mesh.color_attributes.active_color_name = best
    mesh.color_attributes.default_color_name = best


def floor_glass_alpha(mesh):
    attr = mesh.color_attributes.active_color
    if not attr or not TRANSP_MATS:
        return
    slots = {i for i, m in enumerate(mesh.materials) if m and m.name in TRANSP_MATS}
    if not slots:
        return
    for poly in mesh.polygons:
        if poly.material_index not in slots:
            continue
        for li in poly.loop_indices:
            idx = li if attr.domain == "CORNER" else mesh.loops[li].vertex_index
            c = attr.data[idx].color
            if c[3] < MIN_GLASS_ALPHA:
                attr.data[idx].color = (c[0], c[1], c[2], MIN_GLASS_ALPHA)

CAM_DIR = Vector((0.62, -0.78, 0.42)).normalized()  # three-quarter view from the front-right, slightly above
WORLD_UP = Vector((0, 0, 1))


def frame_camera(objs):
    pts = [o.matrix_world @ Vector(c) for o in objs for c in o.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    center = (mn + mx) / 2
    fwd = CAM_DIR
    right = fwd.cross(WORLD_UP).normalized()
    up = right.cross(fwd).normalized()
    t = math.tan(cam_data.angle / 2) * 0.88
    D = 0.0
    for p in pts:
        rel = p - center
        depth_off = rel.dot(fwd)
        D = max(D, depth_off + abs(rel.dot(right)) / t, depth_off + abs(rel.dot(up)) / t)
    D = max(D, 1e-3)
    cam.location = center + fwd * D
    cam.rotation_euler = (-fwd).to_track_quat("-Z", "Y").to_euler()
    span = (mx - mn).length
    cam_data.clip_start = max(D - span, D * 0.001, 1e-4)
    cam_data.clip_end = D + span * 2


def make_copies(meshes, label, scale):
    """Copy the variant's meshes into the work collection, re-centred (bottom-centre at origin) and unit-corrected."""
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    mn = Vector([min(p[i] for p in pts) for i in range(3)])
    mx = Vector([max(p[i] for p in pts) for i in range(3)])
    pivot = Vector(((mn.x + mx.x) / 2, (mn.y + mx.y) / 2, mn.z))
    fix = Matrix.Scale(scale, 4) @ Matrix.Translation(-pivot)
    copies = []
    for i, o in enumerate(meshes):
        c = o.copy()
        for m in [m for m in c.modifiers if m.type == "PARTICLE_SYSTEM"]:
            c.modifiers.remove(m)
        c.parent = None
        c.animation_data_clear()
        # Bake the transform into a private mesh copy so exports have identity transforms (scale 1, no rotation).
        mat = fix @ o.matrix_world
        c.data = o.data.copy()
        c.data.transform(mat)
        clean_color_attributes(c.data)
        floor_glass_alpha(c.data)
        if mat.determinant() < 0:
            c.data.flip_normals()
        c.matrix_world = Matrix.Identity(4)
        part = re.sub(r"[.]\d+$", "", o.name)
        c.name = label if len(meshes) == 1 else f"{label}_{part}"
        work.objects.link(c)
        c.hide_viewport = False
        c.hide_render = True
        copies.append(c)
    dims = [float(f"{(mx[i] - mn[i]) * scale:.4g}") for i in range(3)]
    tris = sum(sum(max(len(p.vertices) - 2, 1) for p in o.data.polygons) for o in meshes)
    return copies, dims, tris


def select_only(objs):
    for o in view_layer.objects:
        if o.select_get():
            o.select_set(False)
    for o in objs:
        o.select_set(True)
    view_layer.objects.active = objs[0]


def export_gltf(path):
    kw = dict(filepath=path, export_format="GLB", use_selection=True, export_apply=True,
              export_yup=True, export_materials="EXPORT", export_cameras=False, export_lights=False,
              export_animations=False, export_extras=True)
    try:
        bpy.ops.export_scene.gltf(export_vertex_color="ACTIVE", **kw)
    except TypeError:
        bpy.ops.export_scene.gltf(**kw)


def export_gltf_split(path, copies):
    """Export glTF from per-material duplicates.

    The exporter cannot hold per-material vertex colours on one mesh — it warns
    "glTF specification does not allow this case" and silently writes white — so give
    it one material per mesh. The duplicates are thrown away afterwards, leaving the
    originals intact for the FBX export and the thumbnail render.
    """
    select_only(copies)
    bpy.ops.object.duplicate()
    parts = []
    for d in list(bpy.context.selected_objects):
        select_only([d])
        if len(d.data.materials) > 1:
            bpy.ops.object.mode_set(mode="EDIT")
            bpy.ops.mesh.select_all(action="SELECT")
            bpy.ops.mesh.separate(type="MATERIAL")
            bpy.ops.object.mode_set(mode="OBJECT")
            parts.extend(bpy.context.selected_objects)
        else:
            parts.append(d)
    select_only(parts)
    export_gltf(path)
    select_only(parts)
    bpy.ops.object.delete()


def export_fbx(path):
    bpy.ops.export_scene.fbx(filepath=path, use_selection=True, object_types={"MESH"},
                             use_mesh_modifiers=True, apply_scale_options="FBX_SCALE_UNITS",
                             colors_type="SRGB", bake_anim=False, path_mode="AUTO", use_custom_props=True)


# ---------------------------------------------------------------- export loop
cat_slug = slug(CATEGORY)
os.makedirs(os.path.join(OUT, "thumbs"), exist_ok=True)
os.makedirs(os.path.join(OUT, "data", "parts"), exist_ok=True)
records = []
used_ids = set()
t0 = time.time()

for n, item in enumerate(items, 1):
    item_id = f"{cat_slug}-{slug(item['subcategory'])}-{slug(item['name'])}"
    while item_id in used_ids:
        item_id += "-x"
    used_ids.add(item_id)
    rel_dir = f"models/{cat_slug}/{item_id}"
    os.makedirs(os.path.join(OUT, rel_dir), exist_ok=True)

    variant_records, all_copies = [], []
    for vi, meshes in enumerate(item["variants"], 1):
        label = f"{item['name']}_v{vi}" if len(item["variants"]) > 1 else item["name"]
        if "scales" in item:
            scale = item["scales"][vi - 1]
        else:
            scale = 1.0 if item["name"] in SCALE_EXCEPTIONS.get(CATEGORY, ()) else SCALE
        copies, dims, tris = make_copies(meshes, label, scale)
        magnify = item.get("magnify", 1)
        if magnify > 1:
            for c in copies:  # exported as glTF extras / FBX custom properties
                c["magnified"] = magnify
                c["scale_to_real_size"] = 1 / magnify
        all_copies.append(copies)
        base = f"{item_id}_v{vi}"

        select_only(copies)
        set_light_emission(False)
        export_fbx(os.path.join(OUT, rel_dir, base + ".fbx"))
        export_gltf_split(os.path.join(OUT, rel_dir, base + ".glb"), copies)

        set_light_emission(True)
        # Render at a ~1 m working scale so microscopic or huge models frame and light like everything else.
        k = 1.0 / max(max(dims), 1e-9)
        for c in copies:
            c.hide_render = False
            c.matrix_world = Matrix.Scale(k, 4)
        frame_camera(copies)
        r.filepath = os.path.join(OUT, "thumbs", base + ".webp")
        bpy.ops.render.render(write_still=True)
        for c in copies:
            c.hide_render = True
            c.matrix_world = Matrix.Identity(4)

        variant_records.append({
            "glb": f"{rel_dir}/{base}.glb",
            "fbx": f"{rel_dir}/{base}.fbx",
            "thumb": f"thumbs/{base}.webp",
            "dims": dims,
            "tris": tris,
            "parts": len(copies),
            # Canvas models: sizes are estimates, or unknown where no estimate was given.
            **({"size": "estimated" if item["sizeKnown"][vi - 1] else "unknown"} if "sizeKnown" in item else {}),
            **({"magnified": item["magnify"]} if item.get("magnify", 1) > 1 else {}),
        })

    # One .blend per item with every variant side by side along X.
    x = 0.0
    item_coll = bpy.data.collections.new(item["name"])
    for copies, vr in zip(all_copies, variant_records):
        w = vr["dims"][0]
        for c in copies:
            c.matrix_world = Matrix.Translation((x + w / 2, 0, 0)) @ c.matrix_world
            c.hide_render = False
            item_coll.objects.link(c)
        x += w + max(w * 0.25, 0.1)
    blend_rel = f"{rel_dir}/{item_id}.blend"
    # Writing a Scene here crashes Blender 5.2, so write the collection; finalize_blends.py links it into a scene.
    bpy.data.libraries.write(os.path.join(OUT, blend_rel), {item_coll}, path_remap="RELATIVE_ALL",
                             fake_user=True, compress=True)
    bpy.data.collections.remove(item_coll)
    for copies in all_copies:
        for c in copies:
            mesh = c.data
            bpy.data.objects.remove(c, do_unlink=True)
            bpy.data.meshes.remove(mesh)

    records.append({
        "id": item_id,
        "name": item["name"],
        "category": CATEGORY,
        "subcategory": item["subcategory"],
        "tags": item["tags"],
        "blend": blend_rel,
        "variants": variant_records,
        **({"sourceFiles": item["sourceFiles"], "source": "Everything Canvas"} if "sourceFiles" in item else {}),
    })
    if n % 10 == 0 or n == len(items):
        log(f"{n}/{len(items)}  {time.time() - t0:.0f}s")

with open(os.path.join(OUT, "data", "parts", f"{cat_slug}.json"), "w") as f:
    json.dump(records, f, indent=1)
log("done")

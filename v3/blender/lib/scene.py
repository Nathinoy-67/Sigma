"""scene.py -- fresh scene, Cycles settings, colour management, output, lights.

Shared framework for "ONE YEAR. ONE SECOND." (v3).  Import with

    import sys; sys.path.insert(0, "/home/user/Sigma/v3/blender/lib")
    import scene as S

Everything is in metres (true scale: a shot glass is 0.06 m tall).

Main entry points
-----------------
new_scene(res="look", preset="default", ...)  wipe all data, configure Cycles CPU + OIDN + AgX
set_resolution(res)                           "look" 640x268 | "previs" 960x402 | "final" 1920x804 | (w, h)
set_quality(samples, threshold, min_samples)  adaptive sampling
set_bounces(preset_or_dict)                   "default" (non-glass sets) | "glass" (glass shots)
world(color, strength) / world_image(path)    background (world_image: our own equirect panorama EXR)
kelvin(K) -> (r, g, b)                        linear-sRGB colour of a black body, max channel = 1
area_light / spot_light / point_light / sun_light   lights aimed with `target=`, colour by `kelvin=`
light_group(obj, name)                        assign a Cycles light group (created on the view layer)
light_link(light, exclude=[..]|include=[..])  Cycles light linking (e.g. keep a rim off the table top)
enable_passes(mist, depth, crypto, ...)       render passes for comp
look_at(obj, target, roll=0)                  point -Z of obj at target (lights and cameras)
collection(name) / link(obj, coll)            collection helpers
render_still(path) -> seconds                 render the current frame to PNG/JPEG/EXR (by extension)
render_frames(out_dir, start, end, step)      render an animation range to <out_dir>/<prefix>####.png
save_blend(path)                              save the built scene for inspection
"""
import math
import os
import random
import time

import bpy

# --------------------------------------------------------------------------- paths
LIB_DIR = os.path.dirname(os.path.abspath(__file__))
BLENDER_DIR = os.path.dirname(LIB_DIR)                 # v3/blender
V3_DIR = os.path.dirname(BLENDER_DIR)                  # v3
TEXTURES = os.path.join(BLENDER_DIR, "textures")       # PIL-drawn artwork and baked maps
FRAMES = os.path.join(V3_DIR, "frames")                # rendered frames (git-ignored)
LOOKDEV = os.path.join(V3_DIR, "lookdev")              # small look-dev stills
FONTS = {
    "inter": "/usr/share/fonts/opentype/inter/Inter-Regular.otf",
    "inter_italic": "/usr/share/fonts/opentype/inter/Inter-Italic.otf",
    "inter_medium": "/usr/share/fonts/opentype/inter/Inter-Medium.otf",
    "inter_semibold": "/usr/share/fonts/opentype/inter/Inter-SemiBold.otf",
    "inter_bold": "/usr/share/fonts/opentype/inter/Inter-Bold.otf",
    "display_black": "/usr/share/fonts/opentype/inter/InterDisplay-Black.otf",
    "display_extrabold": "/usr/share/fonts/opentype/inter/InterDisplay-ExtraBold.otf",
    "display_bold": "/usr/share/fonts/opentype/inter/InterDisplay-Bold.otf",
    "display_medium": "/usr/share/fonts/opentype/inter/InterDisplay-Medium.otf",
    "display_light_italic": "/usr/share/fonts/opentype/inter/InterDisplay-LightItalic.otf",
    "display_italic": "/usr/share/fonts/opentype/inter/InterDisplay-Italic.otf",
    "liberation_bold": "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "liberation": "/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf",
    "jetbrains": "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Regular.ttf",
    "jetbrains_bold": "/usr/share/fonts/truetype/jetbrains-mono/JetBrainsMono-Bold.ttf",
    "courier": "/usr/share/fonts/X11/Type1/c0419bt_.pfb",
}

# --------------------------------------------------------------------------- presets
RES = {"look": (640, 268), "previs": (960, 402), "final": (1920, 804)}

QUALITY = {   # adaptive sampling per resolution class
    "look": dict(samples=16, threshold=0.05, min_samples=8),
    "previs": dict(samples=12, threshold=0.1, min_samples=4),
    "final": dict(samples=96, threshold=0.025, min_samples=16),
}

BOUNCES = {
    # non-glass sets (workroom, cellar, hold, lodge room)
    "default": dict(max=12, diffuse=3, glossy=3, transmission=6, transparent=8, volume=0),
    # glass shots (glass stage, back bar, packshot)
    "glass": dict(max=16, diffuse=2, glossy=4, transmission=12, transparent=16, volume=0),
}

DEFAULT_LOOK = "AgX - Medium High Contrast"


def seed_all(seed=0):
    """Seed Python's and numpy's RNGs (every generator also takes its own seed)."""
    random.seed(seed)
    try:
        import numpy as np
        np.random.seed(seed % (2 ** 32))
    except ImportError:
        pass


# --------------------------------------------------------------------------- scene
def new_scene(res="look", preset="default", samples=None, threshold=None, min_samples=None,
              fps=24, exposure=0.0, look=DEFAULT_LOOK, seed=0, persistent=True, guiding=False,
              clamp_indirect=4.0, filter_glossy=1.0, light_tree=True, threads=0):
    """Wipe every datablock and return a fresh Cycles scene configured to the production rules.

    res      "look" | "previs" | "final" | (w, h).  Also picks default sampling (QUALITY).
    preset   bounce preset: "default" or "glass" (see BOUNCES), or a dict.
    samples/threshold/min_samples override the QUALITY preset.
    exposure film exposure in stops (AgX view transform, `look` = AgX look name or "None").
    """
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    sc.name = "Scene"
    seed_all(seed)
    sc.render.engine = "CYCLES"
    cy = sc.cycles
    cy.device = "CPU"
    cy.seed = seed
    cy.use_animated_seed = True
    cy.use_light_tree = light_tree
    cy.caustics_reflective = False
    cy.caustics_refractive = False
    cy.blur_glossy = filter_glossy
    cy.sample_clamp_direct = 0.0
    cy.sample_clamp_indirect = clamp_indirect
    cy.use_guiding = guiding
    cy.volume_step_rate = 1.0
    cy.film_exposure = 1.0
    cy.pixel_filter_type = "BLACKMAN_HARRIS"
    cy.filter_width = 1.5
    cy.tile_size = 2048
    sc.render.use_persistent_data = persistent
    sc.render.threads_mode = "FIXED" if threads else "AUTO"
    if threads:
        sc.render.threads = threads
    sc.render.fps = fps
    sc.render.fps_base = 1.0
    sc.render.film_transparent = False
    sc.render.use_compositing = False
    sc.render.use_sequencer = False
    sc.unit_settings.system = "METRIC"
    sc.unit_settings.scale_length = 1.0
    # colour management: AgX
    sc.display_settings.display_device = "sRGB"
    sc.view_settings.view_transform = "AgX"
    sc.view_settings.look = look
    sc.view_settings.exposure = exposure
    sc.view_settings.gamma = 1.0
    sc.sequencer_colorspace_settings.name = "sRGB"
    set_resolution(res)
    q = QUALITY.get(res if isinstance(res, str) else "look")
    set_quality(samples if samples is not None else q["samples"],
                threshold if threshold is not None else q["threshold"],
                min_samples if min_samples is not None else q["min_samples"])
    set_bounces(preset)
    # denoiser: OIDN with albedo + normal
    cy.use_denoising = True
    cy.denoiser = "OPENIMAGEDENOISE"
    cy.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    cy.denoising_prefilter = "ACCURATE"
    try:
        cy.denoising_quality = "HIGH"
    except (AttributeError, TypeError):
        pass
    # an empty world so nothing is lit by Blender's default grey
    world((0.0, 0.0, 0.0), 0.0)
    sc.frame_start, sc.frame_end, sc.frame_current = 0, 0, 0
    return sc


def set_resolution(res, percent=100):
    sc = bpy.context.scene
    w, h = RES[res] if isinstance(res, str) else res
    sc.render.resolution_x, sc.render.resolution_y = int(w), int(h)
    sc.render.resolution_percentage = percent
    sc.render.pixel_aspect_x = sc.render.pixel_aspect_y = 1.0
    return w, h


def set_quality(samples=16, threshold=0.05, min_samples=8, time_limit=0.0):
    cy = bpy.context.scene.cycles
    cy.samples = int(samples)
    cy.use_adaptive_sampling = True
    cy.adaptive_threshold = float(threshold)
    cy.adaptive_min_samples = int(min(min_samples, samples))
    cy.time_limit = time_limit


def set_bounces(preset="default"):
    b = BOUNCES[preset] if isinstance(preset, str) else preset
    cy = bpy.context.scene.cycles
    cy.max_bounces = b.get("max", 12)
    cy.diffuse_bounces = b.get("diffuse", 3)
    cy.glossy_bounces = b.get("glossy", 3)
    cy.transmission_bounces = b.get("transmission", 6)
    cy.transparent_max_bounces = b.get("transparent", 8)
    cy.volume_bounces = b.get("volume", 0)
    return b


# --------------------------------------------------------------------------- world
def world(color=(0.0, 0.0, 0.0), strength=1.0, name="World"):
    """Uniform background colour (linear RGB).  Returns the world."""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new(name)
    sc.world = w
    nt = w.node_tree if w.node_tree else None
    if nt is None:
        w.use_nodes = True
        nt = w.node_tree
    nt.nodes.clear()
    bg = nt.nodes.new("ShaderNodeBackground")
    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg.inputs["Color"].default_value = (*color[:3], 1.0)
    bg.inputs["Strength"].default_value = strength
    nt.links.new(bg.outputs[0], out.inputs["Surface"])
    return w


def world_image(path, strength=1.0, rotation_z_deg=0.0, camera_strength=None):
    """Equirectangular world from one of OUR renders (e.g. the Set E panorama EXR).
    camera_strength: if given, what the camera sees directly (e.g. 0 to hide it)."""
    sc = bpy.context.scene
    w = sc.world or bpy.data.worlds.new("World")
    sc.world = w
    if w.node_tree is None:
        w.use_nodes = True
    nt = w.node_tree
    nt.nodes.clear()
    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Rotation"].default_value = (0, 0, math.radians(rotation_z_deg))
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    env.image = bpy.data.images.load(path, check_existing=True)
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    out = nt.nodes.new("ShaderNodeOutputWorld")
    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs[0], env.inputs["Vector"])
    nt.links.new(env.outputs[0], bg.inputs["Color"])
    if camera_strength is None:
        nt.links.new(bg.outputs[0], out.inputs["Surface"])
    else:
        lp = nt.nodes.new("ShaderNodeLightPath")
        bg2 = nt.nodes.new("ShaderNodeBackground")
        bg2.inputs["Strength"].default_value = camera_strength
        nt.links.new(env.outputs[0], bg2.inputs["Color"])
        mix = nt.nodes.new("ShaderNodeMixShader")
        nt.links.new(lp.outputs["Is Camera Ray"], mix.inputs[0])
        nt.links.new(bg.outputs[0], mix.inputs[1])
        nt.links.new(bg2.outputs[0], mix.inputs[2])
        nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return w


# --------------------------------------------------------------------------- colour
def kelvin(K):
    """Linear-sRGB RGB of a black body at K kelvin, normalised so max channel = 1.
    (Tanner Helland fit, converted from display sRGB to linear.)"""
    t = K / 100.0
    if t <= 66:
        r = 255.0
        g = 99.4708025861 * math.log(t) - 161.1195681661
        b = 0.0 if t <= 19 else 138.5177312231 * math.log(t - 10) - 305.0447927307
    else:
        r = 329.698727446 * ((t - 60) ** -0.1332047592)
        g = 288.1221695283 * ((t - 60) ** -0.0755148492)
        b = 255.0
    rgb = [min(max(c, 0.0), 255.0) / 255.0 for c in (r, g, b)]
    lin = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in rgb]
    m = max(lin)
    return tuple(c / m for c in lin)


def hex_rgb(h):
    """'#FF4F9A' -> linear RGB tuple."""
    h = h.lstrip("#")
    c = [int(h[i:i + 2], 16) / 255.0 for i in (0, 2, 4)]
    return tuple(v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in c)


# --------------------------------------------------------------------------- helpers
def look_at(obj, target, roll=0.0):
    """Rotate obj so its -Z axis points at `target` (point or object), +Y up, then roll (degrees)."""
    from mathutils import Vector, Matrix
    tgt = target.matrix_world.translation if hasattr(target, "matrix_world") else Vector(target)
    d = tgt - obj.location
    q = d.to_track_quat("-Z", "Y")
    if roll:
        q = q @ Matrix.Rotation(math.radians(roll), 4, "Z").to_quaternion()
    obj.rotation_mode = "XYZ"
    obj.rotation_euler = q.to_euler()
    return obj


def collection(name, parent=None):
    """Get or create a collection linked under `parent` (default: scene root)."""
    c = bpy.data.collections.get(name)
    if c is None:
        c = bpy.data.collections.new(name)
    par = parent.children if parent else bpy.context.scene.collection.children
    if c.name not in par:
        par.link(c)
    return c


def link(obj, coll=None):
    """Link obj into coll (default scene root), removing it from any other collection."""
    coll = coll or bpy.context.scene.collection
    for c in list(obj.users_collection):
        if c != coll:
            c.objects.unlink(obj)
    if obj.name not in coll.objects:
        coll.objects.link(obj)
    return obj


def empty(name, location=(0, 0, 0), size=0.02, coll=None, kind="PLAIN_AXES"):
    e = bpy.data.objects.new(name, None)
    e.empty_display_type = kind
    e.empty_display_size = size
    e.location = location
    link(e, coll)
    return e


def _light(kind, name, power, color, kelvin_, location, target, coll):
    ld = bpy.data.lights.new(name, kind)
    ld.energy = power
    if kelvin_:
        ld.color = kelvin(kelvin_)
    elif color is not None:
        ld.color = color[:3]
    ob = bpy.data.objects.new(name, ld)
    ob.location = location
    link(ob, coll)
    if target is not None:
        look_at(ob, target)
    return ob


def area_light(name="Area", size=(0.5, 0.5), power=50.0, kelvin=None, color=None, location=(0, 0, 1),
               target=(0, 0, 0), shape="RECTANGLE", spread_deg=180.0, camera_visible=False,
               glossy_visible=True, coll=None, group=None, transmission_visible=False):
    """Area light (power in W).  size=(x, y) metres.  spread_deg < 180 = gridded softbox."""
    ob = _light("AREA", name, power, color, kelvin, location, target, coll)
    ld = ob.data
    ld.shape = shape
    ld.size, ld.size_y = size[0], size[1]
    ld.spread = math.radians(spread_deg)
    ob.visible_camera = camera_visible
    ob.visible_glossy = glossy_visible
    ob.visible_transmission = transmission_visible     # seen through glass a softbox reads as a white slab
    if group:
        light_group(ob, group)
    return ob


def spot_light(name="Spot", power=100.0, kelvin=None, color=None, location=(0, 0, 1), target=(0, 0, 0),
               angle_deg=40.0, blend=0.3, radius=0.02, coll=None, group=None):
    ob = _light("SPOT", name, power, color, kelvin, location, target, coll)
    ob.data.spot_size = math.radians(angle_deg)
    ob.data.spot_blend = blend
    ob.data.shadow_soft_size = radius
    if group:
        light_group(ob, group)
    return ob


def point_light(name="Point", power=10.0, kelvin=None, color=None, location=(0, 0, 1), radius=0.01,
                coll=None, group=None):
    ob = _light("POINT", name, power, color, kelvin, location, None, coll)
    ob.data.shadow_soft_size = radius
    if group:
        light_group(ob, group)
    return ob


def sun_light(name="Sun", strength=3.0, kelvin=None, color=None, azimuth_deg=0.0, elevation_deg=30.0,
              angle_deg=0.53, coll=None, group=None):
    """Sun from compass azimuth (0 = +Y/north, 90 = +X/east) and elevation, strength in W/m^2."""
    ob = _light("SUN", name, strength, color, kelvin, (0, 0, 5), None, coll)
    ob.data.angle = math.radians(angle_deg)
    az, el = math.radians(azimuth_deg), math.radians(elevation_deg)
    d = (math.sin(az) * math.cos(el), math.cos(az) * math.cos(el), math.sin(el))  # towards the sun
    look_at(ob, (ob.location[0] - d[0], ob.location[1] - d[1], ob.location[2] - d[2]))
    if group:
        light_group(ob, group)
    return ob


def light_group(obj, name):
    """Put a light (or emissive object) into a Cycles light group (pass named Combined_<name>)."""
    vl = bpy.context.view_layer
    if name not in [g.name for g in vl.lightgroups]:
        vl.lightgroups.add(name=name)
    obj.lightgroup = name
    return obj


def light_link(light, exclude=(), include=None):
    """Cycles light linking.  include=[objs]: ONLY these receive the light.  exclude=[objs]: everything
    but these receives it (e.g. keep a rim light's streak out of a glossy table top)."""
    c = bpy.data.collections.new(light.name + "_receivers")
    objs = list(include) if include is not None else list(exclude)
    for o in objs:
        c.objects.link(o)
    light.light_linking.receiver_collection = c
    if include is None:
        for co in c.collection_objects:
            co.light_linking.link_state = "EXCLUDE"
    return c


def enable_passes(mist=False, depth=False, crypto=False, albedo=False, normal=False, mist_range=(0.1, 20.0)):
    vl = bpy.context.view_layer
    vl.use_pass_mist = mist
    vl.use_pass_z = depth
    vl.use_pass_cryptomatte_object = crypto
    vl.use_pass_cryptomatte_material = crypto
    vl.use_pass_diffuse_color = albedo
    vl.use_pass_normal = normal
    if mist:
        sc = bpy.context.scene
        if sc.world is None:
            world()
        sc.world.mist_settings.start, sc.world.mist_settings.depth = mist_range
        sc.world.mist_settings.falloff = "QUADRATIC"


# --------------------------------------------------------------------------- output
_EXT = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".exr": "OPEN_EXR"}


def set_output(path, fmt=None, quality=92, color_depth=None):
    """Configure output format from the file extension (or `fmt`)."""
    sc = bpy.context.scene
    ext = os.path.splitext(path)[1].lower()
    fmt = fmt or _EXT.get(ext, "PNG")
    s = sc.render.image_settings
    s.file_format = fmt
    if fmt == "JPEG":
        s.color_mode = "RGB"
        s.quality = quality
    elif fmt == "PNG":
        s.color_mode = "RGB"
        s.color_depth = color_depth or "16"
        s.compression = 15
    elif fmt == "OPEN_EXR":
        s.color_mode = "RGBA"
        s.color_depth = color_depth or "16"
        s.exr_codec = "DWAA"
    sc.render.filepath = path
    sc.render.use_file_extension = False   # paths always carry their extension
    return fmt


def render_still(path, frame=None, quiet=True):
    """Render the current (or given) frame to `path`.  Returns wall-clock seconds."""
    sc = bpy.context.scene
    path = os.path.abspath(path)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    if frame is not None:
        sc.frame_set(frame)
    set_output(path)
    sc.render.use_file_extension = False
    t = time.time()
    bpy.ops.render.render(write_still=True)
    dt = time.time() - t
    if not quiet:
        print(f"[render] {path}  {sc.render.resolution_x}x{sc.render.resolution_y}  {dt:.1f}s", flush=True)
    return dt


def render_frames(out_dir, start, end, step=1, prefix="", fmt="PNG", skip_existing=True):
    """Render frames start..end (inclusive) to <out_dir>/<prefix>####.png (frame numbers as given).
    Frames already on disk are skipped (resumable).  Returns {frame: seconds}."""
    sc = bpy.context.scene
    out_dir = os.path.abspath(out_dir)
    os.makedirs(out_dir, exist_ok=True)
    set_output(os.path.join(out_dir, prefix + "x.png"), fmt=fmt)
    sc.render.use_file_extension = False
    times = {}
    ext = {"PNG": ".png", "JPEG": ".jpg", "OPEN_EXR": ".exr"}[fmt]
    for f in range(start, end + 1, step):
        path = os.path.join(out_dir, f"{prefix}{f:04d}{ext}")
        if skip_existing and os.path.exists(path) and os.path.getsize(path) > 0:
            continue
        sc.frame_set(f)
        sc.render.filepath = path
        t = time.time()
        bpy.ops.render.render(write_still=True)
        times[f] = time.time() - t
        print(f"[render] frame {f}  {times[f]:.1f}s  -> {sc.render.filepath}", flush=True)
    return times


def save_blend(path):
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    bpy.ops.wm.save_as_mainfile(filepath=path, check_existing=False, compress=True)
    return path

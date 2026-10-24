"""S05 GEHEIM (film frames 225-300, 75 local frames).

Top-down over the typed recipe card on the workbench, in mixed window light (cool, from the left) and a 2700 K desk
lamp pool (warm, from the top right).  Rendered as ONE high-resolution still: the drift is a 2D move in post
(post/moves.json), easing to rest exactly centred on the round red GEHEIM stamp at 30 % of picture height, for the
match cut to the chalked cask head at f300.  The card is flat, so a 2D move of a top-down still is exact.

    render_shot.py --shot s05 --res 3200x1800 --frames 0     (the still; framing info in s05_frame.json)
"""
import json
import math
import os

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import botanicals as B
import workroom as A

FRAMES = 75
PRESET = "default"
LAYOUT = json.load(open(os.path.join(S.TEXTURES, "card_layout.json")))
CARD = Vector((-0.05, -0.02, 0.0016))       # card centre on the bench (on the kraft sheet)
CARD_ROT = -3.5                             # degrees
COVER = (0.44, 0.2475)                      # world size (m) covered by the still (16:9)


def card_object(coll):
    w, h = LAYOUT["size_mm"][0] / 1000, LAYOUT["size_mm"][1] / 1000
    nx, ny = 64, 48
    verts, faces, uvs = [], [], []
    from mathutils import noise as mn
    for j in range(ny + 1):
        for i in range(nx + 1):
            x, y = (i / nx - 0.5) * w, (j / ny - 0.5) * h
            z = 0.0006 * max(0.0, abs(i / nx - 0.5) * 2) ** 3 + 0.00025 * mn.noise(Vector((x * 30, y * 30, 0.4)))
            verts.append((x, y, z))
    for j in range(ny):
        for i in range(nx):
            a = j * (nx + 1) + i
            faces.append((a, a + 1, a + nx + 2, a + nx + 1))
            uvs.append([(i / nx, j / ny), ((i + 1) / nx, j / ny), ((i + 1) / nx, (j + 1) / ny), (i / nx, (j + 1) / ny)])
    ob = P.mesh("RecipeCard", verts, faces, coll, True, uvs)
    so = ob.modifiers.new("t", "SOLIDIFY")
    so.thickness = 0.00025
    ob.location = CARD
    ob.rotation_euler = (0, 0, math.radians(CARD_ROT))
    m, t = M.new_material("RecipeCard")
    uv = t.node("ShaderNodeUVMap").outputs[0]
    img = bpy.data.images.load(os.path.join(S.TEXTURES, "card_full.png"), check_existing=True)
    img.colorspace_settings.name = "Non-Color"
    tex = t.node("ShaderNodeTexImage", interpolation="Cubic", extension="CLIP")
    tex.image = img
    t.set(tex.inputs[0], uv)
    sep = t.node("ShaderNodeSeparateColor", {"Color": tex.outputs["Color"]})
    ink, height = sep.outputs[0], sep.outputs[1]
    red = tex.outputs["Alpha"]
    p = t.texco("Object")
    fib = t.noise(t.mapping(p, scale=(1, 3, 1)), scale=2400.0, detail=3.0)
    blot = t.noise(p, scale=60.0, detail=3.0)
    age = t.noise(p, scale=12.0, detail=3.0)
    paper = t.mixc(t.add(t.mul(t.add(blot, -0.5), 0.5), 0.5), (0.66, 0.58, 0.40), (0.74, 0.66, 0.47))
    paper = t.mixc(t.mul(t.smooth(age, 0.55, 0.8), 0.35), paper, (0.55, 0.42, 0.24))       # foxing / age
    paper = t.mixc(t.mul(t.add(fib, -0.5), 0.2), paper, (0.0, 0.0, 0.0), blend="MULTIPLY")
    ink = t.mul(ink, 1.35, clamp=True)
    red = t.mul(red, 1.7, clamp=True)
    edge = t.math("MAXIMUM", t.math("ABSOLUTE", t.add(t.xyz(uv)[0], -0.5)), t.math("ABSOLUTE", t.add(t.xyz(uv)[1], -0.5)))
    paper = t.mixc(t.mul(t.smooth(edge, 0.42, 0.5), 0.45), paper, (0.48, 0.36, 0.20))          # handled, darker edges
    col = t.mixc(ink, paper, (0.022, 0.020, 0.022))
    col = t.mixc(red, col, (0.32, 0.012, 0.016))
    rough = t.mixf(ink, 0.78, 0.6)
    nrm = t.bump(t.add(height, t.mul(fib, 0.15)), strength=0.35, distance=0.00006)
    bsdf = t.principled(base=col, rough=rough, normal=nrm, sheen=0.25, sheen_rough=0.6, spec=0.45)
    t.output(bsdf)
    ob.data.materials.append(m)
    return ob, (w, h)


def stamp_world():
    """World xy of the stamp centre."""
    w, h = LAYOUT["size_mm"][0], LAYOUT["size_mm"][1]
    sx, sy = LAYOUT["stamp_center_mm"]
    local = Vector(((sx / w - 0.5) * w / 1000, (0.5 - sy / h) * h / 1000, 0))
    a = math.radians(CARD_ROT)
    return Vector((CARD.x + local.x * math.cos(a) - local.y * math.sin(a),
                   CARD.y + local.x * math.sin(a) + local.y * math.cos(a), CARD.z))


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-1.4)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, 0
    coll = S.collection("S05")
    A.room(coll, floor=False, walls=True)
    A.kraft_sheet("Kraft", size=(0.30, 0.22), center=(-0.035, -0.012, 0.0), rotation_z_deg=6.0, seed=12, coll=coll)
    card, (cw, ch) = card_object(coll)
    # a fountain pen and a few botanicals at the edge of frame, a brass weight
    pen_prof = [(0.0, 0.0), (0.0035, 0.002), (0.0055, 0.01), (0.0062, 0.06), (0.0066, 0.062), (0.0066, 0.066),
                (0.0058, 0.068), (0.0058, 0.12), (0.0062, 0.128), (0.0045, 0.135), (0.0, 0.137)]
    pen_prof, _ = P.fillet(pen_prof, [0, 0.001, 0.002, 0.001, 0.0005, 0.0005, 0.0005, 0.001, 0.002, 0.002, 0], steps=4)
    pen = P.lathe("FountainPen", pen_prof, 48, coll=coll)
    pen.data.materials.append(M.plastic((0.008, 0.006, 0.005), roughness=0.18, name="PenResin", coat=1.0))
    pen.location = (CARD.x + 0.135, CARD.y - 0.035, 0.0068)
    pen.rotation_euler = (0, math.radians(90), math.radians(112))
    nib = P.lathe("PenBand", [(0.0, 0.0), (0.0067, 0.0), (0.0067, 0.004), (0.0, 0.004)], 48, coll=coll)
    nib.data.materials.append(M.metal("brass", name="PenGold", roughness=0.15, seed=9))
    nib.parent = pen
    nib.location = (0, 0, 0.061)
    B.heap(center=(CARD.x - 0.17, CARD.y + 0.07, 0.0), radius=0.03, counts={"star_anise": 6, "juniper": 40, "cardamom": 9},
           seed=55, coll=coll, n_crumbs=250, spread=0.22, height=0.025)
    B.heap(center=(CARD.x + 0.16, CARD.y + 0.09, 0.0), radius=0.022, counts={"cinnamon": 3, "juniper": 8},
           seed=56, coll=coll, n_crumbs=60)
    # nothing that rolled onto the card stays there (the card must read clean for the match cut)
    a = math.radians(CARD_ROT)
    for ob in list(coll.objects):
        if ob.get("botanical") is None:
            continue
        d = ob.matrix_world.translation - CARD
        lx, ly = d.x * math.cos(-a) - d.y * math.sin(-a), d.x * math.sin(-a) + d.y * math.cos(-a)
        if abs(lx) < cw / 2 + 0.008 and abs(ly) < ch / 2 + 0.008:
            bpy.data.objects.remove(ob, do_unlink=True)
    # light: cool window from the left, warm desk-lamp pool from top right
    lights = A.dawn(target=CARD, azimuth_deg=22.0, elevation_deg=24.0, strength=2.4, kelvin=5600, sky_strength=0.6,
                    sky_kelvin=8000, bounce=0.1, coll=coll, bar_through=CARD + Vector((-0.12, 0, 0)),
                    transom_through=CARD + Vector((0, 0.16, 0)))
    lamp = S.spot_light("DeskLamp", power=55.0, kelvin=2700, location=CARD + Vector((0.20, 0.14, 0.40)),
                        target=CARD + Vector((0.07, -0.01, 0)), angle_deg=46, blend=0.7, radius=0.03)
    S.world((0.003, 0.003, 0.004), 1.0)
    # top-down camera covering COVER (m); 85 mm from ~0.9 m
    st = stamp_world()
    centre = (CARD + st) / 2
    lens = 85.0
    dist = COVER[0] * lens / 36.0
    cam = C.add_camera("CAM_S05", lens=lens, location=(centre.x, centre.y, dist + CARD.z),
                       rotation_deg=(0, 0, 0), fstop=4.0, focus=dist)
    cam.data.sensor_height = 36.0 * COVER[1] / COVER[0]
    cam.data.sensor_fit = "HORIZONTAL"
    info = dict(cover_m=list(COVER), centre=list(centre[:2]), stamp=list(st[:2]),
                card_header=list((CARD + Vector((-0.07, 0.055, 0)))[:2]), stamp_diameter_m=LAYOUT["stamp_radius_mm"] * 2 / 1000)
    json.dump(info, open(os.path.join(S.LOOKDEV, "s05_frame.json"), "w"), indent=1)
    return dict(cam=cam)

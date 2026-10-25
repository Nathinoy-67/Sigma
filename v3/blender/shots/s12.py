"""S12 THE DISC (film frames 630-660, 30 local frames).

Straight down onto the brim-full frosted shot glass, 100 mm.  The near-black surface mirrors the round enamel pendant
above as a bright, perfect disc dead centre, frost crystals soft around the rim.  Rendered as ONE still; the slow
push-in is a 2D move in post that ends with the disc moon-sized and centred for the match cut to the moon (S13).
"""
import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import backbar as D

FRAMES = 30
PRESET = "glass"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-1.2)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, 0
    coll = S.collection("S12")
    D.counter(coll)
    D.bar_mat(coll)
    # (no tap machine: from straight above, its spout would hang out of focus over the glass)
    L = D.lights(coll, pendant=True)
    # the disc: only the diffuser should read in the mirror of the liquid (bright, crisp); the shade goes dark inside
    L["pendant"].data.materials[0].node_tree.nodes["Emission"].inputs["Strength"].default_value = 260.0
    bpy.data.objects.remove(bpy.data.objects["PendantShade"], do_unlink=True)   # its lit interior reads as a halo
    L["pendant"].scale = (0.42, 0.42, 1.0)
    L["pendant"].visible_diffuse = False         # it only has to read in the mirror, not light the mat
    jager = M.jagermeister("JagerS12", density=520.0)
    g = P.shot_glass("Shot", location=D.GLASS, frosted=True, fill=0.97, seed=11, coll=coll, frost=0.72, frost_density=0.7,
                     melt_beads=90, liquid_material=jager)
    # the surface as the lens sees it: a black liquid mirror (an opaque dark film over the refractive volume, which
    # otherwise shows a bright ring of the frosted walls refracted through its meniscus from straight above)
    r_in = 0.0222 - 0.0026 - 0.0004
    bpy.ops.mesh.primitive_circle_add(vertices=128, radius=r_in, fill_type="NGON",
                                      location=D.GLASS + Vector((0, 0, g.info["fill_z"] + 0.0003)))
    mirror = bpy.context.active_object
    mirror.name = "LiquidMirror"
    mm, mt = M.new_material("JagerMirror")
    mt.output(mt.principled(base=(0.004, 0.0015, 0.001), rough=0.0, spec=0.5, ior=1.355, coat=0.0))
    mirror.data.materials.append(mm)
    S.link(mirror, coll)
    S.world((0.001, 0.001, 0.0012), 1.0)
    top = D.GLASS + Vector((0, 0, g.info["cavity_top"]))
    # focus on the mirrored disc (its virtual image lies as far below the surface as the pendant hangs above it);
    # the frosted rim falls soft
    pend = L["pendant"].matrix_world.translation.z - g.info["fill_z"] - D.GLASS.z
    cam = C.add_camera("CAM_S12", lens=62, location=top + Vector((0.0, 0.0, 0.42)), rotation_deg=(0, 0, 0), fstop=5.6,
                       focus=0.42 + pend)
    L["tube"].data.energy = 22.0
    return dict(cam=cam)

"""S16 THE RING (film frames 870-930, 60 local frames).

100 mm macro on the bar top where the shot glass stood.  It is gone: only a ring of melting frost water remains on the
lacquer, its beads still trembling and holding the pink neon.  Rack focus to the highball standing soft behind,
untouched.  'Everybody knows the name' lands on the cut; the sub heartbeat begins.
"""
import math
import random

import bpy
from mathutils import Vector

import scene as S
import camera as C
import materials as M
import props as P
import lodge as E
from s14 import HB, SHOT

FRAMES = 60
PRESET = "glass"


def build(res="look", samples=None, threshold=None, **kw):
    S.new_scene(res, PRESET, samples=samples, threshold=threshold, exposure=-0.4)
    sc = bpy.context.scene
    sc.frame_start, sc.frame_end = 0, FRAMES - 1
    coll = S.collection("S16")
    out = E.build_room(coll, moon_z=7.2, moon_x=-1.2, neon_c=Vector((0.36, E.WIN_Y - 0.06, 1.36)))
    E.key_neon(out["neon"], [(0, 1.0)])
    P.highball("Highball", location=HB, fill=0.62, seed=5, coll=coll, cond_facing_deg=-100.0)
    # the frost-water ring: beads on an annulus where the heavy foot stood, plus a thin wet film
    c = SHOT + Vector((0, 0, 0.0))
    rng0 = random.Random(16)

    def ring(rng):
        a = rng.uniform(0, 2 * math.pi)
        r = rng.gauss(0.0214, 0.0012)
        return Vector((c.x + r * math.cos(a), c.y + r * math.sin(a), c.z)), Vector((0, 0, 1))
    drops = P.scatter_drops("FrostRing", ring, 420, 0.00018, 0.0016, alpha=2.2, seed=16, coll=coll, min_gap=0.08)
    bpy.ops.mesh.primitive_torus_add(major_radius=0.0214, minor_radius=0.0016, major_segments=128, minor_segments=12,
                                     location=c + Vector((0, 0, -0.0013)))
    film = bpy.context.active_object
    film.name = "WetFilm"
    film.scale = (1, 1, 0.9)
    film.data.materials.append(M.water("WetFilmWater"))
    S.link(film, coll)
    # the beads tremble (the room hums; somebody just walked off)
    for f in range(FRAMES):
        k = 1.0 + 0.035 * math.sin(f * 1.9) * math.exp(-f / 40.0) + 0.01 * math.sin(f * 4.3)
        drops.scale = (1.0, 1.0, k)
        drops.location = (0, 0, (k - 1.0) * -0.0)
        drops.keyframe_insert("scale", frame=f)
    S.area_light("PinkKick", size=(0.3, 0.3), power=1.2, color=(1.0, 0.18, 0.5), location=c + Vector((0.15, 0.6, 0.25)),
                 target=c, coll=coll)
    d = (c - HB)
    d.z = 0
    d.normalize()
    cam_p = c + d * 0.30 + Vector((0, 0, 0.06))
    cam = C.add_camera("CAM_S16", lens=100, location=cam_p, target=c + Vector((0.0, 0.0, 0.012)) - d * 0.02, fstop=2.8, focus=c)
    C.rack_focus(cam, [(0, c + d * 0.021), (26, c + d * 0.021), (46, HB + Vector((0, -0.03, 0.06))),
                       (FRAMES - 1, HB + Vector((0, -0.03, 0.06)))], breathing=0.02)
    C.breathe(cam, amplitude_deg=0.02, period_frames=60, seed=16)
    return dict(cam=cam)

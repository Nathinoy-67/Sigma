"""fluid.py -- surface the MPM particle frames (sims/mpm_plunge.py) as a liquid mesh in Cycles.

    import fluid as F
    ob = F.particle_liquid("Plunge", "v3/frames/sim2", material=drink, coll=coll, frame_map=lambda f: f)
    # every render frame loads p_<frame_map(f)>.npy into the point mesh; Geometry Nodes turn the points into a
    # smooth closed surface: Points to Volume (spheres) -> Volume to Mesh -> a few passes of position blur.
"""
import os

import bpy
import numpy as np

import materials as M

_HANDLERS = []


def _surface_group(voxel, radius, threshold, smooth_iter):
    name = f"OYOS_ParticleSurface_{voxel:.5f}_{radius:.5f}"
    ng = bpy.data.node_groups.get(name)
    if ng:
        return ng
    ng = bpy.data.node_groups.new(name, "GeometryNodeTree")
    ng.interface.new_socket("Geometry", in_out="INPUT", socket_type="NodeSocketGeometry")
    ng.interface.new_socket("Material", in_out="INPUT", socket_type="NodeSocketMaterial")
    ng.interface.new_socket("Geometry", in_out="OUTPUT", socket_type="NodeSocketGeometry")
    t = M.Tree(ng)
    gi = t.node("NodeGroupInput")
    go = t.node("NodeGroupOutput")
    m2p = t.node("GeometryNodeMeshToPoints", {"Mesh": gi.outputs["Geometry"], "Radius": radius})
    p2v = t.node("GeometryNodePointsToVolume", {"Points": m2p.outputs[0], "Density": 1.0, "Radius": radius})
    try:
        p2v.resolution_mode = "VOXEL_SIZE"
        t.set(p2v.inputs["Voxel Size"], voxel)
    except (AttributeError, KeyError, TypeError):
        pass
    v2m = t.node("GeometryNodeVolumeToMesh", {"Volume": p2v.outputs[0], "Threshold": threshold, "Adaptivity": 0.0})
    geo = v2m.outputs[0]
    pos = t.node("GeometryNodeInputPosition").outputs[0]
    blur = t.node("GeometryNodeBlurAttribute", {"Value": pos, "Iterations": smooth_iter, "Weight": 1.0}, data_type="FLOAT_VECTOR")
    sp = t.node("GeometryNodeSetPosition", {"Geometry": geo, "Position": blur.outputs[0]})
    sm = t.node("GeometryNodeSetShadeSmooth", {"Geometry": sp.outputs[0]})
    mat = t.node("GeometryNodeSetMaterial", {"Geometry": sm.outputs[0], "Material": gi.outputs["Material"]})
    t.link(mat.outputs[0], go.inputs[0])
    return ng


def particle_liquid(name, sim_dir, material, coll=None, frame_map=None, voxel=0.00035, radius=0.00075,
                    threshold=0.3, smooth_iter=3, location=(0, 0, 0)):
    """A mesh of the sim's particles (vertex positions swapped every frame) surfaced by Geometry Nodes."""
    import scene as S
    p0 = np.load(os.path.join(sim_dir, "p_0000.npy")).astype(np.float32)
    me = bpy.data.meshes.new(name + "_pts")
    me.vertices.add(len(p0))
    me.vertices.foreach_set("co", p0.ravel())
    me.update()
    ob = bpy.data.objects.new(name, me)
    S.link(ob, coll)
    ob.location = location
    mod = ob.modifiers.new("surface", "NODES")
    mod.node_group = _surface_group(voxel, radius, threshold, smooth_iter)
    import props as P
    P.modifier_input(mod, "Material", material)
    frame_map = frame_map or (lambda f: f)
    n_avail = len([f for f in os.listdir(sim_dir) if f.startswith("p_")])

    state = {"k": None}

    def load(scene, *args):
        k = int(min(max(frame_map(scene.frame_current), 0), n_avail - 1))
        if state["k"] == k:
            return
        P = np.load(os.path.join(sim_dir, f"p_{k:04d}.npy")).astype(np.float32)
        if len(P) == len(ob.data.vertices):
            ob.data.vertices.foreach_set("co", P.ravel())
            ob.data.update()
        state["k"] = k
    bpy.app.handlers.frame_change_pre.append(load)
    _HANDLERS.append(load)
    load(bpy.context.scene)
    return ob

# include parent path
import os
import sys
import numpy as np
import math
import ctypes

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


import oglang as og

import render

@og.kernel
def simulate(positions: og.array(og.vec3),
            velocities: og.array(og.vec3),
            mesh: og.uint64,
            dt: float):
    
    tid = og.tid()

    x = og.load(positions, tid)
    v = og.load(velocities, tid)

    # v = v + og.vec3(0.0, 0.0-9.8, 0.0)*dt
    # xpred = x + v*dt

    # if (xpred[1] < 0.0):
    #     v = og.vec3(v[0], 0.0 - v[1]*0.5, v[2])

    p = og.mesh_query_point (mesh, x)
    f = (p-x)*0.501# - v*0.1

    #v = v + f*dt
    x = x + v*dt + f*dt

    og.store(positions, tid, x)    
    og.store(velocities, tid, v)


# create og mesh
device = "cuda"


num_particles = 10000

sim_steps = 1000
sim_dt = 1.0/60.0

sim_time = 0.0
sim_timers = {}
sim_render = True

from pxr import Usd, UsdGeom, Gf, Sdf

torus = Usd.Stage.Open("./tests/assets/torus.usda")
torus_geom = UsdGeom.Mesh(torus.GetPrimAtPath("/torus_obj/torus_obj"))

points = torus_geom.GetPointsAttr().Get()
indices = torus_geom.GetFaceVertexIndicesAttr().Get()

mesh = og.Mesh(
    og.from_numpy(np.array(points), dtype=og.vec3, device=device),  
    og.from_numpy(np.array(indices), dtype=int, device=device), 
    device=device)


np.random.seed(42)

init_pos = (np.random.rand(num_particles, 3) - np.array([0.5, 0.5, 0.5]))*10.0
init_vel = np.random.rand(num_particles, 3)*0.0


positions = og.from_numpy(init_pos.astype(np.float32), dtype=og.vec3, device=device)
velocities = og.from_numpy(init_vel.astype(np.float32), dtype=og.vec3, device=device)

positions_host = og.from_numpy(init_pos.astype(np.float32), dtype=og.vec3, device="cpu")

if (sim_render):
    stage = render.UsdRenderer("tests/outputs/test_mesh.usd")

for i in range(sim_steps):

    with og.ScopedTimer("simulate", detailed=False, dict=sim_timers):

        og.launch(

            kernel=simulate, 
            dim=num_particles, 
            inputs=[positions, velocities, mesh.id, sim_dt], 
            outputs=[], 
            device=device)

        og.synchronize()
    
    # render
    if (sim_render):

        with og.ScopedTimer("render", detailed=False):

            og.copy(positions_host, positions)

            stage.begin_frame(sim_time)
            
            stage.render_ground()

            stage.render_ref(name="mesh", path="../assets/torus.usda", pos=(0.0, 0.0, 0.0), rot=(0.0, 0.0, 0.0, 1.0), scale=(1.0, 1.0, 1.0))
            stage.render_points(name="points", points=positions_host.numpy(), radius=0.1)

            stage.end_frame()

    sim_time += sim_dt

if (sim_render):
    stage.save()

print(np.mean(sim_timers["simulate"]))
print(np.min(sim_timers["simulate"]))
print(np.max(sim_timers["simulate"]))
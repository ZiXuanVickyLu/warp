# Copyright (c) 2023 NVIDIA CORPORATION.  All rights reserved.
# NVIDIA CORPORATION and its licensors retain all intellectual property
# and proprietary rights in and to this software, related documentation
# and any modifications thereto.  Any use, reproduction, disclosure or
# distribution of this software and related documentation without an express
# license agreement from NVIDIA CORPORATION is strictly prohibited.

"""Node creating a geometry mesh grid."""

import traceback

import numpy as np
import omni.graph.core as og
import warp as wp

import omni.warp.nodes
from omni.warp.nodes._impl.kernels.grid_create import grid_create_launch_kernel
from omni.warp.nodes.ogn.OgnGridCreateDatabase import OgnGridCreateDatabase


PROFILING = False


#   Internal State
# ------------------------------------------------------------------------------


class InternalState:
    """Internal state for the node."""

    def __init__(self) -> None:
        self.xform_prim_path = None
        self.size = None
        self.dims = None

        self.is_valid = False

    def have_setting_attrs_changed(self, db: OgnGridCreateDatabase) -> bool:
        """Checks if the values of the attributes that set-up the node have changed."""
        return (
            db.inputs.xformPrimPath != self.xform_prim_path
            or not np.array_equal(db.inputs.size, self.size)
            or not np.array_equal(db.inputs.dims, self.dims)
        )

    def store_setting_attrs(self, db: OgnGridCreateDatabase) -> None:
        """Stores the values of the attributes that set-up the node."""
        self.xform_prim_path = db.inputs.xformPrimPath
        self.size = db.inputs.size.copy()
        self.dims = db.inputs.dims.copy()


#   Compute
# ------------------------------------------------------------------------------


def compute(db: OgnGridCreateDatabase) -> None:
    """Evaluates the node."""
    db.outputs.mesh.changes().activate()

    if not db.outputs.mesh.valid:
        return

    state = db.internal_state

    if state.is_valid and not state.have_setting_attrs_changed(db):
        return

    # Compute the mesh's topology counts.
    face_count = db.inputs.dims[0] * db.inputs.dims[1]
    vertex_count = face_count * 4
    point_count = (db.inputs.dims[0] + 1) * (db.inputs.dims[1] + 1)

    # Create a new geometry mesh within the output bundle.
    omni.warp.nodes.mesh_create_bundle(
        db.outputs.mesh,
        point_count,
        vertex_count,
        face_count,
        xform=omni.warp.nodes.prim_get_world_xform(db.inputs.xformPrimPath),
    )

    with omni.warp.nodes.NodeTimer("grid_create", db, active=PROFILING):
        # Evaluate the kernel.
        grid_create_launch_kernel(
            omni.warp.nodes.mesh_get_points(db.outputs.mesh),
            omni.warp.nodes.mesh_get_face_vertex_counts(db.outputs.mesh),
            omni.warp.nodes.mesh_get_face_vertex_indices(db.outputs.mesh),
            omni.warp.nodes.mesh_get_normals(db.outputs.mesh),
            omni.warp.nodes.mesh_get_uvs(db.outputs.mesh),
            db.inputs.size.tolist(),
            db.inputs.dims.tolist(),
        )

    state.store_setting_attrs(db)


#   Node Entry Point
# ------------------------------------------------------------------------------


class OgnGridCreate:
    """Node."""

    @staticmethod
    def internal_state() -> InternalState:
        return InternalState()

    @staticmethod
    def compute(db: OgnGridCreateDatabase) -> None:
        device = wp.get_device("cuda:0")

        try:
            with wp.ScopedDevice(device):
                compute(db)
        except Exception:
            db.log_error(traceback.format_exc())
            db.internal_state.is_valid = False
            return

        db.internal_state.is_valid = True

        # Fire the execution for the downstream nodes.
        db.outputs.execOut = og.ExecutionAttributeState.ENABLED

# -*- coding: utf-8 -*-
"""LDR Importer GPLv2 license.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

"""

import bpy


def init():
    # Select all the mesh
    for cur_obj in objects:
        bpy.ops.object.select_all(action='DESELECT')
        cur_obj.select = True
        bpy.context.scene.objects.active = cur_obj

        # To change the width of the gaps, change the gapWidth variable
        gapWidth = 0.007
        objScale = cur_obj.scale * scale
        dim = cur_obj.dimensions

        # Checks whether the object isn't flat in a certain direction
        # to avoid division by zero.
        # Else, the scale factor is set proportional to the inverse of
        # the dimension so that the mesh shrinks a fixed distance
        # (determined by the gap_width and the scale of the object)
        # in every direction, creating a uniform gap.
        scaleFac = {"x": 1, "y": 1, "z": 1}

        if dim.x != 0:
            scaleFac["x"] = 1 - 2 * gapWidth * abs(objScale.x) / dim.x
        if dim.y != 0:
            scaleFac["y"] = 1 - 2 * gapWidth * abs(objScale.y) / dim.y
        if dim.z != 0:
            scaleFac["z"] = 1 - 2 * gapWidth * abs(objScale.z) / dim.z

        bpy.context.object.scale[0] *= scaleFac["x"]
        bpy.context.object.scale[1] *= scaleFac["y"]
        bpy.context.object.scale[2] *= scaleFac["z"]

        bpy.ops.object.transform_apply(scale=True)
        bpy.ops.object.select_all(action='DESELECT')

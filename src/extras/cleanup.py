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
        cur_obj.select = True
        bpy.context.scene.objects.active = cur_obj

        if bpy.ops.object.mode_set.poll():
            # Change to edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            # Remove doubles, calculate normals
            bpy.ops.mesh.remove_doubles(threshold=0.01)
            bpy.ops.mesh.normals_make_consistent()

            if bpy.ops.object.mode_set.poll():
                # Go back to object mode, set origin to geometry
                bpy.ops.object.mode_set(mode='OBJECT')
                # When using linked bricks, keep original origin point
                if not LinkParts:  # noqa
                    bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')

                # Set smooth shading
                bpy.ops.object.shade_smooth()

    # Add 30 degree edge split modifier to all bricks
    for cur_obj in objects:
        edges = cur_obj.modifiers.new(
            "Edge Split", type='EDGE_SPLIT')
        edges.split_angle = 0.523599
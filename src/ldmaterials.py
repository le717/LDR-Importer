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

from .ldconsole import Console


__all__ = ("main")


def getBIMaterial(ldColors, mat_list, colour):

    # We have already generated this material, reuse it
    if colour in mat_list:
        return mat_list[colour]

    # Generate a material from a direct color
    if not ldColors.contains(colour):
        # Check for a possible direct color
        col = ldColors.makeDirectColor(colour)

        # No direct color was found
        if not col["valid"]:
            return None

        # We have a direct color on our hands
        Console.log("Direct color {0} found".format(colour))
        mat = bpy.data.materials.new("Mat_{0}".format(colour))
        mat.diffuse_color = col["value"]

        # Add it to the material lists to avoid duplicate processing
        mat_list[colour] = mat
        return mat_list[colour]

    # Valid LDraw color, generate the material
    else:
        col = ldColors.get(colour)
        mat = bpy.data.materials.new("Mat_{0}".format(colour))

        mat.diffuse_color = col["value"]

        alpha = col["alpha"]
        if alpha < 1.0:
            mat.use_transparency = True
            mat.alpha = alpha

        mat.emit = col["luminance"] / 100

        if col["material"] == "CHROME":
            mat.specular_intensity = 1.4
            mat.roughness = 0.01
            mat.raytrace_mirror.use = True
            mat.raytrace_mirror.reflect_factor = 0.3

        elif col["material"] == "PEARLESCENT":
            mat.specular_intensity = 0.1
            mat.roughness = 0.32
            mat.raytrace_mirror.use = True
            mat.raytrace_mirror.reflect_factor = 0.07

        elif col["material"] == "RUBBER":
            mat.specular_intensity = 0.19

        elif col["material"] == "METAL":
            mat.specular_intensity = 1.473
            mat.specular_hardness = 292
            mat.diffuse_fresnel = 0.93
            mat.darkness = 0.771
            mat.roughness = 0.01
            mat.raytrace_mirror.use = True
            mat.raytrace_mirror.reflect_factor = 0.9

        # elif col["material"] == "GLITTER":
        #    slot = mat.texture_slots.add()
        #    tex = bpy.data.textures.new("GlitterTex", type = "STUCCI")
        #    tex.use_color_ramp = True
        #
        #    slot.texture = tex

        else:
            mat.specular_intensity = 0.2

        mat_list[colour] = mat
        return mat_list[colour]

    # We were unable to generate a material
    return None


def main(ldColors, mat_list, render_engine, color):

    if render_engine == "CYCLES":
        return getCyclesMaterial(ldColors, mat_list, color)
    else:
        return getBIMaterial(ldColors, mat_list, color)

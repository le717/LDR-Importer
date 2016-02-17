# -*- coding: utf-8 -*-
"""LDR Importer GPLv2 license.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

"""


import os
import re
import math
import mathutils
import traceback

import bpy
from bpy.props import (StringProperty,
                       FloatProperty,
                       EnumProperty,
                       BoolProperty
                       )

from bpy_extras.io_utils import ImportHelper

from .src.ldcolors import Colors
from .src.ldconsole import Console
from .src.ldprefs import Preferences

# Global variables
objects = []
paths = []
mat_list = {}


def debugPrint(msg):
    """Compatibility function for easier debugging of older patches.

    Do not use this function in new code! Always use the appropriate
    static method in the Console class when displaying information
    in the Blender console. This function may be removed by
    the developers at any time and will not be permanent.

    @param {String} msg The message to be displayed.
    """
    Console.warn("""debugPrint() is deprecated!
Use the appropriate Console method instead.""")
    Console.log(msg)


class LDrawFile(object):

    """Scans LDraw files."""

    # FIXME: rewrite - Rewrite entire class (#35)
    def __init__(self, context, filename, level, mat,
                 colour=None, orientation=None):

        engine = context.scene.render.engine
        self.level = level
        self.points = []
        self.faces = []
        self.material_index = []
        self.subparts = []
        self.submodels = []
        self.part_count = 0

        # Orientation matrix to handle orientation separately
        # (top-level part only)
        self.orientation = orientation
        self.mat = mat
        self.colour = colour
        self.parse(filename)

        # Deselect all objects before import.
        # This prevents them from receiving any cleanup (if applicable).
        bpy.ops.object.select_all(action='DESELECT')

        if len(self.points) > 0 and len(self.faces) > 0:
            me = bpy.data.meshes.new('LDrawMesh')
            me.from_pydata(self.points, [], self.faces)
            me.validate()
            me.update()

            for i, f in enumerate(me.polygons):
                n = self.material_index[i]

                # Get the proper materials depending on the current engine
                # (Cycles vs. BI, BGE, POV-Ray, etc)
                material = (getCyclesMaterial(n) if engine == "CYCLES"
                            else getMaterial(n))

                if material is not None:
                    if me.materials.get(material.name) is None:
                        me.materials.append(material)

                    f.material_index = me.materials.find(material.name)

            self.ob = bpy.data.objects.new('LDrawObj', me)
            # Naming of objects: filename of .dat-file, without extension
            self.ob.name = os.path.basename(filename)[:-4]

            if LinkParts:  # noqa
                # Set top-level part orientation using Blender's 'matrix_world'
                self.ob.matrix_world = self.orientation.normalized()
            else:
                self.ob.location = (0, 0, 0)

            objects.append(self.ob)

            # Link object to scene
            bpy.context.scene.objects.link(self.ob)

        for i in self.subparts:
            self.submodels.append(LDrawFile(context, i[0], i[1], i[2],
                                            i[3], i[4]))

    def parse_line(self, line):
        """Harvest the information from each line."""
        verts = []
        color = line[1]

        if color == '16':
            color = self.colour

        num_points = int((len(line) - 2) / 3)
        for i in range(num_points):
                self.points.append(
                    (self.mat * mathutils.Vector((float(line[i * 3 + 2]),
                     float(line[i * 3 + 3]), float(line[i * 3 + 4])))).
                    to_tuple())
                verts.append(len(self.points) - 1)
        self.faces.append(verts)
        self.material_index.append(color)

    def parse_quad(self, line):
        """Properly construct quads in each brick."""
        color = line[1]
        verts = []
        num_points = 4
        v = []

        if color == '16':
            color = self.colour

        v.append(self.mat * mathutils.Vector((float(line[0 * 3 + 2]),
                 float(line[0 * 3 + 3]), float(line[0 * 3 + 4]))))
        v.append(self.mat * mathutils.Vector((float(line[1 * 3 + 2]),
                 float(line[1 * 3 + 3]), float(line[1 * 3 + 4]))))
        v.append(self.mat * mathutils.Vector((float(line[2 * 3 + 2]),
                 float(line[2 * 3 + 3]), float(line[2 * 3 + 4]))))
        v.append(self.mat * mathutils.Vector((float(line[3 * 3 + 2]),
                 float(line[3 * 3 + 3]), float(line[3 * 3 + 4]))))

        nA = (v[1] - v[0]).cross(v[2] - v[0])
        nB = (v[2] - v[1]).cross(v[3] - v[1])

        for i in range(num_points):
            verts.append(len(self.points) + i)

        if (nA.dot(nB) < 0):
            self.points.extend([v[0].to_tuple(), v[1].to_tuple(),
                               v[3].to_tuple(), v[2].to_tuple()])
        else:
            self.points.extend([v[0].to_tuple(), v[1].to_tuple(),
                               v[2].to_tuple(), v[3].to_tuple()])

        self.faces.append(verts)
        self.material_index.append(color)

    def parse(self, filename):
        """Construct tri's in each brick."""
        # FIXME: rewrite - Rework function (#35)
        subfiles = []

        while True:
            # Get the path to the part
            filename = (filename if os.path.exists(filename)
                        else locatePart(filename))

            # The part does not exist
            # TODO Do not halt on this condition (#11)
            if filename is None:
                return False

            # Read the located part
            with open(filename, "rt", encoding="utf_8") as f:
                lines = f.readlines()

            # Check the part header for top-level part status
            isPart = isTopLevelPart(lines[3])

            # Linked parts relies on the flawed isPart logic (#112)
            # TODO Correct linked parts to use proper logic
            # and remove this kludge
            if LinkParts:  # noqa
                isPart = filename == fileName  # noqa

            self.part_count += 1
            if self.part_count > 1 and self.level == 0:
                self.subparts.append([filename, self.level + 1, self.mat,
                                      self.colour, self.orientation])
            else:
                for retval in lines:
                    tmpdate = retval.strip()
                    if tmpdate != "":
                        tmpdate = tmpdate.split()

                        # Part content
                        if tmpdate[0] == "1":
                            new_file = tmpdate[14]
                            (
                                x, y, z, a, b, c,
                                d, e, f, g, h, i
                            ) = map(float, tmpdate[2:14])

                            # Reset orientation of top-level part,
                            # track original orientation
                            # TODO Use corrected isPart logic
                            if self.part_count == 1 and isPart and LinkParts:  # noqa
                                mat_new = self.mat * mathutils.Matrix((
                                    (1, 0, 0, 0),
                                    (0, 1, 0, 0),
                                    (0, 0, 1, 0),
                                    (0, 0, 0, 1)
                                ))
                                orientation = self.mat * mathutils.Matrix((
                                    (a, b, c, x),
                                    (d, e, f, y),
                                    (g, h, i, z),
                                    (0, 0, 0, 1)
                                )) * mathutils.Matrix.Rotation(
                                    math.radians(90), 4, 'X')
                            else:
                                mat_new = self.mat * mathutils.Matrix((
                                    (a, b, c, x),
                                    (d, e, f, y),
                                    (g, h, i, z),
                                    (0, 0, 0, 1)
                                ))
                                orientation = None
                            color = tmpdate[1]
                            if color == '16':
                                color = self.colour
                            subfiles.append([new_file, mat_new, color])

                            # When top-level part, save orientation separately
                            # TODO Use corrected isPart logic
                            if self.part_count == 1 and isPart:
                                subfiles.append(['orientation',
                                                 orientation, ''])

                        # Triangle (tri)
                        if tmpdate[0] == "3":
                            self.parse_line(tmpdate)

                        # Quadrilateral (quad)
                        if tmpdate[0] == "4":
                            self.parse_quad(tmpdate)

            if len(subfiles) > 0:
                subfile = subfiles.pop()
                filename = subfile[0]
                # When top-level brick orientation information found,
                # save it in self.orientation
                if filename == 'orientation':
                    self.orientation = subfile[1]
                    subfile = subfiles.pop()
                    filename = subfile[0]
                self.mat = subfile[1]
                self.colour = subfile[2]
            else:
                break


def convertDirectColor(color):
    """Convert direct colors to usable RGB values.

    @param {String} An LDraw direct color in the format 0x2RRGGBB.
                    Details at http://www.ldraw.org/article/218.html#colours.
    @return {Tuple.<boolean, ?tuple>} Index zero is a boolean value indicating
                                     if a direct color was found or not.
                                     If it is True, index one is the color
                                     converted into a three-index
                                     RGB color tuple.
    """
    if (
        color is None or
        re.fullmatch(r"^0x2(?:[A-F0-9]{2}){3}$", color) is None
    ):
        return (False,)
    return (True, colors.hexToRgb(color[3:]))


def getMaterial(colour):
    """Get Blender Internal Material Values."""
    if colour in colors.getAll():
        if not (colour in mat_list):
            mat = bpy.data.materials.new("Mat_{0}".format(colour))
            col = colors.get(colour)

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
    else:
        # Check for a possible direct color
        directColor = convertDirectColor(colour)

        # We have a direct color on our hands
        if directColor[0]:
            Console.log("Direct color {0} found".format(colour))
            mat = bpy.data.materials.new("Mat_{0}".format(colour))
            mat.diffuse_color = directColor[1]

            # Add it to the material lists to avoid duplicate processing
            # TODO Do not add it to the LDraw-defined colors but only
            # to the Blender material list
            colors.add(colour, mat)
            mat_list[colour] = mat
            return mat_list[colour]

    return None


def getCyclesMaterial(colour):
    """Get Cycles Material Values."""
    if colour in colors.getAll():
        if not (colour in mat_list):
            col = colors.get(colour)

            if col["name"] == "Milky_White":
                mat = getCyclesMilkyWhite("Mat_{0}".format(colour),
                                          col["value"])

            elif col["material"] == "BASIC" and col["luminance"] == 0:
                mat = getCyclesBase("Mat_{0}".format(colour),
                                    col["value"], col["alpha"])

            elif col["luminance"] > 0:
                mat = getCyclesEmit("Mat_{0}".format(colour), col["value"],
                                    col["alpha"], col["luminance"])

            elif col["material"] == "CHROME":
                mat = getCyclesChrome("Mat_{0}".format(colour), col["value"])

            elif col["material"] == "PEARLESCENT":
                mat = getCyclesPearlMetal("Mat_{0}".format(colour),
                                          col["value"])

            elif col["material"] == "METAL":
                mat = getCyclesPearlMetal("Mat_{0}".format(colour),
                                          col["value"])

            elif col["material"] == "RUBBER":
                mat = getCyclesRubber("Mat_{0}".format(colour),
                                      col["value"], col["alpha"])

            else:
                mat = getCyclesBase("Mat_{0}".format(colour),
                                    col["value"], col["alpha"])

            mat_list[colour] = mat

        return mat_list[colour]
    else:
        # Check for a possible direct color
        directColor = convertDirectColor(colour)

        # We have a direct color on our hands
        if directColor[0]:
            Console.log("Direct color {0} found".format(colour))
            mat = getCyclesBase("Mat_{0}".format(colour),
                                directColor[1], 1.0)

            # Add it to the material lists to avoid duplicate processing
            # TODO Do not add it to the LDraw-defined colors but only
            # to the Blender material list
            colors.add(colour, mat)
            mat_list[colour] = mat
            return mat_list[colour]

    return None


def getCyclesBase(name, diffColor, alpha):
    """Basic material colors for Cycles render engine."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = diffColor

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove all previous nodes
    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90
    mix.inputs['Fac'].default_value = 0.05

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    # Solid bricks
    if alpha == 1.0:
        node = nodes.new('ShaderNodeBsdfDiffuse')
        node.location = -242, 154
        node.inputs['Color'].default_value = diffColor + (1.0,)
        node.inputs['Roughness'].default_value = 0.0

    # Transparent bricks
    else:
        # TODO Figure out a good way to make use of the alpha value
        node = nodes.new('ShaderNodeBsdfGlass')
        node.location = -242, 154
        node.inputs['Color'].default_value = diffColor + (1.0,)
        node.inputs['Roughness'].default_value = 0.05
        node.inputs['IOR'].default_value = 1.46

    gloss = nodes.new('ShaderNodeBsdfGlossy')
    gloss.location = -242, -23
    gloss.distribution = 'BECKMANN'
    gloss.inputs['Roughness'].default_value = 0.05
    gloss.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)

    links.new(mix.outputs[0], out.inputs[0])
    links.new(node.outputs[0], mix.inputs[1])
    links.new(gloss.outputs[0], mix.inputs[2])

    return mat


def getCyclesEmit(name, diff_color, alpha, luminance):

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90
    mix.inputs['Fac'].default_value = luminance / 100

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    """
    NOTE: The alpha value again is not making much sense here.
    I'm leaving it in, in case someone has an idea how to use it.
    """

    trans = nodes.new('ShaderNodeBsdfTranslucent')
    trans.location = -242, 154
    trans.inputs['Color'].default_value = diff_color + (1.0,)

    emit = nodes.new('ShaderNodeEmission')
    emit.location = -242, -23

    links.new(mix.outputs[0], out.inputs[0])
    links.new(trans.outputs[0], mix.inputs[1])
    links.new(emit.outputs[0], mix.inputs[2])

    return mat


def getCyclesChrome(name, diffColor):
    """Chrome material colors for Cycles render engine."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = diffColor

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove all previous nodes
    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90
    mix.inputs['Fac'].default_value = 0.01

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    glossOne = nodes.new('ShaderNodeBsdfGlossy')
    glossOne.location = -242, 154
    glossOne.distribution = 'GGX'
    glossOne.inputs['Color'].default_value = diffColor + (1.0,)
    glossOne.inputs['Roughness'].default_value = 0.03

    glossTwo = nodes.new('ShaderNodeBsdfGlossy')
    glossTwo.location = -242, -23
    glossTwo.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
    glossTwo.inputs['Roughness'].default_value = 0.03

    links.new(mix.outputs[0], out.inputs[0])
    links.new(glossOne.outputs[0], mix.inputs[1])
    links.new(glossTwo.outputs[0], mix.inputs[2])

    return mat


def getCyclesPearlMetal(name, diffColor):
    """Pearlescent material colors for Cycles render engine."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = diffColor

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove all previous nodes
    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90
    mix.inputs['Fac'].default_value = 0.4

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    gloss = nodes.new('ShaderNodeBsdfGlossy')
    gloss.location = -242, 154
    gloss.distribution = 'BECKMANN'
    gloss.inputs['Color'].default_value = diffColor + (1.0,)
    gloss.inputs['Roughness'].default_value = 0.05

    diffuse = nodes.new('ShaderNodeBsdfDiffuse')
    diffuse.location = -242, -23
    diffuse.inputs['Color'].default_value = diffColor + (1.0,)
    diffuse.inputs['Roughness'].default_value = 0.0

    links.new(mix.outputs[0], out.inputs[0])
    links.new(gloss.outputs[0], mix.inputs[1])
    links.new(diffuse.outputs[0], mix.inputs[2])

    return mat


def getCyclesRubber(name, diffColor, alpha):
    """Rubber material colors for Cycles render engine."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    mat.diffuse_color = diffColor

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    # Remove all previous nodes
    for n in nodes:
        nodes.remove(n)

    mixTwo = nodes.new('ShaderNodeMixShader')
    mixTwo.location = 0, 90
    mixTwo.inputs['Fac'].default_value = 0.05

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    # Solid bricks
    if alpha == 1.0:
        diffuse = nodes.new('ShaderNodeBsdfDiffuse')
        diffuse.location = -242, 154
        diffuse.inputs['Color'].default_value = diffColor + (1.0,)
        diffuse.inputs['Roughness'].default_value = 0

        trans = nodes.new('ShaderNodeBsdfTranslucent')
        trans.location = -242, 154
        trans.inputs['Color'].default_value = diffColor + (1.0,)

        mixOne = nodes.new('ShaderNodeMixShader')
        mixOne.location = 0, 90
        mixOne.inputs['Fac'].default_value = 0.7

        gloss = nodes.new('ShaderNodeBsdfGlossy')
        gloss.location = -242, 154
        gloss.distribution = 'BECKMANN'
        gloss.inputs['Color'].default_value = diffColor + (1.0,)
        gloss.inputs['Roughness'].default_value = 0.2

        links.new(diffuse.outputs[0], mixOne.inputs[1])
        links.new(trans.outputs[0], mixOne.inputs[2])
        links.new(mixOne.outputs[0], mixTwo.inputs[1])
        links.new(gloss.outputs[0], mixTwo.inputs[2])

    # Transparent bricks
    else:
        glass = nodes.new('ShaderNodeBsdfGlass')
        glass.location = -242, 154
        glass.distribution = 'BECKMANN'
        glass.inputs['Color'].default_value = diffColor + (1.0,)
        glass.inputs['Roughness'].default_value = 0.4
        glass.inputs['IOR'].default_value = 1.160

        gloss = nodes.new('ShaderNodeBsdfGlossy')
        gloss.location = -242, 154
        gloss.distribution = 'GGX'
        gloss.inputs['Color'].default_value = (1.0, 1.0, 1.0, 1.0)
        gloss.inputs['Roughness'].default_value = 0.2

        links.new(glass.outputs[0], mixTwo.inputs[1])
        links.new(gloss.outputs[0], mixTwo.inputs[2])

    links.new(mixTwo.outputs[0], out.inputs[0])

    return mat


def getCyclesMilkyWhite(name, diff_color):

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90
    mix.inputs['Fac'].default_value = 0.1

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    trans = nodes.new('ShaderNodeBsdfTranslucent')
    trans.location = -242, 154
    trans.inputs['Color'].default_value = diff_color + (1.0,)

    diff = nodes.new('ShaderNodeBsdfDiffuse')
    diff.location = -242, -23
    diff.inputs['Color'].default_value = diff_color + (1.0,)
    diff.inputs['Roughness'].default_value = 0.1

    links.new(mix.outputs[0], out.inputs[0])
    links.new(trans.outputs[0], mix.inputs[1])
    links.new(diff.outputs[0], mix.inputs[2])

    return mat


def isTopLevelPart(headerLine):
    """Check if the given part is a top level part.

    @param {String} headerLine The header line stating the part level.
    @return {Boolean} True if a top level part, False otherwise
                      or the header does not specify.
    """
    # Make sure the file has the spec'd META command
    # If it does not, we cannot do easily determine the part type,
    # so we will simply say it is not top level
    headerLine = headerLine.lower().strip()
    if headerLine == "":
        return False

    headerLine = headerLine.split()
    if headerLine[0] != "0 !ldraw_org":
        return False

    # We can determine if this is top level or not
    return headerLine[2] in ("part", "unofficial_part")


def locatePart(partName):
    """Find the given part in the defined search paths.

    @param {String} partName The part to find.
    @return {!String} The absolute path to the part if found.
    """
    # Use the OS's path separator to ensure the parts are found
    partName = partName.replace("\\", os.path.sep)

    for path in paths:
        # Find the part filename using the exact case in the file
        fname = os.path.join(path, partName)
        if os.path.exists(fname):
            return fname

        # Because case-sensitive file systems, if the first check fails
        # check again using a normalized part filename
        # See #112#issuecomment-136719763
        else:
            fname = os.path.join(path, partName.lower())
            if os.path.exists(fname):
                return fname

    Console.log("Could not find part {0}".format(fname))
    return None


def create_model(self, context, scale):
    """Create the actual model."""
    # FIXME: rewrite - Rewrite entire function (#35)
    global objects
    global colors
    global mat_list
    global fileName

    fileName = self.filepath
    # Attempt to get the directory the file came from
    # and add it to the `paths` list
    paths[0] = os.path.dirname(fileName)
    Console.log("Attempting to import {0}".format(fileName))

    # The file format as hinted to by
    # conventional file extensions is not supported.
    # Recommended: http://ghost.kirk.by/file-extensions-are-only-hints
    if fileName[-4:].lower() not in (".ldr", ".dat"):

        Console.log('''ERROR: Reason: Invalid File Type
Must be a .ldr or .dat''')
        self.report({'ERROR'}, '''Error: Invalid File Type
Must be a .ldr or .dat''')
        return {'ERROR'}

    # It has the proper file extension, continue with the import
    try:
        # Rotate and scale the parts
        # Scale factor is divided by 25 so we can use whole number
        # scale factors in the UI. For reference,
        # the default scale 1 = 0.04 to Blender
        trix = mathutils.Matrix((
            (1.0,  0.0, 0.0, 0.0),  # noqa
            (0.0,  0.0, 1.0, 0.0),  # noqa
            (0.0, -1.0, 0.0, 0.0),
            (0.0,  0.0, 0.0, 1.0)  # noqa
        )) * (scale / 25)

        # If LDrawDir does not exist, stop the import
        if not os.path.isdir(LDrawDir):  # noqa
            Console.log(''''ERROR: Cannot find LDraw installation at
{0}'''.format(LDrawDir))  # noqa
            self.report({'ERROR'}, '''Cannot find LDraw installation at
{0}'''.format(LDrawDir))  # noqa
            return {'CANCELLED'}

        # Instance the colors module and
        # load the LDraw-defined color definitions
        colors = Colors(LDrawDir, False)  # noqa
        colors.load()
        mat_list = {}

        LDrawFile(context, fileName, 0, trix)

        """
        Remove doubles and recalculate normals in each brick.
        The model is super high-poly without the cleanup.
        Cleanup can be disabled by user if wished.
        """

        # FIXME Rewrite - Split into separate function
        # The CleanUp import option was selected
        if CleanUpOpt == "CleanUp":  # noqa
            Console.log("CleanUp option selected")

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

        # The Gaps import option was selected
        if GapsOpt:  # noqa
            Console.log("Gaps option selected")

            # Select all the mesh
            for cur_obj in objects:
                cur_obj.select = True
                bpy.context.scene.objects.active = cur_obj
                if bpy.ops.object.mode_set.poll():

                    # Change to edit mode
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')

                    # Add small gaps between each brick
                    bpy.ops.transform.resize(value=(0.99, 0.99, 0.99))
                    if bpy.ops.object.mode_set.poll():

                        # Go back to object mode
                        bpy.ops.object.mode_set(mode='OBJECT')

        # Link identical bricks
        if LinkParts:  # noqa
            Console.log("LinkParts option selected")
            linkedParts()

        # Select all the mesh now that import is complete
        for cur_obj in objects:
            cur_obj.select = True

        # Update the scene with the changes
        context.scene.update()
        objects = []

        # Always reset 3D cursor to <0,0,0> after import
        bpy.context.scene.cursor_location = (0.0, 0.0, 0.0)

        # Display success message
        Console.log("{0} successfully imported!".format(fileName))
        return {'FINISHED'}

    except Exception as e:
        Console.log("ERROR: {0}\n{1}\n".format(
                    type(e).__name__, traceback.format_exc()))

        Console.log("ERROR: Reason: {0}.".format(
                    type(e).__name__))

        self.report({'ERROR'}, '''File not imported ("{0}").
Check the console logs for more information.'''.format(type(e).__name__))
        return {'CANCELLED'}


def linkedParts():
    """Clean-up design by linking identical parts (mesh/color)."""
    # Generate list of all materials (colors).
    colors = [color.name for color in bpy.data.materials]

    # List all unique meshes
    # For example 3002 and 3002.001 are considered equal.
    parts = []
    for part in objects:
        # Find all unique names of meshes, ignoring everything behind the '.'
        # and create a list of these names, making sure no double enties occur.
        if part.type == 'MESH' and part.name.split('.')[0] not in parts:
            parts.append(part.name.split('.')[0])

    # For each mesh/color combination create a link to a unique mesh.
    for part in parts:
        for color in colors:
            replaceParts(part, color)


def replaceParts(part, color):
    """Replace identical meshes of part/color-combination
       with a linked version.
    """
    mat = bpy.data.materials[color]
    mesh = None

    # For each imported object in the scene check
    # if it matches the given part name.
    for ob in objects:
        if ob.type == 'MESH' and ob.name.split('.')[0] == part:
            for slot in ob.material_slots:
                if slot.material == mat:
                    # First occurrence of part, save in mesh.
                    if mesh is None:
                        mesh = ob.data
                    # Following occurrences of part, link to mesh.
                    else:
                        ob.data = mesh
                    ob.select = True
        else:
            ob.select = False

    # Change mesh name in combination of .dat-filename and material.
    if mesh is not None:
        mesh.name = "{0} {1}".format(part, color)


# ------------ Operator ------------ #


class LDRImporterOps(bpy.types.Operator, ImportHelper):

    """LDR Importer Import Operator."""

    bl_idname = "import_scene.ldraw"
    bl_description = "Import an LDraw model (.ldr/.dat)"
    bl_label = "Import LDraw Model"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    # Instance the preferences system
    prefs = Preferences()

    # File type filter in file browser
    filename_ext = ".ldr"
    filter_glob = StringProperty(
        default="*.ldr;*.dat",
        options={'HIDDEN'}
    )

    ldrawPath = StringProperty(
        name="",
        description="Path to the LDraw Parts Library",
        default=prefs.getLDraw()
    )

    # Import options

    importScale = FloatProperty(
        name="Scale",
        description="Use a specific scale for each part",
        default=prefs.get("importScale", 1.00)
    )

    resPrims = EnumProperty(
        name="Resolution of part primitives",
        description="Resolution of part primitives",
        default=prefs.get("resPrims", "StandardRes"),
        items=(
            ("StandardRes", "Standard Primitives",
             "Import using standard resolution primitives"),
            ("HighRes", "High-Res Primitives",
             "Import using high resolution primitives. "
             "NOTE: This feature may create mesh errors"),
            ("LowRes", "Low-Res Primitives",
             "Import using low resolution primitives. "
             "NOTE: This feature may create mesh errors")
        )
    )

    cleanUpParts = EnumProperty(
        name="Model Cleanup Options",
        description="Model Cleanup Options",
        default=prefs.get("cleanUpParts", "CleanUp"),
        items=(
            ("CleanUp", "Basic Cleanup",
             "Remove double vertices, recalculate normals, "
             "add Edge Split modifier"),
            ("DoNothing", "Original LDraw Mesh",
             "Import using original LDraw Mesh"),
        )
    )

    addGaps = BoolProperty(
        name="Spaces Between Parts",
        description="Add small spaces between each part",
        default=prefs.get("addGaps", False)
    )

    lsynthParts = BoolProperty(
        name="Use LSynth Parts",
        description="Use LSynth parts during import",
        default=prefs.get("lsynthParts", False)
    )

    linkParts = BoolProperty(
        name="Link Identical Parts",
        description="Link identical parts by type and color (experimental)",
        default=prefs.get("linkParts", False)
    )

    def draw(self, context):
        """Display import options."""
        layout = self.layout
        box = layout.box()
        box.label("Import Options", icon='SCRIPTWIN')
        box.label("LDraw Path", icon='FILESEL')
        box.prop(self, "ldrawPath")
        box.prop(self, "importScale")
        box.label("Primitives", icon='MOD_BUILD')
        box.prop(self, "resPrims", expand=True)
        box.label("Model Cleanup", icon='EDIT')
        box.prop(self, "cleanUpParts", expand=True)
        box.label("Additional Options", icon='PREFERENCES')
        box.prop(self, "addGaps")
        box.prop(self, "lsynthParts")
        box.prop(self, "linkParts")

    def execute(self, context):
        """Set import options and run the script."""
        global LDrawDir, CleanUpOpt, GapsOpt, LinkParts
        LDrawDir = str(self.ldrawPath)
        CleanUpOpt = str(self.cleanUpParts)
        GapsOpt = bool(self.addGaps)
        LinkParts = bool(self.linkParts)

        # Clear array before adding data if it contains data already
        # Not doing so duplicates the indexes
        if paths:
            del paths[:]

        # Create placeholder for index 0.
        # It will be filled with the location of the model later.
        paths.append("")

        # Always search for parts in the `models` folder
        paths.append(os.path.join(LDrawDir, "models"))

        # The unofficial folder exists, search the standard folders
        if os.path.exists(os.path.join(LDrawDir, "unofficial")):
            paths.append(os.path.join(LDrawDir, "unofficial", "parts"))

            # The user wants to use high-res unofficial primitives
            if self.resPrims == "HighRes":
                paths.append(os.path.join(LDrawDir, "unofficial", "p", "48"))
            # The user wants to use low-res unofficial primitives
            elif self.resPrims == "LowRes":
                paths.append(os.path.join(LDrawDir, "unofficial", "p", "8"))

            # Search in the `unofficial/p` folder
            paths.append(os.path.join(LDrawDir, "unofficial", "p"))

            # The user wants to use LSynth parts
            if self.lsynthParts:
                if os.path.exists(os.path.join(LDrawDir, "unofficial",
                                               "lsynth")):
                    paths.append(os.path.join(LDrawDir, "unofficial",
                                              "lsynth"))
                    Console.log("Use LSynth Parts selected")

        # Always search for parts in the `parts` folder
        paths.append(os.path.join(LDrawDir, "parts"))

        # The user wants to use high-res primitives
        if self.resPrims == "HighRes":
            paths.append(os.path.join(LDrawDir, "p", "48"))
            Console.log("High-res primitives substitution selected")

        # The user wants to use low-res primitives
        elif self.resPrims == "LowRes":
            paths.append(os.path.join(LDrawDir, "p", "8"))
            Console.log("Low-res primitives substitution selected")

        # The user wants to use normal-res primitives
        else:
            Console.log("Standard-res primitives substitution selected")

        # Finally, search in the `p` folder
        paths.append(os.path.join(LDrawDir, "p"))

        # Create the preferences dictionary
        importOpts = {
            "addGaps": self.addGaps,
            "cleanUpParts": self.cleanUpParts,
            "importScale": self.importScale,
            "linkParts": self.linkParts,
            "lsynthParts": self.lsynthParts,
            "resPrims": self.resPrims
        }

        # Save the preferences and import the model
        self.prefs.saveLDraw(self.ldrawPath)
        self.prefs.save(importOpts)
        create_model(self, context, self.importScale)
        return {'FINISHED'}

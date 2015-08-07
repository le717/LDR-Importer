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

bl_info = {
    "name": "LDR Importer",
    "description": "Import LDraw models in .ldr and .dat format",
    "author": "LDR Importer developers and contributors",
    "version": (1, 2, 5),
    "blender": (2, 67, 0),
    "api": 31236,
    "location": "File > Import",
    "warning": "Incomplete Cycles support, MPD and Bricksmith models not supported",  # noqa
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/LDRAW_Importer",  # noqa
    "tracker_url": "https://github.com/le717/LDR-Importer/issues",
    "category": "Import-Export"
    }

import os
import sys
import mathutils
import traceback
from struct import unpack
from datetime import datetime

import bpy
from bpy.props import (StringProperty,
                       FloatProperty,
                       EnumProperty,
                       BoolProperty
                       )

from bpy_extras.io_utils import ImportHelper

# Global variables
objects = []
paths = []
mat_list = {}

"""
Default LDraw installation paths
Index 0: Windows
Index 1: Mac OS X
Index 2: Linux
Index 3: User defined, raw string
Storing the paths in a list prevents the creation of global variables
if they are changed. Instead, simply update the proper index.
"""
LDrawDirs = ["C:\\LDraw", "/Applications/ldraw/", "~/ldraw/", r""]

# Location of configuration file...
# ...on Windows...
if sys.platform == "win32":
    # Get the location of the user's %AppData%
    userAppData = os.path.expandvars(os.path.join(
        "%AppData%", "Blender Foundation", "Blender"))

    # Get the version of Blender being used
    blVersion = bpy.app.version_string[:4]

    # Set the final configuration path
    config_path = os.path.join(userAppData, blVersion, "scripts",
                               "presets", "io_import_ldraw")

# ...and not on Windows...
else:
    # `up` and `os.path.abspath` is used to break it out of core app files
    up = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    config_path = os.path.abspath(os.path.join(
        up, "presets", "io_import_ldraw"))

# Name of configuration file
config_filename = os.path.abspath(os.path.join(config_path, "config.py"))

def debugPrint(*myInput):
    """Debug print with identification timestamp."""
    # Format the output like print() does
    myOutput = [str(say) for say in myInput]

    # `strftime("%H:%M:%S.%f")[:-4]` trims milliseconds down to two places
    print("\n[LDR Importer] {0} - {1}\n".format(
        " ".join(myOutput), datetime.now().strftime("%H:%M:%S.%f")[:-4]))

# Attempt to read and use the path in the config
try:
    # A hacky trick that basically is: from config import *
    debugPrint("Configuration file found at\n{0}".format(config_filename))
    with open(config_filename, "rt", encoding="utf_8") as f:
        lines = f.read()
    exec(compile(lines, config_filename, 'exec'))

    # Set LDrawDirs[3] to the value that was in the file (ldraw_dir)
    LDrawDirs[3] = ldraw_dir  # noqa

# Suppress error when script is run the first time
# and config.py does not yet exist
except FileNotFoundError:  # noqa
    pass

# If we had an error, dump the traceback
except Exception as e:
    debugPrint("ERROR: {0}\n{1}\n".format(
               type(e).__name__, traceback.format_exc()))

    debugPrint("ERROR: Reason: {0}.".format(
               type(e).__name__))


def checkEncoding(file_path):
    """Check the encoding of a file for Endian encoding."""
    # Open it, read just the area containing a possible byte mark
    with open(file_path, "rb") as encode_check:
        encoding = encode_check.readline(3)

    # The file uses UCS-2 (UTF-16) Big Endian encoding
    if encoding == b"\xfe\xff\x00":
        return "utf_16_be"

    # The file uses UCS-2 (UTF-16) Little Endian
    elif encoding == b"\xff\xfe0":
        return "utf_16_le"

    # Use LDraw model stantard UTF-8
    else:
        return "utf_8"


class LDrawFile(object):

    """Scans LDraw files."""

    # FIXME: rewrite - Rewrite entire class (#35)
    def __init__(self, context, filename, mat, colour=None):

        engine = context.scene.render.engine
        self.points = []
        self.faces = []
        self.material_index = []
        self.subparts = []
        self.submodels = []
        self.part_count = 0

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

                # Use Cycles materials if user is using Cycles
                if engine == 'CYCLES':
                    material = getCyclesMaterial(n)
                # Non-Cycles materials (BI, BGE, POV-Ray, etc...)
                else:
                    material = getMaterial(n)

                if material is not None:
                    if me.materials.get(material.name) is None:
                        me.materials.append(material)

                    f.material_index = me.materials.find(material.name)

            self.ob = bpy.data.objects.new('LDrawObj', me)
            self.ob.name = os.path.basename(filename)

            self.ob.location = (0, 0, 0)

            objects.append(self.ob)

            # Link object to scene
            bpy.context.scene.objects.link(self.ob)

        for i in self.subparts:
            self.submodels.append(LDrawFile(context, i[0], i[1], i[2]))

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
            isPart = False
            if os.path.exists(filename):

                # Check encoding of `filename` for non UTF-8 compatibility
                # GitHub Issue #37
                file_encode = checkEncoding(filename)

                # Check if this is a main part or a subpart
                if not isSubPart(filename):
                    isPart = True

                # Read the brick using relative path (to entire model)
                with open(filename, "rt", encoding=file_encode) as f_in:
                    lines = f_in.readlines()

            else:
                # Search for the brick in the various folders
                fname, isPart = locate(filename)

                # The brick does not exist
                # TODO Do not halt on this condition
                if fname is None:
                    return False

                # Check encoding of `fname` too
                file_encode = checkEncoding(fname)

                # It exists, read it and get the data
                if os.path.exists(fname):
                    with open(fname, "rt", encoding=file_encode) as f_in:
                        lines = f_in.readlines()

            self.part_count += 1
            if self.part_count > 1 and isPart:
                self.subparts.append([filename, self.mat, self.colour])
            else:
                for retval in lines:
                    tmpdate = retval.strip()
                    if tmpdate != "":
                        tmpdate = tmpdate.split()

                        # TODO What is this condition for?
                        # le717 unable to find a case where it is hit.
                        if (tmpdate[0] == "0" and
                            len(tmpdate) >= 3 and
                            tmpdate[1].lower() == "!ldraw_org" and
                            "part" in tmpdate[2].lower() and
                            self.part_count > 1
                        ):
                            self.subparts.append(
                                [filename, self.mat, self.colour]
                            )
                            break

                        # Part content
                        if tmpdate[0] == "1":
                            new_file = tmpdate[14]
                            (
                                x, y, z, a, b, c,
                                d, e, f, g, h, i
                            ) = map(float, tmpdate[2:14])
                            mat_new = self.mat * mathutils.Matrix((
                                    (a, b, c, x),
                                    (d, e, f, y),
                                    (g, h, i, z),
                                    (0, 0, 0, 1)
                                ))

                            color = tmpdate[1]
                            if color == '16':
                                color = self.colour
                            subfiles.append([new_file, mat_new, color])

                        # Triangle (tri)
                        if tmpdate[0] == "3":
                            self.parse_line(tmpdate)

                        # Quadrilateral (quad)
                        if tmpdate[0] == "4":
                            self.parse_quad(tmpdate)

            if len(subfiles) > 0:
                subfile = subfiles.pop()
                filename = subfile[0]
                self.mat = subfile[1]
                self.colour = subfile[2]
            else:
                break


def getMaterial(colour):
    """Get Blender Internal Material Values."""
    if colour in colors:
        if not (colour in mat_list):
            mat = bpy.data.materials.new("Mat_{0}_".format(colour))
            col = colors[colour]

            mat.diffuse_color = col["color"]

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

    return None


def getCyclesMaterial(colour):
    """Get Cycles Material Values."""
    # FIXME: Not all colors are accessible
    if colour in colors:
        if not (colour in mat_list):
            col = colors[colour]

            if col["name"] == "Milky_White":
                mat = getCyclesMilkyWhite("Mat_{0}_".format(colour),
                                          col["color"])

            elif col["material"] == "BASIC" and col["luminance"] == 0:
                mat = getCyclesBase("Mat_{0}_".format(colour),
                                    col["color"], col["alpha"])

            elif col["luminance"] > 0:
                mat = getCyclesEmit("Mat_{0}_".format(colour), col["color"],
                                    col["alpha"], col["luminance"])

            elif col["material"] == "CHROME":
                mat = getCyclesChrome("Mat_{0}_".format(colour), col['color'])

            elif col["material"] == "PEARLESCENT":
                mat = getCyclesPearlMetal("Mat_{0}_".format(colour),
                                          col["color"], 0.2)

            elif col["material"] == "METAL":
                mat = getCyclesPearlMetal("Mat_{0}_".format(colour),
                                          col["color"], 0.5)

            elif col["material"] == "RUBBER":
                mat = getCyclesRubber("Mat_{0}_".format(colour),
                                      col["color"], col["alpha"])

            else:
                mat = getCyclesBase("Mat_{0}_".format(colour),
                                    col["color"], col["alpha"])

            mat_list[colour] = mat

        return mat_list[colour]
    else:
        mat_list[colour] = getCyclesBase("Mat_{0}_".format(colour),
                                         (1, 1, 0), 1.0)
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
        """
        The alpha transparency used by LDraw is too simplistic for Cycles,
        so I'm not using the value here. Other transparent colors
        like 'Milky White' will need special materials.
        """
        node = nodes.new('ShaderNodeBsdfGlass')
        node.location = -242, 154
        node.inputs['Color'].default_value = diffColor + (1.0,)
        node.inputs['Roughness'].default_value = 0.05
        node.inputs['IOR'].default_value = 1.46

    gloss = nodes.new('ShaderNodeBsdfGlossy')
    gloss.location = -242, -23
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


def getCyclesPearlMetal(name, diff_color, roughness):

    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90
    mix.inputs['Fac'].default_value = 0.4

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    glossy = nodes.new('ShaderNodeBsdfGlossy')
    glossy.location = -242, 154
    glossy.inputs['Color'].default_value = diff_color + (1.0,)
    glossy.inputs['Roughness'].default_value = 3.25

    aniso = nodes.new('ShaderNodeBsdfDiffuse')
    aniso.location = -242, -23
    aniso.inputs['Roughness'].default_value = 0.0

    links.new(mix.outputs[0], out.inputs[0])
    links.new(glossy.outputs[0], mix.inputs[1])
    links.new(aniso.outputs[0], mix.inputs[2])

    return mat


def getCyclesRubber(name, diff_color, alpha):
    """Cycles render engine Rubber material."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True

    nodes = mat.node_tree.nodes
    links = mat.node_tree.links

    for n in nodes:
        nodes.remove(n)

    mix = nodes.new('ShaderNodeMixShader')
    mix.location = 0, 90

    out = nodes.new('ShaderNodeOutputMaterial')
    out.location = 290, 100

    if alpha == 1.0:
        mix.inputs['Fac'].default_value = 0.05
        node = nodes.new('ShaderNodeBsdfDiffuse')
        node.location = -242, 154
        node.inputs['Color'].default_value = diff_color + (1.0,)
        node.inputs['Roughness'].default_value = 0.3

    else:
        """
        The alpha transparency used by LDraw is too simplistic for Cycles,
        so I'm not using the value here. Other transparent colors
        like 'Milky White' will need special materials.
        """
        mix.inputs['Fac'].default_value = 0.1
        node = nodes.new('ShaderNodeBsdfGlass')
        node.location = -242, 154
        node.inputs['Color'].default_value = diff_color + (1.0,)
        node.inputs['Roughness'].default_value = 0.01
        node.inputs['IOR'].default_value = 1.5191

    aniso = nodes.new('ShaderNodeBsdfAnisotropic')
    aniso.location = -242, -23
    aniso.inputs['Roughness'].default_value = 0.5
    aniso.inputs['Anisotropy'].default_value = 0.02

    links.new(mix.outputs[0], out.inputs[0])
    links.new(node.outputs[0], mix.inputs[1])
    links.new(aniso.outputs[0], mix.inputs[2])

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


def isSubPart(part):
    """Check if part is a main part or a subpart."""
    # FIXME: Remove this function
    # TODO: A file is a "part" only if its header states so.
    # (#40#issuecomment-31279788)
    return str.lower(os.path.split(part)[0]) == "s"


def locate(pattern):
    """Check if a part exists."""
    partName = pattern.replace("\\", os.path.sep)

    for path in paths:
        # Perform a case-sensitive check
        fname = os.path.join(path, partName)
        if os.path.exists(fname):
            return (fname, False)
        else:
            # Perform a normalized check
            fname = os.path.join(path, partName.lower())
            if os.path.exists(fname):
                return (fname, False)

    debugPrint("Could not find file {0}".format(fname))
    return (None, False)


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
    debugPrint("Attempting to import {0}".format(fileName))

    # The file format as hinted to by
    # conventional file extensions is not supported.
    # Recommended: http://ghost.kirk.by/file-extensions-are-only-hints
    if fileName[-4:].lower() not in (".ldr", ".dat"):

        debugPrint('''ERROR: Reason: Invalid File Type
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
            (1.0,  0.0, 0.0, 0.0), # noqa
            (0.0,  0.0, 1.0, 0.0), # noqa
            (0.0, -1.0, 0.0, 0.0),
            (0.0,  0.0, 0.0, 1.0) # noqa
        )) * (scale / 25)

        # If LDrawDir does not exist, stop the import
        if not os.path.isdir(LDrawDir):  # noqa
            debugPrint(''''ERROR: Cannot find LDraw installation at
{0}'''.format(LDrawDir))  # noqa
            self.report({'ERROR'}, '''Cannot find LDraw installation at
{0}'''.format(LDrawDir))  # noqa
            return {'CANCELLED'}

        colors = {}
        mat_list = {}

        # Get the material list from LDConfig.ldr
        getLDColors(self)

        LDrawFile(context, fileName, trix)

        """
        Remove doubles and recalculate normals in each brick.
        The model is super high-poly without the cleanup.
        Cleanup can be disabled by user if wished.
        """

        # FIXME Rewrite - Split into separate function
        # The CleanUp import option was selected
        if CleanUpOpt == "CleanUp":  # noqa
            debugPrint("CleanUp option selected")

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
            debugPrint("Gaps option selected")

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

        # Select all the mesh now that import is complete
        for cur_obj in objects:
            cur_obj.select = True

        # Update the scene with the changes
        context.scene.update()
        objects = []

        # Always reset 3D cursor to <0,0,0> after import
        bpy.context.scene.cursor_location = (0.0, 0.0, 0.0)

        # Display success message
        debugPrint("{0} successfully imported!".format(fileName))
        return {'FINISHED'}

    except Exception as e:
        debugPrint("ERROR: {0}\n{1}\n".format(
                   type(e).__name__, traceback.format_exc()))

        debugPrint("ERROR: Reason: {0}.".format(
                   type(e).__name__))

        self.report({'ERROR'}, '''File not imported ("{0}").
Check the console logs for more information.'''.format(type(e).__name__))
        return {'CANCELLED'}


def getLDColors(self):
    """Scan LDConfig to get the material color info."""
    # LDConfig.ldr does not exist for some reason
    if not os.path.exists(os.path.join(LDrawDir, "LDConfig.ldr")):  # noqa
        self.report({'ERROR'}, '''Could not find LDConfig.ldr at
{0}
Check the console logs for more information.'''.format(LDrawDir))  # noqa

        debugPrint('''ERROR: Could not find LDConfig.ldr at
{0}'''.format(LDrawDir))  # noqa
        return {'CANCELLED'}

    with open(os.path.join(LDrawDir, "LDConfig.ldr"),  # noqa
              "rt", encoding="utf_8") as ldconfig:
        lines = ldconfig.readlines()

    for line in lines:
        if len(line) > 3:
            if line[2:4].lower() == '!c':
                line_split = line.split()

                name = line_split[2]
                code = line_split[4]

                color = {
                    "name": name,
                    "color": hex_to_rgb(line_split[6][1:]),
                    "alpha": 1.0,
                    "luminance": 0.0,
                    "material": "BASIC"
                }

                if hasColorValue(line_split, "ALPHA"):
                    color["alpha"] = int(
                        getColorValue(line_split, "ALPHA")) / 256.0

                if hasColorValue(line_split, "LUMINANCE"):
                    color["luminance"] = int(
                        getColorValue(line_split, "LUMINANCE"))

                if hasColorValue(line_split, "CHROME"):
                    color["material"] = "CHROME"

                if hasColorValue(line_split, "PEARLESCENT"):
                    color["material"] = "PEARLESCENT"

                if hasColorValue(line_split, 'RUBBER'):
                    color["material"] = "RUBBER"

                if hasColorValue(line_split, "METAL"):
                    color["material"] = "METAL"

                if hasColorValue(line_split, "MATERIAL"):
                    subline = line_split[line_split.index("MATERIAL"):]

                    color["material"] = getColorValue(subline, "MATERIAL")
                    color["secondary_color"] = getColorValue(subline, "VALUE")[1:]
                    color["fraction"] = getColorValue(subline, "FRACTION")
                    color["vfraction"] = getColorValue(subline, "VFRACTION")
                    color["size"] = getColorValue(subline, "SIZE")
                    color["minsize"] = getColorValue(subline, "MINSIZE")
                    color["maxsize"] = getColorValue(subline, "MAXSIZE")

                colors[code] = color


def hasColorValue(line, value):
    """Check if the color value is present."""
    return value in line


def getColorValue(line, value):

    if value in line:
        n = line.index(value)
        return line[n + 1]


def findWinLDrawDir():
    """Detect LDraw installation path on Windows."""
    # Use previously defined path if it exists
    if LDrawDirs[3] != r"":
        install_path = LDrawDirs[3]

    # No previous path, so check at default installation (C:\\LDraw)
    elif os.path.isfile(os.path.join(LDrawDirs[0], "LDConfig.ldr")):
        install_path = LDrawDirs[0]

    # If that fails, look in Program Files
    elif os.path.isfile(os.path.join(
                        "C:\\Program Files\\LDraw", "LDConfig.ldr")):
        install_path = "C:\\Program Files\\LDraw"

    # If it fails again, look in Program Files (x86)
    elif os.path.isfile(os.path.join(
                        "C:\\Program Files (x86)\\LDraw", "LDConfig.ldr")):
        install_path = "C:\\Program Files (x86)\\LDraw"

    # If all that fails, fall back to default installation
    else:
        install_path = LDrawDirs[0]

    # Update the list with the path (avoids creating a global variable)
    LDrawDirs[0] = install_path


def RunMe(self, context):
    """Run process to store the installation path."""
    saveInstallPath(self)


def hex_to_rgb(rgb_str):
    """Convert color hex value to RGB value."""
    int_tuple = unpack('BBB', bytes.fromhex(rgb_str))
    return tuple([val / 255 for val in int_tuple])

# Model cleanup options
# DoNothing option does not require a check later on
cleanupOptions = (
    ("CleanUp", "Basic Cleanup",
        "Remove double vertices, recalculate normals, add Edge Split modifier"),
    ("DoNothing", "Original LDraw Mesh", "Import LDraw Mesh as Original"),
)

# Primitives import options
primsOptions = (
    ("StandardRes", "Standard Primitives",
        "Import primitives using standard resolution"),
    ("HighRes", "High-Res Primitives",
        "Import primitives using high resolution"),
    ("LowRes", "Low-Res Primitives",
        "Import primitives using low resolution")
)

# ------------ Operator ------------ #


class LDRImporterOps(bpy.types.Operator, ImportHelper):

    """LDR Importer Operator."""

    bl_idname = "import_scene.ldraw"
    bl_description = "Import an LDraw model (.ldr/.dat)"
    bl_label = "Import LDraw Model"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    # File type filter in file browser
    filename_ext = ".ldr"

    filter_glob = StringProperty(
        default="*.ldr;*.dat",
        options={'HIDDEN'}
    )

    # The installation path was defined, use it
    if LDrawDirs[3] != r"":
        FinalLDrawDir = LDrawDirs[3]

    # The installation path was not defined, fall back to defaults
    # On Windows, this means attempting to detect the installation
    else:

        # Run Windows installation path detection process
        if sys.platform == "win32":
            findWinLDrawDir()

        FinalLDrawDir = {
            "win32": LDrawDirs[0],
            "darwin": LDrawDirs[1]
        }.get(sys.platform, LDrawDirs[2])

    debugPrint('''The LDraw Parts Library installation path to be used is
{0}'''.format(FinalLDrawDir))

    ldrawPath = StringProperty(
        name="",
        description="Path to the LDraw Parts Library",
        default=FinalLDrawDir,
        update=RunMe
    )

    # Import options

    scale = FloatProperty(
        name="Scale",
        description="Use a specific scale for each brick",
        default=1.00
    )

    resPrims = EnumProperty(
        name="Resolution of part primitives",
        description="Resolution of part primitives",
        items=primsOptions
    )

    cleanUpModel = EnumProperty(
        name="Model Cleanup Options",
        description="Model Cleanup Options",
        items=cleanupOptions
    )

    addGaps = BoolProperty(
        name="Spaces Between Bricks",
        description="Add small spaces between each brick",
        default=False
    )

    lsynthParts = BoolProperty(
        name="Use LSynth Parts",
        description="Use LSynth parts during import",
        default=False
    )

    def draw(self, context):
        """Display import options."""
        layout = self.layout
        box = layout.box()
        box.label("Import Options", icon='SCRIPTWIN')
        box.label("LDraw Path", icon='FILESEL')
        box.prop(self, "ldrawPath")
        box.prop(self, "scale")
        box.label("Primitives", icon='MOD_BUILD')
        box.prop(self, "resPrims", expand=True)
        box.label("Model Cleanup", icon='EDIT')
        box.prop(self, "cleanUpModel", expand=True)
        box.label("Additional Options", icon='PREFERENCES')
        box.prop(self, "addGaps")
        box.prop(self, "lsynthParts")

    def execute(self, context):
        """Set import options and run the script."""
        global LDrawDir, CleanUpOpt, GapsOpt
        LDrawDir = str(self.ldrawPath)
        WhatRes = str(self.resPrims)
        CleanUpOpt = str(self.cleanUpModel)
        GapsOpt = bool(self.addGaps)
        LSynth = bool(self.lsynthParts)

        # Clear array before adding data if it contains data already
        # Not doing so duplicates the indexes
        try:
            if paths[0]:
                del paths[:]
        except IndexError:
            pass

        # Create placeholder for index 0.
        # It will be filled with the location of the model later.
        paths.append("")

        # Always search for parts in the `models` folder
        paths.append(os.path.join(LDrawDir, "models"))

        # The unofficial folder exists, search the standard folders
        if os.path.exists(os.path.join(LDrawDir, "unofficial")):
            paths.append(os.path.join(LDrawDir, "unofficial", "parts"))

            # The user wants to use high-res unofficial primitives
            if WhatRes == "HighRes":
                paths.append(os.path.join(LDrawDir, "unofficial", "p", "48"))
            # The user wants to use low-res unofficial primitives
            elif WhatRes == "LowRes":
                paths.append(os.path.join(LDrawDir, "unofficial", "p", "8"))

            # Search in the `unofficial/p` folder
            paths.append(os.path.join(LDrawDir, "unofficial", "p"))

            # The user wants to use LSynth parts
            if LSynth:
                if os.path.exists(os.path.join(LDrawDir, "unofficial",
                                               "lsynth")):
                    paths.append(os.path.join(LDrawDir, "unofficial",
                                              "lsynth"))
                    debugPrint("Use LSynth Parts selected")

        # Always search for parts in the `parts` folder
        paths.append(os.path.join(LDrawDir, "parts"))

        # The user wants to use high-res primitives
        if WhatRes == "HighRes":
            paths.append(os.path.join(LDrawDir, "p", "48"))
            debugPrint("High-res primitives substitution selected")

        # The user wants to use low-res primitives
        elif WhatRes == "LowRes":
            paths.append(os.path.join(LDrawDir, "p", "8"))
            debugPrint("Low-res primitives substitution selected")

        # The user wants to use normal-res primitives
        else:
            debugPrint("Standard-res primitives substitution selected")

        # Finally, search in the `p` folder
        paths.append(os.path.join(LDrawDir, "p"))

        """
        Blender for Windows does not like the 'update' key in ldrawPath{},
        so force it to run. We can run the process directly,
        rather than going through RunMe().
        """
        if sys.platform == "win32":
            saveInstallPath(self)

        create_model(self, context, self.scale)
        return {'FINISHED'}


def saveInstallPath(self):
    """Save the LDraw installation path for future use."""
    # TODO: Remove this dangerous thing
    # The contents of the configuration file
    config_contents = '''# -*- coding: utf-8 -*-
# LDR Importer Configuration File #

# Path to the LDraw Parts Library
{0}"{1}"
'''.format("ldraw_dir = r", self.ldrawPath)

    # Create the config path if it does not exist
    if not os.path.exists(config_path):
        os.makedirs(config_path)

    # Write the config file
    with open(config_filename, "wt", encoding="utf_8") as f:
        f.write(config_contents)


def menuImport(self, context):
    """Import menu listing label."""
    self.layout.operator(LDRImporterOps.bl_idname, text="LDraw (.ldr/.dat)")


def register():
    """Register Menu Listing."""
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menuImport)


def unregister():
    """Unregister Menu Listing."""
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menuImport)


if __name__ == "__main__":
    register()

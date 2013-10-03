###### BEGIN GPL LICENSE BLOCK #####
#
#  This program is free software; you can redistribute it and/or
#  modify it under the terms of the GNU General Public License
#  as published by the Free Software Foundation; either version 2
#  of the License, or (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program; if not, write to the Free Software Foundation,
#  Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.
#
###### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Blender 2.6 LDraw Importer 1.0",
    "description": "Import LDraw models in .dat, and .ldr format",
    "author": "David Pluntze, JrMasterModelBuilder, Triangle717, Banbury",
    "version": (1, 0, 0),
    "blender": (2, 63, 0),
    "api": 31236,
    "location": "File > Import",
    "warning": "Does not support Cycles materials",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/LDRAW_Importer",
    #"tracker_url": "maybe"
                   #"soon",
    "category": "Import-Export"}

import os
import sys
import math
import mathutils
import traceback
from struct import unpack

import bpy
import bpy.props
from bpy_extras.io_utils import ImportHelper


# Global variables
mat_list = {}
colors = {}
scale = 1.0
WinLDrawDir = "C:\\LDraw"
OSXLDrawDir = "/Applications/ldraw/"
LinuxLDrawDir = "~/ldraw/"
objects = []


# Scans LDraw files
class LDrawFile(object):

    def __init__(self, filename, mat, colour=None):
        self.points = []
        self.faces = []
        self.material_index = []
        self.subparts = []
        self.submodels = []
        self.part_count = 0

        self.mat = mat
        self.colour = colour
        self.parse(filename)

        if len(self.points) > 0 and len(self.faces) > 0:
            me = bpy.data.meshes.new('LDrawMesh')
            me.from_pydata(self.points, [], self.faces)
            me.validate()
            me.update()

            for i, f in enumerate(me.polygons):
                n = self.material_index[i]
                material = getMaterial(n)

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
            self.submodels.append(LDrawFile(i[0], i[1], i[2]))

    def parse_line(self, line):
        verts = []
        color = line[1]

        if color == '16':
            color = self.colour

        num_points = int((len(line) - 2) / 3)
        #matrix = mathutils.Matrix(mat)
        for i in range(num_points):
                self.points.append((self.mat * mathutils.Vector((float(line[i * 3 + 2]), float(line[i * 3 + 3]), float(line[i * 3 + 4])))).
                to_tuple())
                verts.append(len(self.points) - 1)
        self.faces.append(verts)
        self.material_index.append(color)

    def parse_quad(self, line):
        """Properly construct quads in each brick"""
        color = line[1]
        verts = []
        num_points = 4
        v = []

        if color == '16':
            color = self.colour

        v.append(self.mat * mathutils.Vector((float(line[0 * 3 + 2]), float(line[0 * 3 + 3]), float(line[0 * 3 + 4]))))
        v.append(self.mat * mathutils.Vector((float(line[1 * 3 + 2]), float(line[1 * 3 + 3]), float(line[1 * 3 + 4]))))
        v.append(self.mat * mathutils.Vector((float(line[2 * 3 + 2]), float(line[2 * 3 + 3]), float(line[2 * 3 + 4]))))
        v.append(self.mat * mathutils.Vector((float(line[3 * 3 + 2]), float(line[3 * 3 + 3]), float(line[3 * 3 + 4]))))

        nA = (v[1] - v[0]).cross(v[2] - v[0])
        nB = (v[2] - v[1]).cross(v[3] - v[1])

        for i in range(num_points):
            verts.append(len(self.points) + i)

        if (nA.dot(nB) < 0):
            self.points.extend([v[0].to_tuple(), v[1].to_tuple(), v[3].to_tuple(), v[2].to_tuple()])
        else:
            self.points.extend([v[0].to_tuple(), v[1].to_tuple(), v[2].to_tuple(), v[3].to_tuple()])

        self.faces.append(verts)
        self.material_index.append(color)

    def parse(self, filename):
        subfiles = []

        while True:
            # Attempt to open the required brick using relative path
            try:
                with open(filename, "rt") as f_in:
                    lines = f_in.readlines()
            except Exception as ex:
                # That didn't work, so attempt to open the required brick
                # using absolute path
                try:
                    fname, isPart = locate(filename)
                    with open(fname, "rt") as f_in:
                        lines = f_in.readlines()

                # The brick could not be found at all
                except Exception as ex:
                    print("\nFile not found: {0}".format(fname))
                    # break prevents a consequential but unnecessary traceback
                    # from occurring, while only displaying the missing brick
                    break

            self.part_count += 1
            if self.part_count > 1 and isPart:
                self.subparts.append([filename, self.mat, self.colour])
            else:
                for retval in lines:
                    tmpdate = retval.strip()
                    if tmpdate != '':
                        tmpdate = tmpdate.split()
                        # LDraw brick comments
                        if tmpdate[0] == "0":
                            if len(tmpdate) >= 3:
                                if (
                                    tmpdate[1] == "!LDRAW_ORG" and
                                    'Part' in tmpdate[2]
                                ):
                                    if self.part_count > 1:
                                        self.subparts.append([filename, self.mat, self.colour])
                                        break
                        # The brick content
                        if tmpdate[0] == "1":
                            new_file = tmpdate[14]
                            x, y, z, a, b, c, d, e, f, g, h, i = map(float, tmpdate[2:14])
                           #mat_new = self.mat * mathutils.Matrix( [[a, d, g, 0], [b, e, h, 0], [c, f, i, 0], [x, y, z, 1]] )
                            mat_new = self.mat * mathutils.Matrix(((a, b, c, x), (d, e, f, y), (g, h, i, z), (0, 0, 0, 1)))

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
    """Get and apply each brick's material"""
    if colour in colors:
        if not (colour in mat_list):
            mat = bpy.data.materials.new('Mat_' + colour + "_")
            col = colors[colour]

            mat.diffuse_color = col['color']

            alpha = col['alpha']
            if alpha < 1.0:
                mat.use_transparency = True
                mat.alpha = alpha

            mat.emit = col['luminance'] / 100

            if col['material'] == 'CHROME':
                mat.specular_intensity = 1.4
                mat.roughness = 0.01
                mat.raytrace_mirror.use = True
                mat.raytrace_mirror.reflect_factor = 0.3
            elif col['material'] == 'PEARLESCENT':
                mat.specular_intensity = 0.1
                mat.roughness = 0.32
                mat.raytrace_mirror.use = True
                mat.raytrace_mirror.reflect_factor = 0.07
            elif col['material'] == 'RUBBER':
                mat.specular_intensity = 0.19
            elif col['material'] == 'METAL':
                mat.specular_intensity = 1.473
                mat.specular_hardness = 292
                mat.diffuse_fresnel = 0.93
                mat.darkness = 0.771
                mat.roughness = 0.01
                mat.raytrace_mirror.use = True
                mat.raytrace_mirror.reflect_factor = 0.9
            #elif col['material'] == 'GLITTER':
            #    slot = mat.texture_slots.add()
            #    tex = bpy.data.textures.new('GlitterTex', type = 'STUCCI')
            #    tex.use_color_ramp = True
            #
            #    slot.texture = tex
            else:
                mat.specular_intensity = 0.2

            mat_list[colour] = mat

        return mat_list[colour]
    return mat_list['0']


def locate(pattern):
    """
    Locate all files matching supplied filename pattern in and below
    supplied root directory.
    Check all available possible folders so every single brick
    can be imported, even unofficial ones.
    """
    fname = pattern.replace('\\', os.path.sep)
    isPart = False
    if str.lower(os.path.split(fname)[0]) == 's':
        isSubpart = True
    else:
        isSubpart = False

    #lint:disable
    ldrawPath = os.path.join(LDrawDir, fname).lower()
    hiResPath = os.path.join(LDrawDir, "p", "48", fname).lower()
    primitivesPath = os.path.join(LDrawDir, "p", fname).lower()
    partsPath = os.path.join(LDrawDir, "parts", fname).lower()
    partsSPath = os.path.join(LDrawDir, "parts", "s", fname).lower()
    UnofficialPath = os.path.join(LDrawDir, "unofficial", fname).lower()
    UnofficialhiResPath = os.path.join(LDrawDir, "unofficial", "p", "48", fname).lower()
    UnofficialPrimPath = os.path.join(LDrawDir, "unofficial", "p", fname).lower()
    UnofficialPartsPath = os.path.join(LDrawDir, "unofficial", "parts", fname).lower()
    UnofficialPartsSPath = os.path.join(LDrawDir, "unofficial", "parts", "s", fname).lower()
    #lint:enable
    if os.path.exists(fname):
        pass
    elif os.path.exists(ldrawPath):
        fname = ldrawPath
    elif os.path.exists(hiResPath) and not HighRes:  # lint:ok
        fname = hiResPath
    elif os.path.exists(primitivesPath):
        fname = primitivesPath
    elif os.path.exists(partsPath):
        fname = partsPath
    elif os.path.exists(partsSPath):
        fname = partsSPath
    elif os.path.exists(UnofficialPath):
        fname = UnofficialPath
    elif os.path.exists(UnofficialhiResPath):
        fname = UnofficialhiResPath
    elif os.path.exists(UnofficialPrimPath):
        fname = UnofficialPrimPath
    elif os.path.exists(UnofficialPartsPath):
        fname = UnofficialPartsPath
    elif os.path.exists(UnofficialPartsSPath):
        fname = UnofficialPartsSPath
        if not isSubpart:
            isPart = True
    else:
        print("Could not find file {0}".format(fname))
        return None

    return (fname, isPart)


def create_model(self, scale, context):
    """Create the actual model"""
    global objects
    global colors
    global mat_list

    file_name = self.filepath
    print("\n{0}".format(file_name))
    try:

        # Set the initial transformation matrix, set the scale factor to 0.05
        # and rotate -90 degrees around the x-axis, so the object is upright.
        mat = mathutils.Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))) * scale
        mat = mat * mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')

        # If LDrawDir does not exist, stop the import
        if not os.path.isdir(LDrawDir):
            print ('''
ERROR: Cannot find LDraw System of Tools installation at
{0}
'''.format(LDrawDir))
            return False

        colors = {}
        mat_list = {}

        # Get material list from LDConfig
        scanLDConfig()

        model = LDrawFile(file_name, mat)
        """
        Remove doubles and recalculate normals in each brick.
        The model is super high-poly without the cleanup.
        Cleanup can be disabled by user if wished.
        """
        if CleanUp:
            for cur_obj in objects:
                cur_obj.select = True
                bpy.context.scene.objects.active = cur_obj
                if bpy.ops.object.mode_set.poll():
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.remove_doubles(threshold=0.01)
                    bpy.ops.mesh.normals_make_consistent()
                    if bpy.ops.object.mode_set.poll():
                        bpy.ops.object.mode_set(mode='OBJECT')
                        bpy.ops.object.shade_smooth()
                        bpy.ops.object.mode_set()
                        m = cur_obj.modifiers.new("edge_split", type='EDGE_SPLIT')
                        m.split_angle = math.pi / 4
                cur_obj.select = False

        context.scene.update()
        objects = []

        # Always reset 3D cursor to <0,0,0> after import
        bpy.context.scene.cursor_location = (0.0, 0.0, 0.0)

        # Display success message
        print("{0} successfully imported!".format(file_name))

    except Exception as ex:
        print(traceback.format_exc())
        print("\nOops, something went wrong!")


def scanLDConfig():
    """Scan LDConfig to get the material color info."""
    with open(os.path.join(LDrawDir, "LDConfig.ldr"), "rt") as ldconfig:
        ldconfig_lines = ldconfig.readlines()

    for line in ldconfig_lines:
        if len(line) > 3:
            if line[2:4].lower() == '!c':
                line_split = line.split()

                name = line_split[2]
                code = line_split[4]

                color = {'name': name, 'color': hex_to_rgb(line_split[6][1:]), 'alpha': 1.0, 'luminance': 0.0, 'material': 'BASIC'}

                #if len(line_split) > 10 and line_split[9] == 'ALPHA':
                if hasColorValue(line_split, 'ALPHA'):
                    color['alpha'] = int(getColorValue(line_split, 'ALPHA')) / 256.0

                if hasColorValue(line_split, 'LUMINANCE'):
                    color['luminance'] = int(getColorValue(line_split, 'LUMINANCE'))

                if hasColorValue(line_split, 'CHROME'):
                    color['material'] = 'CHROME'

                if hasColorValue(line_split, 'PEARLESCENT'):
                    color['material'] = 'PEARLESCENT'

                if hasColorValue(line_split, 'RUBBER'):
                    color['material'] = 'RUBBER'

                if hasColorValue(line_split, 'METAL'):
                    color['material'] = 'METAL'

                if hasColorValue(line_split, 'MATERIAL'):
                    subline = line_split[line_split.index('MATERIAL'):]

                    color['material'] = getColorValue(subline, 'MATERIAL')
                    color['secondary_color'] = getColorValue(subline, 'VALUE')[1:]
                    color['fraction'] = getColorValue(subline, 'FRACTION')
                    color['vfraction'] = getColorValue(subline, 'VFRACTION')
                    color['size'] = getColorValue(subline, 'SIZE')
                    color['minsize'] = getColorValue(subline, 'MINSIZE')
                    color['maxsize'] = getColorValue(subline, 'MAXSIZE')

                colors[code] = color


def hasColorValue(line, value):
    return value in line


def getColorValue(line, value):
    if value in line:
        n = line.index(value)
        return line[n + 1]


def get_path(self, context):
    """Displays full file path of model being imported"""
    print(context)


def hex_to_rgb(rgb_str):
    """Convert color hex value to RGB value"""
    int_tuple = unpack('BBB', bytes.fromhex(rgb_str))
    return tuple([val / 255 for val in int_tuple])

# ------------ Operator ------------ #


class IMPORT_OT_ldraw(bpy.types.Operator, ImportHelper):
    """LDraw Importer Operator"""
    bl_idname = "import_scene.ldraw"
    bl_description = 'Import an LDraw model (.dat/.ldr)'
    bl_label = "Import LDraw Model"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'UNDO', 'PRESET'}

    ## Script Options ##

    ldrawPath = bpy.props.StringProperty(
        name="LDraw Path",
        description="The folder path to your LDraw System of Tools installation.",
        default={"win32": WinLDrawDir, "darwin": OSXLDrawDir}.get(sys.platform, LinuxLDrawDir),
        update=get_path
    )

    scale = bpy.props.FloatProperty(
        name="Scale",
        description="Scale the model by this amount.",
        default=0.05
    )

    cleanupModel = bpy.props.BoolProperty(
        name="Enable Model Cleanup",
        description="Remove double vertices and make normals consistent",
        default=True
    )

    highresBricks = bpy.props.BoolProperty(
        name="Do Not Use High-res bricks",
        description="Do not use high-res bricks to import your model.",
        default=True
    )

    def execute(self, context):
        global LDrawDir, CleanUp, HighRes, CenterMesh
        LDrawDir = str(self.ldrawPath)
        CleanUp = bool(self.cleanupModel)
        HighRes = bool(self.highresBricks)
        create_model(self, self.scale, context)
        return {'FINISHED'}


# Registering / Unregister
def menu_import(self, context):
    self.layout.operator(IMPORT_OT_ldraw.bl_idname, text="LDraw (.dat/.ldr)")


def register():
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_import)


def unregister():
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_import)


if __name__ == "__main__":
    register()

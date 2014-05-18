# -*- coding: utf-8 -*-
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
    "name": "LDR Importer NG",
    "description": "Import LDraw models in .ldr and .dat format",
    "author": "The LDR Importer Developers and Contributors",
    "version": (0, 1),
    "blender": (2, 69, 0),
    #"api": 31236,
    "location": "File > Import",
    "warning": "No materials!",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/LDRAW_Importer",  # noqa
    "tracker_url": "https://github.com/le717/LDR-Importer/issues",
    "category": "Import-Export"
}

import os
from time import strftime

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

from mathutils import Matrix, Vector


def debugPrint(*myInput):
    """Debug print with identification timestamp"""
    myOutput = [str(say) for say in myInput]

    print("\n[LDR Importer] {0} - {1}\n".format(
        " ".join(myOutput), strftime("%H:%M:%S")))


def checkEncoding(filePath):
    """Check the encoding of a file"""

    # Open it, read just the area containing a possible byte mark
    with open(filePath, "rb") as encodeCheck:
        fileEncoding = encodeCheck.readline(3)

    # The file uses UCS-2 (UTF-16) Big Endian encoding
    if fileEncoding == b"\xfe\xff\x00":
        return "utf_16_be"

    # The file uses UCS-2 (UTF-16) Little Endian
    # There seem to be two variants of UCS-2LE that must be checked for
    elif fileEncoding in (b"\xff\xfe0", b"\xff\xfe/"):
        return "utf_16_le"

    # Use LDraw model standard UTF-8
    else:
        return "utf_8"


class LDRImporterPreferences(AddonPreferences):
    """LDR Importer Preferences"""
    bl_idname = __name__
    ldraw_library_path = StringProperty(name="LDraw Library path",
                                        subtype="DIR_PATH"
                                        )

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ldraw_library_path")


def mergePart(active):
    emptyMesh = bpy.data.meshes.new(name=active.name)
    bpy.context.scene.objects.active = active

    # Selects children without selecting the empty
    bpy.ops.object.select_grouped(type='CHILDREN_RECURSIVE', extend=False)
    
    for obj in bpy.context.object.children:
        if obj.type != 'EMPTY':
            obj.select = True

    # Merges brick parts into one mesh
    bpy.ops.object.join()
    bpy.ops.object.parent_clear(type='CLEAR_KEEP_TRANSFORM')

def deleteEmpty():
    # Selects and deletes empties
    bpy.ops.object.select_by_type(type='EMPTY')
    bpy.ops.object.delete(use_global=False)


def cleanUpOptions(objects):
    """
    Remove doubles and recalculate normals in each brick.
    The model is really high-poly without the cleanup.
    Cleanup can be disabled by user if wished.
    """

    # Select all the mesh
    for cur_obj in objects:
        cur_obj.select = True
        bpy.context.scene.objects.active = cur_obj

        if bpy.ops.object.mode_set.poll():
            # Switch to edit mode
            bpy.ops.object.mode_set(mode='EDIT')
            bpy.ops.mesh.select_all(action='SELECT')

            # Remove doubles, calculate normals
            bpy.ops.mesh.remove_doubles(threshold=0.01)
            bpy.ops.mesh.normals_make_consistent()

            if bpy.ops.object.mode_set.poll():
                # Go back to object mode
                bpy.ops.object.mode_set(mode='OBJECT')

                # Set smooth shading
                bpy.ops.object.shade_smooth()

        # Add 30 degree edge split modifier to all bricks
        edges = cur_obj.modifiers.new(
            "Edge Split", type='EDGE_SPLIT')
        if edges is not None:
            edges.split_angle = 0.523599


#def originChange(argument):
#    bpy.ops.object.origin_set(type='ORIGIN_CENTER_OF_MASS')
#    # bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY')


class LDRImporterOperator(bpy.types.Operator, ImportHelper):
    """LDR Importer Operator"""
    bl_idname = "import_scene.ldraw_ng"
    bl_description = "Import an LDraw model (.ldr/.dat)"
    bl_label = "Import LDraw Model - NG"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'REGISTER', 'UNDO', 'PRESET'}

    filename_ext = ".ldr"

    filter_glob = StringProperty(
        default="*.ldr;*.dat",
        options={'HIDDEN'}
    )

    scale = FloatProperty(
        name="Scale",
        description="Use a specific scale for each brick",
        default=0.05
    )

    resPrims = EnumProperty(
        name="Resolution of part primitives",
        description="Resolution of part primitives",
        items=(
            ("Standard", "Standard primitives",
                "Import primitives using standard resolution"),
            ("48", "High resolution primitives",
                "Import primitives using high resolution"),
            ("8", "Low resolution primitives",
                "Import primitives using low resolution")
        )
    )

    mergeParts = EnumProperty(
        # Leave `name` blank for better display
        name="Merge parts",
        description="Merge the models from the subfiles into one mesh",
        items=(
            ("MERGE_TOPLEVEL_PARTS", "Merge top-level parts",
                "Merge the children of the base model with all their children"),
            ("NO_MERGE", "No merge",
                "Do not merge any meshes"),
#            ("MERGE_EVERYTHING", "Merge everything",
#                "Merge the whole model into one mesh")
        )
    )

    cleanUpModel = EnumProperty(
        name="Model Cleanup Options",
        description="Model Cleanup Options",
        items=(
            ("CleanUp", "Basic Cleanup",
                "Remove double vertices, recalculate normals, add Edge Split modifier"),
            ("DoNothing", "Original LDraw Mesh", "Import LDraw Mesh as Original"),
            )
    )

    def draw(self, context):
        """Display import options"""
        layout = self.layout
        box = layout.box()
        box.label("Import Options", icon='SCRIPTWIN')
        box.prop(self, "scale")
        box.label("Primitives", icon='MOD_BUILD')
        box.prop(self, "resPrims", expand=True)
        box.label("Merge parts", icon='MOD_BOOLEAN')
        box.prop(self, "mergeParts", expand=True)
        box.label("Model Cleanup", icon='EDIT')
        box.prop(self, "cleanUpModel", expand=True)

    def findLDrawDir(self, context):
        """
        Attempt to detect Parts Library location
        and populate set proper part search folders.
        """
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        chosen_path = addon_prefs.ldraw_library_path
        library_path = ""
        if chosen_path.strip() != "":
            if os.path.isfile(os.path.join(chosen_path, "LDConfig.ldr")):
                library_path = chosen_path
            else:
                self.report({"ERROR"},
                            "Specified path {0} does not exist".format(
                                chosen_path))
                return
        else:
            path_guesses = [
                r"C:\LDraw",
                r"C:\Program Files\LDraw",
                r"C:\Program Files (x86)\LDraw",
                os.path.expanduser("~/ldraw"),
                os.path.expanduser("~/LDraw"),
                "/usr/local/share/ldraw",
                "/opt/ldraw",
                "/Applications/LDraw",
                "/Applications/ldraw",
            ]
            for guess in path_guesses:
                if os.path.isfile(os.path.join(guess, "LDConfig.ldr")):
                    library_path = guess
                    break
            if not library_path:
                return

        subdirs = ["models", "parts", "p"]
        unofficial_path = os.path.join(library_path, "unofficial")
        if os.path.isdir(unofficial_path):
            subdirs.append(os.path.join("unofficial", "parts"))
            subdirs.append(os.path.join("unofficial", "p"))
            subdirs.append(os.path.join("unofficial", "p", str(self.resPrims)))

        subdirs.append(os.path.join("p", str(self.resPrims)))

        return [os.path.join(library_path, component) for component in subdirs]

    def execute(self, context):
        self.complete = True
        self.no_mesh_errors = True
        # Part cache - keys = filenames, values = LDrawPart subclasses
        self.part_cache = {}

        self.search_paths = self.findLDrawDir(context)
        if not self.search_paths:
            self.report({"ERROR"}, ("Could not find LDraw Parts Library"
                                    " after looking in common locations."
                                    " Please check the addon preferences!"))
            return {"CANCELLED"}
        self.report({"INFO"}, "Search paths are {0}".format(self.search_paths))

        self.search_paths.insert(0, os.path.dirname(self.filepath))
        model = self.parse_part(self.filepath)()

        # Rotate model to proper LDraw orientation
        model.obj.matrix_world = Matrix((
            (1.0,  0.0, 0.0, 0.0),  # noqa
            (0.0,  0.0, 1.0, 0.0),  # noqa
            (0.0, -1.0, 0.0, 0.0),
            (0.0,  0.0, 0.0, 1.0)   # noqa
        )) * self.scale

        if not self.complete:
            self.report({"WARNING"}, ("Not all parts could be found. "
                                      "Check the console for a list."))
        if not self.no_mesh_errors:
            self.report({"WARNING"}, "Some of the meshes loaded contained errors.")

        # Make a copy of the mesh list for use later
        modelBricks = model.obj.children[:]

        if str(self.mergeParts) == "MERGE_TOPLEVEL_PARTS":
            for child in model.obj.children:
                mergePart(child)

        # Deletes left-over empties from `mergePart()`
        deleteEmpty()

        # The model cleanup option was selected,
        # now we use that copy made a few lines above
        if str(self.cleanUpModel) == "CleanUp":
            cleanUpOptions(modelBricks)
#        elif str(self.cleanUpModel) == "DoNothing":
#            pass

        return {"FINISHED"}

    def findParsePart(self, filename):

        # Use OS native path separators
        if "\\" in filename:
            filename = filename.replace("\\", os.path.sep)

        # Remove possible colons in filenames
        #TODO: Expand to use a regex search for all illegal characters on Windows
        if ":" in filename:
            filename = filename.replace(":", os.path.sep)

        if filename in self.part_cache:
            return self.part_cache[filename]

        for testpath in self.search_paths:
            path = os.path.join(testpath, filename)
            if os.path.isfile(path):
                LoadedPart = self.parse_part(path)
                self.part_cache[filename] = LoadedPart
                return LoadedPart

        """
        If we haven't returned by now, the part hasn't been found.
        We will therefore send a warning, create a class for the missing
        part, put it in the cache, and return it.

        The object created by this class will be an empty, because its mesh
        attribute is set to None.
        """
        self.report({"WARNING"}, "Could not find part {0}".format(filename))
        self.complete = False

        class NonFoundPart(LDrawPart):
            part_name = filename + ".NOTFOUND"
            mesh = None
            subpart_info = []
        self.part_cache[filename] = NonFoundPart
        return NonFoundPart

    def parse_part(self, filename):
        if filename in self.part_cache:
            return self.part_cache[filename]

        # Points are Vector instances
        # Faces are tuples of 3/4 point indices
        # Lines are tuples of 2 point indices
        # Subpart info contains tuples of the form
        #    (LDrawPart subclass, Matrix instance)
        loaded_points = []
        loaded_faces = []
        _subpart_info = []

        with open(filename, "rt", encoding=checkEncoding(filename)) as f:
            for lineno, line in enumerate(f, start=1):
                split = [item.strip() for item in line.split()]
                # Skip blank lines
                if len(split) == 0:
                    continue
                #TODO: BIG: Error case handling.
                # - Line has too many elements => warn user? Skip line?
                # - Line has too few elements => skip line and warn user
                # - Coordinates cannot be converted to float => skip line
                #     and warn user
                # - (for subfiles) detect and skip circular references,
                #     including indirect ones...

                def element_from_points(length, values):
                    indices = []
                    values = [float(s) for s in values]
                    if len(values) < length * 3:
                        raise ValueError("Not enough values for {0} points".format(length))
                    for point_n in range(length):
                        x, y, z = values[point_n * 3:point_n * 3 + 3]
                        indices.append(len(loaded_points))
                        loaded_points.append(Vector((x, y, z)))
                    return indices

                if split[0] == "1":
                    # If we've found a subpart, append to _subpart_info
                    # !!! We need to handle circular references here !!!
                    if len(split) < 15:
                        continue
                    #TODO: Handle color here

                    # Load the matrix...
                    # Line structure is translation(3), first row(3), second row(3), third row(3)
                    # We can convert this into a homogeneous matrix, thanks blender!
                    translation = Vector([float(s) for s in split[2:5]])
                    m_row1 = [float(s) for s in split[5:8]]
                    m_row2 = [float(s) for s in split[8:11]]
                    m_row3 = [float(s) for s in split[11:14]]
                    matrix = Matrix((m_row1, m_row2, m_row3)).to_4x4()
                    matrix.translation = translation

                    filename = split[14]
                    part_class = self.findParsePart(filename)

                    _subpart_info.append((part_class, matrix))

                elif split[0] == "3":
                    try:
                        tri = element_from_points(3, split[2:11])
                    except ValueError:
                        self.no_mesh_errors = False
                        continue
                    loaded_faces.append(tri)

                elif split[0] == "4":
                    try:
                        quad = element_from_points(4, split[2:14])
                    except ValueError:
                        self.no_mesh_errors = False
                        continue
                    loaded_faces.append(quad)

        if len(loaded_faces) > 0:
            loaded_mesh = bpy.data.meshes.new(filename)
            loaded_mesh.from_pydata(loaded_points, [], loaded_faces)
            loaded_mesh.validate()
            loaded_mesh.update()
        else:
            loaded_mesh = None

        if len(_subpart_info) > 0 or loaded_mesh:
            # Create a new part class and return it.
            class LoadedPart(LDrawPart):
                """Create a new part class, put it in the cache, and return it."""
                mesh = loaded_mesh
                # Take off the file extensions
                part_name = ".".join(filename.split(".")[:-1])
                subpart_info = _subpart_info

            return LoadedPart
        else:
            return NullPart


class LDrawPart:
    """
    Base class for parts/models/subfiles.
    Should not be instantiated directly!
    """
    def __init__(self, parent=None, depth=0, transform=Matrix()):
        self.obj = bpy.data.objects.new(name=self.part_name,
                                        object_data=self.mesh
                                        )
        self.obj.parent = parent
        self.obj.matrix_local = transform
        self.subparts = []
        if len(self.subpart_info) >= 1:
            for subpart, subpart_matrix in self.subpart_info:
                self.subparts.append(subpart(
                    parent=self.obj,
                    depth=depth + 1,
                    transform=subpart_matrix))

        bpy.context.scene.objects.link(self.obj)


class NullPart(LDrawPart):
    """Empty part, used for parts containing no tris, no quads and no subfiles"""
    def __init__(self, parent=None, depth=0, transform=Matrix()):
        pass


def menuItem(self, context):
    """Import menu listing"""
    self.layout.operator(LDRImporterOperator.bl_idname,
                         text="LDraw - NG (.ldr/.dat)")


def register():
    """Register menu misting"""
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menuItem)


def unregister():
    """Unregister menu listing"""
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menuItem)

if __name__ == "__main__":
    register()

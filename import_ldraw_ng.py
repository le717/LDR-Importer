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

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, FloatProperty, EnumProperty
from bpy_extras.io_utils import ImportHelper

from mathutils import Matrix, Vector


class LDrawImportPreferences(AddonPreferences):
    bl_idname = __name__
    ldraw_library_path = StringProperty(name="LDraw Library path",
                                        subtype="DIR_PATH")

    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ldraw_library_path")


class LDrawImportOperator(bpy.types.Operator, ImportHelper):
    """LDR Importer Operator"""
    bl_idname = "import_scene.ldraw_ng"
    bl_description = "Import an LDraw model (.ldr/.dat)"
    bl_label = "Import LDraw Model - NG"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'REGISTER', 'UNDO'}

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
        # Leave `name` blank for better display
        name="Resolution of part primitives",
        description="Resolution of part primitives",
        items=(
            ("", "Standard primitives",
                "Import primitives using standard resolution"),
            ("48", "High resolution primitives",
                "Import primitives using high resolution"),
            ("8", "Low resolution primitives",
                "Import primitives using low resolution")
        )
    )

    """cleanUpModel = EnumProperty(
        name="Model Cleanup Options",
        description="Model Cleanup Options",
        items=cleanupOptions
    )"""

    def draw(self, context):
        """Display import options"""
        layout = self.layout
        box = layout.box()
        box.label("Import Options", icon='SCRIPTWIN')
        box.prop(self, "scale")
        box.label("Primitives", icon='MOD_BUILD')
        box.prop(self, "resPrims", expand=True)
        #box.label("Model Cleanup", icon='EDIT')
        #box.prop(self, "cleanUpModel", expand=True)

    def get_search_paths(self, context):
        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        chosen_path = addon_prefs.ldraw_library_path
        library_path = ""
        if chosen_path.strip() != "":
            if os.path.isfile(os.path.join(chosen_path, "LDConfig.ldr")):
                library_path = chosen_path
            else:
                self.report({"ERROR"},
                            'Specified path %s does not exist' % chosen_path)
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

        self.search_paths = self.get_search_paths(context)
        if not self.search_paths:
            self.report({"ERROR"}, ('Could not find parts library after'
                                    'looking in various common locations.'
                                    ' Please check the addon preferences!'))
            return {"CANCELLED"}
        self.report({"INFO"}, "Search paths are {}".format(self.search_paths))

        self.search_paths.insert(0, os.path.dirname(self.filepath))
        model = self.parse_part(self.filepath)()

        model.obj.matrix_world = Matrix((
            (1.0, 0.0, 0.0, 0.0),
            (0.0, 0.0, -1.0, 0.0),
            (0.0, -1.0, 0.0, 0.0),
            (0.0, 0.0, 0.0, 1.0)
        )) * self.scale

        if not self.complete:
            self.report({"WARNING"}, ("Not all parts could be found. "
                                      "Check the console for a list."))

        return {"FINISHED"}

    def find_and_parse_part(self, filename):
        filename = filename.replace("\\", os.sep)
        filename = filename.replace(":", os.sep)
        if filename in self.part_cache:
            return self.part_cache[filename]
        for testpath in self.search_paths:
            path = os.path.join(testpath, filename)
            if os.path.isfile(path):
                LoadedPart = self.parse_part(path)
                self.part_cache[filename] = LoadedPart
                return LoadedPart

        # If we haven't returned by now, the part hasn't been found.
        # We will therefore send a warning, create a class for the missing
        # part, put it in the cache, and return it.
        #
        # The object created by this class will be an empty, because its mesh
        # attribute is set to None.
        self.report({"WARNING"}, "Could not find part {}".format(filename))
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
        loaded_lines = []
        _subpart_info = []

        with open(filename, "r", encoding="utf-8") as f:  # TODO hack encoding
            for lineno, line in enumerate(f, start=1):
                split = [item.strip() for item in line.split()]
                # Skip blank lines
                if len(split) == 0:
                    continue
                # BIG TODO: Error case handling.
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
                    # TODO: Handle colour

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
                    part_class = self.find_and_parse_part(filename)

                    _subpart_info.append((part_class, matrix))

                elif split[0] == "2":
                    try:
                        line = element_from_points(2, split[2:8])
                    except ValueError:
                        self.no_mesh_errors = False
                        continue
                    loaded_lines.append(line)

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

        if len(loaded_points) > 0:
            loaded_mesh = bpy.data.meshes.new(filename)
            loaded_mesh.from_pydata(loaded_points, loaded_lines, loaded_faces)
            loaded_mesh.validate()
            loaded_mesh.update()
        else:
            loaded_mesh = None

        # Create a new part class, put it in the cache, and return it.
        class LoadedPart(LDrawPart):
            mesh = loaded_mesh
            # Take off the file extensions
            part_name = ".".join(filename.split(".")[:-1])
            subpart_info = _subpart_info

        return LoadedPart


class LDrawPart:
    """
    Base class for parts/models/subfiles. Should not be instantiated directly!
    """
    def __init__(self, parent=None, depth=0, transform=Matrix()):
        self.obj = bpy.data.objects.new(name=self.part_name, object_data=self.mesh)
        self.obj.parent = parent
        self.obj.matrix_local = transform
        self.subparts = []
        if len(self.subpart_info) >= 1:
            for subpart, subpart_matrix in self.subpart_info:
                self.subparts.append(subpart(parent=self.obj, depth=depth + 1, transform=subpart_matrix))

        bpy.context.scene.objects.link(self.obj)


def menu_import(self, context):
    """Import menu listing label"""
    self.layout.operator(LDrawImportOperator.bl_idname,
                         text="LDraw - NG (.ldr/.dat)")


def register():
    """Register Menu Listing"""
    bpy.utils.register_module(__name__)
    bpy.types.INFO_MT_file_import.append(menu_import)


def unregister():
    """Unregister Menu Listing"""
    bpy.utils.unregister_module(__name__)
    bpy.types.INFO_MT_file_import.remove(menu_import)

if __name__ == "__main__":
    register()

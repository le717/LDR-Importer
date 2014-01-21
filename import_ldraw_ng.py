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
    "name": "LDraw Importer NG",
    "author": "David Pluntze, Triangle717, Banbury, Tribex, MinnieTheMoocher, rioforce, JrMasterModelBuilder, Linus Heckemann",
    "version": (0, 1),
    "blender": (2, 69, 0),
    "location": "File > Import",
    "description": "Imports LDraw parts",
    "warning": "No materials!",
    "wiki_url": "",
    "tracker_url": "",
    "category": "Import-Export"
}

import os

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty, FloatProperty
from bpy_extras.io_utils import ImportHelper

from mathutils import Matrix, Vector


class LDrawImportPreferences(AddonPreferences):
    bl_idname = __name__
    ldraw_library_path = StringProperty(name="LDraw Library path", subtype="DIR_PATH", default="/Users/linus/Downloads/ldraw/")
    def draw(self, context):
        layout = self.layout
        layout.prop(self, "ldraw_library_path")

class LDrawImportOperator(bpy.types.Operator, ImportHelper):
    """LDraw part import operator"""
    bl_idname = "import_scene.ldraw"
    bl_description = "Import an LDraw model (.ldr/.dat)"
    bl_label = "Import LDraw Model"
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

    """resPrims = EnumProperty(
        # Leave `name` blank for better display
        name="Resolution of part primitives",
        description="Resolution of part primitives",
        items=primsOptions
    )"""

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
        #box.label("Primitives", icon='MOD_BUILD')
        #box.prop(self, "resPrims", expand=True)
        #box.label("Model Cleanup", icon='EDIT')
        #box.prop(self, "cleanUpModel", expand=True)

    def get_search_paths(self, context): # TODO: Extend behaviour (look in appropriate LoD folders, maybe guess paths?)
        search_paths = []

        user_preferences = context.user_preferences
        addon_prefs = user_preferences.addons[__name__].preferences
        chosen_path = addon_prefs.ldraw_library_path
        if os.path.isdir(chosen_path):
            library_path = chosen_path
        else:
            self.report({"ERROR"}, 'Could not find parts library (looked in "{}"). Please check the addon preferences!'.format(chosen_path))
            library_path = chosen_path
            #return {"CANCELLED"}
        # Or should we do some guessing?
        #base_path_guesses = ["C:\\LDraw", "~/ldraw", "/Applications/ldraw"]
        return [os.path.join(library_path, component) for component in ("parts",)]

    def execute(self, context):
        search_paths = self.get_search_paths(context)
        parser = LDrawParser(search_paths)

        parser.search_paths.append(os.path.dirname(self.filepath))
        parser.parse_part(self.filepath)()
        return {"FINISHED"}



MAX_DEPTH = 64 # For ugly circular-reference protection

class LDrawPart: # Base class for parts that should not be instantiated directly
    def __init__(self, parent=None, depth=0, transform=Matrix()):
        self.obj = bpy.data.objects.new(name=self.part_name, object_data=self.mesh)
        self.obj.parent = parent
        self.obj.matrix_local = transform
        self.subparts = []
        if len(self.subpart_info) >= 1:
            if depth < MAX_DEPTH:
                for subpart, subpart_matrix in self.subpart_info:
                    self.subparts.append(subpart(parent=self.obj, depth=depth+1, transform=subpart_matrix))
            else:
                self.report({'WARNING'}, "MAX_DEPTH exceeded; circular reference? Skipping subparts of {}".format(self.obj.name))

        bpy.context.scene.objects.link(self.obj)


class LDrawParser:
    def __init__(self, search_paths):
        self.search_paths = search_paths
        self.part_cache = {} # Keys = filenames, values = LDrawPart subclasses

    def find_and_parse_part(self, filename):
        for testpath in self.search_paths:
            path = os.path.join(testpath, filename)
            if os.path.isfile(path):
                return self.parse_part(path)
        print("Could not find part {}".format(filename))
        class NonFoundPart(LDrawPart):
            part_name = filename + ".NOTFOUND"
            mesh = None
            subpart_info = []
        return NonFoundPart # Fallback: Empty part

    def parse_part(self, filename):
        if filename in self.part_cache:
            return self.part_cache[filename]

        loaded_points = [] # Points will be unique so we'll use an ordered dict (key = point, value = None)
        loaded_faces = [] # Groups of 3/4 indices
        loaded_lines = [] # Groups of 2 indices
        _subpart_info = [] # (LDrawPart subclass, Matrix instance) tuples

        with open(filename, "r", encoding="utf-8") as f: # TODO hack encoding
            for lineno, line in enumerate(f, start=1):
                split = [item.strip() for item in line.split()]
                if len(split) == 0: continue
                # BIG TODO: Error case handling.
                # - Line has too many elements => warn user? Skip line?
                # - Line has too few elements => skip line and warn user
                # - Coordinates cannot be converted to float => skip line and warn user
                # - (for subfiles) detect and skip circular references, including indirect ones...
                if split[0] == "1":
                    # If we've found a subpart, append to _subpart_info
                    # !!! We need to handle circular references here !!!
                    if len(split) < 15:
                        continue
                    # TODO: Handle colour
                    x, y, z, a, b, c, d, e, f, g, h, i = map(float, split[2:14])
                    filename = split[14]
                    matrix = Matrix(((a, b, c, x), (d, e, f, y), (g, h, i, z), (0, 0, 0, 1)))

                    _subpart_info.append((self.find_and_parse_part(filename), matrix))

                elif split[0] == "2":
                    # We've found a line! Nice and simple.
                    if len(split) < 8:
                        continue
                    x1, y1, z1, x2, y2, z2 = map(float, split[2:8])
                    idx_1 = len(loaded_points)
                    loaded_points.append(Vector((x1, y1, z1)))
                    idx_2 = len(loaded_points)
                    loaded_points.append(Vector((x2, y2, z2)))

                    loaded_lines.append((idx_1, idx_2))

                elif split[0] == "3":
                    # Triangle!
                    if len(split) < 11:
                        continue # Not enough data, TODO warn user
                    x1, y1, z1, x2, y2, z2, x3, y3, z3 = map(float, split[2:11])
                    idx_1 = len(loaded_points)
                    loaded_points.append(Vector((x1, y1, z1)))
                    idx_2 = len(loaded_points)
                    loaded_points.append(Vector((x2, y2, z2)))
                    idx_3 = len(loaded_points)
                    loaded_points.append(Vector((x3, y3, z3)))

                    loaded_faces.append((idx_1, idx_2, idx_3))

                elif split[0] == "4":
                    # Quad!
                    if len(split) < 11:
                        continue # Not enough data, TODO warn user
                    x1, y1, z1, x2, y2, z2, x3, y3, z3, x4, y4, z4 = map(float, split[2:14])
                    idx_1 = len(loaded_points)
                    loaded_points.append(Vector((x1, y1, z1)))
                    idx_2 = len(loaded_points)
                    loaded_points.append(Vector((x2, y2, z2)))
                    idx_3 = len(loaded_points)
                    loaded_points.append(Vector((x3, y3, z3)))
                    idx_4 = len(loaded_points)
                    loaded_points.append(Vector((x4, y4, z4)))

                    loaded_faces.append((idx_1, idx_2, idx_3, idx_4))

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
            part_name = ".".join(filename.split(".")[:-1]) # Take off the .dat, .ldr, or whatever
            subpart_info = _subpart_info

        self.part_cache[filename] = LoadedPart
        return LoadedPart


def menu_import(self, context):
    """Import menu listing label"""
    self.layout.operator(LDrawImportOperator.bl_idname, text="LDraw (.ldr/.dat)")

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

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

import bpy
from bpy.types import AddonPreferences
from bpy.props import StringProperty
from bpy_extras.io_utils import ImportHelper

from mathutils import Matrix, Vector


class LDrawImportPreferences(AddonPreferences):
    bl_idname = __name__
    ldraw_library_path = StringProperty(name="LDraw Library path", subtype="DIR_PATH")
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
            return {"CANCELLED"}
        # Or should we do some guessing?
        #base_path_guesses = ["C:\\LDraw", "~/ldraw", "/Applications/ldraw"]

    def execute(self, context):
        search_paths = self.get_search_paths()
        parser = LDrawParser(search_paths)



MAX_DEPTH = 64 # For ugly circular-reference protection

class LDrawPart: # Base class for parts that should not be instantiated directly
    def __init__(self, parent=None, depth=0, transform=Matrix()):
        self.obj = bpy.data.objects.new(name=self.part_name, data=self.mesh)
        self.obj.parent = parent
        self.obj.matrix_local = transform
        if len(self.subpart_info) >= 1:
            if depth < MAX_DEPTH:
                for subpart, subpart_matrix in self.subpart_info:
                    self.subparts.append(subpart(parent=self.obj, depth=depth+1, matrix=subpart_matrix))
            else:
                self.report({'WARNING'}, "MAX_DEPTH exceeded; circular reference? Skipping subparts of {}".format(self.obj.name))

        bpy.context.scene.objects.link(self.obj)


class LDrawParser:
    def __init__(self, searchpaths):
        self.searchpaths = searchpaths
        self.part_cache = {} # Keys = filenames, values = LDrawPart subclasses

    def find_and_parse_part(self, filename):
        for testpath in self.searchpaths:
            path = os.path.join(testpath, filename)
            if os.path.isfile(path):
                return self.parse_part(path)
        self.report({"WARNING"}, "Could not find part {}".format(filename))
        class NonFoundPart(LDrawPart):
            part_name = filename + ".NOTFOUND"
            mesh = None
            subpart_info = []
        return LDrawPart # Fallback: Empty part

    def parse_part(self, filename):
        if filename in self.part_cache:
            return self.part_cache[filename]

        loaded_points = [] # Points will be unique so we'll use an ordered dict (key = point, value = None)
        loaded_faces = [] # Groups of 3/4 indices
        loaded_lines = [] # Groups of 2 indices
        subpart_info = [] # (LDrawPart subclass, Matrix instance) tuples

        with open(filename, "r", encoding=...) as f:
            for lineno, line in enumerate(f, start=1):
                split = [strip(item) for item in line.split()]
                if split[0] == "1":
                    # If we've found a subpart, append to subpart_info
                    # !!! We need to handle circular references here !!!
                    if len(split) < 15:
                        continue
                        # TODO: Warn user
                    if len(split) > 15:
                        pass # TODO: Warn user; also decide whether to skip line or parse it anyway...
                    # TODO: Handle colour
                    x, y, z, a, b, c, d, e, f, g, h, i = line[2:14]
                    filename = line[14]
                    matrix = Matrix((a, b, c, x), (d, e, f, y), (g, h, i, z), (0, 0, 0, 1))

                    subpart_info.append((self.find_and_parse_part(filename), matrix))
                elif split[0] == "2":
                    # We've found a line! Nice and simple.
                    if len(split) < 8:
                        continue # Not enough data, TODO warn user
                    x1, x2, y1, y2, z1, z2 = line[2:8] # TODO skip if too much data?
                    point_a = Vector(x1, y1, z1)
                    point_b = Vector(x2, y2, z2)
                    idx_a = len(self.loaded_points)
                    self.loaded_points.append(point_a)
                    idx_b = len(self.loaded_points)
                    self.loaded_points.append(point_b)
                    self.loaded_lines.append((idx_a, idx_b))
                # If we've found a primitive (line, tri, quad), add its points (Vector instances) to loaded_points
                loaded_points.append(Vector(x, y, z))
                #loaded_faces.append((indices, of, points))
        loaded_mesh = bpy.data.meshes.new(filename)
        loaded_mesh.from_pydata(loaded_points, loaded_lines, loaded_faces)
        loaded_mesh.validate()
        loaded_mesh.update()

        # Create a new part class, put it in the cache, and return it.
        class LoadedPart(LDrawPart):
            mesh = loaded_mesh
            part_name = ".".join(filename.split(".")[:-1]) # Take off the .dat, .ldr, or whatever
            subpart_info = subpart_info

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

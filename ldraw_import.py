# ##### BEGIN GPL LICENSE BLOCK #####
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
# ##### END GPL LICENSE BLOCK #####

bl_info = {
    "name": "Blender 2.6 LDraw Importer 0.8 Beta 2",
    "description": "Import LDraw models in .dat, and .ldr format",
    "author": "David Pluntze, JrMasterModelBuilder, le717",
    "version": (0, 8, 0),
    "blender": (2, 6, 3),
    "api": 31236,
    "location": "File > Import",
    "warning": "A few bugs, otherwise fully functional script.",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/LDRAW_Importer",
    "tracker_url": "not"
                   "never",
    "category": "Import-Export"}

import os
import math
import mathutils

import bpy
from bpy_extras.io_utils import ImportHelper
from bpy.props import * # TODO: Find what functions are being used and remove this universal import.


# Global variables
colors = {}
file_list = {}
mat_list = {}
scale = 1.0
LDrawDir = "C:\Program Files (x86)\LDraw"
mode_save = bpy.context.mode
objects = []


# Scans LDraw files     
class ldraw_file (object):

    def __init__ (self, filename, mat, colour = None ):
        self.subfiles = []
        self.points = []
        self.faces = []
        self.subparts = []
        self.submodels = []
        self.part_count = 0
        
        self.mat = mat
        self.colour = colour
        self.me = bpy.data.meshes.new('LDrawMesh')
        self.ob = bpy.data.objects.new('LDrawObj', self.me)
        self.ob.name = os.path.basename(filename)
        
        self.ob.location = (0,0,0)
        
        if ( colour is None ):
            self.material = None
        else:
            if colour in mat_list:
                self.ob.data.materials.append( mat_list[colour] )
            else:
                mat_list[colour] = bpy.data.materials.new('Mat_'+colour+"_")
                mat_list[colour].diffuse_color = colors[ colour ]
                #mat_list[colour].use_nodes = True
                # TODO: Add switch to Blender GUI to choose between nodes for Cycles and material color for Blender Internal. Or just else. Adding it this way for debugging purposes.
                self.ob.data.materials.append( mat_list[colour] )
                
        # Link object to scene
        bpy.context.scene.objects.link(self.ob)
        
        self.parse(filename)
        
        self.me.from_pydata(self.points, [], self.faces)
        
        self.ob.select = True
        
        objects.append(self.ob) 
        for i in self.subparts:
            self.submodels.append( ldraw_file( i[0], i[1], i[2] ) )
                
    def parse_line(self, line):
        verts = []
#       color = int(line[1])
        num_points = int ( ( len(line) - 2 ) / 3 )
        #matrix = mathutils.Matrix(mat)
        for i in range(num_points):
                self.points.append( ( self.mat * mathutils.Vector( ( float(line[i * 3 + 2]), float(line[i * 3 + 3]), float(line[i * 3 + 4]) ) ) ).
                to_tuple() )
                verts.append(len(self.points)-1)
        self.faces.append(verts)
                
    def parse (self, filename):

        while True:
#           file_found = True
            try:
                f_in = open(filename)
            except:
                try:
                    finds = locate( filename )
                    isPart = finds[1]
                    f_in = open(finds[0])
                except:
                    print("File not found: ",filename)
#                   file_found = False
            self.part_count = self.part_count + 1
            if self.part_count > 1 and isPart:
                self.subparts.append([filename, self.mat, self.colour])
            else:
                lines = f_in.readlines()
                f_in.close()
                for retval in lines:
                    tmpdate = retval.strip()
                    if tmpdate != '':
                        tmpdate = tmpdate.split()
                        #comment
                        if tmpdate[0] == "0":
                            if len(tmpdate) >= 3:
                                if tmpdate[1] == "!LDRAW_ORG" and 'Part' in tmpdate[2] :
                                    if self.part_count > 1:
                                        self.subparts.append([filename, self.mat, self.colour])
                                        break
                        #file
                        if tmpdate[0] == "1":
                            new_file = tmpdate[14]
                            x, y, z, a, b, c, d, e, f, g, h, i = map(float, tmpdate[2:14])
#                           mat_new = self.mat * mathutils.Matrix( [[a, d, g, 0], [b, e, h, 0], [c, f, i, 0], [x, y, z, 1]] )
                            mat_new = self.mat * mathutils.Matrix( ((a, b, c, x), (d, e, f, y), (g, h, i, z), (0, 0, 0, 1)) )
                            self.subfiles.append([new_file, mat_new, tmpdate[1]])
                            
                        # Triangle (tri)
                        if tmpdate[0] == "3":
                            self.parse_line(tmpdate)
                            
                        # Quadrilateral (quad)
                        if tmpdate[0] == "4":
                            self.parse_line(tmpdate)
            if len(self.subfiles) > 0:
                subfile = self.subfiles.pop()
                filename = subfile[0]
                self.mat = subfile[1]
                self.colour = subfile[2]
            else:        
                break
            
            
# Find the needed parts and add it to the list, so second scan is not necessary
# Every last LDraw Brick Library folder added for the ability to import every single brick.
def locate( pattern ):
    '''Locate all files matching supplied filename pattern in and below
    supplied root directory.'''
    finds = []
    fname = pattern.replace('\\', os.path.sep)
    isPart = False
    if str.lower( os.path.split(fname)[0] ) == 's' :
        isSubpart = True
    else:
        isSubpart = False
    ldrawPath = os.path.join(LDrawDir, fname)
    hiResPath = os.path.join(LDrawDir, "P", "48", fname)
    primitivesPath = os.path.join(LDrawDir, "P", fname)
    partsPath = os.path.join(LDrawDir, "PARTS", fname)
    partsSPath = os.path.join(LDrawDir, "PARTS", "S", fname)
    UnofficialPath = os.path.join(LDrawDir, "UNOFFICIAL", fname)
    UnofficialhiResPath = os.path.join(LDrawDir, "UNOFFICIAL",  "P", "48", fname)
    UnofficialPrimPath = os.path.join(LDrawDir, "UNOFFICIAL",  "P", fname)
    UnofficialPartsPath = os.path.join(LDrawDir, "UNOFFICIAL",  "PARTS", fname)
    UnofficialPartsSPath = os.path.join(LDrawDir, "UNOFFICIAL",  "PARTS", "S", fname)
    if os.path.exists(fname):
        pass
    elif os.path.exists(ldrawPath):
        fname = ldrawPath
    elif os.path.exists(hiResPath):
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
        if isSubpart == False:
            isPart = True
    else:
        print("Could not find file %s" % fname)
        return

    finds.append(fname)
    finds.append(isPart)
    return finds    

# Create the actual model         
def create_model(self, context):
    file_name = self.filepath
    print(file_name)
    try:
        
        # Set the initial transformation matrix, set the scale factor to 0.05 
        # and rotate -90 degrees around the x-axis, so the object is upright.
        mat = mathutils.Matrix( ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1)) ) * 0.05
        mat = mat * mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
 
        # Scan LDConfig to get the material color info.
        ldconfig = open ( locate( "LDConfig.ldr" )[0] )
        ldconfig_lines = ldconfig.readlines()
        ldconfig.close()
        
        for line in ldconfig_lines:
            if len(line) > 3 :
                if line[2:4].lower() == '!c':
                    line_split = line.split()
                    print( line, 'color ', line_split[4], 'code ', line_split[6][1:] )
                    colors[line_split[4]] = [ float (int ( line_split[6][1:3], 16) ) / 255.0, float (int ( line_split[6][3:5], 16) ) / 255.0, float 
                    (int ( line_split[6][5:7], 16) ) / 255.0 ]
                    
        model = ldraw_file (file_name, mat)
# Restored and corrected 'Remove Doubles' and 'Recalculate Normals' code from V0.6.
        for cur_obj in objects:
            bpy.context.scene.objects.active = cur_obj
            bpy.ops.object.editmode_toggle()
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.mesh.remove_doubles()
            bpy.ops.mesh.normals_make_consistent()
            bpy.ops.object.mode_set(mode='OBJECT')
            bpy.ops.object.mode_set()
       
    except:
        print("Oops. Something messed up.")
        pass
   
    print ("Import complete!")

def get_path(self, context):
    print(self)
    print(context)
    
#----------------- Operator -------------------------------------------
class IMPORT_OT_ldraw ( bpy.types.Operator, ImportHelper ):
    '''LDraw Importer Operator'''
    bl_idname = "import_scene.ldraw"
    bl_description = 'Import an LDraw model (.dat/.ldr)'
    bl_label = "Import LDraw Model"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'UNDO'}
    
    ## OPTIONS ##
    
    ldraw_path = StringProperty( 
        name="LDraw Home directory", 
        description=( "The directory where LDraw is installed to." ), 
        default=LDrawDir, subtype="DIR_PATH",
        update=get_path
        )

    ## DRAW ##
    #def draw(self, context):
    #   layout = self.layout
        
    #   box = layout.box()
    #   box.label('Import Options:', icon='FILTER')
# need to find a way to set the LDraw homedir interactivly -David Pluntze
#       box.prop(self, 'ldraw_path')

    def execute(self, context):
        print("executes\n")
        create_model(self, context)
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
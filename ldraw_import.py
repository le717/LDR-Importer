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
    "name": "Blender 2.6 LDraw Importer 0.8 Beta 2",
    "description": "Import LDraw models in .dat, and .ldr format",
    "author": "David Pluntze, JrMasterModelBuilder, le717",
    "version": (0, 8, 0),
    "blender": (2, 6, 3),
    "api": 31236,
    "location": "File > Import",
    "warning": "A few bugs, otherwise fully functional script.",
    "wiki_url": "http://wiki.blender.org/index.php/Extensions:2.6/Py/Scripts/Import-Export/LDRAW_Importer",
    "tracker_url": "maybe"
                   "soon",
    "category": "Import-Export"}

import os, sys, math, mathutils
import traceback
from struct import unpack

import bpy
from bpy_extras.io_utils import ImportHelper
import bpy.props


# Global variables
file_list = {}
mat_list = {}
colors = {}
scale = 1.0
WinLDrawDir = "C:\\LDraw"
OSXLDrawDir = "/Applications/ldraw/"
LinuxLDrawDir = "~/ldraw/"
objects = []


# Scans LDraw files     
class ldraw_file(object):

    def __init__(self, filename, mat, colour = None):
        self.points = []
        self.faces = []
        self.material_index = []
        self.subparts = []
        self.submodels = []
        self.part_count = 0
        
        self.mat = mat
        self.colour = colour
        self.me = bpy.data.meshes.new('LDrawMesh')
        self.ob = bpy.data.objects.new('LDrawObj', self.me)
        self.ob.name = os.path.basename(filename)
        
        self.ob.location = (0,0,0)
        
        if (colour is None):
            self.material = None
        else:
            self.ob.data.materials.append(getMaterial(colour))
                
        # Link object to scene
        bpy.context.scene.objects.link(self.ob)
        
        self.parse(filename)
        
        self.me.from_pydata(self.points, [], self.faces)
        
        for i, f in enumerate(self.me.polygons):
            n = self.material_index[i]
            mat = getMaterial(n)
            
            if self.me.materials.get(mat.name) == None:
                self.me.materials.append(mat)
            
            f.material_index = self.me.materials.find(mat.name)

        objects.append(self.ob)
        self.ob.select = True

        for i in self.subparts:
            self.submodels.append(ldraw_file( i[0], i[1], i[2] ))

    def parse_line(self, line):
        verts = []
        color = line[1]
        
        if color == '16':
            color = self.colour

        num_points = int (( len(line) - 2 ) / 3)
        #matrix = mathutils.Matrix(mat)
        for i in range(num_points):
                self.points.append((self.mat * mathutils.Vector((float(line[i * 3 + 2]), float(line[i * 3 + 3]), float(line[i * 3 + 4])))).
                to_tuple())
                verts.append(len(self.points)-1)
        self.faces.append(verts)
        self.material_index.append(color)
                
    def parse_quad(self, line):
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
#           file_found = True
            try:
                f_in = open(filename)
            except:
                try:
                    fname, isPart = locate(filename)
                    f_in = open(fname)
                except:
                    print("File not found: ", filename)

            self.part_count += 1
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
    if colour in colors:
        if not (colour in mat_list):
            print(colors[colour])
            mat_list[colour] = bpy.data.materials.new('Mat_'+colour+"_")
            mat_list[colour].diffuse_color = colors[colour]['color']
            
            alpha = colors[colour]['alpha']
            if alpha < 1.0:
                mat_list[colour].use_transparency = True
                mat_list[colour].alpha = alpha
            
        return mat_list[colour]
    return mat_list['0']

            
# Find the needed parts and add it to the list, so second scan is not necessary
# Every last LDraw Brick Library folder added for the ability to import every single brick.
def locate(pattern):
    '''Locate all files matching supplied filename pattern in and below
    supplied root directory.'''
    fname = pattern.replace('\\', os.path.sep)
    isPart = False
    if str.lower(os.path.split(fname)[0]) == 's' :
        isSubpart = True
    else:
        isSubpart = False  

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
    if os.path.exists(fname):
        pass
    elif os.path.exists(ldrawPath):
        fname = ldrawPath
    elif os.path.exists(hiResPath) and not HighRes:
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

    return (fname, isPart)

# Create the actual model         
def create_model(self, context):
    file_name = self.filepath
    print(file_name)
    try:
        
        # Set the initial transformation matrix, set the scale factor to 0.05 
        # and rotate -90 degrees around the x-axis, so the object is upright.
        mat = mathutils.Matrix(((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))) * 0.05
        mat = mat * mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
 
        # Scan LDConfig to get the material color info.
        ldconfig = open(locate("LDConfig.ldr")[0])
        ldconfig_lines = ldconfig.readlines()
        ldconfig.close()
        
        for line in ldconfig_lines:
            if len(line) > 3 :
                if line[2:4].lower() == '!c':
                    line_split = line.split()
                    #print(line, 'color ', line_split[4], 'code ', line_split[6][1:])
                    name = line_split[4]
                    colors[name] = {'color': hex_to_rgb(line_split[6][1:]), 'alpha': 1.0}
                    if len(line_split) > 10 and line_split[9] == 'ALPHA':
                        colors[name]['alpha'] = int(line_split[10]) / 255.0
                    
        model = ldraw_file(file_name, mat)
        # Removes doubles and recalculate normals in each brick. Model is super high-poly without it.
        if not CleanUp:
            for cur_obj in objects:
                bpy.context.scene.objects.active = cur_obj
                bpy.ops.object.editmode_toggle()
                bpy.ops.mesh.select_all(action='SELECT')
                bpy.ops.mesh.remove_doubles(threshold=0.01)
                bpy.ops.mesh.normals_make_consistent()
                bpy.ops.object.mode_set(mode='OBJECT')
                bpy.ops.object.shade_smooth() 
                bpy.ops.object.mode_set()
                m = cur_obj.modifiers.new("edge_split", type='EDGE_SPLIT')
                m.split_angle = 0.78539
       
    except Exception as ex:
        print (traceback.format_exc())
        print("Oops. Something messed up.")
   
    print ("Import complete!")

def get_path(self, context):
    print(self)
    print(context)
    
def hex_to_rgb(rgb_str):
    int_tuple = unpack('BBB', bytes.fromhex(rgb_str))
    return tuple([val/255 for val in int_tuple]) 
    
#----------------- Operator -------------------------------------------
class IMPORT_OT_ldraw(bpy.types.Operator, ImportHelper):
    '''LDraw Importer Operator'''
    bl_idname = "import_scene.ldraw"
    bl_description = 'Import an LDraw model (.dat/.ldr)'
    bl_label = "Import LDraw Model"
    bl_space_type = "PROPERTIES"
    bl_region_type = "WINDOW"
    bl_options = {'UNDO'}
    
    ## Script Options ##
    
    ldrawPath = bpy.props.StringProperty(name="LDraw Path", description="The folder path to your LDraw System of Tools installation.", maxlen=1024,
    default = {"win32": WinLDrawDir, "darwin": OSXLDrawDir}.get(sys.platform, LinuxLDrawDir), update=get_path)
    
    cleanupModel = bpy.props.BoolProperty(name="Disable Model Cleanup", description="Does not remove double vertices or make normals consistent.", default=False)

    highresBricks = bpy.props.BoolProperty(name="Do Not Use High-res bricks", description="Do not use high-res bricks to import your model.", default=True) 
    
    #ldraw_path = StringProperty( 
        #name="LDraw Path", 
        #description=("The path to your LDraw System of Tools installation."), 
        #default=LDrawDir,
        #update=get_path
        #)

    def execute(self, context):
        global LDrawDir, CleanUp, HighRes
        LDrawDir = str(self.ldrawPath)
        CleanUp = bool(self.cleanupModel)
        HighRes = bool(self.highresBricks)
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
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
	"name": "Blender 2.6 LDraw Importer 1.1",
	"description": "Import LDraw models in .dat, and .ldr format",
	"author": "David Pluntze, JrMasterModelBuilder, Triangle717, Banbury, rioforce, Tribex",
	"version": (1, 1, 0),
	"blender": (2, 63, 0),
	"api": 31236,
	"location": "File > Import",
	"warning": "Cycles support is incomplete",
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
from time import strftime

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


class LDrawFile(object):
	"""Scans LDraw files"""
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

		verts = []
		color = line[1]

		if color == '16':
			color = self.colour

		num_points = int((len(line) - 2) / 3)
		#matrix = mathutils.Matrix(mat)
		for i in range(num_points):
				self.points.append(
					(self.mat * mathutils.Vector((float(line[i * 3 + 2]),
					 float(line[i * 3 + 3]), float(line[i * 3 + 4])))).
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

		subfiles = []

		while True:
			# Attempt to open the required brick using relative path
			if os.path.exists(filename):
				with open(filename, "rt") as f_in:
					lines = f_in.readlines()

				"""
				That didn't work, so attempt to open the required brick
				using absolute path.
				"""
			else:
				fname, isPart = locate(filename)

				if os.path.exists(fname):
					with open(fname, "rt") as f_in:
						lines = f_in.readlines()
				else:
					#TODO: URL
					"""
					http://www.blender.org/documentation/blender_python_api_2_69_release/bpy.types.Operator.html?highlight=operator#bpy.types.Operator.report
					See 2.69\scripts\addons\io_scene_fbx\import_fbx.py
					"""
					debugPrint("File not found: {0}".format(fname))
					return False

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
										self.subparts.append(
											[filename, self.mat, self.colour]
										)
										break

						# The brick content
						if tmpdate[0] == "1":
							new_file = tmpdate[14]
							x, y, z, a, b, c, d, e, f, g, h, i = map(float, tmpdate[2:14])
							#mat_new = self.mat * mathutils.Matrix(
								#[[a, d, g, 0], [b, e, h, 0], [c, f, i, 0],
								 #[x, y, z, 1]])
							mat_new = self.mat * mathutils.Matrix(
								((a, b, c, x), (d, e, f, y), (g, h, i, z),
								 (0, 0, 0, 1)))

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
			mat = bpy.data.materials.new("Mat_" + colour + "_")
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

			#elif col["material"] == "GLITTER":
			#    slot = mat.texture_slots.add()
			#    tex = bpy.data.textures.new("GlitterTex", type = "STUCCI")
			#    tex.use_color_ramp = True
			#
			#    slot.texture = tex

			else:
				mat.specular_intensity = 0.2

			mat_list[colour] = mat

		return mat_list[colour]
	return mat_list["0"]


def getCyclesMaterial(colour):
	"""Get Cycles Material Values"""
	if colour in colors:
		if not (colour in mat_list):
			col = colors[colour]

			if col["name"] == "Milky_White":
				mat = getCyclesMilkyWhite("Mat_{0}_".format(colour),
										  col["color"])

			elif (col["material"] == "BASIC" and col["luminance"]) == 0:
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
		mat_list[colour] = getCyclesBase('Mat_' + colour + "_", (1, 1, 0), 1.0)
		return mat_list[colour]

	return None


def getCyclesBase(name, diff_color, alpha):

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
		mix.inputs['Fac'].default_value = 0.25
		node = nodes.new('ShaderNodeBsdfDiffuse')
		node.location = -242, 154
		node.inputs['Color'].default_value = diff_color + (1.0,)
		node.inputs['Roughness'].default_value = 0.1

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
		# The IOR of LEGO brick plastic is 1.46
		node.inputs['IOR'].default_value = 1.46

	aniso = nodes.new('ShaderNodeBsdfAnisotropic')
	aniso.location = -242, -23
	aniso.inputs['Roughness'].default_value = 0.2
	aniso.inputs['Anisotropy'].default_value = 0.02

	links.new(mix.outputs[0], out.inputs[0])
	links.new(node.outputs[0], mix.inputs[1])
	links.new(aniso.outputs[0], mix.inputs[2])

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

	# NOTE: The alpha value again is not making much sense here.
	# I'm leaving it in, in case someone has an idea how to use it.

	trans = nodes.new('ShaderNodeBsdfTranslucent')
	trans.location = -242, 154
	trans.inputs['Color'].default_value = diff_color + (1.0,)

	emit = nodes.new('ShaderNodeEmission')
	emit.location = -242, -23

	links.new(mix.outputs[0], out.inputs[0])
	links.new(trans.outputs[0], mix.inputs[1])
	links.new(emit.outputs[0], mix.inputs[2])

	return mat


def getCyclesChrome(name, diff_color):
	"""Set Cycles Chrome Material"""
	mat = bpy.data.materials.new(name)
	mat.use_nodes = True

	nodes = mat.node_tree.nodes
	links = mat.node_tree.links

	for n in nodes:
		nodes.remove(n)

	out = nodes.new('ShaderNodeOutputMaterial')
	out.location = 290, 100

	glass = nodes.new('ShaderNodeBsdfGlossy')
	glass.location = -242, 154
	glass.inputs['Color'].default_value = diff_color + (1.0,)
	glass.inputs['Roughness'].default_value = 0.1

	links.new(glass.outputs[0], out.inputs[0])

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
	mix.inputs['Fac'].default_value = 0.5

	out = nodes.new('ShaderNodeOutputMaterial')
	out.location = 290, 100

	glossy = nodes.new('ShaderNodeBsdfGlossy')
	glossy.location = -242, 154
	glossy.inputs['Color'].default_value = diff_color + (1.0,)
	glossy.inputs['Roughness'].default_value = roughness

	aniso = nodes.new('ShaderNodeBsdfAnisotropic')
	aniso.location = -242, -23
	aniso.inputs['Roughness'].default_value = 0.3
	aniso.inputs['Anisotropy'].default_value = 0.02

	links.new(mix.outputs[0], out.inputs[0])
	links.new(glossy.outputs[0], mix.inputs[1])
	links.new(aniso.outputs[0], mix.inputs[2])

	return mat


def getCyclesRubber(name, diff_color, alpha):

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
		mix.inputs['Fac'].default_value = 0.25
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


def locate(pattern):
	"""
	Locate all files matching supplied filename pattern in and below
	supplied root directory.
	Check all available possible folders so every single brick
	can be imported, even unofficial ones.
	"""
	fname = pattern.replace("\\", os.path.sep)
	isPart = False
	if str.lower(os.path.split(fname)[0]) == "s":
		isSubpart = True
	else:
		isSubpart = False

	#lint:disable
	# Define all possible folders in the library, including unofficial bricks
	
	# Standard Paths:
	ldrawPath = os.path.join(LDrawDir, fname)
	hiResPath = os.path.join(LDrawDir, "p", "48", fname)
	primitivesPath = os.path.join(LDrawDir, "p", fname)
	partsPath = os.path.join(LDrawDir, "parts", fname)
	partsSPath = os.path.join(LDrawDir, "parts", "s", fname)
	
	# Unoffical Paths:
	UnofficialPath = os.path.join(LDrawDir, "unofficial", fname)
	UnofficialhiResPath = os.path.join(LDrawDir, "unofficial",
									   "p", "48", fname)
	UnofficialPrimPath = os.path.join(LDrawDir, "unofficial",
									  "p", fname)
	UnofficialPartsPath = os.path.join(LDrawDir, "unofficial",
									   "parts", fname)
	UnofficialPartsSPath = os.path.join(LDrawDir, "unofficial",
										"parts", "s", fname)
	#lint:enable
	if os.path.exists(ldrawPath):
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

		# Since this is not a subpart, mark it as a root part
		if not isSubpart:
			isPart = True
	else:
		debugPrint("Could not find file {0}".format(fname))

		
	 
	# TODO: Currently will return the inputted path, possibly causing any error checking to clear 
	# until it tries to actually load parts.
	return (fname, isPart)


def create_model(self, scale, context):
	"""Create the actual model"""
	global objects
	global colors
	global mat_list

	file_name = self.filepath
	debugPrint("Attempting to import {0}".format(file_name))
	if file_name.endswith(".ldr") or file_name.endswith(".dat") or file_name.endswith(".mpd"):
		try:
	
			# Set the initial transformation matrix, set the scale factor to 0.05
			# and rotate -90 degrees around the x-axis, so the object is upright.
			mat = mathutils.Matrix(
				((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1))) * scale
			mat = mat * mathutils.Matrix.Rotation(math.radians(-90), 4, 'X')
	
			# If LDrawDir does not exist, stop the import
			if not os.path.isdir(LDrawDir):
				debugPrint ('ERROR: Cannot find LDraw System of Tools installation at {0}'.format(LDrawDir))
				self.report({'ERROR'}, 'Cannot find LDraw System of Tools installation at {0}'.format(LDrawDir))
				return {'CANCELLED'}
	
			colors = {}
			mat_list = {}
	
			# Get material list from LDConfig
			scanLDConfig()
	
			LDrawFile(context, file_name, mat)
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
							m = cur_obj.modifiers.new("edge_split",
													  type='EDGE_SPLIT')
							m.split_angle = math.pi / 4
					cur_obj.select = False
	
			context.scene.update()
			objects = []
	
			# Always reset 3D cursor to <0,0,0> after import
			bpy.context.scene.cursor_location = (0.0, 0.0, 0.0)
	
			# Display success message
			debugPrint("{0} successfully imported!".format(file_name))
			return {'FINISHED'}
	
		except Exception as e:
			debugPrint("ERROR: "+type(e).__name__+"\n"+traceback.format_exc()+'\n')
			debugPrint("ERROR: File not imported. Reason: "+type(e).__name__+".")
			self.report({'ERROR'}, 'File not imported ('+type(e).__name__+'). \nCheck the console logs for more information.')
			return {'CANCELLED'}
	else:
		debugPrint("ERROR: File not imported. Reason: Invalid File Type (Must be a .dat, .ldr, or .mpd)")
		self.report({'ERROR'}, 'File not imported. Reason: Invalid File Type (Must be a .dat, .ldr, or .mpd)')
		return {'CANCELLED'}


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
	
	# FIXME: Currently prints the class information of the context object, not a path
	debugPrint(context)


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
		description="Folder path to your LDraw System of Tools installation",
		default={"win32": WinLDrawDir, "darwin": OSXLDrawDir}.get(
			sys.platform, LinuxLDrawDir), update=get_path
	)

	scale = bpy.props.FloatProperty(
		name="Scale",
		description="Scale the model by this amount",
		default=0.05
	)

	cleanupModel = bpy.props.BoolProperty(
		name="Enable Model Cleanup",
		description="Remove double vertices and make normals consistent",
		default=True
	)

	highresBricks = bpy.props.BoolProperty(
		name="Do Not Use High-res bricks",
		description="Do not use high-res bricks to import your model",
		default=True
	)

	def execute(self, context):
		"""Set import options and run the script"""
		global LDrawDir, CleanUp, HighRes
		LDrawDir = str(self.ldrawPath)
		CleanUp = bool(self.cleanupModel)
		HighRes = bool(self.highresBricks)

		create_model(self, self.scale, context)
		return {'FINISHED'}


def menu_import(self, context):
	"""Import menu listing label"""
	self.layout.operator(IMPORT_OT_ldraw.bl_idname, text="LDraw (.dat/.ldr)")


def register():
	"""Register Menu Listing"""
	bpy.utils.register_module(__name__)
	bpy.types.INFO_MT_file_import.append(menu_import)


def unregister():
	"""Unregister Menu Listing"""
	bpy.utils.unregister_module(__name__)
	bpy.types.INFO_MT_file_import.remove(menu_import)

def debugPrint(string):
	print("[LDraw Importer] "+str(string)+" - "+strftime("%H:%M:%S"))
	
if __name__ == "__main__":
	register()

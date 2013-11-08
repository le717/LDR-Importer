#! /usr/bin/env python3
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

# <pep8-80 compliant>

import os
import distutils.file_util
import distutils.dir_util
import shutil

from __version__ import __version__


# Various folders
curDir = os.path.dirname(__file__)
archivesFolder = os.path.join(curDir, "Archives")
tempFolder = os.path.join(archivesFolder, "tmp")
blenderFolder = os.path.join(tempFolder, "io_scene_ldraw")

# Ensure the stated version number is in the proper format [(int, int, int)],
# and stop packaging if it is not.
for number in __version__:
    if type(number) != int:
        print("\nERROR: Invalid version number")
        print('''The version number defined in "__version__.py"
is not in the proper format. Please consult "Documentation/CONTRIBUTING.md"
for the proper format.''')

        input("\nPress Enter to close.")
        raise SystemExit(0)

print("\nCreating required folders")
# Create the Archives directory if it does not exist
if not os.path.exists(archivesFolder):
    os.makedirs(archivesFolder)

# Create the folder that will contain the script
# This way, it can be installed straight from the Zip archive
if not os.path.exists(blenderFolder):
    os.makedirs(blenderFolder)

# Construct final version number (maj, min)
finalVersion = "v{0}.{1}".format(__version__[0], __version__[1])

# Check if this is a patch release and if so use it too
if __version__[2] > 0:
    finalVersion = "{0}.{1}".format(finalVersion, __version__[2])

# Construct Zip archive filename using final version number
zipFileName = "Blender-2.6-LDraw-Importer-{0}".format(finalVersion)

print("Filtering out unneeded files and folders")
print("Compressing Zip archive")

for root, dirnames, filenames in os.walk(curDir):
    # Remove uneeded folders from the list
    if "Archives" in dirnames:
        dirnames.remove("Archives")
    if "Testing" in dirnames:
        dirnames.remove("Testing")
    if ".git" in dirnames:
        dirnames.remove(".git")
    if "__pycache__" in dirnames:
        dirnames.remove("__pycache__")

    # Copy the Documentation folder to the staging area
    distutils.dir_util.copy_tree(
        os.path.join(curDir, "Documentation"),
        os.path.join(blenderFolder, "Documentation"))

    # Remove the folder from the list so the contents
    # are not copied over again
    dirnames.remove("Documentation")

    # Remove uneeded files from the list
    if ".gitignore" in filenames:
        filenames.remove(".gitignore")
    if ".gitattributes" in filenames:
        filenames.remove(".gitattributes")
    if "__version__.py" in filenames:
        filenames.remove("__version__.py")
    if "setup.py" in filenames:
        filenames.remove("setup.py")

    for files in filenames:
        # Get the full path to the remaining files and copy them
        myFile = os.path.join(root, files)
        distutils.file_util.copy_file(myFile, blenderFolder)

        # Change the cwd to the Archives folder, create Zip archive
        os.chdir(archivesFolder)
        shutil.make_archive(zipFileName, format="zip", root_dir=tempFolder)

# Go back to the root directory, remove staging area
print("Cleaning up temporary files")
os.chdir(curDir)
distutils.dir_util.remove_tree(tempFolder)
print('''
Blender 2.6 LDraw Importer {0} release packaged and saved to
{1}.zip'''.format(finalVersion, os.path.join(archivesFolder, zipFileName)))
input("\nPress Enter to close. :) ")
raise SystemExit(0)

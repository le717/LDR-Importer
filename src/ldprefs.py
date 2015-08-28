# -*- coding: utf-8 -*-
"""LDR Importer GPLv2 license.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

"""


import os
import json
import platform

from .ldconsole import Console


class Preferences:

    def __init__(self):
        self.__ldPath = None
        self.__curPlatform = None
        self.__prefsData = None
        self.__prefsPath = self.__getPrefsDir()
        self.__prefsFile = os.path.join(self.__prefsPath, "LDR-Importer.json")
        self.__load()

        self.__paths = {
            "win": [
                "C:/LDraw",
                "C:/Program Files (x86)/LDraw",
                "C:/Program Files/LDraw"
            ],
            "mac": [
                "/Applications/LDraw/",
                "/Applications/ldraw/",
            ],
            "linux": [
                os.path.expanduser("~/LDraw"),
                os.path.expanduser("~/ldraw"),
                "/usr/local/share/ldraw",
                "/opt/ldraw"
            ]
        }

    def __getPrefsDir(self):
        """Get the file path where preferences file will be stored.

        @return {String} The configuration path.
        """
        return os.path.join(os.path.dirname(
            os.path.dirname(__file__)), "prefs")

    def __load(self):
        """Read and store the preferences file.

        @return {Boolean} True if the preferences file was read,
                          False otherwise.
        """
        if os.path.exists(self.__prefsFile):
            try:
                with open(self.__prefsFile, "rt", encoding="utf_8") as f:
                    self.__prefsData = json.load(f)
                return True

            # The file is not valid JSON, sliently fail
            except ValueError:
                return False
        return False

    def __confirmLDraw(self, ldPath):
        """Confirm an LDraw installation exists at the given location.

        @param {String} ldPath The path to confirm an LDraw installation.
        @return {Boolean} True if an installation exists, False otherwise.
        """
        if os.path.isfile(os.path.join(ldPath, "LDConfig.ldr")):
            Console.log("Found LDraw installation at {0}".format(ldPath))
            return True
        return False

    def findLDraw(self):
        """Try to find an LDraw installation.

        @return {String} The found LDraw installation
        or the default Windows path if one could not be found.
        """
        # The path was previously stored in the preferences
        if self.__prefsData is not None:
            Console.log("Retrieve LDraw path from preferences")
            self.__ldPath = self.__prefsData["ldPath"]

            Console.log("The current platform is {0}".format(
                        self.__prefsData["platform"]))
            Console.log("The LDraw Parts Library to be used is\n{0}".format(
                        self.__ldPath))
            return self.__ldPath

        # Get and resolve the current platform
        curOS = platform.system()
        if curOS == "Windows":
            self.__curPlatform = "win"
        elif curOS == "Darwin":
            self.__curPlatform = "mac"
        elif curOS == "Linux":
            self.__curPlatform = "linux"
        else:
            self.__curPlatform = "win"
        Console.log("The current platform is {0}".format(self.__curPlatform))

        # Perform platform-specific searches to find the LDraw installation
        Console.log("Search {0}-specific paths for the LDraw path".format(
                    self.__curPlatform))
        for path in self.__paths[self.__curPlatform]:
            if self.setLDraw(path):
                return path

        # We came up dry, default to Windows default
        self.__ldPath = self.__paths["win"][0]
        Console.log("Cound not find LDraw installation, default to {0}".format(
                    self.__ldPath))
        return self.__ldPath

    def setLDraw(self, ldPath):
        """Set the LDraw installation.

        @param {String} ldPath The LDraw installation
        @return {Boolean} True if the installation was set, False otherwise.
        """
        if self.__confirmLDraw(ldPath):
            self.__ldPath = ldPath.replace("\\", "/")
            return True
        return False

    def get(self, opt, default):
        """Retrieve the desired import option from the preferences.

        @param {String} opt The key for the import option desired.
        @param {TODO} default TODO.
        @return {TODO} TODO.
        """
        # Make sure we have preferences to use
        if self.__prefsData is None or not self.__prefsData["importOpts"]:
            return default

        # Retrieve the desired import option
        options = self.__prefsData["importOpts"]
        if opt in options.keys():
            return options[opt]
        return default

    def save(self, importOpts):
        """Write the JSON preferences.

        @param {Dictionary} importOpts TODO.
        @return {Boolean} True if the preferences were written,
                          False otherwise.
        """
        # Round off any numbers to two decimal places
        for k, v in importOpts.items():
            if type(v) == float:
                importOpts[k] = round(v, 2)

        prefs = {
            "importOpts": importOpts,
            "ldPath": self.__ldPath,
            "platform": self.__curPlatform
        }

        # Create the preferences folder if it does not exist
        if not os.path.exists(self.__prefsPath):
            os.makedirs(self.__prefsPath)

        try:
            with open(self.__prefsFile, "wt", encoding="utf_8") as f:
                # TODO Consder removing the indent parameter
                # once work on the system is completed.
                f.write(json.dumps(prefs, indent=4, sort_keys=True))
            Console.log("Preferences saved to {0}".format(self.__prefsFile))
            return True

        # Silently fail
        except PermissionError:
            return False

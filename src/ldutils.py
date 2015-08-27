# -*- coding: utf-8 -*-
"""LDR Importer GPLv2 license.

This program is free software; you can redistribute it and/or
modify it under the terms of the GNU General Public License
as published by the Free Software Foundation; either version 2
of the License, or (at your option) any later version.

This program is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with this program; if not, write to the Free Software Foundation,
Inc., 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301, USA.

"""


import os
import json
import platform
from datetime import datetime


class Console:

    @staticmethod
    def __makeMessage(msg, prefix=None):
        """Construct the message for displaying in the console.

        Formats, timestamps, and identifies the message
        as coming from this script.

        @param {Tuple} msg The message to be displayed.
        @param {String} prefix Any text to prefix to the message.
        @return {String} The constucted message.
        """
        msg = [str(text) for text in msg]

        # Prefix text if needed
        if prefix:
            msg.insert(0, str(prefix))

        return "[LDR Importer] ({0})\n{1}".format(
            datetime.now().strftime("%H:%M:%S.%f")[:-4], " ".join(msg))

    @staticmethod
    def log(*msg):
        """Print logging messages to the console.

        @param {Tuple} msg The message to be displayed.
        """
        print(Console.__makeMessage(msg))

    @staticmethod
    def warn(*msg):
        """Print warning messages to the console.

        @param {Tuple} msg The message to be displayed.
        """
        print(Console.__makeMessage(msg, "Warning!"))


class Preferences:

    def __init__(self):
        self.ldPath = None
        self.__curPlatform = None
        self.__prefsData = None
        self.__prefsPath = self.__getPrefsDir()
        self.__prefsFile = os.path.join(self.__prefsPath, "LDR-Importer.json")
        self.__getPrefs()

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

        @returns {String} The configuration path.
        """
        return os.path.join(os.path.dirname(
            os.path.dirname(__file__)), "prefs")

    def __getPrefs(self):
        """Read and store the preferences file.

        @returns {Boolean} True if the preferences file was read,
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
            self.ldPath = self.__prefsData["ldPath"]

            Console.log("The LDraw Parts Library to be used is\n{0}".format(
                        self.ldPath))
            return self.__prefsData["ldPath"]

        # Get and resolve the current platform
        curOS = platform.platform()
        if "Windows" in curOS:
            self.__curPlatform = "win"
        elif "MacOS" in curOS:
            self.__curPlatform = "mac"
        elif "Linux" in curOS:
            self.__curPlatform = "linux"
        Console.log("The current platform is", self.__curPlatform)

        # Perform platform-specific searches to find the LDraw installation
        Console.log("Search {0}-specific paths for the LDraw path".format(
                    self.__curPlatform))

        for path in self.__paths[self.__curPlatform]:
            if self.setLDraw(path):
                return path

        # We came up dry, default to Windows default
        Console.log("Cound not find LDraw installation, default to {0}".format(
                    self.__paths["win"][0]))
        self.ldPath = self.__paths["win"][0]
        return self.__paths["win"][0]

    def setLDraw(self, ldPath):
        """Set the LDraw installation.

        @param {String} ldPath The LDraw installation
        @return {Boolean} True if the installation was set, False otherwise.
        """
        if self.__confirmLDraw(ldPath):
            self.ldPath = ldPath.replace("\\", "/")
            return True
        return False

    def savePrefs(self):
        """Write the JSON-based preferences file.

        @returns {Boolean} True if the preferences file was written,
                           False otherwise.
        """
        prefs = {
            "platform": self.__curPlatform,
            "ldPath": self.ldPath,
            "importOpts": {}
        }

        # Create the preferences folder if it does not exist
        if not os.path.exists(self.__prefsPath):
            os.makedirs(self.__prefsPath)

        try:
            with open(self.__prefsFile, "wt", encoding="utf_8") as f:
                f.write(json.dumps(prefs, indent=4, sort_keys=True))
            Console.log("Preferences saved to {0}".format(self.__prefsFile))
            return True

        # Silently fail
        except PermissionError:
            return False

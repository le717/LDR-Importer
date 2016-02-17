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
import struct


class Colors:

    def __init__(self, ldPath, useAltColors):
        self.__ldPath = ldPath
        self.__colorFile = ("LDCfgalt.ldr" if useAltColors else "LDConfig.ldr")
        self.__colors = {
            "filename": self.__colorFile
        }

    def __hexToRgb(self, color):
        """Convert a Hex color value to the RGB format Blender requires.

        @param {String} color The hex color value to convert.
                              Can be prefixed with "#".
        @return {!Tuple.<number>} A three-index tuple containing
                                  the converted RGB value.
                                  Otherwise None if the color
                                  could not be converted.
        """
        color = color.lstrip("#")
        rgbColor = struct.unpack("BBB", bytes.fromhex(color))
        return tuple([val / 255 for val in rgbColor])

    def __hasColorValue(self, line, value):
        """Check if the color tag has a specific attribute.

        @param {List} line The color line to search.
        @param {String} value The attribute to find.
        @return {Boolean} True if attribute is present, False otherwise.
        """
        return value in line

    def __getColorValue(self, line, value):
        """Get a specific attribute for a given color tag.

        @param {List} line The color line to search.
        @param {String} value The value to find.
        @return {!String} The color value is present, None otherwise.
        """
        if value in line:
            return line[line.index(value) + 1]
        return None

    def get(self, code):
        """Get an individual LDraw color object.
        @param {String} code The color code.
        @param {!Dictionary} The color code dictionary
                             if available, None otherwise.
        """
        return self.__colors.get(code)

    def getAll(self):
        """Get all available LDraw colors.
        @param {!Dictionary} The complete LDraw color dictionary.
        """
        return self.__colors

    def load(self):
        """Parse the LDraw color definitions file.

        @return {Dictionary} All defined LDraw colors,
                             with color codes as the keys.
        """
        # Read the color definition file
        with open(os.path.join(self.__ldPath, self.__colorFile),
                  "rt", encoding="utf_8") as f:
            lines = f.readlines()

        for line in lines:
            # Normalize the lines
            line = line.lstrip("0").strip().lower()

            # Make sure this is a color
            if line.startswith("!colour"):
                line = line.split()
                code = line[3]

                # Create the color
                color = {
                    "alpha": 1.0,
                    "code": code,
                    "edge": self.__hexToRgb(
                        self.__getColorValue(line, "edge")),
                    "luminance": 0.0,
                    "material": "basic",
                    "name": self.__getColorValue(line, "!colour"),
                    "value": self.__hexToRgb(
                        self.__getColorValue(line, "value"))
                }

                # Extract the alpha value
                if self.__hasColorValue(line, "alpha"):
                    color["alpha"] = int(
                        self.__getColorValue(line, "alpha")) / 256

                # Extract the luminance value
                if self.__hasColorValue(line, "luminance"):
                    color["luminance"] = int(
                        self.__getColorValue(line, "luminance"))

                # Extract the valueless attributes
                if self.__hasColorValue(line, "chrome"):
                    color["material"] = "chrome"
                if self.__hasColorValue(line, "pearlescent"):
                    color["material"] = "pearlescent"
                if self.__hasColorValue(line, "rubber"):
                    color["material"] = "rubber"
                if self.__hasColorValue(line, "metal"):
                    color["material"] = "metal"

                # Extract extra material values if present
                if self.__hasColorValue(line, "material"):
                    subLine = line[line.index("material"):]
                    color["material"] = self.__getColorValue(subLine,
                                                             "material")
                    color["secondary_color"] = self.__getColorValue(
                        subLine, "value")[1:]
                    color["fraction"] = self.__getColorValue(subLine,
                                                             "fraction")
                    color["vfraction"] = self.__getColorValue(subLine,
                                                              "vfraction")
                    color["size"] = self.__getColorValue(subLine, "size")
                    color["minsize"] = self.__getColorValue(subLine, "minsize")
                    color["maxsize"] = self.__getColorValue(subLine, "maxsize")

                # Store the color
                self.__colors[code] = color
        return self.__colors

Contributing to Blender 2.6 LDraw Importer
==========================================

There are a few guidelines that must be followed at all times when developing **Blender 2.6 LDraw Importer**

Thou Shalt Do The Dance
-----------------------

* Fork the repository by clicking ![the Fork button](http://i81.servimg.com/u/f81/16/33/06/11/forkme12.png)
* Clone the script onto your computer by running ```git clone https://github.com/yourusername/PatchIt.git``` or if you are using a GUI client, however you clone repositories.
* Read up on the code and project layout and guidelines [below](#for-your-reading-pleasure)
* Edit away! A list of stuff to do is in the [Issues](https://github.com/le717/Blender-2.6-LDraw-Importer/issues).
* Once you finish your work, submit a [Pull Request](https://github.com/le717/Blender-2.6-LDraw-Importer/pulls) by clicking ![the Pull Request button](http://i81.servimg.com/u/f81/16/33/06/11/pullre10.png)
* If everything checks out, your changes will be merged! :grinning:
* Don't forget to share the project with your friends and ![Star!](http://i81.servimg.com/u/f81/16/33/06/11/star11.png)


For Your Reading Pleasure
-------------------------

### Backward Compatibility ###

This project is called **Blender 2.6 LDraw Importer** for a reason. Although the Blender 2.6 Python API is still in development,
the goal is to support as many versions of Blender 2.6 as possible, from Blender 2.63 to the newest nightly build
(we can worry about 2.7 later), and not just the newest stable release.
Although this project is no longer in the personal possession of [Triangle717](https://github.com/le717) but open-source,
this backward compatibility process guideline is still being enforced.
Therefore, the following guidelines have been laid out to help you support multiple Blender versions and make
**Blender 2.6 LDraw Importer** the best available LDraw script for Blender.


### Python Code Layout ###

* [PEP 8](http://www.python.org/dev/peps/pep-0008/) should be followed at all times. Line length should be followed when possible
(it is not always feasible to keep lines at 79 characters. You can use the [PEP8 online](http://pep8online.com/) website to
check for errors.
* The [Blender Python API style guidelines](http://www.blender.org/documentation/blender_python_api_2_69_0/info_best_practice.html),
which is mainly a small extension of PEP 8.
* Use double quotes (`""`) when possible. For multi-line strings, use triple quotes (`''' '''`, `""" """`).
* [`str.format()`](http://docs.python.org/3/library/stdtypes.html#str.format) is the preferred way to join strings.
It a single line string is more than 79 characters and does not need to be on a second line, `str.format()` to keep it on one line
and wrap the extended string on the next physical  line.
It is better than the [% operator](http://docs.python.org/3/tutorial/inputoutput.html#old-string-formatting),
and using `+` (plus) signs is just bad practice. :wink:
* Always trim whitespace from the end of lines, blank lines, and around operators.
* Please try to document your code as much as possible. It is understood you may not have the time to and others might need to do it,
but if you do have the time do document, go right ahead and do it and perhaps whatever else may need it!

### Separate Branches ###

The project into is divided into two separate, distinct branches, in addition to feature branches.

* The **master** branch is where stable, complete, mostly bug-free code belongs. It is this script that will make up the next, official release. If someone
wanted to download a prerelease version and not worry about it being broken, they would download this branch.

* The **unstable** branch is where all beta, draft, and buggy code belongs. Features that may be harder to implement or take longer to add go here so the
master branch does not contain error code. If someone wanted to download the newest, possible broken script, they would download ths branch.

The **unstable** branch is never to be merged into the **master** branch. When the changes made in the unstable is to be added into the master, you need to
manually merge them and commit it.

* **Feature branches** are

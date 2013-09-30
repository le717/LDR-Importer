Contributing to the Blender 2.6 LDraw Importer
==============================================

There are a few guidelines that must be followed at all times when developing the **Blender 2.6 LDraw Importer**

Backward Compatibility
----------------------

This project is called **Blender 2.6 LDraw Importer** for a reason. Although the Blender 2.6 Python API is still in development, the goal is to support as
many versions of Blender 2.6 as possible, and not just the newest stable release. While JrMasterModelBuilder and I maintained this project, I was reluctantly 
forced to bump the minimum Blender version a few times. I did not like doing this, as not everybody runs the newest version of Blender everywhere. I personally 
use computers that have versions of Blender from 2.63 to the newest nightly build. Although this project is no longer in my personal possession and anyone can 
work on it, I plan on continuing this backward compatibility. Therefore, this following guidelines have been laid out to help you support multiple Blender 
versions.

```
Coming soon.
```

Blender Script Guidelines
-------------------------

```
Coming soon.
```

Separate Branches
-----------------

I've divided the project into three separate, distinct branches: master, unstable, and exporter.

* The **master** branch is where stable, complete, mostly bug-free code belongs. It is this script that will make up the next, official release. If someone 
wanted to download a prerelease version and not worry about it being broken, they would download this branch.

* The **unstable** branch is where all beta, draft, and buggy code belongs. Features that may be harder to implement or take longer to add go here so the 
master branch does not contain error code. If someone wanted to download the newest, possible broken script, they would download ths branch.

The **unstable** branch is never to be merged into the **master** branch. When the changes made in the unstable is to be added into the master, you need to 
manually merge them and commit it.

* The **exporter** branch contains an experimental Blender 2.6 LDraw exporter script, ported from another Blender 2.3 LDraw script. It is no where near 
completion, and requires a large amount of new and rewritten code to use LDConfig.ldr and support modern LDraw guidelines to considered stable and be released 
with the importer script.
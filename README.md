Blender 2.6 LDraw Importer
==========================
Hello everybody! le717 here, reminding you that if you would like to learn more about this project, or donate code to it, you need to read this first.

History Lesson
--------------

This is a [Blender 2.6] (http://www.blender.org) Importer script for the [LDraw System of Tools's Brick Library.] (http://www.ldraw.org) 

> LDraw™ is an open standard for LEGO CAD programs that allow the user to create virtual LEGO models and scenes. You can use it to document models you have
>physically built, create building instructions just like LEGO, render 3D photo realistic images of your virtual models and even make animations. 
>The possibilities are endless. Unlike real LEGO bricks where you are limited by the number of parts and colors, in LDraw nothing is impossible.

There are many LDraw importer scripts for Blender 2.3 available, each one with its own errors and quirks, some that have even been lost over time due to dead 
links. Many people have wanted an updated version of these scripts for a while, but nobody seemed to want to write one.
 
However, David Pluntze did, and posted it [online] (http://projects.blender.org/tracker/index.php?func=detail&aid=30327&group_id=153&atid=467) on Febuary 23, 
2012.
However, the script, written for Blender 2.5, was in poor shape and was imcomplete. By the time I found it in early October 2012, Blender 2.6 was already 
released, and the script would not even activate. I contacted my friend [JrMasterModelBuilder] (http://jrmastermodelbuilder.netai.net) who corrected the 
script for me, and allowed it to be used in Blender 2.6.

From then until January 2013, he and I tried to improve the script as much as possible. Many versions were released, and many bugs were fixed and identified. 
However, since I knew very little Python, the process was a challenge.

After putting off uploading the script to the web for anyone to improve, I finally uploaded here, on GitHub.

Commit Guidelines
-----------------

There are a few guidelines that must be followed at all times when developing the Blender 2.6 LDraw Importer:

### Backward compatibility
* This project is called **Blender 2.6 LDraw Importer** for a reason. Although the Blender 2.6 Python API is still in development, the goal is to support as m
many versions of Blender 2.6 as possible, and not just the newest stable release. While JrMasterModelBuilder and I maintained this project, I was reluctantly 
forced to bump the minimum Blender version a few times. I do not like doing this, as not everybody runs the newest version of Blender everywhere. I personally use computers that have versions of Blender from 2.63 to the newest nightly build. Although this project is no longer in my personal position and anyone can work on it, I plan on continuing this backward compatibility. Therefore, this following guidelines have been laid out to help you support muiltple Blender versions.

```
Coming soon.
```

### Blender script guidelines

* Coming soon.

### Separate branches
* I've divided the project into three separate, distinct branches: master, unstable, and exporter.

* The **master** branch is where stable, complete, mostly bug-free belongs. It is this code that will make up the next, official release. If someone wanted to 
download the next release and not worry about it being broken, they would download this branch.
* The **unstable** branch is where all beta, draft, and buggy code belongs. Features that may be harder to implement or take longer to add go here so the 
master branch does not contain error code. If someone wanted to download the newest, possible broken script, they would download ths branch.
* The **exporter** branch contains an experimental Blender 2.6 LDraw exporter script, ported from another Blender 2.3 LDraw script. It is no where near 
completion, and requires a large amount of new and rewritten code to use LDConfig.ldr and support modern LDraw guildelines to considered stable and be released 
with the importer script.

### Official releases
* For the time being, I will say when a official release of this project will happen, and it will be hosted on my personal [Sourceforge.net account] (
http://sourceforge.net/projects/le717.u). In the future, the release cycle and download host will be changed, but it will stay as-is for now.

# ModOrganizer-to-OpenMW
A Mod Organizer plugin to export your VFS, plugin selection and load order to OpenMW

## Why you'd want this:

* OpenMW has no GUI for mod directory installation and management.
Mod Organizer does.
* If you use OpenMW's VFS system to manage your mods, tools like MLOX can't see all your content files, so aren't much use.
If you start these tools through Mod Organizer, it will inject its VFS into them and they'll be able to do their jobs properly.

* Starting your game through Mod Organizer every time might be a bit of a hassle, but that's the only way to make a program see its VFS.
OpenMW has its own VFS, so if you use it, you can just start OpenMW normally.
* Mod Organizer (more specifically its VFS implementation, USVFS) has some issues that mean it doesn't always work as intended stemming from the complexity of injecting a VFS into a process only designed to load things from one directory.
OpenMW's VFS is far more reliable because it's 'supposed to be there' and was therefore much simpler to write without bugs.

## Installation:

Put `OpenMWExport.py` and (optionally) `openmw.ico` in your Mod Organizer `plugins` directory.

## Usage:

You'll find an 'Export to OpenMW' option under the tools menu.
Clicking it will make the plugin do its thing.
If you need to do anything else, you'll get a message box explaining it.

## Note:

When this readme was written, the latest Mod Organizer release was 2.1.1, but this has issues with the Python plugin interface (and you had to manually find and install a plugin to make Morrowind work).
These issues should be resolved by the release after this, but some of these fixes haven't even made it to an internal testing build as of 2018-03-19.
If MO 2.1.1 is still the latest release, you'll probably have to build your own Mod Organizer to use this.

## Future possibilities

* As the Mod Organizer Morrowind plugin matures, this tool will gradually become more useful.
* This plugin could be adapted to use callbacks so it runs automatically whenever you make any changes in Mod Organizer
* If Mod Organizer ever re-implements archive management, this plugin could copy Mod Organizer's list to OpenMW's `fallback-archive` list.
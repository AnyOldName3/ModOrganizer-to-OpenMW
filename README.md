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
If you don't want to use this plugin in English and a translation `.qm` file exists for this plugin in your desired language, put it in your Mod Organizer `translations` directory.

## Usage:

You'll find an 'Export to OpenMW' option under the tools menu.
Clicking it will make the plugin do its thing.
If you need to do anything else, you'll get a message box explaining it.

## Note:

When this readme was written, the latest Mod Organizer release was 2.1.1, but this has issues with the Python plugin interface (and you had to manually find and install a plugin to make Morrowind work).
These issues will be resolved by the MO 2.1.2 release, but these fixes are only available in a pre-release internal testing build as of 2018-03-21.
If MO 2.1.1 is still the latest release, you'll probably have to visit the Mod Organizer Discord server to get a beta build to use this.

## Translating this plugin:

As of version 1.1, this plugin has a `.ts` file.
This allows people who know multiple languages to create translations of it.
Using either Qt Linguist or your l33t h4x0r skillz and a text editor, you can fill this file with text in your own language.
This can be converted to a `.qm` file (somehow) and if you get this to me, I can provide it as an optional download so others can use it, too.
If someone tells me a simple way of getting Transifex involved, I might set that up.

## Future possibilities

* As the Mod Organizer Morrowind plugin matures, this tool will gradually become more useful.
* This plugin could be adapted to use callbacks so it runs automatically whenever you make any changes in Mod Organizer
* If Mod Organizer ever re-implements archive management, this plugin could copy Mod Organizer's list to OpenMW's `fallback-archive` list.
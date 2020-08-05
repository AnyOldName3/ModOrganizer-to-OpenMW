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

As of version 2.0.0, ModOrganizer-to-OpenMW has been upgraded to take advantage of Python 3.
The upgrade to Python 3 is included in the MO 2.1.6 release, and older versions are not compatible with the latest version of this plugin.
If MO 2.1.5 is still the latest release, you'll probably have to visit the Mod Organizer Discord server to get a release candidate build to use this.
You can still use older versions of this plugin in older Mod Organizer builds (although MO 2.1.2 is the minimum which will work).

## Translating this plugin:

As of version 1.1, this plugin has a `.ts` file.
This allows people who know multiple languages to create translations of it.
You can contribute your own translations at https://www.transifex.com/anyoldname3/modorganizer-to-openmw and I'll try to include them in the next release.
If you want to translate to a language that isn't listed there, there should be a Request Language button somewhere.

## Building this plugin

As this plugin is pure Python, it doesn't need building - you can just copy the files into place by hand.
However, obviously that won't update the translation files, and can become annoying when working on the plugin, as you'll need to do it repeatedly.
Because of that, some automation is provided:


`install.ps1` will regenerate the `.ts` file and copy the plugin files to the location specified by its first argument or given via stdin.
To use it, you'll need a Python interpreter with some version of PyQt5's `PyQt5.pylupdate_main` package installed to be available in the current shell.
If you've got a Mod Organizer 2 development environment on your machine, you can add its Python interpreter to the current shell's path, otherwise `pip install PyQt5` will get you what you need.

Also, a VS Code `tasks.json` file is provided that will call the install script as a build task.
To specify the install destination, create a file in the `.vscode` directory called `InstallDestination.txt` containing the path to the MO2 plugins directory.

## Future possibilities

* As the Mod Organizer Morrowind plugin matures, this tool will gradually become more useful.
* This plugin could be adapted to use callbacks so it runs automatically whenever you make any changes in Mod Organizer
* If Mod Organizer ever re-implements archive management, this plugin could copy Mod Organizer's list to OpenMW's `fallback-archive` list.
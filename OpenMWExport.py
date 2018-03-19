# This Mod Organizer plugin is released to the pubic under the terms of the GNU GPL version 3, which is accessible from the Free Software Foundation here: https://www.gnu.org/licenses/gpl-3.0-standalone.html

# To use this plugin, place it in the plugins directory of your Mod Organizer install (ideally along with the OpenMW icon). You will then find an 'Export to OpenMW' option under the tools menu.

# If someone wanted to, they could expand upon this by registering callbacks for mod and plugin state changes so that you didn't manually have to click the button any more to make this work.

# Also, if Mod Organizer ever re-implements archive handling, then it wouldn't be too hard to make this also copy the list of these to fallback-archive= lines.

import sys

from PyQt5.QtCore import QCoreApplication
from PyQt5.QtGui import QIcon
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtWidgets import QFileDialog

if "mobase" not in sys.modules:
    import mock_mobase as mobase

class OpenMWExportPlugin(mobase.IPluginTool):
    
    def __init__(self):
        super(OpenMWExportPlugin, self).__init__()
        self.__organizer = None
        self.__parentWidget = None

    def init(self, organizer):
        self.__organizer = organizer
        return True

    def name(self):
        return "OpenMW Exporter"

    def author(self):
        return "AnyOldName3"

    def description(self):
        return self.__tr("Transfers mod list (left pane) to data fields in OpenMW.cfg and plugin list (right pane, plugins tab) to content fields in OpenMW.cfg. This allows you to run OpenMW with the current profile's setup from outside of Mod Organizer")

    def version(self):
        return mobase.VersionInfo(1, 0, 0, mobase.ReleaseType.final)

    def isActive(self):
        return True

    def settings(self):
        return []

    def displayName(self):
        return self.__tr("Export to OpenMW")

    def tooltip(self):
        return self.__tr("Exports the current mod list and plugin load order to OpenMW.cfg")

    def icon(self):
        return QIcon("plugins/openmw.ico")

    def setParentWidget(self, widget):
        self.__parentWidget = widget
    
    def display(self):
        # We should test if the current game is compatible with OpenMW here
        # We can't do that directly, so instead we just test if the current game is Morrowind
        game = self.__organizer.managedGame()
        if game.gameName() != u"Morrowind":
            QMessageBox.critical(self.__parentWidget, self.__tr("Incompatible game"), self.__tr("(At least when this plugin is being written) OpenMW only supports game data designed for the Morrowind engine. The game being managed is not Morrowind, so the export will abort. If you think you know better than this message, update this plugin."))
            return
        # Give the user the opportunity to abort
        confirmationButton = QMessageBox.question(self.__parentWidget, self.__tr("Before starting export..."), self.__tr("Before starting the export to OpenMW, please ensure you've backed up anything in OpenMW.cfg which you do not want to risk losing forever."), QMessageBox.StandardButtons(QMessageBox.Ok | QMessageBox.Cancel))
        if confirmationButton != QMessageBox.Ok:
            return
        # Get the path to the OpenMW.cfg file
        configPath = self.__getOpenMWConfigPath()
        if not os.path.isfile(configPath):
            QMessageBox.critical(self.__parentWidget, self.__tr("Config file not specified"), self.__tr("No config file was specified"))
            return
        # Clear out the existing data= and content= lines from openmw.cfg
        self.__clearOpenMWConfig(configPath)
        import codecs
        with codecs.open(configPath, "a", "utf-8") as openmwcfg:
            # write out data directories
            openmwcfg.write(self.__processDataPath(game.dataDirectory().absolutePath().decode("utf-8")))
            for mod in self.__organizer.modsSortedByProfilePriority():
                self.__processMod(openmwcfg, mod)
            self.__processMod(openmwcfg, u"Overwrite")
            
            # write out content (plugin) files
            # order content files by load order
            loadOrder = {}
            for plugin in self.__organizer.pluginList().pluginNames():
                loadIndex = self.__organizer.pluginList().loadOrder(plugin)
                if loadIndex >= 0:
                    loadOrder[loadIndex] = plugin
            # actually write out the list
            for pluginIndex in range(len(loadOrder)):
                openmwcfg.write(u"content=" + loadOrder[pluginIndex] + u"\n")
        QMessageBox.information(self.__parentWidget, self.__tr("OpenMW Export Complete"), self.__tr("The export to OpenMW completed successfully. The current setup was saved to ") + configPath)
    
    def __tr(self, str):
        return QCoreApplication.translate(self.name(), str)
    
    def __processMod(self, configFile, modName):
        state = self.__organizer.modList().state(modName)
        if (state & 0x2) != 0 or modName == u"Overwrite":
            path = self.__organizer.getMod(modName).absolutePath().decode("utf-8")
            configLine = self.__processDataPath(path)
            configFile.write(configLine)
    
    def __processDataPath(self, dataPath):
        # boost::filesystem::path uses a weird format in order to round-trip being constructed from a stream correctly, even when quotation characters are in the path
        processedPath = "data=\""
        for character in dataPath:
            if character == u'&' or character == u'"':
                processedPath += "&"
            processedPath += character
        processedPath += "\"\n"
        return processedPath
    
    def __clearOpenMWConfig(self, configPath):
        import tempfile
        import os
        import shutil
        import codecs
        # copy the lines we want to keep to a temp file
        tempFileName = None
        with tempfile.NamedTemporaryFile(delete = False) as f:
            tempFileName = f.name
            lastLine = None
            with codecs.open(configPath, "r", "utf-8-sig") as openmwcfg:
                for line in openmwcfg:
                    if not line.startswith(u"data=") and not line.startswith(u"content="):
                        f.write(line.encode("utf-8"))
                        lastLine = line
            # ensure the last line ended with a line break
            if not lastLine.endswith(u"\n"):
                f.write("\n")
        # remove the original file
        os.remove(configPath)
        # put the temporary file where the original was
        shutil.move(tempFileName, configPath)
    
    def __getOpenMWConfigPath(self):
        # We're too sandboxed to reliably find the documents directory, so there are a few fallbacks here
        defaultLocation = os.path.join(os.path.expanduser("~"), "Documents", "My Games", "OpenMW", "openmw.cfg")
        if os.path.isfile(defaultLocation):
            return defaultLocation
        # If we've got this far, then the user has put their documents folder somewhere other than the default, so they can find it themselves.
        return QFileDialog.getOpenFileName(self.__parentWidget, self.__tr("Locate OpenMW Config File"), ".", "OpenMW Config File (openmw.cfg)")[0]
    
def createPlugin():
    return OpenMWExportPlugin()
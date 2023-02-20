# This Mod Organizer plugin is released to the pubic under the terms of the GNU GPL version 3, which is accessible from the Free Software Foundation here: https://www.gnu.org/licenses/gpl-3.0-standalone.html

# To use this plugin, place it in the plugins directory of your Mod Organizer install (ideally along with the OpenMW icon). You will then find an 'Export to OpenMW' option under the tools menu.

# If someone wanted to, they could expand upon this by registering callbacks for mod and plugin state changes so that you didn't manually have to click the button any more to make this work.

# Also, if Mod Organizer ever re-implements archive handling, then it wouldn't be too hard to make this also copy the list of these to fallback-archive= lines.

from pathlib import Path
import sys

from PyQt6.QtCore import QCoreApplication, QStandardPaths, QUrl, qCritical
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QFileDialog, QMessageBox

if "mobase" not in sys.modules:
    import mobase

class OpenMWExportPlugin(mobase.IPluginTool):
    
    def __init__(self):
        super(OpenMWExportPlugin, self).__init__()
        self.__organizer : mobase.IOrganizer
        self.__nexusBridge : mobase.IModRepositoryBridge

    def init(self, organizer):
        self.__organizer = organizer
        self.__nexusBridge = self.__organizer.createNexusBridge()
        self.__nexusBridge.descriptionAvailable.connect(self.__onDescriptionReceived)
        self.__organizer.onUserInterfaceInitialized(self.__checkForUpdate)
        return True

    def name(self):
        return "OpenMW Exporter"

    def author(self):
        return "AnyOldName3"

    def description(self):
        return OpenMWExportPlugin.tr("Transfers mod list (left pane) to data fields in OpenMW.cfg and plugin list (right pane, plugins tab) to content fields in OpenMW.cfg. This allows you to run OpenMW with the current profile's setup from outside of Mod Organizer")

    def version(self):
        return mobase.VersionInfo(4, 0, 0, mobase.ReleaseType.ALPHA)

    def requirements(self):
        return [
            mobase.PluginRequirementFactory.gameDependency("Morrowind")
        ]

    def isActive(self):
        return (self.__organizer.managedGame().gameName() == "Morrowind")

    def settings(self):
        return []

    def displayName(self):
        return OpenMWExportPlugin.tr("Export to OpenMW")

    def tooltip(self):
        return OpenMWExportPlugin.tr("Exports the current mod list and plugin load order to OpenMW.cfg")

    def icon(self):
        return QIcon("plugins/openmw.ico")
    
    def display(self):
        # We should test if the current game is compatible with OpenMW here
        # We can't do that directly, so instead we just test if the current game is Morrowind
        game = self.__organizer.managedGame()
        if game.gameName() != "Morrowind":
            QMessageBox.critical(self._parentWidget(), OpenMWExportPlugin.tr("Incompatible game"), OpenMWExportPlugin.tr("(At least when this plugin is being written) OpenMW only supports game data designed for the Morrowind engine. The game being managed is not Morrowind, so the export will abort. If you think you know better than this message, update this plugin."))
            return
        # Give the user the opportunity to abort
        confirmationButton = QMessageBox.question(self._parentWidget(), OpenMWExportPlugin.tr("Before starting export..."), OpenMWExportPlugin.tr("Before starting the export to OpenMW, please ensure you've backed up anything in OpenMW.cfg which you do not want to risk losing forever."), QMessageBox.StandardButton(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel))
        if confirmationButton != QMessageBox.StandardButton.Ok:
            return
        # Get the path to the OpenMW.cfg file
        configPath = self.__getOpenMWConfigPath()
        if not configPath.is_file():
            QMessageBox.critical(self._parentWidget(), OpenMWExportPlugin.tr("Config file not specified"), OpenMWExportPlugin.tr("No config file was specified"))
            return
        # Clear out the existing data= and content= lines from openmw.cfg
        self.__clearOpenMWConfig(configPath)
        with configPath.open("a", encoding="utf-8") as openmwcfg:
            # write out data directories
            openmwcfg.write(self.__processDataPath(game.dataDirectory().absolutePath()))
            for mod in self.__organizer.modList().allModsByProfilePriority():
                self.__processMod(openmwcfg, mod)
            self.__processMod(openmwcfg, "Overwrite")
            
            # write out content (plugin) files
            # order content files by load order
            loadOrder = {}
            for plugin in self.__organizer.pluginList().pluginNames():
                loadIndex = self.__organizer.pluginList().loadOrder(plugin)
                if loadIndex >= 0:
                    loadOrder[loadIndex] = plugin
            # actually write out the list
            for pluginIndex in range(len(loadOrder)):
                openmwcfg.write("content=" + loadOrder[pluginIndex] + "\n")
        QMessageBox.information(self._parentWidget(), OpenMWExportPlugin.tr("OpenMW Export Complete"), OpenMWExportPlugin.tr("The export to OpenMW completed successfully. The current setup was saved to {0}").format(configPath))
    
    @staticmethod
    def tr(str):
        return QCoreApplication.translate("OpenMWExportPlugin", str)
    
    def __processMod(self, configFile, modName):
        state = self.__organizer.modList().state(modName)
        if (state & 0x2) != 0 or modName == "Overwrite":
            path = self.__organizer.modList().getMod(modName).absolutePath()
            configLine = self.__processDataPath(path)
            configFile.write(configLine)
    
    def __processDataPath(self, dataPath):
        # boost::filesystem::path uses a weird format in order to round-trip being constructed from a stream correctly, even when quotation characters are in the path.
        # Modern OpenMW versions don't require this unless the path begins or ends in whitespace, or begins with a double quote, but do it anyway for backwards compatibility.
        processedPath = "data=\""
        for character in dataPath:
            if character == '&' or character == '"':
                processedPath += "&"
            processedPath += character
        processedPath += "\"\n"
        return processedPath
    
    def __clearOpenMWConfig(self, configPath):
        import tempfile
        import os
        import shutil
        # copy the lines we want to keep to a temp file
        tempFilePath = None
        with tempfile.NamedTemporaryFile(mode="w", delete = False, encoding="utf-8") as f:
            tempFilePath = f.name
            lastLine = ""
            with configPath.open("r", encoding="utf-8-sig") as openmwcfg:
                for line in openmwcfg:
                    if not line.startswith("data=") and not line.startswith("content="):
                        f.write(line)
                        lastLine = line
            # ensure the last line ended with a line break
            if not lastLine.endswith("\n"):
                f.write("\n")
        # we can't move to Path.replace due to https://bugs.python.org/issue29805
        os.remove(configPath)
        shutil.move(tempFilePath, configPath)
    
    def __getOpenMWConfigPath(self):
        defaultLocation = Path(QStandardPaths.locate(QStandardPaths.StandardLocation.DocumentsLocation, str(Path("My Games", "OpenMW", "openmw.cfg"))))
        if defaultLocation.is_file():
            return defaultLocation
        # If we've got this far, then the user is doing something very weird, so they can find it themselves.
        return Path(QFileDialog.getOpenFileName(self._parentWidget(), OpenMWExportPlugin.tr("Locate OpenMW Config File"), ".", "OpenMW Config File (openmw.cfg)")[0])
    
    def __checkForUpdate(self, mainWindow):
        self.__nexusBridge.requestDescription("Morrowind", 45642, None)

    def __onDescriptionReceived(self, gameName, modID, userData, resultData):
        version = mobase.VersionInfo(resultData["version"])
        if self.version() < version:
            response = QMessageBox.question(self._parentWidget(), OpenMWExportPlugin.tr("Plugin update available"), OpenMWExportPlugin.tr("{0} can be updated from version {1} to {2}. Do you want to open the download page in your browser?").format(self.displayName(), self.version(), version))
            if response == QMessageBox.StandardButton.Yes:
                QDesktopServices.openUrl(QUrl("https://www.nexusmods.com/morrowind/mods/45642"))
    
def createPlugin():
    return OpenMWExportPlugin()

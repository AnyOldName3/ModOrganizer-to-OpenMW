# This Mod Organizer plugin is released to the pubic under the terms of the GNU GPL version 3, which is accessible from the Free Software Foundation here: https://www.gnu.org/licenses/gpl-3.0-standalone.html

# To use this plugin, place it in the plugins directory of your Mod Organizer install (ideally along with the OpenMW icon). You will then find an 'Export to OpenMW' option under the tools menu.

# If someone wanted to, they could expand upon this by registering callbacks for mod and plugin state changes so that you didn't manually have to click the button any more to make this work.

# Also, if Mod Organizer ever re-implements archive handling, then it wouldn't be too hard to make this also copy the list of these to fallback-archive= lines.

from pathlib import Path
import sys

from PyQt6.QtCore import QCoreApplication, QStandardPaths, QUrl, qCritical
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QCheckBox, QFileDialog, QMessageBox

if "mobase" not in sys.modules:
    import mobase

class OpenMWExportPlugin(mobase.IPluginTool):
    __NAME = "OpenMW Exporter"
    __CONFIG_PATH = "config path"
    __ALWAYS_USE_THIS_CONFIG_PATH = "always use this config path"
    __SHOW_FOR_EXPERIMENTAL_GAMES = "show for experimental games"

    __PARTIALLY_SUPPORTED_GAMES = [
        "Morrowind",
        "Oblivion",
        "Fallout 3",
        "Fallout New Vegas",
        "Skyrim"
    ]
    
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
        return OpenMWExportPlugin.__NAME

    def author(self):
        return "AnyOldName3"

    def description(self):
        return OpenMWExportPlugin.tr("Transfers mod list (left pane) to data fields in OpenMW.cfg and plugin list (right pane, plugins tab) to content fields in OpenMW.cfg. This allows you to run OpenMW with the current profile's setup from outside of Mod Organizer")

    def version(self):
        return mobase.VersionInfo(4, 0, 0, mobase.ReleaseType.BETA)

    def requirements(self):
        return [
            mobase.PluginRequirementFactory.gameDependency(
                OpenMWExportPlugin.__PARTIALLY_SUPPORTED_GAMES
                if self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES) 
                else "Morrowind"
            )
        ]

    def isActive(self):
        if self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES):
            return self.__organizer.managedGame().gameName() in OpenMWExportPlugin.__PARTIALLY_SUPPORTED_GAMES
        else:
            return self.__organizer.managedGame().gameName() == "Morrowind"

    def settings(self):
        return [
            mobase.PluginSetting(OpenMWExportPlugin.__CONFIG_PATH, OpenMWExportPlugin.tr("The most-recently-used openmw.cfg path."), ""),
            mobase.PluginSetting(OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH, OpenMWExportPlugin.tr("Whether to always use the saved openmw.cfg without asking each time."), False),
            mobase.PluginSetting(OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES, OpenMWExportPlugin.tr("Whether to show the Export to OpenMW option for games with only limited experimental support."), False)
        ]

    def displayName(self):
        return OpenMWExportPlugin.tr("Export to OpenMW")

    def tooltip(self):
        return OpenMWExportPlugin.tr("Exports the current mod list and plugin load order to OpenMW.cfg")

    def icon(self):
        return QIcon("plugins/openmw.ico")
    
    def display(self):
        game = self.__organizer.managedGame()
        if self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES):
            if game.gameName() != "Morrowind":
                QMessageBox.warning(self._parentWidget(), OpenMWExportPlugin.tr("Experimental game"), OpenMWExportPlugin.tr("(At least when this plugin is being written) OpenMW only fully supports game data designed for the Morrowind engine. The game being managed is not Morrowind, so do not expect the game to be fully playable. If you think you know better than this message, update this plugin."))
        # Give the user the opportunity to abort
        confirmationButton = QMessageBox.question(self._parentWidget(), OpenMWExportPlugin.tr("Before starting export..."), OpenMWExportPlugin.tr("Before starting the export to OpenMW, please ensure you've backed up anything in OpenMW.cfg which you do not want to risk losing forever."), QMessageBox.StandardButton(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel))
        if confirmationButton != QMessageBox.StandardButton.Ok:
            return
        # Get the path to the OpenMW.cfg file
        configPath = self.__getOpenMWConfigPath()
        if not (configPath.exists() and configPath.is_file()):
            QMessageBox.critical(self._parentWidget(), OpenMWExportPlugin.tr("Config file not specified"), OpenMWExportPlugin.tr("No config file was specified"))
            return
        # Clear out the existing data= and content= lines from openmw.cfg
        self.__clearOpenMWConfig(configPath)
        # get already enabled groundcover plugins
        existing_groundcovers = set()
        with configPath.open("r", encoding="utf-8") as openmwcfg:
            for line in openmwcfg:
                if line.lower().startswith("groundcover="):
                    existing_groundcovers.add(line.strip().split('=')[1].lower())
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
                pluginName = loadOrder[pluginIndex]
                if pluginName.lower() not in existing_groundcovers:
                    openmwcfg.write("content=" + pluginName + "\n")
        QMessageBox.information(self._parentWidget(), OpenMWExportPlugin.tr("OpenMW Export Complete"), OpenMWExportPlugin.tr("The export to OpenMW completed successfully. The current setup was saved to {0}").format(configPath))
    
    @staticmethod
    def tr(str):
        return QCoreApplication.translate("OpenMWExportPlugin", str)
    
    def __processMod(self, configFile, modName):
        state = self.__organizer.modList().state(modName)
        if (state & mobase.ModState.ACTIVE) != 0 or modName == "Overwrite":
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
        savedPath = Path(self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__CONFIG_PATH))
        alwaysUse = self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH)
        if alwaysUse:
            if savedPath.exists() and savedPath.is_file():
                return savedPath
            else:
                #: {0} is the key for the setting that's being reset.
                QMessageBox.information(self._parentWidget(), OpenMWExportPlugin.tr("Saved openmw.cfg path unavailable"), OpenMWExportPlugin.tr("Saved openmw.cfg path unavailable. Resetting {0}").format(OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH))
                self.__organizer.setPluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH, False)
        defaultPath = Path(QStandardPaths.locate(QStandardPaths.StandardLocation.DocumentsLocation, str(Path("My Games", "OpenMW", "openmw.cfg"))))

        messageBox = QMessageBox(self._parentWidget())
        messageBox.setText(OpenMWExportPlugin.tr("Choose openmw.cfg path"))
        #: <div style=\"white-space:pre\">{0}</div> is the saved path.
        #: <div style=\"white-space:pre\">{1}</div> is the default path.
        #: <br> is a line break between them.
        messageBox.setInformativeText(OpenMWExportPlugin.tr("Saved:<div style=\"white-space:pre\">{0}</div><br>Default:<div style=\"white-space:pre\">{1}</div>").format(savedPath, defaultPath))
        savedButton = messageBox.addButton(OpenMWExportPlugin.tr("Saved"), QMessageBox.ButtonRole.AcceptRole)
        savedButton.setEnabled(savedPath.exists() and savedPath.is_file())
        defaultButton = messageBox.addButton(OpenMWExportPlugin.tr("Default"), QMessageBox.ButtonRole.AcceptRole)
        defaultButton.setEnabled(defaultPath.exists() and defaultPath.is_file())
        browseButton = messageBox.addButton(OpenMWExportPlugin.tr("Browse"), QMessageBox.ButtonRole.AcceptRole)
        rememberCheckBox = QCheckBox(OpenMWExportPlugin.tr("Always use this path"))
        messageBox.setCheckBox(rememberCheckBox)

        messageBox.exec()

        clickedButton = messageBox.clickedButton()
        if clickedButton == savedButton:
            path = savedPath
        elif clickedButton == defaultButton:
            path = defaultPath
            if ((not savedPath.exists() or not savedPath.is_file()) and savedPath != defaultPath) or rememberCheckBox.isChecked():
                self.__organizer.setPluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__CONFIG_PATH, str(defaultPath))
        else:
            path = Path(QFileDialog.getOpenFileName(self._parentWidget(), OpenMWExportPlugin.tr("Locate OpenMW Config File"), ".", "OpenMW Config File (openmw.cfg)")[0])
            if savedPath != path:
                self.__organizer.setPluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__CONFIG_PATH, str(path))

        if rememberCheckBox.isChecked():
            self.__organizer.setPluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH, True)

        return path

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

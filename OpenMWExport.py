# This Mod Organizer plugin is released to the pubic under the terms of the GNU GPL version 3, which is accessible from the Free Software Foundation here: https://www.gnu.org/licenses/gpl-3.0-standalone.html

# To use this plugin, place it in the plugins directory of your Mod Organizer install (ideally along with the OpenMW icon). You will then find an 'Export to OpenMW' option under the tools menu.

# If someone wanted to, they could expand upon this by registering callbacks for mod and plugin state changes so that you didn't manually have to click the button any more to make this work.  # DONE -luke

# Also, if Mod Organizer ever re-implements archive handling, then it wouldn't be too hard to make this also copy the list of these to fallback-archive= lines.

from pathlib import Path
import sys
from collections.abc import Iterable
from typing import Final

from PyQt6.QtCore import QCoreApplication, QStandardPaths, QTimer, QUrl, qCritical, qInfo
from PyQt6.QtGui import QDesktopServices, QIcon
from PyQt6.QtWidgets import QCheckBox, QFileDialog, QMessageBox

if "mobase" not in sys.modules:
    import mobase

class OpenMWExportPlugin(mobase.IPluginTool, mobase.IPluginDiagnose):
    __NAME = "OpenMW Exporter"
    __CONFIG_PATH = "config path"
    __ALWAYS_USE_THIS_CONFIG_PATH = "always use this config path"
    __SHOW_FOR_EXPERIMENTAL_GAMES = "show for experimental games"
    __AUTOMATIC_EXPORT_ENABLED = "automatic export when changes detected"
    __VERBOSE_LOGGING_ENABLED = "toggle verbose logging"
    __PERFORMANCE_MODE_ENABLED = "enable performance mode"

    __AUTO_EXPORT_DELAY_MS: Final[int] = 750
    __DUMMY_CONTENT_EXTENSIONS: Final[tuple[str, ...]] = (".omwaddon", ".omwscripts", ".omwgame")

    __PARTIALLY_SUPPORTED_GAMES = [
        "Morrowind",
        "Oblivion",
        "Fallout 3",
        "Fallout New Vegas",
        "Skyrim"
    ]
    __DUMMY_SUFFIX_MAP: Final[dict[str, str]] = {
        ".omwaddon.esp": ".omwaddon",
        ".omwscripts.esp": ".omwscripts",
        ".omwgame.esp": ".omwgame"
    }
    
    def __init__(self):
        super(OpenMWExportPlugin, self).__init__()
        # I think this shouldn't be necessary and a base class should be calling super
        mobase.IPluginDiagnose.__init__(self)
        self.__organizer : mobase.IOrganizer
        self.__nexusBridge : mobase.IModRepositoryBridge
        self.__autoExportTimer: QTimer | None = None
        self.__autoExportReasons: set[str] = set()
        self.__exportInProgress: bool = False
        self.__autoHooksRegistered: bool = False
        self.__missingConfigNotified: bool = False
        self.__initialDummyScanTimer: QTimer | None = None
        self.__cachedModSearchPaths: list[Path] | None = None
        self.__dummyContentCache: dict[str, Path | None] = {}

    def init(self, organizer):
        self.__organizer = organizer
        self.__nexusBridge = self.__organizer.createNexusBridge()
        self.__nexusBridge.descriptionAvailable.connect(self.__onDescriptionReceived)
        self.__organizer.onUserInterfaceInitialized(self.__on_ui_initialized)
        self.__register_automatic_export_hooks()
        return True

    def name(self):
        return OpenMWExportPlugin.__NAME

    def author(self):
        return "AnyOldName3"

    def description(self):
        return OpenMWExportPlugin.tr("Transfers mod list (left pane) to data fields in OpenMW.cfg and plugin list (right pane, plugins tab) to content fields in OpenMW.cfg. This allows you to run OpenMW with the current profile's setup from outside of Mod Organizer")

    def version(self):
        return mobase.VersionInfo(4, 1, 0, mobase.ReleaseType.FINAL)

    def requirements(self):
        return [
            mobase.PluginRequirementFactory.gameDependency(
                OpenMWExportPlugin.__PARTIALLY_SUPPORTED_GAMES
                if self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES) 
                else "Morrowind"
            )
        ]

    def isActive(self):
        game = self.__organizer.managedGame()
        if game is None:
            return False

        game_name = game.gameName()
        show_experimental = bool(
            self.__organizer.pluginSetting(
                OpenMWExportPlugin.__NAME,
                OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES,
            )
        )
        if show_experimental:
            return game_name in OpenMWExportPlugin.__PARTIALLY_SUPPORTED_GAMES
        return game_name == "Morrowind"

    def settings(self):
        return [
            mobase.PluginSetting(OpenMWExportPlugin.__CONFIG_PATH, OpenMWExportPlugin.tr("The most-recently-used openmw.cfg path."), ""),
            mobase.PluginSetting(OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH, OpenMWExportPlugin.tr("Whether to always use the saved openmw.cfg without asking each time."), False),
            mobase.PluginSetting(OpenMWExportPlugin.__AUTOMATIC_EXPORT_ENABLED, OpenMWExportPlugin.tr("Automatically export to OpenMW.cfg when the mod list or plugin load order changes."), True),
            mobase.PluginSetting(OpenMWExportPlugin.__VERBOSE_LOGGING_ENABLED, OpenMWExportPlugin.tr("Enable verbose diagnostic logging for the OpenMW Export plugin."), False),
            mobase.PluginSetting(OpenMWExportPlugin.__PERFORMANCE_MODE_ENABLED, OpenMWExportPlugin.tr("Enable performance mode to minimize automatic export work while browsing."), True),
            mobase.PluginSetting(OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES, OpenMWExportPlugin.tr("Whether to show the Export to OpenMW option for games with only limited experimental support."), False)
        ]

    def displayName(self):
        return OpenMWExportPlugin.tr("Export to OpenMW")

    def tooltip(self):
        return OpenMWExportPlugin.tr("Exports the current mod list and plugin load order to OpenMW.cfg")

    def icon(self):
        return QIcon("plugins/openmw.ico")
    
    def display(self):
        self.__export_interactive()

    def __export_interactive(self) -> None:
        game = self.__organizer.managedGame()
        if game is None:
            QMessageBox.critical(
                self._parentWidget(),
                OpenMWExportPlugin.tr("OpenMW Export Unavailable"),
                OpenMWExportPlugin.tr(
                    "The managed game information has not been initialised yet."
                    " Please wait for Mod Organizer to finish loading and try again."
                ),
            )
            return
        if self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__SHOW_FOR_EXPERIMENTAL_GAMES):
            if game.gameName() != "Morrowind":
                QMessageBox.warning(
                    self._parentWidget(),
                    OpenMWExportPlugin.tr("Experimental game"),
                    OpenMWExportPlugin.tr("(At least when this plugin is being written) OpenMW only fully supports game data designed for the Morrowind engine. The game being managed is not Morrowind, so do not expect the game to be fully playable. If you think you know better than this message, update this plugin."),
                )
        confirmation_button = QMessageBox.question(
            self._parentWidget(),
            OpenMWExportPlugin.tr("Before starting export..."),
            OpenMWExportPlugin.tr("Before starting the export to OpenMW, please ensure you've backed up anything in OpenMW.cfg which you do not want to risk losing forever."),
            QMessageBox.StandardButton(QMessageBox.StandardButton.Ok | QMessageBox.StandardButton.Cancel),
        )
        if confirmation_button != QMessageBox.StandardButton.Ok:
            return

        config_path = self.__getOpenMWConfigPath()
        self.__perform_export(config_path, interactive=True, reason="manual export")

    def activeProblems(self):
        return [0] if self.__organizer.profile().invalidationActive()[0] else []

    def shortDescription(self, key):
        return OpenMWExportPlugin.tr("Automatic Archive Invalidation is enabled.")

    def fullDescription(self, key):
        return OpenMWExportPlugin.tr("Automatic Archive Invalidation is enabled in the current profile. Automatic Archive Invalidation attempts to work around a problem in the later Bethesda Games Studios games. It is unnecessary for Morrowind or OpenMW, and the archive used is known to crash the game. You should disable it in the Manage Profiles window.")

    def hasGuidedFix(self, key):
        return False

    def startGuidedFix(self, key):
        pass
    
    @staticmethod
    def tr(str):
        return QCoreApplication.translate("OpenMWExportPlugin", str)
    
    def __processMod(self, configFile, modName):
        if self.__is_mod_active(modName) or modName == "Overwrite":
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

    def __on_ui_initialized(self, mainWindow) -> None:
        self.__log_verbose("User interface initialised; scheduling initial dummy scan.")
        self.__checkForUpdate(mainWindow)
        self.__schedule_initial_dummy_scan()

    def __schedule_initial_dummy_scan(self) -> None:
        if self.__initialDummyScanTimer is None:
            self.__initialDummyScanTimer = QTimer()
            self.__initialDummyScanTimer.setSingleShot(True)
            self.__initialDummyScanTimer.setInterval(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)
            self.__initialDummyScanTimer.timeout.connect(self.__run_initial_dummy_scan)
        self.__initialDummyScanTimer.start(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)

    def __run_initial_dummy_scan(self) -> None:
        self.__log_verbose("Running initial dummy scan after UI initialization.")
        if self.__organizer.managedGame() is None:
            self.__log_verbose("Managed game unavailable during initial dummy scan; retrying shortly.")
            self.__schedule_initial_dummy_scan()
            return
        self.__ensure_dummy_files_for_all_mods("ui initialization")


    def __perform_export(self, config_path: Path, interactive: bool, reason: str | None = None) -> bool:
        if config_path is None or str(config_path).strip() == "":
            self.__report_export_failure(OpenMWExportPlugin.tr("No config file was specified"), interactive)
            return False

        if not (config_path.exists() and config_path.is_file()):
            self.__report_export_failure(
                OpenMWExportPlugin.tr("The selected openmw.cfg path is unavailable: {0}").format(config_path),
                interactive,
            )
            return False

        if not self.isActive():
            if interactive:
                QMessageBox.information(
                    self._parentWidget(),
                    OpenMWExportPlugin.tr("OpenMW Export Skipped"),
                    OpenMWExportPlugin.tr("The OpenMW Exporter plugin is inactive for the current game."),
                )
            return False

        try:
            if self.__exportInProgress:
                return False
            game = self.__organizer.managedGame()
            if game is None:
                self.__report_export_failure(
                    OpenMWExportPlugin.tr("OpenMW export skipped: managed game information is not available yet."),
                    interactive,
                )
                return False
            self.__log_verbose(
                f"Starting export to '{config_path}' (interactive={interactive}, reason='{reason}')"
            )
            self.__exportInProgress = True
            self.__clearOpenMWConfig(config_path)
            existing_groundcovers = self.__read_existing_groundcovers(config_path)
            with config_path.open("a", encoding="utf-8") as openmwcfg:
                openmwcfg.write(self.__processDataPath(game.dataDirectory().absolutePath()))
                for mod in self.__organizer.modList().allModsByProfilePriority():
                    self.__processMod(openmwcfg, mod)
                self.__processMod(openmwcfg, "Overwrite")

                ordered_plugins = self.__collect_sorted_plugins()
                context_label = reason or ("manual export" if interactive else "automatic export")
                normalized_plugins = self.__ensure_dummy_plugins(ordered_plugins, context_label)
                written_plugins = set()
                for plugin_name in ordered_plugins:
                    normalized_name = normalized_plugins.get(
                        plugin_name,
                        self.__normalize_content_name(plugin_name),
                    )
                    lowered_name = normalized_name.lower()
                    if lowered_name in existing_groundcovers or lowered_name in written_plugins:
                        continue
                    openmwcfg.write(f"content={normalized_name}\n")
                    written_plugins.add(lowered_name)
        except (OSError, IOError) as error:
            self.__report_export_failure(
                OpenMWExportPlugin.tr("OpenMW Export failed: {0}").format(error),
                interactive,
            )
            return False
        finally:
            self.__exportInProgress = False

        self.__report_export_success(config_path, interactive, reason)
        return True

    def __read_existing_groundcovers(self, config_path: Path) -> set[str]:
        groundcovers: set[str] = set()
        try:
            with config_path.open("r", encoding="utf-8") as openmwcfg:
                for line in openmwcfg:
                    if line.lower().startswith("groundcover="):
                        groundcovers.add(line.strip().split('=', 1)[1].lower())
        except (OSError, IOError) as error:
            qCritical(OpenMWExportPlugin.tr("Unable to inspect existing groundcover entries in {0}: {1}").format(config_path, error))
        self.__log_verbose(
            f"Found {len(groundcovers)} existing groundcover entries while preparing export."
        )
        return groundcovers

    def __report_export_failure(self, message: str, interactive: bool) -> None:
        self.__log_verbose(f"Export failure reported (interactive={interactive}): {message}")
        if interactive:
            QMessageBox.critical(self._parentWidget(), OpenMWExportPlugin.tr("OpenMW Export Failed"), message)
        else:
            qCritical(message)

    def __report_export_success(self, config_path: Path, interactive: bool, reason: str | None) -> None:
        self.__missingConfigNotified = False
        if interactive:
            QMessageBox.information(
                self._parentWidget(),
                OpenMWExportPlugin.tr("OpenMW Export Complete"),
                OpenMWExportPlugin.tr("The export to OpenMW completed successfully. The current setup was saved to {0}").format(config_path),
            )
        else:
            suffix = f" ({reason})" if reason else ""
            qInfo(OpenMWExportPlugin.tr("Automatic OpenMW export completed to {0}{1}").format(config_path, suffix))
        self.__log_verbose(
            f"Export operation finished successfully for '{config_path}' (interactive={interactive}, reason='{reason}')."
        )

    def __is_verbose_logging_enabled(self) -> bool:
        try:
            return bool(
                self.__organizer.pluginSetting(
                    OpenMWExportPlugin.__NAME,
                    OpenMWExportPlugin.__VERBOSE_LOGGING_ENABLED,
                )
            )
        except Exception:
            return False

    def __log_verbose(self, message: str) -> None:
        if self.__is_verbose_logging_enabled():
            qInfo(f"[OpenMWExport][verbose] {message}")

    def __is_auto_export_setting_enabled(self) -> bool:
        """
        Checks whether automatic export automation is currently enabled by the user.

        Returns:
            bool: ``True`` when automatic export scheduling should be active.
        """

        return bool(
            self.__organizer.pluginSetting(
                OpenMWExportPlugin.__NAME,
                OpenMWExportPlugin.__AUTOMATIC_EXPORT_ENABLED,
            )
        )

    def __is_performance_mode(self) -> bool:
        try:
            return bool(
                self.__organizer.pluginSetting(
                    OpenMWExportPlugin.__NAME,
                    OpenMWExportPlugin.__PERFORMANCE_MODE_ENABLED,
                )
            )
        except Exception:
            return True

    def __is_auto_export_enabled(self) -> bool:
        if not self.__is_auto_export_setting_enabled():
            return False
        return self.isActive()

    def __register_automatic_export_hooks(self) -> None:
        if self.__autoHooksRegistered:
            return

        self.__log_verbose("Registering automatic export hooks.")
        if self.__autoExportTimer is None:
            self.__autoExportTimer = QTimer()
            self.__autoExportTimer.setSingleShot(True)
            self.__autoExportTimer.setInterval(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)
            self.__autoExportTimer.timeout.connect(self.__execute_scheduled_export)

        mod_list = self.__organizer.modList()
        if not mod_list.onModStateChanged(self.__handle_mod_states_changed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to mod state changes; automatic OpenMW export will be limited."))
        if not mod_list.onModMoved(self.__handle_mod_moved):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to mod movement events; automatic OpenMW export will be limited."))
        if not mod_list.onModInstalled(self.__handle_mod_installed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to mod installation events; automatic OpenMW export will be limited."))
        if not mod_list.onModRemoved(self.__handle_mod_removed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to mod removal events; automatic OpenMW export will be limited."))

        plugin_list = self.__organizer.pluginList()
        if not plugin_list.onPluginStateChanged(self.__handle_plugin_states_changed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to plugin state changes; automatic OpenMW export will be limited."))
        if not plugin_list.onPluginMoved(self.__handle_plugin_moved):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to plugin movement events; automatic OpenMW export will be limited."))
        if not plugin_list.onRefreshed(self.__handle_plugin_refreshed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to plugin refresh events; automatic OpenMW export will be limited."))

        if not self.__organizer.onProfileChanged(self.__handle_profile_changed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to profile change events; automatic OpenMW export may become stale."))
        if not self.__organizer.onPluginSettingChanged(self.__handle_plugin_setting_changed):
            qCritical(OpenMWExportPlugin.tr("Failed to subscribe to plugin setting changes; automatic OpenMW export settings may not update immediately."))

        self.__autoHooksRegistered = True
        self.__log_verbose("Automatic export hooks registered.")
        self.__scheduleAutomaticExport("initialization")

    def __scheduleAutomaticExport(self, reason: str) -> None:
        if self.__autoExportTimer is None:
            return
        if not self.__is_auto_export_setting_enabled():
            self.__log_verbose(
                f"Automatic export scheduling skipped (setting disabled) for reason '{reason}'."
            )
            return

        self.__autoExportReasons.add(reason)
        if self.__organizer.managedGame() is None:
            self.__log_verbose(
                f"Managed game unavailable; deferring export scheduling (reason='{reason}')."
            )
            self.__autoExportTimer.start(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)
            return

        if not self.__is_auto_export_enabled():
            self.__autoExportReasons.clear()
            self.__log_verbose("Automatic export scheduling cancelled because plugin is inactive for the current game.")
            return

        self.__log_verbose(
            f"Scheduling automatic export due to '{reason}'."
        )
        self.__autoExportTimer.start(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)

    def __execute_scheduled_export(self) -> None:
        if not self.__is_auto_export_setting_enabled():
            self.__autoExportReasons.clear()
            self.__log_verbose("Automatic export execution aborted: setting disabled.")
            return

        if self.__organizer.managedGame() is None:
            if self.__autoExportTimer is not None:
                self.__log_verbose("Managed game still unavailable; rescheduling automatic export execution.")
                self.__autoExportTimer.start(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)
            return

        if not self.__is_auto_export_enabled():
            self.__autoExportReasons.clear()
            self.__log_verbose("Automatic export execution aborted: plugin inactive for current game.")
            return
        if self.__exportInProgress:
            self.__autoExportTimer.start(OpenMWExportPlugin.__AUTO_EXPORT_DELAY_MS)
            self.__log_verbose("Automatic export execution deferred because another export is in progress.")
            return
        reasons = ", ".join(sorted(self.__autoExportReasons)) if self.__autoExportReasons else OpenMWExportPlugin.tr("automatic trigger")
        self.__autoExportReasons.clear()
        self.__log_verbose(f"Executing scheduled export (reasons: {reasons}).")
        config_path = self.__resolve_automation_config_path()
        if config_path is None:
            return
        self.__perform_export(config_path, interactive=False, reason=reasons)

    def __resolve_automation_config_path(self) -> Path | None:
        saved_value = self.__organizer.pluginSetting(OpenMWExportPlugin.__NAME, OpenMWExportPlugin.__CONFIG_PATH)
        if not saved_value:
            if not self.__missingConfigNotified:
                qCritical(OpenMWExportPlugin.tr("Automatic OpenMW export skipped: no openmw.cfg path has been saved yet."))
                self.__missingConfigNotified = True
            self.__log_verbose("Automatic export aborted: no saved openmw.cfg path.")
            return None
        config_path = Path(str(saved_value))
        if not (config_path.exists() and config_path.is_file()):
            if not self.__missingConfigNotified:
                qCritical(OpenMWExportPlugin.tr("Automatic OpenMW export skipped: saved openmw.cfg path is unavailable ({0}).").format(config_path))
                self.__missingConfigNotified = True
            self.__log_verbose(
                f"Automatic export aborted: saved openmw.cfg path '{config_path}' unavailable."
            )
            return None
        self.__log_verbose(f"Automatic export will target '{config_path}'.")
        return config_path

    def __handle_mod_states_changed(self, states: dict[str, mobase.ModState]) -> None:
        if not states:
            return
        self.__log_verbose(f"Mod state change received for {len(states)} mod(s).")
        self.__invalidate_mod_search_path_cache()
        self.__ensure_dummy_files_for_mod_names(states.keys(), "mod states changed")
        self.__scheduleAutomaticExport("mod states changed")

    def __handle_mod_moved(self, mod_name: str, old_priority: int, new_priority: int) -> None:
        _ = (mod_name, old_priority, new_priority)
        self.__log_verbose(
            f"Mod '{mod_name}' moved from {old_priority} to {new_priority}."
        )
        self.__invalidate_mod_search_path_cache()
        self.__scheduleAutomaticExport("mod priorities changed")

    def __handle_mod_installed(self, mod: mobase.IModInterface) -> None:
        try:
            mod_label = mod.name()
        except Exception:
            try:
                mod_label = mod.displayName()
            except Exception:
                mod_label = "<unknown>"
        mod_path = Path(mod.absolutePath())
        self.__log_verbose(f"Mod installed: '{mod_label}' at '{mod_path}'.")
        self.__invalidate_mod_search_path_cache()
        self.__ensure_dummy_files_in_paths([mod_path], "mod installed", force=True)
        self.__scheduleAutomaticExport("mod installed")

    def __handle_mod_removed(self, mod_name: str) -> None:
        _ = mod_name
        self.__log_verbose(f"Mod removed: '{mod_name}'.")
        self.__invalidate_mod_search_path_cache()
        self.__scheduleAutomaticExport("mod removed")

    def __handle_plugin_states_changed(self, states: dict[str, mobase.PluginState]) -> None:
        if not states:
            return
        self.__log_verbose(f"Plugin state change received for {len(states)} plugin(s).")
        self.__scheduleAutomaticExport("plugin states changed")

    def __handle_plugin_moved(self, plugin_name: str, old_priority: int, new_priority: int) -> None:
        _ = (plugin_name, old_priority, new_priority)
        self.__log_verbose(
            f"Plugin '{plugin_name}' moved from {old_priority} to {new_priority}."
        )
        self.__scheduleAutomaticExport("plugin priorities changed")

    def __handle_plugin_refreshed(self) -> None:
        self.__log_verbose("Plugin list refreshed; ensuring dummy files before scheduling export.")
        self.__invalidate_mod_search_path_cache()
        self.__ensure_dummy_files_for_all_mods("plugin list refreshed")
        if self.__is_performance_mode():
            self.__log_verbose(
                "Performance mode active; skipping automatic export scheduling for plugin refresh event."
            )
            return
        self.__scheduleAutomaticExport("plugin list refreshed")

    def __handle_profile_changed(self, old_profile: mobase.IProfile | None, new_profile: mobase.IProfile | None) -> None:
        _ = (old_profile, new_profile)
        self.__log_verbose("Profile changed; refreshing dummy files and scheduling export.")
        self.__invalidate_mod_search_path_cache()
        self.__ensure_dummy_files_for_all_mods("profile changed")
        self.__scheduleAutomaticExport("profile changed")

    def __handle_plugin_setting_changed(self, plugin_name: str, setting_name: str, old_value, new_value) -> None:
        if plugin_name != OpenMWExportPlugin.__NAME:
            return
        if setting_name in {
            OpenMWExportPlugin.__CONFIG_PATH,
            OpenMWExportPlugin.__ALWAYS_USE_THIS_CONFIG_PATH,
            OpenMWExportPlugin.__AUTOMATIC_EXPORT_ENABLED,
            OpenMWExportPlugin.__VERBOSE_LOGGING_ENABLED,
            OpenMWExportPlugin.__PERFORMANCE_MODE_ENABLED,
        }:
            self.__missingConfigNotified = False
            if setting_name == OpenMWExportPlugin.__AUTOMATIC_EXPORT_ENABLED and not bool(new_value):
                self.__autoExportReasons.clear()
                if self.__autoExportTimer is not None:
                    self.__autoExportTimer.stop()
            if setting_name == OpenMWExportPlugin.__VERBOSE_LOGGING_ENABLED:
                state = "enabled" if bool(new_value) else "disabled"
                qInfo(f"[OpenMWExport] Verbose logging {state} via plugin settings.")
            if setting_name == OpenMWExportPlugin.__PERFORMANCE_MODE_ENABLED:
                state = "enabled" if bool(new_value) else "disabled"
                qInfo(f"[OpenMWExport] Performance mode {state} via plugin settings.")
                self.__invalidate_mod_search_path_cache()
            self.__log_verbose(
                f"Plugin setting '{setting_name}' changed from '{old_value}' to '{new_value}'."
            )
            self.__scheduleAutomaticExport("settings updated")

    def __collect_sorted_plugins(self) -> list[str]:
        """
        Aggregates plugin identifiers sorted by load order for deterministic vibes.

        Returns:
            list[str]: Plugin names sorted ascending by their load index.
        """

        plugin_list = self.__organizer.pluginList()
        ordered_plugins: list[tuple[int, str]] = []
        for plugin_name in plugin_list.pluginNames():
            load_index = plugin_list.loadOrder(plugin_name)
            if load_index >= 0:
                ordered_plugins.append((load_index, plugin_name))
        ordered_plugins.sort(key=lambda item: item[0])
        sorted_plugins = [plugin_name for _, plugin_name in ordered_plugins]
        self.__log_verbose(
            f"Collected {len(sorted_plugins)} plugin(s) for export order validation."
        )
        return sorted_plugins

    def __ensure_dummy_plugins(self, plugin_names: Iterable[str], context: str) -> dict[str, str]:
        """
        Ensures placeholder ESP files exist for OpenMW-specific content entries.

        Args:
            plugin_names: Iterable of plugin names ordered by load index.
            context: Text describing why the check is being performed (for diagnostics).

        Returns:
            dict[str, str]: Mapping from original plugin names to their normalized
                content names (with dummy suffix stripped when needed).
        """

        if self.__is_performance_mode():
            search_paths = self.__collect_cached_mod_search_paths()
        else:
            search_paths = self.__collect_mod_search_paths()
        processed: set[str] = set()
        normalized: dict[str, str] = {}
        for plugin_name in plugin_names:
            content_name, requires_dummy = self.__resolve_content_descriptor(plugin_name)
            normalized[plugin_name] = content_name
            self.__log_verbose(
                f"Plugin '{plugin_name}' normalized to '{content_name}' (requires dummy={requires_dummy}, context='{context}')."
            )
            if not requires_dummy:
                continue
            lowered_content = content_name.lower()
            if lowered_content in processed:
                continue
            processed.add(lowered_content)
            content_path = self.__find_content_file(content_name, search_paths)
            if content_path is None:
                qCritical(OpenMWExportPlugin.tr("Unable to locate {0} to generate a dummy .esp for Mod Organizer.").format(content_name))
                continue
            self.__ensure_dummy_file_for_content(content_path, context)
        return normalized

    def __collect_mod_search_paths(self) -> list[Path]:
        """
        Builds an ordered list of directories to inspect for OpenMW assets.

        Returns:
            list[Path]: Candidate directories respecting MO2's priority order.
        """

        paths: list[Path] = []
        game = self.__organizer.managedGame()
        if game is None:
            self.__log_verbose("Managed game unavailable while collecting mod search paths.")
            return []
        game_data_path = Path(game.dataDirectory().absolutePath())
        if game_data_path.exists():
            paths.append(game_data_path)
        mod_list = self.__organizer.modList()
        for mod_name in mod_list.allModsByProfilePriority():
            if not self.__is_mod_active(mod_name):
                continue
            mod_path = Path(mod_list.getMod(mod_name).absolutePath())
            if mod_path.exists():
                paths.append(mod_path)
        try:
            overwrite_path = Path(mod_list.getMod("Overwrite").absolutePath())
            if overwrite_path.exists():
                paths.append(overwrite_path)
        except Exception:
            pass
        unique_paths: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            normalized = str(path).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            unique_paths.append(path)
        self.__log_verbose(
            f"Prepared {len(unique_paths)} search path(s) for dummy resolution."
        )
        return unique_paths

    def __collect_cached_mod_search_paths(self) -> list[Path]:
        if self.__cachedModSearchPaths is not None:
            self.__log_verbose("Using cached mod search paths (performance mode).")
            return self.__cachedModSearchPaths
        paths = self.__collect_mod_search_paths()
        self.__cachedModSearchPaths = paths
        return paths

    def __invalidate_mod_search_path_cache(self) -> None:
        if self.__cachedModSearchPaths is not None:
            self.__log_verbose("Invalidating cached mod search paths.")
        self.__cachedModSearchPaths = None
        if self.__dummyContentCache:
            self.__log_verbose("Clearing cached dummy content lookups.")
            self.__dummyContentCache.clear()

    def __ensure_dummy_files_in_paths(self, paths: Iterable[Path], context: str, *, force: bool = False) -> None:
        paths_list: list[Path] = []
        seen: set[str] = set()
        for path in paths:
            if path is None:
                continue
            normalized = str(path).lower()
            if normalized in seen:
                continue
            seen.add(normalized)
            paths_list.append(path)
        if self.__is_performance_mode() and not force:
            self.__log_verbose(
                f"Performance mode active; skipping dummy scan for {len(paths_list)} path(s) in context '{context}'."
            )
            return
        created_count = 0
        inspected = 0
        for base_path in paths_list:
            if base_path is None or not base_path.exists():
                self.__log_verbose(
                    f"Skipping dummy scan path '{base_path}' (unavailable)."
                )
                continue
            inspected += 1
            try:
                for extension in OpenMWExportPlugin.__DUMMY_CONTENT_EXTENSIONS:
                    pattern = f"*{extension}"
                    for content_path in base_path.rglob(pattern):
                        if not content_path.is_file():
                            continue
                        created_count += int(self.__ensure_dummy_file_for_content(content_path, context))
            except (OSError, PermissionError) as error:
                qCritical(OpenMWExportPlugin.tr("OpenMW Export could not inspect {0}: {1}").format(base_path, error))
        self.__log_verbose(
            f"Dummy scan '{context}' inspected {inspected} path(s) and created {created_count} new placeholder(s)."
        )

    def __ensure_dummy_file_for_content(self, content_path: Path, context: str) -> bool:
        dummy_path = content_path.with_name(f"{content_path.name}.esp")
        if dummy_path.exists():
            self.__log_verbose(f"Dummy already present for '{content_path}' (context: {context}).")
            return False
        try:
            dummy_path.parent.mkdir(parents=True, exist_ok=True)
            dummy_path.touch(exist_ok=True)
            self.__log_verbose(f"Created dummy plugin at '{dummy_path}' for '{content_path}' (context: {context}).")
            self.__dummyContentCache[content_path.name.lower()] = content_path
            return True
        except (OSError, PermissionError) as error:
            qCritical(OpenMWExportPlugin.tr("OpenMW Export could not create dummy plugin at {0}: {1}").format(dummy_path, error))
            self.__log_verbose(
                f"Failed to create dummy plugin at '{dummy_path}' for '{content_path}': {error}."
            )
        return False

    def __ensure_dummy_files_for_mod_names(self, mod_names: Iterable[str], context: str, *, force: bool = False) -> None:
        if self.__is_performance_mode() and not force:
            self.__log_verbose(
                f"Performance mode active; skipping targeted dummy scan for context '{context}'."
            )
            return
        paths: list[Path] = []
        mod_list = self.__organizer.modList()
        for mod_name in mod_names:
            try:
                mod_interface = mod_list.getMod(mod_name)
            except Exception:
                continue
            mod_path = Path(mod_interface.absolutePath())
            if mod_path.exists():
                paths.append(mod_path)
        if not paths:
            self.__log_verbose(
                f"No mod paths resolved for dummy scan context '{context}'."
            )
            return
        self.__ensure_dummy_files_in_paths(paths, context, force=force)

    def __ensure_dummy_files_for_all_mods(self, context: str, *, force: bool = False) -> None:
        if self.__is_performance_mode() and not force:
            self.__log_verbose(
                f"Performance mode active; comprehensive dummy scan skipped for context '{context}'."
            )
            return
        try:
            mod_list = self.__organizer.modList()
        except Exception:
            return
        paths: list[Path] = []
        mod_names: set[str] = set()
        try:
            for name in mod_list.allMods():
                mod_names.add(name)
        except Exception:
            pass
        try:
            for name in mod_list.allModsByProfilePriority():
                mod_names.add(name)
        except Exception:
            pass
        for mod_name in mod_names:
            try:
                mod_interface = mod_list.getMod(mod_name)
            except Exception:
                continue
            mod_path = Path(mod_interface.absolutePath())
            if mod_path.exists():
                paths.append(mod_path)
        try:
            overwrite_path = Path(mod_list.getMod("Overwrite").absolutePath())
            if overwrite_path.exists():
                paths.append(overwrite_path)
        except Exception:
            pass
        if not paths:
            self.__log_verbose(
                f"No mod directories available for comprehensive dummy scan ('{context}')."
            )
            return
        self.__ensure_dummy_files_in_paths(paths, context, force=force)

    def __find_content_file(self, content_filename: str, search_paths: Iterable[Path]) -> Path | None:
        """
        Attempts to locate the requested OpenMW content file in the provided directories.

        Args:
            content_filename: File name (with extension) to locate.
            search_paths: Directories to inspect.

        Returns:
            Path | None: The path to the requested content file if found.
        """

        target_lower = content_filename.lower()
        if target_lower in self.__dummyContentCache:
            cached = self.__dummyContentCache[target_lower]
            if cached is None:
                self.__log_verbose(
                    f"Cached miss reused for '{content_filename}'."
                )
                return None
            if cached.exists():
                self.__log_verbose(
                    f"Reusing cached content path '{cached}' for '{content_filename}'."
                )
                return cached
            self.__log_verbose(
                f"Cached content entry for '{content_filename}' no longer valid; refreshing lookup."
            )
            self.__dummyContentCache.pop(target_lower, None)
        for base_path in search_paths:
            direct_candidate = base_path / content_filename
            if direct_candidate.exists():
                self.__log_verbose(
                    f"Located content '{direct_candidate}' for '{content_filename}' via direct lookup."
                )
                self.__dummyContentCache[target_lower] = direct_candidate
                return direct_candidate
            try:
                for candidate in base_path.rglob(content_filename):
                    if candidate.is_file() and candidate.name.lower() == target_lower:
                        self.__log_verbose(
                            f"Located content '{candidate}' for '{content_filename}' via recursive search."
                        )
                        self.__dummyContentCache[target_lower] = candidate
                        return candidate
            except (OSError, PermissionError) as error:
                qCritical(OpenMWExportPlugin.tr("OpenMW Export could not inspect {0}: {1}").format(base_path, error))
                self.__log_verbose(
                    f"Failed to inspect '{base_path}' while searching for '{content_filename}': {error}."
                )
        self.__log_verbose(
            f"Content '{content_filename}' was not found in the inspected search paths."
        )
        self.__dummyContentCache[target_lower] = None
        return None

    def __create_dummy_file(self, dummy_path: Path) -> None:
        """
        Creates an empty ESP placeholder at the requested location.

        Args:
            dummy_path: Destination path for the dummy plugin.
        """

        try:
            dummy_path.touch(exist_ok=True)
        except (OSError, PermissionError) as error:
            qCritical(OpenMWExportPlugin.tr("OpenMW Export could not create dummy plugin at {0}: {1}").format(dummy_path, error))

    def __normalize_content_name(self, plugin_name: str) -> str:
        """
        Converts dummy plugin names into their OpenMW target file names.

        Args:
            plugin_name: Plugin entry from the load order.

        Returns:
            str: The name to be written to openmw.cfg.
        """

        content_name, _ = self.__resolve_content_descriptor(plugin_name)
        return content_name

    def __needs_dummy_plugin(self, plugin_name: str) -> bool:
        """
        Checks whether the provided plugin matches a known dummy suffix.

        Args:
            plugin_name: Plugin entry from the load order.

        Returns:
            bool: True if a dummy ESP needs to exist for the plugin.
        """

        _, requires_dummy = self.__resolve_content_descriptor(plugin_name)
        return requires_dummy

    def __resolve_content_descriptor(self, plugin_name: str) -> tuple[str, bool]:
        """
        Resolves the content name associated with a plugin and whether a dummy is needed.

        Args:
            plugin_name: Plugin entry from the load order.

        Returns:
            tuple[str, bool]: Pair of (content name, requires dummy).
        """

        lowered_name = plugin_name.lower()
        for dummy_suffix, _ in OpenMWExportPlugin.__DUMMY_SUFFIX_MAP.items():
            if lowered_name.endswith(dummy_suffix):
                return plugin_name[:-4], True
        for extension in OpenMWExportPlugin.__DUMMY_CONTENT_EXTENSIONS:
            if lowered_name.endswith(extension):
                return plugin_name, True
        return plugin_name, False

    def __is_mod_active(self, mod_name: str) -> bool:
        """
        Determines whether the provided mod is enabled in the current profile.

        Args:
            mod_name: Name of the mod as presented by Mod Organizer.

        Returns:
            bool: True when the mod contributes data to the profile.
        """

        try:
            return (self.__organizer.modList().state(mod_name) & mobase.ModState.ACTIVE) != 0
        except Exception:
            return False
    
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

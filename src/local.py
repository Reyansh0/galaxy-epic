import asyncio
import json
import logging as log
from collections import defaultdict
import os.path

from galaxy.api.types import LocalGameState

from consts import LAUNCHER_INSTALLED_PATH, SYSTEM, System, LAUNCHER_PROCESS_IDENTIFIER
from process_watcher import ProcessWatcher

if SYSTEM == System.WINDOWS:
    import winreg
    from consts import EPIC_WINREG_LOCATION
elif SYSTEM == System.MACOS:
    from consts import EPIC_MAC_INSTALL_LOCATION


class LauncherInstalledParser:
    def __init__(self):
        self._path = LAUNCHER_INSTALLED_PATH
        self._last_modified = None

    def file_has_changed(self):
        try:
            stat = os.stat(self._path)
        except FileNotFoundError as e:
            log.debug(str(e))
            return False
        except Exception as e:
            log.exception(f'Stating {self._path} has failed: {str(e)}')
            raise RuntimeError('Stating failed:' + str(e))
        else:
            if stat.st_mtime != self._last_modified:
                self._last_modified = stat.st_mtime
                return True
            return False

    def _load_file(self):
        content = {}
        try:
            with open(self._path, 'r') as f:
                content = json.load(f)
        except FileNotFoundError as e:
            log.debug(str(e))
        return content

    def parse(self):
        installed_games = {}
        content = self._load_file()
        game_list = content.get('InstallationList', [])
        for entry in game_list:
            app_name = entry.get('AppName', None)
            if not app_name or app_name.startswith('UE'):
                continue
            installed_games[entry['AppName']] = entry['InstallLocation']
        return installed_games


class LocalGamesProvider:
    def __init__(self):
        self._parser = LauncherInstalledParser()
        self._ps_watcher = ProcessWatcher(LAUNCHER_PROCESS_IDENTIFIER)
        self._games = defaultdict(lambda: LocalGameState.None_)
        self._updated_games = set()
        self._was_installed = dict()
        self._was_running = set()
        self._first_run = True
        self._status_updater = None

    @property
    def is_launcher_installed(self):
        if SYSTEM == System.WINDOWS:
            try:
                reg = winreg.ConnectRegistry(None, winreg.HKEY_LOCAL_MACHINE)
                winreg.OpenKey(reg, EPIC_WINREG_LOCATION)
                return True
            except OSError:
                return False
        elif SYSTEM == System.MACOS:
            return os.path.exists(EPIC_MAC_INSTALL_LOCATION)

    @property
    def first_run(self):
        return self._first_run

    @property
    def games(self):
        return self._games

    async def search_process(self, game_id, timeout):
        await self._ps_watcher.pool_until_game_start(game_id, timeout, sint=0.5, lint=2)

    def is_game_running(self, game_id):
        return self._ps_watcher._is_app_tracked_and_running(game_id)

    def consume_updated_games(self):
        tmp = self._updated_games.copy()
        self._updated_games.clear()
        return tmp

    def setup(self):
        log.info('Running local games provider setup')
        self.check_for_installed()
        self.check_for_running()
        loop = asyncio.get_event_loop()
        self._status_updater = loop.create_task(self._endless_status_checker())
        self._first_run = False

    async def _endless_status_checker(self):
        log.info('Starting endless status checker')
        counter = 0
        while True:
            try:
                if self.is_launcher_installed:
                    self.check_for_installed()
                    if 0 == counter % 21:
                        await self.parse_all_procs_if_needed()
                    elif 0 == counter % 7:
                        self.check_for_running(check_for_new=True)
                    self.check_for_running()
            except Exception as e:
                log.error(e)
            finally:
                counter += 1
                await asyncio.sleep(1)

    def check_for_installed(self):
        if not self._parser.file_has_changed():
            return
        log.debug('Ini file has been changed. Parsing')
        installed = self._parser.parse()
        self._update_game_statuses(set(self._was_installed), set(installed), LocalGameState.Installed)
        self._ps_watcher.watched_games = installed
        self._was_installed = installed

    async def parse_all_procs_if_needed(self):
        if len(self._was_installed) > 0 and len(self._was_running) == 0:
            await self._ps_watcher._serach_in_all_slowly(interval=0.015)

    def check_for_running(self, check_for_new=False):
        running = self._ps_watcher.get_running_games(check_under_launcher=check_for_new)
        self._update_game_statuses(self._was_running, running, LocalGameState.Running)
        self._was_running = running

    def _update_game_statuses(self, previous, current, status):
        for id_ in (current - previous):
            self._games[id_] |= status
            if not self._first_run:
                self._updated_games.add(id_)

        for id_ in (previous - current):
            self._games[id_] ^= status
            if not self._first_run:
                self._updated_games.add(id_)

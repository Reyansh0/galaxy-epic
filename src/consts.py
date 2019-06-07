import os
import sys
from enum import EnumMeta


class System(EnumMeta):
    WINDOWS = 1
    MACOS = 2
    LINUX = 3


_program_data = ''

SYSTEM = None

if sys.platform == 'win32':
    SYSTEM = System.WINDOWS
    _program_data = os.getenv('PROGRAMDATA')
    EPIC_WINREG_LOCATION = "SOFTWARE\\WOW6432Node\\Epic Games\\EpicGamesLauncher"
    LAUNCHER_WINREG_LOCATION = r"Computer\HKEY_CLASSES_ROOT\com.epicgames.launcher\shell\open\command"
    LAUNCHER_PROCESS_IDENTIFIER = 'EpicGamesLauncher.exe'

elif sys.platform == 'darwin':
    SYSTEM = System.MACOS
    _program_data = os.path.expanduser('~/Library/Application Support')
    EPIC_MAC_INSTALL_LOCATION = "/Applications/Epic Games Launcher.app"
    LAUNCHER_PROCESS_IDENTIFIER = 'Epic Games Launcher'

LAUNCHER_INSTALLED_PATH = os.path.join(_program_data,
                                       'Epic',
                                       'UnrealEngineLauncher',
                                       'LauncherInstalled.dat')

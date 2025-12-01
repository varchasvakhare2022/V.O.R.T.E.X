"""
Application Launcher and System Controller.
Handles launching applications and managing VORTEX window state.
"""

import logging
import subprocess
import os
import time
import threading
from typing import Dict, Optional, Callable

from utils.windows_integration import WindowsIntegration


class AppLauncher:
    """
    Handles application launching with support for embedded and fullscreen apps.
    Manages VORTEX window state (minimize/restore).
    """
    
    def __init__(self):
        """Initialize AppLauncher with app mappings."""
        self.logger = logging.getLogger("VORTEX.AppLauncher")
        self.win_integration = WindowsIntegration()
        
        # App name mappings to executable paths/commands
        # Default values (can be overridden by config)
        self.app_paths: Dict[str, str] = {
            'notepad': 'notepad.exe',
            'calculator': 'calc.exe',
            'chrome': 'chrome.exe',
            'firefox': 'firefox.exe',
            'valorant': r'C:\Riot Games\VALORANT\live\VALORANT.exe',
            'steam': 'steam://',
        }
        
        # Apps that should run in fullscreen mode (VORTEX minimizes)
        self.fullscreen_apps = {
            'valorant',
            'game',
            'games',
            'steam',
        }
        
        # Apps that should be embedded in VORTEX window (normal apps)
        self.embedded_apps = {
            'notepad',
            'calculator',
            'chrome',
            'firefox',
            'edge',
        }
        
        # Callback for window operations (set by VORTEX main class)
        self.minimize_callback: Optional[Callable] = None
        self.restore_callback: Optional[Callable] = None
        self.embed_callback: Optional[Callable[[int], bool]] = None  # Callback to embed window
    
    def set_window_callbacks(self, minimize_callback: Callable, restore_callback: Callable,
                            embed_callback: Optional[Callable[[int], bool]] = None):
        """
        Set callbacks for window minimize/restore operations.
        These will be called when VORTEX needs to minimize/restore.
        
        Args:
            minimize_callback: Function to call to minimize VORTEX window
            restore_callback: Function to call to restore VORTEX window
            embed_callback: Function to call to embed a window (takes HWND, returns bool)
        """
        self.minimize_callback = minimize_callback
        self.restore_callback = restore_callback
        self.embed_callback = embed_callback
    
    def is_fullscreen_app(self, app_name: str) -> bool:
        """
        Check if an app should run in fullscreen mode.
        
        Args:
            app_name: Name of the application
            
        Returns:
            True if app should run fullscreen (VORTEX minimizes), False otherwise
        """
        app_lower = app_name.lower()
        
        # Check exact match
        if app_lower in self.fullscreen_apps:
            return True
        
        # Check if app name contains fullscreen keywords
        for fullscreen_keyword in self.fullscreen_apps:
            if fullscreen_keyword in app_lower:
                return True
        
        return False
    
    def launch_embedded_app(self, app_name: str) -> bool:
        """
        Launch an application that should be embedded in VORTEX window.
        Attempts to find the window and embed it into VORTEX.
        
        Args:
            app_name: Name of the application to launch
            
        Returns:
            True if launch successful, False otherwise
        """
        app_lower = app_name.lower()
        self.logger.info(f"Launching embedded app: {app_name}")
        
        try:
            # Get app path/command
            app_path = self._get_app_path(app_lower)
            if not app_path:
                self.logger.error(f"Unknown app: {app_name}")
                return False
            
            # Launch application
            process = None
            if app_path.startswith('steam://'):
                # URI scheme - use os.startfile on Windows
                os.startfile(app_path)
            else:
                # Regular executable
                process = subprocess.Popen(app_path, shell=False)
            
            self.logger.info(f"Launched process: {app_name}")
            
            # Try to embed the window
            if self.embed_callback:
                # Wait for window to appear and try to embed it
                threading.Thread(
                    target=self._wait_and_embed_window,
                    args=(app_name, app_path, process),
                    daemon=True
                ).start()
            else:
                # No embed callback - just ensure window appears on top
                threading.Thread(
                    target=self._bring_window_to_front,
                    args=(app_name, app_path),
                    daemon=True
                ).start()
            
            return True
        
        except Exception as e:
            self.logger.error(f"Error launching app {app_name}: {e}", exc_info=True)
            return False
    
    def _wait_and_embed_window(self, app_name: str, app_path: str, process):
        """
        Wait for window to appear and embed it.
        Runs in background thread.
        
        Args:
            app_name: Name of the app
            app_path: Path to the executable
            process: Process object (if available)
        """
        try:
            # Wait a bit for window to appear
            time.sleep(0.5)
            
            # Try to find window by name first
            window_titles = [
                app_name.capitalize(),
                app_name,
                os.path.basename(app_path).replace('.exe', ''),
            ]
            
            hwnd = None
            for title in window_titles:
                hwnd = self.win_integration.find_window_by_name(title, partial_match=True, timeout=3.0)
                if hwnd:
                    break
            
            # If not found by name, try by process
            if not hwnd and process:
                try:
                    import win32process
                    pid = process.pid
                    def enum_handler(hwnd, ctx):
                        try:
                            _, found_pid = win32process.GetWindowThreadProcessId(hwnd)
                            if found_pid == pid and win32gui.IsWindowVisible(hwnd):
                                ctx.append(hwnd)
                        except Exception:
                            pass
                        return True
                    
                    windows = []
                    import win32gui
                    win32gui.EnumWindows(enum_handler, windows)
                    if windows:
                        hwnd = windows[0]
                except Exception as e:
                    self.logger.debug(f"Could not find window by process: {e}")
            
            if hwnd:
                self.logger.info(f"Found window for {app_name}: HWND={hwnd}")
                
                # Try to embed
                if self.embed_callback:
                    success = self.embed_callback(hwnd)
                    if success:
                        self.logger.info(f"Successfully embedded {app_name}")
                    else:
                        self.logger.warning(f"Failed to embed {app_name}, bringing to front instead")
                        self.win_integration.bring_to_front(hwnd)
                else:
                    self.win_integration.bring_to_front(hwnd)
            else:
                self.logger.warning(f"Could not find window for {app_name}, app may have opened in background")
                # Bring any window with app name to front
                for title in window_titles:
                    hwnd = self.win_integration.find_window_by_name(title, partial_match=True, timeout=1.0)
                    if hwnd:
                        self.win_integration.bring_to_front(hwnd)
                        break
        
        except Exception as e:
            self.logger.error(f"Error in window embedding thread: {e}", exc_info=True)
    
    def _bring_window_to_front(self, app_name: str, app_path: str):
        """
        Bring app window to front without embedding.
        Runs in background thread.
        
        Args:
            app_name: Name of the app
            app_path: Path to the executable
        """
        try:
            time.sleep(0.5)
            
            window_titles = [
                app_name.capitalize(),
                app_name,
                os.path.basename(app_path).replace('.exe', ''),
            ]
            
            for title in window_titles:
                hwnd = self.win_integration.find_window_by_name(title, partial_match=True, timeout=2.0)
                if hwnd:
                    self.win_integration.bring_to_front(hwnd)
                    self.logger.info(f"Brought {app_name} window to front")
                    break
        
        except Exception as e:
            self.logger.error(f"Error bringing window to front: {e}", exc_info=True)
    
    def launch_fullscreen_app(self, app_name: str) -> bool:
        """
        Launch a fullscreen application and minimize VORTEX.
        
        Args:
            app_name: Name of the application to launch
            
        Returns:
            True if launch successful, False otherwise
        """
        app_lower = app_name.lower()
        self.logger.info(f"Launching fullscreen app: {app_name}")
        
        # Minimize VORTEX window first
        self.minimize_vortex_window()
        
        try:
            # Get app path/command
            app_path = self._get_app_path(app_lower)
            if not app_path:
                self.logger.error(f"Unknown app: {app_name}")
                return False
            
            # Launch application
            if app_path.startswith('steam://'):
                # URI scheme
                os.startfile(app_path)
            else:
                # Regular executable
                subprocess.Popen(app_path, shell=False)
            
            self.logger.info(f"Successfully launched fullscreen app: {app_name}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error launching fullscreen app {app_name}: {e}", exc_info=True)
            return False
    
    def minimize_vortex_window(self):
        """Minimize the VORTEX window."""
        self.logger.info("Minimizing VORTEX window")
        
        if self.minimize_callback:
            try:
                self.minimize_callback()
            except Exception as e:
                self.logger.error(f"Error in minimize callback: {e}", exc_info=True)
        else:
            self.logger.warning("Minimize callback not set")
    
    def restore_vortex_window(self):
        """Restore/maximize the VORTEX window."""
        self.logger.info("Restoring VORTEX window")
        
        if self.restore_callback:
            try:
                self.restore_callback()
            except Exception as e:
                self.logger.error(f"Error in restore callback: {e}", exc_info=True)
        else:
            self.logger.warning("Restore callback not set")
    
    def _get_app_path(self, app_name: str) -> Optional[str]:
        """
        Get the executable path or command for an app name.
        
        Args:
            app_name: Name of the application (lowercase)
            
        Returns:
            Path/command string or None if not found
        """
        # Direct lookup
        if app_name in self.app_paths:
            return self.app_paths[app_name]
        
        # Partial match lookup
        for key, path in self.app_paths.items():
            if key in app_name or app_name in key:
                return path
        
        return None
    
    def add_app_mapping(self, app_name: str, path: str, is_fullscreen: bool = False):
        """
        Add or update an app mapping.
        
        Args:
            app_name: Name of the application
            path: Path to executable or command
            is_fullscreen: Whether this app should run in fullscreen mode
        """
        app_lower = app_name.lower()
        self.app_paths[app_lower] = path
        
        if is_fullscreen:
            self.fullscreen_apps.add(app_lower)
        else:
            self.embedded_apps.add(app_lower)
        
        self.logger.info(f"Added app mapping: {app_name} -> {path} (fullscreen: {is_fullscreen})")

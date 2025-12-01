"""
Windows-specific integration utilities.
System-level operations and window management.
"""

import logging
import time
import win32gui
import win32con
import win32process
import win32api
from typing import Optional, List


class WindowsIntegration:
    """Windows-specific system integration utilities."""
    
    def __init__(self):
        """Initialize Windows integration."""
        self.logger = logging.getLogger("VORTEX.WindowsIntegration")
    
    def find_window_by_name(self, window_name: str, partial_match: bool = True, timeout: float = 10.0) -> Optional[int]:
        """
        Find window handle by window name.
        
        Args:
            window_name: Name or title of the window to find
            partial_match: If True, matches if window_name is contained in window title
            timeout: Maximum time to wait for window to appear (seconds)
            
        Returns:
            Window handle (HWND) or None if not found
        """
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            def enum_handler(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    title = win32gui.GetWindowText(hwnd)
                    if title:
                        if partial_match:
                            if window_name.lower() in title.lower():
                                ctx.append(hwnd)
                        else:
                            if title.lower() == window_name.lower():
                                ctx.append(hwnd)
                return True
            
            windows = []
            win32gui.EnumWindows(enum_handler, windows)
            
            if windows:
                hwnd = windows[0]  # Return first match
                self.logger.info(f"Found window '{window_name}': HWND={hwnd}")
                return hwnd
            
            time.sleep(0.1)  # Wait 100ms before retrying
        
        self.logger.warning(f"Window '{window_name}' not found within {timeout} seconds")
        return None
    
    def find_window_by_process(self, process_name: str, timeout: float = 10.0) -> Optional[int]:
        """
        Find window handle by process name.
        
        Args:
            process_name: Name of the process executable (e.g., "notepad.exe")
            timeout: Maximum time to wait for window to appear (seconds)
            
        Returns:
            Window handle (HWND) or None if not found
        """
        start_time = time.time()
        process_name_lower = process_name.lower()
        
        while time.time() - start_time < timeout:
            def enum_handler(hwnd, ctx):
                if win32gui.IsWindowVisible(hwnd):
                    try:
                        _, pid = win32process.GetWindowThreadProcessId(hwnd)
                        handle = win32api.OpenProcess(win32con.PROCESS_QUERY_INFORMATION | win32con.PROCESS_VM_READ, False, pid)
                        exe_name = win32process.GetModuleFileNameEx(handle, 0)
                        if process_name_lower in exe_name.lower():
                            ctx.append(hwnd)
                    except Exception:
                        pass
                return True
            
            windows = []
            try:
                win32gui.EnumWindows(enum_handler, windows)
            except Exception:
                # Fallback to name-based search
                return self.find_window_by_name(process_name, partial_match=True, timeout=timeout)
            
            if windows:
                hwnd = windows[0]
                self.logger.info(f"Found window for process '{process_name}': HWND={hwnd}")
                return hwnd
            
            time.sleep(0.1)
        
        self.logger.warning(f"Window for process '{process_name}' not found within {timeout} seconds")
        return None
    
    def embed_window(self, child_hwnd: int, parent_hwnd: int) -> bool:
        """
        Embed a child window into a parent window.
        Uses Windows SetParent API to embed the window.
        
        Args:
            child_hwnd: Handle of the window to embed
            parent_hwnd: Handle of the parent window (PyQt6 widget)
            
        Returns:
            True if embedding successful, False otherwise
        """
        try:
            # Get PyQt6 window handle
            if hasattr(parent_hwnd, 'winId'):
                parent_hwnd = int(parent_hwnd.winId())
            
            # Remove window decorations
            style = win32gui.GetWindowLong(child_hwnd, win32con.GWL_STYLE)
            style = style & ~win32con.WS_CAPTION & ~win32con.WS_THICKFRAME & ~win32con.WS_SYSMENU
            win32gui.SetWindowLong(child_hwnd, win32con.GWL_STYLE, style)
            
            # Set parent window
            win32gui.SetParent(child_hwnd, parent_hwnd)
            
            # Update window
            win32gui.ShowWindow(child_hwnd, win32con.SW_SHOW)
            win32gui.UpdateWindow(child_hwnd)
            
            self.logger.info(f"Successfully embedded window {child_hwnd} into {parent_hwnd}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error embedding window: {e}", exc_info=True)
            return False
    
    def position_window(self, hwnd: int, x: int, y: int, width: int, height: int):
        """
        Position and resize a window.
        
        Args:
            hwnd: Window handle
            x: X position
            y: Y position
            width: Window width
            height: Window height
        """
        try:
            win32gui.SetWindowPos(
                hwnd,
                win32con.HWND_TOP,
                x, y, width, height,
                win32con.SWP_SHOWWINDOW
            )
            self.logger.debug(f"Positioned window {hwnd} at ({x}, {y}) size {width}x{height}")
        except Exception as e:
            self.logger.error(f"Error positioning window: {e}", exc_info=True)
    
    def minimize_window(self, hwnd: int):
        """Minimize a window."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_MINIMIZE)
            self.logger.debug(f"Minimized window {hwnd}")
        except Exception as e:
            self.logger.error(f"Error minimizing window: {e}", exc_info=True)
    
    def restore_window(self, hwnd: int):
        """Restore a window."""
        try:
            win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
            self.logger.debug(f"Restored window {hwnd}")
        except Exception as e:
            self.logger.error(f"Error restoring window: {e}", exc_info=True)
    
    def bring_to_front(self, hwnd: int):
        """Bring a window to the front."""
        try:
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            self.logger.debug(f"Brought window {hwnd} to front")
        except Exception as e:
            self.logger.error(f"Error bringing window to front: {e}", exc_info=True)

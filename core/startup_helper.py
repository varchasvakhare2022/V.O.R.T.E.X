"""
Windows Startup Helper.
Provides instructions and utilities for adding VORTEX to Windows startup.
"""

import os
import logging
import winreg
from typing import Optional


class StartupHelper:
    """Helper for managing VORTEX Windows startup configuration."""
    
    def __init__(self):
        """Initialize startup helper."""
        self.logger = logging.getLogger("VORTEX.StartupHelper")
    
    def get_startup_instructions(self) -> str:
        """
        Get instructions for adding VORTEX to Windows startup.
        
        Returns:
            Formatted instruction string
        """
        instructions = """
╔══════════════════════════════════════════════════════════════════════════╗
║          VORTEX - Windows Startup Configuration Instructions            ║
╚══════════════════════════════════════════════════════════════════════════╝

There are two methods to add VORTEX to Windows startup:

METHOD 1: Startup Folder (Recommended - Easier)
────────────────────────────────────────────────
1. Press Windows + R to open Run dialog
2. Type: shell:startup
3. Press Enter (opens Startup folder)
4. Create a shortcut to your VORTEX executable:
   - Right-click in the folder → New → Shortcut
   - Browse to your VORTEX.exe location
   - Click Next → Finish
5. VORTEX will now start automatically on Windows login

METHOD 2: Registry (Advanced)
──────────────────────────────
1. Press Windows + R, type: regedit
2. Navigate to:
   HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run
3. Right-click in the right panel → New → String Value
4. Name it: VORTEX
5. Double-click and set value to full path of VORTEX.exe
   Example: C:\\Program Files\\VORTEX\\vortex.exe
6. Close Registry Editor
7. VORTEX will start on next login

NOTE: For production, use METHOD 1 (Startup Folder) as it's simpler and safer.

To remove from startup:
- METHOD 1: Delete the shortcut from Startup folder
- METHOD 2: Delete the registry key created in step 3

═══════════════════════════════════════════════════════════════════════════
        """
        return instructions
    
    def print_startup_instructions(self):
        """Print startup instructions to console."""
        print(self.get_startup_instructions())
    
    def add_to_startup_folder(self, exe_path: str) -> bool:
        """
        Add VORTEX to Windows Startup folder.
        
        Args:
            exe_path: Full path to VORTEX executable
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Get Startup folder path
            startup_folder = os.path.join(
                os.environ.get('APPDATA', ''),
                'Microsoft',
                'Windows',
                'Start Menu',
                'Programs',
                'Startup'
            )
            
            if not os.path.exists(startup_folder):
                self.logger.error(f"Startup folder not found: {startup_folder}")
                return False
            
            # Create shortcut
            shortcut_path = os.path.join(startup_folder, "VORTEX.lnk")
            
            # TODO: Implement shortcut creation using win32com or similar
            # For now, just log the path
            self.logger.info(f"Startup shortcut should be created at: {shortcut_path}")
            self.logger.info(f"Target: {exe_path}")
            self.logger.warning("Automatic shortcut creation not yet implemented")
            self.logger.warning("Please create shortcut manually using instructions above")
            
            return False  # Not implemented yet
        
        except Exception as e:
            self.logger.error(f"Error adding to startup folder: {e}", exc_info=True)
            return False
    
    def add_to_registry(self, exe_path: str) -> bool:
        """
        Add VORTEX to Windows Registry startup.
        
        Args:
            exe_path: Full path to VORTEX executable
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Registry key for current user startup
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            # Open registry key
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE
            )
            
            # Set value
            winreg.SetValueEx(key, "VORTEX", 0, winreg.REG_SZ, exe_path)
            winreg.CloseKey(key)
            
            self.logger.info(f"Added VORTEX to registry startup: {exe_path}")
            return True
        
        except Exception as e:
            self.logger.error(f"Error adding to registry: {e}", exc_info=True)
            return False
    
    def remove_from_registry(self) -> bool:
        """
        Remove VORTEX from Windows Registry startup.
        
        Returns:
            True if successful, False otherwise
        """
        try:
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                key_path,
                0,
                winreg.KEY_SET_VALUE
            )
            
            winreg.DeleteValue(key, "VORTEX")
            winreg.CloseKey(key)
            
            self.logger.info("Removed VORTEX from registry startup")
            return True
        
        except FileNotFoundError:
            self.logger.warning("VORTEX not found in registry startup")
            return False
        except Exception as e:
            self.logger.error(f"Error removing from registry: {e}", exc_info=True)
            return False
    
    def is_in_startup(self) -> bool:
        """
        Check if VORTEX is configured for Windows startup.
        
        Returns:
            True if configured, False otherwise
        """
        try:
            # Check registry
            key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path, 0, winreg.KEY_READ)
            
            try:
                value, _ = winreg.QueryValueEx(key, "VORTEX")
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        
        except Exception:
            return False


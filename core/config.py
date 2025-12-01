"""
Configuration management for VORTEX.
Loads settings from config.json and provides access to configuration values.
"""

import json
import os
import logging
from typing import Dict, Any, Optional


class Config:
    """
    Configuration manager for VORTEX.
    Loads settings from config.json and provides typed access.
    """
    
    def __init__(self, config_path: str = "config.json"):
        """
        Initialize configuration manager.
        
        Args:
            config_path: Path to configuration JSON file
        """
        self.logger = logging.getLogger("VORTEX.Config")
        self.config_path = config_path
        self.config: Dict[str, Any] = {}
        self.load()
    
    def load(self) -> bool:
        """
        Load configuration from JSON file.
        Creates default config if file doesn't exist.
        
        Returns:
            True if loaded successfully, False otherwise
        """
        try:
            if os.path.exists(self.config_path):
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    self.config = json.load(f)
                self.logger.info(f"Configuration loaded from {self.config_path}")
                return True
            else:
                self.logger.warning(f"Config file not found: {self.config_path}, using defaults")
                self._create_default_config()
                return False
        except Exception as e:
            self.logger.error(f"Error loading configuration: {e}", exc_info=True)
            self._create_default_config()
            return False
    
    def _create_default_config(self):
        """Create default configuration."""
        self.config = {
            "wake_word": "vortex",
            "voice_profile_path": "data/voice_profile/",
            "logs_path": "data/logs/",
            "speaker_verification": {
                "similarity_threshold": 0.7,
                "test_mode": True
            },
            "audio": {
                "sample_rate": 16000,
                "chunk_size": 1024,
                "command_recording_duration": 5,
                "wake_word_energy_threshold": 500.0
            },
            "apps": {
                "notepad": "notepad.exe",
                "calculator": "calc.exe",
                "chrome": "chrome.exe",
                "firefox": "firefox.exe",
                "vscode": "code.exe",
                "valorant": r"C:\Riot Games\VALORANT\live\VALORANT.exe"
            },
            "fullscreen_apps": [
                "valorant",
                "game",
                "games",
                "steam"
            ],
            "embedded_apps": [
                "notepad",
                "calculator",
                "chrome",
                "firefox",
                "edge",
                "vscode"
            ]
        }
        self.save()
        self.logger.info("Created default configuration file")
    
    def save(self) -> bool:
        """
        Save current configuration to file.
        
        Returns:
            True if saved successfully, False otherwise
        """
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, indent=2, ensure_ascii=False)
            self.logger.info(f"Configuration saved to {self.config_path}")
            return True
        except Exception as e:
            self.logger.error(f"Error saving configuration: {e}", exc_info=True)
            return False
    
    def get(self, key: str, default: Any = None) -> Any:
        """
        Get configuration value using dot notation (e.g., "audio.sample_rate").
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        keys = key.split('.')
        value = self.config
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return default
        
        return value
    
    def set(self, key: str, value: Any) -> bool:
        """
        Set configuration value using dot notation.
        
        Args:
            key: Configuration key (supports dot notation for nested keys)
            value: Value to set
            
        Returns:
            True if set successfully, False otherwise
        """
        try:
            keys = key.split('.')
            config = self.config
            
            # Navigate to parent dict
            for k in keys[:-1]:
                if k not in config:
                    config[k] = {}
                config = config[k]
            
            # Set value
            config[keys[-1]] = value
            return True
        except Exception as e:
            self.logger.error(f"Error setting configuration: {e}", exc_info=True)
            return False
    
    # Convenience properties
    @property
    def wake_word(self) -> str:
        """Get wake word."""
        return self.get("wake_word", "vortex")
    
    @property
    def voice_profile_path(self) -> str:
        """Get voice profile path."""
        return self.get("voice_profile_path", "data/voice_profile/")
    
    @property
    def logs_path(self) -> str:
        """Get logs path."""
        return self.get("logs_path", "data/logs/")
    
    @property
    def speaker_similarity_threshold(self) -> float:
        """Get speaker verification similarity threshold."""
        return self.get("speaker_verification.similarity_threshold", 0.7)
    
    @property
    def speaker_test_mode(self) -> bool:
        """Get speaker verification test mode."""
        return self.get("speaker_verification.test_mode", True)
    
    @property
    def app_paths(self) -> Dict[str, str]:
        """Get app path mappings."""
        return self.get("apps", {})
    
    @property
    def fullscreen_apps(self) -> list:
        """Get list of fullscreen apps."""
        return self.get("fullscreen_apps", [])
    
    @property
    def embedded_apps(self) -> list:
        """Get list of embedded apps."""
        return self.get("embedded_apps", [])
    
    @property
    def wake_word_energy_threshold(self) -> float:
        """Get wake word energy threshold."""
        return self.get("audio.wake_word_energy_threshold", 500.0)


"""
Audio visualizer widget.
Displays real-time audio waveform/voice bar that responds to microphone input.
"""

from PyQt6.QtWidgets import QWidget
from PyQt6.QtCore import Qt, QTimer, pyqtSignal
from PyQt6.QtGui import QPainter, QColor, QPen
import numpy as np


class AudioVisualizer(QWidget):
    """
    Real-time audio visualizer widget.
    Shows audio activity as a waveform or bar graph.
    """
    
    # Signal to update from audio thread
    energy_update = pyqtSignal(float)
    
    def __init__(self, parent=None):
        """Initialize audio visualizer widget."""
        super().__init__(parent)
        self.setMinimumHeight(80)
        self.setMaximumHeight(120)
        
        # Audio data
        self.current_energy = 0.0
        self.energy_history = []
        self.max_history_length = 100  # Number of samples to display
        
        # Visual settings
        self.bar_count = 20  # Number of bars in the visualizer
        self.max_energy = 1000.0  # Maximum energy for scaling
        self.smoothing_factor = 0.7  # Smoothing factor (0.0 to 1.0)
        
        # Colors
        self.bar_color = QColor(0, 255, 0)  # Neon green
        self.bg_color = QColor(26, 26, 26)  # Dark background
        
        # Connect signal
        self.energy_update.connect(self._update_energy)
        
        # Smoothing timer
        self.smooth_timer = QTimer()
        self.smooth_timer.timeout.connect(self._smooth_update)
        self.smooth_timer.start(16)  # ~60 FPS
        
        # Target energy for smooth animation
        self.target_energy = 0.0
    
    def _update_energy(self, energy: float):
        """
        Update energy level (called from audio thread via signal).
        
        Args:
            energy: Current audio energy level
        """
        self.target_energy = min(energy, self.max_energy)
        
        # Add to history
        self.energy_history.append(self.target_energy)
        if len(self.energy_history) > self.max_history_length:
            self.energy_history.pop(0)
    
    def _smooth_update(self):
        """Smooth animation update."""
        # Smooth interpolation towards target
        self.current_energy = (
            self.smoothing_factor * self.current_energy +
            (1 - self.smoothing_factor) * self.target_energy
        )
        
        # Decay when no new energy
        if self.target_energy < 10:
            self.current_energy *= 0.9  # Decay factor
        
        self.update()  # Trigger repaint
    
    def paintEvent(self, event):
        """Paint the audio visualizer."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), self.bg_color)
        
        width = self.width()
        height = self.height()
        
        # Draw waveform style bars
        bar_width = width / self.bar_count
        spacing = 2
        
        for i in range(self.bar_count):
            # Calculate bar height based on current energy
            # Use different frequencies for visual variety
            if len(self.energy_history) > 0:
                # Use history for wave effect
                history_idx = int((i / self.bar_count) * len(self.energy_history))
                if history_idx < len(self.energy_history):
                    bar_energy = self.energy_history[history_idx]
                else:
                    bar_energy = self.current_energy
            else:
                bar_energy = self.current_energy
            
            # Add some variation based on position (waveform effect)
            wave_factor = 0.5 + 0.5 * np.sin(i * 0.5 + len(self.energy_history) * 0.1)
            bar_energy = bar_energy * wave_factor
            
            # Normalize to 0-1
            normalized = min(bar_energy / self.max_energy, 1.0)
            
            # Calculate bar height (minimum 2px, maximum full height)
            bar_height = max(2, int(normalized * (height - 10)))
            
            # Bar position
            x = i * bar_width + spacing
            y = (height - bar_height) / 2
            
            # Draw bar with gradient effect
            bar_rect = self.rect()
            bar_rect.setLeft(int(x))
            bar_rect.setRight(int(x + bar_width - spacing * 2))
            bar_rect.setTop(int(y))
            bar_rect.setBottom(int(y + bar_height))
            
            # Color intensity based on energy
            intensity = int(255 * normalized)
            bar_color = QColor(
                min(255, 0 + intensity // 2),  # Green component
                min(255, intensity),             # Brightness
                min(255, 0 + intensity // 3)      # Blue tint
            )
            
            painter.fillRect(bar_rect, bar_color)
        
        # Draw center line (optional)
        center_y = height / 2
        pen = QPen(QColor(0, 255, 0, 50), 1, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.drawLine(0, int(center_y), width, int(center_y))
    
    def set_max_energy(self, max_energy: float):
        """
        Set maximum energy for scaling.
        
        Args:
            max_energy: Maximum energy value for normalization
        """
        self.max_energy = max_energy
    
    def reset(self):
        """Reset the visualizer."""
        self.current_energy = 0.0
        self.target_energy = 0.0
        self.energy_history.clear()
        self.update()


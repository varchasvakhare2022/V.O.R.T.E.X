"""
Voice Enrollment Script for VORTEX.
Records multiple voice samples to train the speaker verification model.
"""

import sys
import os
import logging
import time
from pathlib import Path

# Ensure directories exist
os.makedirs('data/logs', exist_ok=True)
os.makedirs('data/voice_profile', exist_ok=True)

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('data/logs/enroll.log', mode='a')
    ]
)

from core.audio_manager import AudioManager
from core.speaker_verification import SpeakerVerifier
from core.config import Config


def record_audio_sample(duration: float = 3.0) -> bytes:
    """
    Record a single audio sample.
    
    Args:
        duration: Recording duration in seconds
        
    Returns:
        Raw audio bytes
    """
    print(f"\n🎤 Recording {duration} seconds of audio...")
    print("   Speak now!")
    
    import pyaudio
    import numpy as np
    
    # Audio configuration
    CHUNK = 1024
    FORMAT = pyaudio.paInt16
    CHANNELS = 1
    RATE = 16000
    
    audio = pyaudio.PyAudio()
    stream = audio.open(
        format=FORMAT,
        channels=CHANNELS,
        rate=RATE,
        input=True,
        frames_per_buffer=CHUNK
    )
    
    audio_samples = []
    num_chunks = int(RATE / CHUNK * duration)
    
    try:
        print("   [Recording...]", end='', flush=True)
        
        for _ in range(num_chunks):
            data = stream.read(CHUNK, exception_on_overflow=False)
            audio_samples.append(data)
            print(".", end='', flush=True)
        
        print(" Done!")
        
        stream.stop_stream()
        stream.close()
        audio.terminate()
        
        # Combine all chunks
        if audio_samples:
            complete_audio = b''.join(audio_samples)
            print(f"✓ Recorded {len(complete_audio)} bytes")
            return complete_audio
        else:
            print("✗ No audio recorded")
            return b''
    
    except Exception as e:
        print(f"\n✗ Error recording: {e}")
        try:
            stream.stop_stream()
            stream.close()
            audio.terminate()
        except:
            pass
        return b''


def enroll_voice(num_samples: int = 5, sample_duration: float = 3.0):
    """
    Enroll owner's voice by recording multiple samples.
    
    Args:
        num_samples: Number of voice samples to record
        sample_duration: Duration of each sample in seconds
    """
    print("=" * 70)
    print("VORTEX - Voice Enrollment")
    print("=" * 70)
    print(f"\nYou will record {num_samples} voice samples.")
    print("Please speak clearly and naturally in each sample.")
    print("You can say anything - your name, a phrase, or just talk.")
    print("\nPress ENTER when ready to start...")
    input()
    
    # Load config
    config = Config()
    
    # Initialize speaker verifier (disable test mode for enrollment)
    verifier = SpeakerVerifier(
        voice_profile_path=config.voice_profile_path,
        test_mode=False  # Disable test mode for real enrollment
    )
    
    # Record samples
    samples = []
    
    for i in range(num_samples):
        print(f"\n{'='*70}")
        print(f"Sample {i+1}/{num_samples}")
        print(f"{'='*70}")
        
        audio = record_audio_sample(sample_duration)
        
        if audio and len(audio) > 0:
            samples.append(audio)
            print(f"✓ Sample {i+1} recorded successfully")
        else:
            print(f"✗ Sample {i+1} failed - will retry")
            i -= 1  # Retry this sample
            continue
        
        # Small delay between samples
        if i < num_samples - 1:
            print("\n⏳ Preparing next sample...")
            time.sleep(1)
    
    # Enroll the voice
    if samples:
        print(f"\n{'='*70}")
        print("Processing voice samples...")
        print(f"{'='*70}")
        
        verifier.enroll_owner(samples)
        
        if verifier.is_enrolled:
            print("\n✓ Voice enrollment successful!")
            print(f"✓ Saved {len(verifier.owner_embeddings)} voice embeddings")
            print(f"✓ Voice profile saved to: {config.voice_profile_path}")
            print("\nYour voice is now enrolled. VORTEX will verify your voice before")
            print("accepting commands. Make sure to set test_mode: false in config.json")
        else:
            print("\n✗ Voice enrollment failed")
            print("Please try again with better audio quality.")
    else:
        print("\n✗ No valid samples recorded. Enrollment failed.")


def main():
    """Main enrollment function."""
    try:
        # Get number of samples from user
        print("\nHow many voice samples would you like to record? (Recommended: 5-10)")
        print("Press ENTER for default (5 samples): ", end='')
        
        user_input = input().strip()
        num_samples = int(user_input) if user_input else 5
        
        if num_samples < 3:
            print("Warning: At least 3 samples recommended for better accuracy.")
            print("Using 3 samples instead.")
            num_samples = 3
        
        # Get sample duration
        print("\nHow long should each sample be? (Recommended: 3 seconds)")
        print("Press ENTER for default (3 seconds): ", end='')
        
        user_input = input().strip()
        sample_duration = float(user_input) if user_input else 3.0
        
        if sample_duration < 1.0:
            print("Warning: Sample duration too short. Using 1 second minimum.")
            sample_duration = 1.0
        
        # Start enrollment
        enroll_voice(num_samples, sample_duration)
        
        print("\n" + "=" * 70)
        print("Enrollment complete!")
        print("=" * 70)
        print("\nNext steps:")
        print("1. Set 'test_mode: false' in config.json")
        print("2. Restart VORTEX")
        print("3. Your voice will now be verified before commands are accepted")
        print("\nPress ENTER to exit...")
        input()
    
    except KeyboardInterrupt:
        print("\n\nEnrollment cancelled by user.")
        sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error during enrollment: {e}")
        logging.error(f"Enrollment error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()


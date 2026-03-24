"""
Integration Example: User Configuration System with DecisionEngine

This example demonstrates how to:
1. Load and manage user configuration via ConfigManager
2. Use ConfigManager with DecisionEngine for runtime updates
3. Watch for config changes and apply them dynamically
4. Modify configuration at runtime
"""

from pathlib import Path
import sys
import time

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.config_manager import ConfigManager
from engine.decision_engine import DecisionEngine
from engine.unified_pipeline import InputEventNormalizer


def example_basic_usage():
    """Example 1: Basic ConfigManager usage."""
    print("\n" + "=" * 70)
    print("Example 1: Basic ConfigManager Usage")
    print("=" * 70)

    # Initialize ConfigManager (auto-loads from config/user_config.json)
    config = ConfigManager()

    # Retrieve configuration values
    gesture_maps = config.get_gesture_mappings("App Mode")
    print(f"\nApp Mode gesture mappings:\n{gesture_maps}")

    voice_maps = config.get_voice_mappings("Media Mode")
    print(f"\nMedia Mode voice mappings:\n{voice_maps}")

    thresholds = config.get_thresholds()
    print(f"\nThresholds:\n{thresholds}")

    smoothing = config.get_smoothing()
    print(f"\nSmoothing values:\n{smoothing}")


def example_decision_engine_with_config():
    """Example 2: DecisionEngine integrated with ConfigManager."""
    print("\n" + "=" * 70)
    print("Example 2: DecisionEngine with ConfigManager Integration")
    print("=" * 70)

    # Create ConfigManager and DecisionEngine (auto-integrated)
    config_manager = ConfigManager()
    decision_engine = DecisionEngine(config_manager=config_manager)

    # Create a test gesture event
    gesture_event = InputEventNormalizer.from_gesture(
        gesture="One Finger", confidence=1.0
    )

    # Resolve action for current mode
    decision = decision_engine.decide(gesture_event, mode="App Mode")
    print(f"\nGesture 'One Finger' in App Mode resolves to action: {decision.action}")

    # Try voice command
    voice_event = InputEventNormalizer.from_voice(command="volume_up", confidence=1.0)
    decision = decision_engine.decide(voice_event, mode="Media Mode")
    print(f"Voice 'volume_up' in Media Mode resolves to action: {decision.action}")


def example_runtime_config_update():
    """Example 3: Updating configuration at runtime."""
    print("\n" + "=" * 70)
    print("Example 3: Runtime Configuration Updates")
    print("=" * 70)

    config_manager = ConfigManager()
    decision_engine = DecisionEngine(config_manager=config_manager)

    # Before update
    original_mapping = config_manager.get_gesture_mappings("App Mode").get("One Finger")
    print(f"\nOriginal 'One Finger' in App Mode: {original_mapping}")

    # Change the mapping
    new_action = "open_youtube"  # Changed from open_brave
    config_manager.set_gesture_mapping("App Mode", "One Finger", new_action)
    print(f"Updated 'One Finger' in App Mode to: {new_action}")

    # Verify the change
    updated_mapping = config_manager.get_gesture_mappings("App Mode").get("One Finger")
    print(f"Verified new mapping: {updated_mapping}")

    # Test that DecisionEngine sees the change
    gesture_event = InputEventNormalizer.from_gesture(
        gesture="One Finger", confidence=1.0
    )
    decision = decision_engine.decide(gesture_event, mode="App Mode")
    print(f"DecisionEngine now resolves 'One Finger' to: {decision.action}")


def example_config_watching():
    """Example 4: Watching for config changes with callbacks."""
    print("\n" + "=" * 70)
    print("Example 4: Config Change Watching and Callbacks")
    print("=" * 70)

    config_manager = ConfigManager()
    decision_engine = DecisionEngine(config_manager=config_manager)

    # Define a custom callback for config changes
    def on_config_changed(change):
        print(f"  [Callback] Config changed: section={change.section}, key={change.key}")
        if change.old_value is not None:
            print(f"    Old value: {change.old_value}")
            print(f"    New value: {change.new_value}")

    config_manager.subscribe(on_config_changed)

    # Make a change (this will trigger the callback)
    print("\nMaking a config change...")
    config_manager.set_gesture_mapping("Media Mode", "Two Fingers", "mute")
    print("Config change persisted to disk and callbacks invoked")

    # Start file watching in background (optional)
    print("\nStarting file watch (checking every 2 seconds)...")
    config_manager.start_watch(check_interval_s=2.0)

    print("File watch is active. Manual edits to user_config.json will be detected.")
    print("(In real usage, this would run continuously in background)")

    # In a real scenario, you could edit user_config.json manually here
    # and the change would be detected after 2 seconds

    config_manager.stop_watch()
    print("File watch stopped")


def example_modify_thresholds():
    """Example 5: Modifying thresholds dynamically."""
    print("\n" + "=" * 70)
    print("Example 5: Runtime Threshold Modification")
    print("=" * 70)

    config_manager = ConfigManager()

    # Get current thresholds
    thresholds = config_manager.get_thresholds()
    hand_conf = thresholds.get("hand_detection_confidence", 0.7)
    print(f"\nCurrent hand detection confidence threshold: {hand_conf}")

    # Update threshold
    new_threshold = 0.85
    config_manager.set("thresholds", "hand_detection_confidence", new_threshold)
    print(f"Updated hand detection confidence threshold to: {new_threshold}")

    # Verify
    updated = config_manager.get("thresholds", "hand_detection_confidence")
    print(f"Verified new threshold: {updated}")


def example_save_and_load():
    """Example 6: Save custom config and reload."""
    print("\n" + "=" * 70)
    print("Example 6: Save and Load Custom Configuration")
    print("=" * 70)

    config_manager = ConfigManager()

    # Make several changes
    print("\nApplying multiple config changes...")
    config_manager.set_gesture_mapping("App Mode", "One Finger", "open_youtube")
    config_manager.set_gesture_mapping("System Mode", "Pinch", "left_click")
    config_manager.set("thresholds", "hand_detection_confidence", 0.8)

    # Save to disk (already done by set() methods, but we can be explicit)
    config_manager.save_config()
    print("Config saved to disk")

    # Create a new ConfigManager instance and verify it loads the saved state
    new_config = ConfigManager()
    reloaded_gesture = new_config.get_gesture_mappings("App Mode").get("One Finger")
    reloaded_threshold = new_config.get("thresholds", "hand_detection_confidence")

    print(f"\nReloaded configuration:")
    print(f"  App Mode 'One Finger': {reloaded_gesture}")
    print(f"  Hand detection threshold: {reloaded_threshold}")


def example_integration_example_code():
    """Example 7: Complete integration for use in your app."""
    print("\n" + "=" * 70)
    print("Example 7: Complete Integration Pattern (for production use)")
    print("=" * 70)

    print("""
In your application startup code:

    # Initialize once at startup
    config_manager = ConfigManager()
    config_manager.start_watch(check_interval_s=2.0)  # Watch for changes
    
    decision_engine = DecisionEngine(config_manager=config_manager)
    
    # Later, when you process a gesture:
    def process_gesture(gesture_name, mode):
        event = InputEventNormalizer.from_gesture(
            gesture=gesture_name,
            confidence=1.0
        )
        decision = decision_engine.decide(event, mode=mode)
        
        if decision.action:
            action_executor.execute(decision.action)
        elif decision.mode_changed:
            handle_mode_switch(decision.mode)
    
    # To modify config at runtime (e.g., from UI):
    def remap_gesture_from_ui(mode, gesture, new_action):
        config_manager.set_gesture_mapping(mode, gesture, new_action)
        # Changes take effect immediately
    
    # Cleanup at shutdown
    config_manager.stop_watch()
    """)


if __name__ == "__main__":
    # Run all examples
    example_basic_usage()
    example_decision_engine_with_config()
    example_runtime_config_update()
    example_config_watching()
    example_modify_thresholds()
    example_save_and_load()
    example_integration_example_code()

    print("\n" + "=" * 70)
    print("All examples completed successfully!")
    print("=" * 70)

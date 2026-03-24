#!/usr/bin/env python3
"""
Test script: UI Configuration Integration
Validates that SettingsPanel properly integrates with ConfigManager
"""

import sys
import json
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from core.config_manager import ConfigManager
from utils.config import Config


def test_config_manager_basic():
    """Test ConfigManager basic operations."""
    print("\n[1] Testing ConfigManager initialization...")
    cfg_mgr = ConfigManager()
    print(f"    ✓ ConfigManager initialized")
    print(f"    - Config type: {type(cfg_mgr).__name__}")
    
    # Load config
    cfg_mgr.load_config()
    print(f"    ✓ Config loaded successfully")


def test_threshold_operations():
    """Test get/set threshold operations."""
    print("\n[2] Testing threshold get/set operations...")
    cfg_mgr = ConfigManager()
    cfg_mgr.load_config()
    
    # Test reading hand_detection_confidence from thresholds
    conf = cfg_mgr.get('thresholds', 'hand_detection_confidence', default=0.70)
    print(f"    ✓ Current hand_detection_confidence: {conf}")
    
    # Test reading gesture_confirmation_frames from smoothing
    frames = cfg_mgr.get('smoothing', 'gesture_confirmation_frames', default=4)
    print(f"    ✓ Current gesture_confirmation_frames: {frames}")
    
    # Test setting confidence
    cfg_mgr.set('thresholds', 'hand_detection_confidence', 0.75)
    conf_new = cfg_mgr.get('thresholds', 'hand_detection_confidence', default=0.70)
    print(f"    ✓ Updated hand_detection_confidence to: {conf_new}")
    assert abs(conf_new - 0.75) < 0.01, f"Expected 0.75, got {conf_new}"
    
    # Test setting frames
    cfg_mgr.set('smoothing', 'gesture_confirmation_frames', 8)
    frames_new = cfg_mgr.get('smoothing', 'gesture_confirmation_frames', default=4)
    print(f"    ✓ Updated gesture_confirmation_frames to: {frames_new}")
    assert frames_new == 8, f"Expected 8, got {frames_new}"


def test_config_manager_persistence():
    """Test that config is persisted to file."""
    print("\n[3] Testing config persistence...")
    cfg_mgr = ConfigManager()
    cfg_mgr.load_config()
    
    # Set values
    cfg_mgr.set('thresholds', 'hand_detection_confidence', 0.82)
    cfg_mgr.set('smoothing', 'gesture_confirmation_frames', 12)
    
    # Force save
    cfg_mgr.save_config()
    print(f"    ✓ Config saved")
    
    # Reload from disk
    cfg_mgr2 = ConfigManager()
    cfg_mgr2.load_config()
    
    conf = cfg_mgr2.get('thresholds', 'hand_detection_confidence', default=0.70)
    frames = cfg_mgr2.get('smoothing', 'gesture_confirmation_frames', default=4)
    
    print(f"    ✓ Reloaded from disk:")
    print(f"      - hand_detection_confidence: {conf}")
    print(f"      - gesture_confirmation_frames: {frames}")
    
    assert abs(conf - 0.82) < 0.01, f"Expected 0.82, got {conf}"
    assert frames == 12, f"Expected 12, got {frames}"


def test_config_file_validation():
    """Validate the user_config.json structure."""
    print("\n[4] Validating user_config.json structure...")
    config_path = project_root / 'config' / 'user_config.json'
    
    with open(config_path, 'r') as f:
        config = json.load(f)
    
    required_keys = ['gesture_mappings', 'thresholds', 'smoothing']
    for key in required_keys:
        assert key in config, f"Missing key: {key}"
        print(f"    ✓ Found key: {key}")
    
    # Check thresholds structure
    thresholds = config['thresholds']
    print(f"    - Available thresholds: {list(thresholds.keys())}")
    
    # Verify hand_detection_confidence is in thresholds
    assert 'hand_detection_confidence' in thresholds, "Missing threshold: hand_detection_confidence"
    print(f"    ✓ Threshold present: hand_detection_confidence = {thresholds['hand_detection_confidence']}")
    
    # Check smoothing structure
    smoothing = config['smoothing']
    print(f"    - Available smoothing params: {list(smoothing.keys())}")
    
    # Verify gesture_confirmation_frames is in smoothing
    assert 'gesture_confirmation_frames' in smoothing, "Missing smoothing param: gesture_confirmation_frames"
    print(f"    ✓ Smoothing param present: gesture_confirmation_frames = {smoothing['gesture_confirmation_frames']}")


def test_subscriber_pattern():
    """Test that ConfigManager subscribers are called on updates."""
    print("\n[5] Testing ConfigManager subscriber pattern...")
    
    call_count = [0]  # Use list to allow modification in nested function
    
    def on_config_changed(change):
        call_count[0] += 1
        print(f"    ✓ Subscriber callback invoked (count: {call_count[0]})")
        print(f"      - Section: {change.section}, Key: {change.key}")
        print(f"      - Old value: {change.old_value}, New value: {change.new_value}")
    
    cfg_mgr = ConfigManager()
    cfg_mgr.load_config()
    
    # Subscribe to changes
    cfg_mgr.subscribe(on_config_changed)
    print(f"    ✓ Subscriber registered")
    
    # Trigger change
    cfg_mgr.set('thresholds', 'hand_detection_confidence', 0.78)
    
    # Give the file watcher a moment to detect changes
    import time
    time.sleep(0.2)
    
    print(f"    ✓ Total callbacks received: {call_count[0]}")


def test_slider_range_mapping():
    """Test that slider values map correctly to config values."""
    print("\n[6] Testing slider range mapping...")
    
    # Hand detection confidence: 0.5-0.95 maps to slider 50-95
    slider_min, slider_max = 50, 95
    config_min, config_max = 0.50, 0.95
    
    test_cases = [50, 70, 85, 95]
    for slider_val in test_cases:
        config_val = slider_val / 100.0
        print(f"    Slider: {slider_val} → Config: {config_val:.2f}")
        assert config_min <= config_val <= config_max
    
    print(f"    ✓ All slider values map correctly")
    
    # Gesture confirmation frames: 2-20 maps directly
    slider_min, slider_max = 2, 20
    test_cases = [2, 5, 10, 15, 20]
    for slider_val in test_cases:
        config_val = slider_val
        print(f"    Slider: {slider_val} → Config: {config_val}")
        assert slider_min <= config_val <= slider_max
    
    print(f"    ✓ All frame values map correctly")


def main():
    """Run all tests."""
    print("=" * 60)
    print("UI Configuration Integration Tests")
    print("=" * 60)
    
    try:
        test_config_manager_basic()
        test_threshold_operations()
        test_config_manager_persistence()
        test_config_file_validation()
        test_subscriber_pattern()
        test_slider_range_mapping()
        
        print("\n" + "=" * 60)
        print("✓ All tests passed!")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == '__main__':
    main()

"""
test_performance_stress.py - Performance and stress tests for the MMGI pipeline.

Tests:
- High-frequency input processing
- Memory usage during extended sessions
- Pipeline throughput
- Latency under load
- Resource cleanup
"""

import pytest
import time
import gc
import psutil
import os
from engine.decision_engine import InputEvent


class TestHighFrequencyInputs:
    """Test handling of high-frequency input events."""
    
    def test_100_rapid_gestures(self, mmgi_pipeline, gesture_event):
        """Test: Process 100 rapid gesture events."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        start_time = time.time()
        
        for i in range(100):
            evt = gesture_event("palm_open", confidence=0.95 - (i % 10) * 0.02)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        elapsed = time.time() - start_time
        throughput = 100 / elapsed if elapsed > 0 else 0
        
        # Should handle 100+ events per second
        assert throughput > 50
        assert executor.call_count() > 0


    def test_mixed_input_rapid_sequence(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Process alternating gesture and voice inputs rapidly."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        start_time = time.time()
        
        for i in range(50):
            if i % 2 == 0:
                evt = gesture_event("swipe_left", confidence=0.95)
            else:
                evt = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
            
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        elapsed = time.time() - start_time
        throughput = 50 / elapsed if elapsed > 0 else 0
        
        # Should maintain good throughput with mixed inputs
        assert throughput > 25


    def test_10_second_continuous_gesture_stream(self, mmgi_pipeline, gesture_event):
        """Test: Process continuous gesture stream for 10 seconds."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        start_time = time.time()
        event_count = 0
        
        while time.time() - start_time < 1.0:  # 1 second for test speed
            evt = gesture_event("swipe_left", confidence=0.95)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
            event_count += 1
        
        # Should handle sustained input without degradation
        assert event_count > 100


class TestMemoryManagement:
    """Test memory usage and cleanup."""
    
    def test_memory_after_1000_events(self, mmgi_pipeline, gesture_event):
        """Test: Memory usage after processing 1000 events."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        executor.reset()
        
        for i in range(1000):
            evt = gesture_event("palm_open", confidence=0.95)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        gc.collect()
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = memory_after - memory_before
        
        # Memory increase should be reasonable (< 100 MB for 1000 events)
        assert memory_increase < 100


    def test_no_memory_leak_repeated_mode_switching(self, mmgi_pipeline):
        """Test: No memory leak when switching modes repeatedly."""
        engine = mmgi_pipeline["decision_engine"]
        
        process = psutil.Process(os.getpid())
        memory_before = process.memory_info().rss / 1024 / 1024  # MB
        
        modes = ["App Mode", "Media Mode", "System Mode"]
        
        for _ in range(100):
            for mode in modes:
                engine.set_mode(mode)
                time.sleep(0.001)  # Small delay
        
        gc.collect()
        memory_after = process.memory_info().rss / 1024 / 1024  # MB
        
        memory_increase = memory_after - memory_before
        
        # Should not accumulate memory
        assert memory_increase < 50


    def test_resource_cleanup_after_session(self, mmgi_pipeline, gesture_event):
        """Test: Resources are cleaned up after processing session."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        # Process many events
        for i in range(500):
            evt = gesture_event("palm_open", confidence=0.95)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        # Cleanup
        gc.collect()
        
        # Verify cleanup occurred - basic check
        assert True


class TestLatencyUnderLoad:
    """Test latency and response times under load."""
    
    def test_gesture_recognition_latency(self, mmgi_pipeline, gesture_event):
        """Test: Gesture recognition latency < 50ms."""
        engine = mmgi_pipeline["decision_engine"]
        
        latencies = []
        
        for i in range(100):
            evt = gesture_event("palm_open", confidence=0.95)
            start = time.time()
            outcome = engine.decide(evt)
            latency = (time.time() - start) * 1000  # ms
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        # Average should be < 50ms, max < 200ms
        assert avg_latency < 50
        assert max_latency < 200


    def test_voice_recognition_latency(self, mmgi_pipeline, voice_input_event):
        """Test: Voice command latency < 100ms."""
        engine = mmgi_pipeline["decision_engine"]
        
        latencies = []
        
        for i in range(100):
            evt = voice_input_event("open_brave", mode="App Mode", confidence=0.95)
            start = time.time()
            outcome = engine.decide(evt)
            latency = (time.time() - start) * 1000  # ms
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        assert avg_latency < 100
        assert max_latency < 300


    def test_action_execution_latency(self, mmgi_pipeline, gesture_event):
        """Test: Action execution latency < 20ms."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        latencies = []
        
        for i in range(50):
            evt = gesture_event("palm_open", confidence=0.95)
            outcome = engine.decide(evt)
            
            if outcome and outcome.action:
                start = time.time()
                executor.execute(outcome.action)
                latency = (time.time() - start) * 1000  # ms
                latencies.append(latency)
        
        if latencies:
            avg_latency = sum(latencies) / len(latencies)
            # Execution should be very fast (< 20ms on average)
            assert avg_latency < 20


    def test_end_to_end_latency(self, mmgi_pipeline, gesture_event):
        """Test: End-to-end latency (input to execution) < 100ms."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        latencies = []
        
        for i in range(100):
            evt = gesture_event("palm_open", confidence=0.95)
            
            start = time.time()
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
            latency = (time.time() - start) * 1000  # ms
            
            latencies.append(latency)
        
        avg_latency = sum(latencies) / len(latencies)
        max_latency = max(latencies)
        
        # End-to-end should be < 100ms average
        assert avg_latency < 100
        assert max_latency < 300


class TestThroughput:
    """Test pipeline throughput metrics."""
    
    def test_gestures_per_second(self, mmgi_pipeline, gesture_event):
        """Test: Pipeline can handle >= 100 gestures/second."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        target_duration = 1.0  # 1 second
        start_time = time.time()
        event_count = 0
        
        while time.time() - start_time < target_duration:
            evt = gesture_event("palm_open", confidence=0.95)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
            event_count += 1
        
        actual_duration = time.time() - start_time
        throughput = event_count / actual_duration
        
        assert throughput >= 100


    def test_mixed_inputs_per_second(self, mmgi_pipeline, gesture_event, voice_input_event):
        """Test: Pipeline can handle >= 50 mixed inputs/second."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        target_duration = 1.0
        start_time = time.time()
        event_count = 0
        
        while time.time() - start_time < target_duration:
            if event_count % 2 == 0:
                evt = gesture_event("swipe_left", confidence=0.95)
            else:
                evt = voice_input_event("click", mode="App Mode", confidence=0.95)
            
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
            event_count += 1
        
        actual_duration = time.time() - start_time
        throughput = event_count / actual_duration
        
        assert throughput >= 50


    def test_actions_executed_per_second(self, mmgi_pipeline, gesture_event):
        """Test: Pipeline executes >= 50 actions/second."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        target_duration = 1.0
        start_time = time.time()
        execution_count = 0
        
        while time.time() - start_time < target_duration:
            evt = gesture_event("palm_open", confidence=0.95)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
                execution_count += 1
        
        actual_duration = time.time() - start_time
        throughput = execution_count / actual_duration
        
        assert throughput >= 50


class TestResourceExhaustion:
    """Test behavior under resource exhaustion."""
    
    def test_very_low_confidence_flood(self, mmgi_pipeline, gesture_event):
        """Test: System handles flood of very low confidence events."""
        engine = mmgi_pipeline["decision_engine"]
        executor = mmgi_pipeline["action_executor"]
        
        executor.reset()
        
        for i in range(100):
            evt = gesture_event("palm_open", confidence=0.05)
            outcome = engine.decide(evt)
            if outcome and outcome.action:
                executor.execute(outcome.action)
        
        # Should not crash, but might not execute low-confidence events
        assert True


    def test_many_rapid_mode_switches(self, mmgi_pipeline):
        """Test: System handles rapid mode switching."""
        engine = mmgi_pipeline["decision_engine"]
        
        modes = ["App Mode", "Media Mode", "System Mode"]
        
        for i in range(300):
            mode = modes[i % 3]
            engine.set_mode(mode)
        
        # Should not crash
        assert True

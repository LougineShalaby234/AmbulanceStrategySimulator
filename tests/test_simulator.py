import os
import pytest
import json
import shutil
import sys
from datetime import datetime, timedelta
sys.path.insert(0, os.path.abspath('..'))

from AmbulanceGame.simulator import (
    parse_time_str,
    read_map,
    load_scenario,
    start_experiment,
    compute_route_linear_interpolation,
    compute_wait_time_statistics,
    apply_decisions,
    move_ambulances_forward,
    all_emergencies_resolved,
    SimulationState,
    Ambulance,
    Emergency,
    Hospital,
    AMBULANCE_STATUS_IDLE,
    AMBULANCE_STATUS_BROKEN,
    AMBULANCE_STATUS_EN_ROUTE_EMERGENCY,
    AMBULANCE_STATUS_AT_EMERGENCY,
    EMERGENCY_STATUS_WAITING_FOR_AMBULANCE_ASSIGNMENT,
    EMERGENCY_STATUS_WAITING_FOR_AMBULANCE,
    EMERGENCY_STATUS_EN_ROUTE_HOSPITAL,
    EMERGENCY_STATUS_FINISHED
)

@pytest.fixture
def clean_output_folder():
    """
    A fixture to clean up 'output/' before each test, so logs from previous runs
    don't interfere with new tests.
    """
    output_dir = "output"
    if os.path.isdir(output_dir):
        shutil.rmtree(output_dir)
    os.makedirs(output_dir, exist_ok=True)
    yield
    # Optional cleanup again afterwards
    # shutil.rmtree(output_dir)

def test_parse_time_str():
    """
    Test that parse_time_str correctly converts a string to a datetime object.
    """
    time_str = "2025-01-27-08-15-00"
    dt = parse_time_str(time_str)
    assert isinstance(dt, datetime)
    assert dt.year == 2025
    assert dt.month == 1
    assert dt.day == 27
    assert dt.hour == 8
    assert dt.minute == 15
    assert dt.second == 0

def test_read_map():
    """
    Test that read_map loads the JSON and creates a SimulationState with ambulances, hospitals, etc.
    """
    # Provide a path to a small, valid map JSON
    map_path = "input/map_montgomeryPa.json"
    state = read_map(map_path)
    assert isinstance(state, SimulationState)
    # Check if we loaded some ambulances
    assert len(state.ambulances) > 0, "No ambulances found in map file"
    # Check at least we have hospitals or stations
    assert len(state.hospitals) >= 1, "No hospitals in map?"
    # Confirm ambulance statuses look correct
    valid_statuses = {AMBULANCE_STATUS_IDLE, AMBULANCE_STATUS_BROKEN}
    for amb in state.ambulances:
        assert amb.status in valid_statuses, f"Ambulance has invalid status: {amb.status}"

def test_load_scenario():
    """
    Test loading a scenario JSON and check that it returns a sorted list of emergencies.
    """
    scenario_path = "input/calls_nyc_simple.json"
    emergencies = load_scenario(scenario_path)
    assert len(emergencies) > 0, "No emergencies found in scenario"
    # Ensure they're in ascending order by timestamp
    for i in range(len(emergencies) - 1):
        assert emergencies[i].timestamp <= emergencies[i+1].timestamp, "Emergencies not sorted by time"

def test_compute_route_linear_interpolation():
    """
    Test the fallback linear interpolation route function for correctness.
    """
    start = (40.0, -75.0)
    end = (40.1, -75.1)
    route = compute_route_linear_interpolation(start, end)
    assert len(route) > 0
    # Each route entry is (minute_offset, (lat, lon))
    first_offset, first_coord = route[0]
    last_offset, last_coord = route[-1]
    assert first_offset == 0
    # Confirm the last coordinate is the end point
    assert pytest.approx(last_coord[0], 0.001) == end[0]
    assert pytest.approx(last_coord[1], 0.001) == end[1]

@pytest.mark.usefixtures("clean_output_folder")
def test_start_experiment():
    """
    Test running a small experiment end-to-end with a known map, scenario, and agent.
    Ensures that logs are created, a final score is returned, etc.
    """
    map_path = "input/map_nyc.json"
    scenario_path = "input/calls_nyc_simple.json"
    # We'll use a simple agent like 'agent_random.py'
    agent_path = "agents/agent_random.py"
    score = start_experiment(map_path, scenario_path, agent_path, experiment_index=0)
    
    # Check we get a numeric score back
    assert isinstance(score, (float, int)), "start_experiment should return a numeric score"
    
    # Check that output logs are created
    scenario_name = os.path.splitext(os.path.basename(scenario_path))[0]
    agent_name = os.path.splitext(os.path.basename(agent_path))[0]
    log_filename = f"output/{scenario_name}__{agent_name}__run0.txt"
    detailed_log_filename = f"output/{scenario_name}__{agent_name}__run0_detailed.txt"
    
    assert os.path.isfile(log_filename), "Simulation did not create event log file"
    assert os.path.isfile(detailed_log_filename), "Simulation did not create detailed log file"

    with open(log_filename, "r") as f:
        log_content = f.read()
        assert "SIMULATION EVENT LOG" in log_content, "Log file missing expected header"

def test_apply_decisions_valid():
    """
    Create a minimal SimulationState with 1 ambulance (idle) and 1 emergency
    that is waiting_for_assignment, then apply a valid decision to send
    that ambulance to the emergency.
    """
    state = SimulationState()
    state.global_clock = datetime.now()

    # Create an ambulance
    amb = Ambulance(amb_id=1, lat=40.0, lng=-75.0, status=AMBULANCE_STATUS_IDLE)
    state.ambulances.append(amb)

    # Create an emergency
    em = Emergency(emerg_id=101, timestamp=datetime.now(), lat=40.001, lng=-75.001, possible_hospitals=[])
    state.emergencies_recent.append(em)

    # The emergency is waiting_for_assignment by default
    assert em.status == EMERGENCY_STATUS_WAITING_FOR_AMBULANCE_ASSIGNMENT

    # Decision: send ambulance #1 to emergency #101
    decisions = [("SendAmbulanceToEmergency", 1, 101)]
    
    class FakeLog:
        def write(self, text):
            pass
    
    event_log = FakeLog()
    result = apply_decisions(decisions, state, event_log)
    # Check that the decision was applied
    assert len(result["applied"]) == 1
    assert len(result["ignored"]) == 0
    # Confirm ambulance is now "on the way to emergency"
    assert amb.status == AMBULANCE_STATUS_EN_ROUTE_EMERGENCY
    # Confirm emergency is now "waiting_for_ambulance"
    assert em.status == EMERGENCY_STATUS_WAITING_FOR_AMBULANCE
    # Check the route was computed
    assert len(amb.remaining_route) > 0

def test_apply_decisions_invalid():
    """
    Test ignoring invalid decisions, e.g. sending a broken ambulance to an emergency
    or referencing a non-existing emergency.
    """
    state = SimulationState()
    state.global_clock = datetime.now()

    # Create an ambulance
    broken_amb = Ambulance(amb_id=1, lat=40.0, lng=-75.0, status=AMBULANCE_STATUS_BROKEN)
    state.ambulances.append(broken_amb)

    # No emergencies in the state
    decisions = [("SendAmbulanceToEmergency", 1, 999)]
    
    class FakeLog:
        def write(self, text):
            pass
    
    event_log = FakeLog()
    result = apply_decisions(decisions, state, event_log)
    # Should be ignored
    assert len(result["applied"]) == 0
    assert len(result["ignored"]) == 1

def test_move_ambulances_forward():
    """
    Test that move_ambulances_forward shifts ambulances along their routes
    or completes them if they've arrived.
    """
    state = SimulationState()
    now = datetime.now()
    state.global_clock = now

    # Ambulance with a short route of 2 minutes
    amb = Ambulance(amb_id=1, lat=40.0, lng=-75.0, status=AMBULANCE_STATUS_EN_ROUTE_EMERGENCY)
    # Route structure: (time_offset_minutes, (lat, lng))
    amb.remaining_route = [
        (1, (40.001, -75.001)),
        (2, (40.002, -75.002))
    ]
    state.ambulances.append(amb)

    class FakeLog:
        def write(self, text):
            pass
    
    event_log = FakeLog()
    move_ambulances_forward(state, event_log)
    # After 1 minute, the ambulance’s route should have one waypoint left
    assert len(amb.remaining_route) == 1, "Should have progressed by one minute in the route"
    # Now the ambulance's position is the next waypoint
    assert amb.position == (40.001, -75.001)
    
    # Move one more minute
    state.global_clock += timedelta(minutes=1)
    move_ambulances_forward(state, event_log)
    # Now route should be empty
    assert len(amb.remaining_route) == 0
    # Position should be final
    assert amb.position == (40.002, -75.002)

def test_all_emergencies_resolved():
    """
    Test that all_emergencies_resolved returns True only if all emergencies are resolved.
    """
    state = SimulationState()
    # 2 emergencies, one resolved, one not resolved
    e1 = Emergency(emerg_id=1, timestamp=datetime.now(), lat=40, lng=-75, possible_hospitals=[])
    e2 = Emergency(emerg_id=2, timestamp=datetime.now(), lat=41, lng=-75, possible_hospitals=[])

    e1.resolved = True
    e2.resolved = False

    state.emergencies_past.append(e1)
    state.emergencies_past.append(e2)

    assert not all_emergencies_resolved(state), "Not all emergencies are resolved"

    # Mark e2 resolved
    e2.resolved = True
    assert all_emergencies_resolved(state), "All emergencies should now be resolved"

def test_compute_wait_time_statistics():
    """
    Test that compute_wait_time_statistics computes average wait times correctly
    for resolved emergencies.
    """
    state = SimulationState()
    now = datetime.now()

    # Create 2 emergencies
    e1 = Emergency(emerg_id=1, timestamp=now, lat=40, lng=-75, possible_hospitals=[])
    e2 = Emergency(emerg_id=2, timestamp=now, lat=41, lng=-75, possible_hospitals=[])
    state.emergencies_past = [e1, e2]

    # Mark them resolved with known times
    e1.resolved = True
    e1.ambulance_arrival_time = now + timedelta(minutes=5)
    e1.hospital_arrival_time = now + timedelta(minutes=20)

    e2.resolved = True
    e2.ambulance_arrival_time = now + timedelta(minutes=3)
    e2.hospital_arrival_time = now + timedelta(minutes=10)

    stats = compute_wait_time_statistics(state)
    # We have 2 resolved
    assert stats["resolved_emergencies"] == 2
    # e1 wait to ambulance = 5, e2 = 3 => average = 4
    assert pytest.approx(stats["avg_ambulance_wait_time"], 0.1) == 4
    # e1 total = 20, e2 total = 10 => average = 15
    assert pytest.approx(stats["avg_total_wait_time"], 0.1) == 15
    assert pytest.approx(stats["median_total_wait_time"], 0.1) == 15  # median of (10, 20) is 15
    assert stats["min_total_wait_time"] == 10
    assert stats["max_total_wait_time"] == 20

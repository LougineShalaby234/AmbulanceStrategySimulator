import random
from agents.base_class import AgentBase

AMBULANCE_STATUS_IDLE = "idle"
AMBULANCE_STATUS_BROKEN = "broken"
AMBULANCE_STATUS_EN_ROUTE_HOSPITAL = "on the way to hospital"
AMBULANCE_STATUS_EN_ROUTE_EMERGENCY = "on the way to emergency"
AMBULANCE_STATUS_RELOCATING = "relocating"

EMERGENCY_STATUS_WAITING_FOR_AMBULANCE_ASSIGNMENT = "waiting_for_assignment"
EMERGENCY_STATUS_WAITING_FOR_AMBULANCE = "waiting_for_ambulance"

class IntelligientReallocateAgent(AgentBase):
    """
    An agent that assigns ambulances and hospitals based on nearest distance using travel time estimation.
    It also relocates ambulances to help maintain coverage.
    """
    def __init__(self, state):
        self.state = state
        self.coverage_threshold_minutes = 10

    def get_actions(self, state):
        decisions = []
        
        def travel_time(source, destination):
            """
            Returns the estimated travel time for an ambulance from 'source' to 'destination'.
            The route is a list of (time_so_far, position) tuples.
            If no route exists, returns float('inf').
            """
            route = self.compute_route(source, destination)
            return route[-1][0] if route else float("inf")
        
        for emergency in state.emergencies_past + state.emergencies_recent:
            if emergency.status == EMERGENCY_STATUS_WAITING_FOR_AMBULANCE_ASSIGNMENT:
                available_ambulances = [
                    amb for amb in state.ambulances
                    if amb.emergency_assigned is None and amb.status in [AMBULANCE_STATUS_IDLE, AMBULANCE_STATUS_RELOCATING]
                ]
                if available_ambulances:
                    nearest_ambulance = min(
                        available_ambulances,
                        key=lambda amb: travel_time(amb.position, emergency.location)
                    )
                    decisions.append(
                        ("SendAmbulanceToEmergency", nearest_ambulance.id, emergency.id)
                    )
        
        for amb in state.ambulances:
            if amb.emergency_assigned is not None and amb.hospital_assigned is None and amb.contains_patient:
                if not amb.remaining_route:
                    associated_emergency = next(
                        (em for em in state.emergencies_past + state.emergencies_recent if em.id == amb.emergency_assigned),
                        None
                    )
                    if associated_emergency:
                        viable_hospitals = [
                            h for h in state.hospitals
                            if h.id in associated_emergency.hospitals and h.free_beds > 0
                        ]
                        if viable_hospitals:
                            chosen_hospital = min(
                                viable_hospitals,
                                key=lambda h: travel_time(amb.position, h.location)
                            )
                        else:
                            # If no hospital has a free bed, go to the nearest hospital regardless.
                            chosen_hospital = min(
                                state.hospitals,
                                key=lambda h: travel_time(amb.position, h.location)
                            ) if state.hospitals else None
                        
                        if chosen_hospital:
                            decisions.append(
                                ("SendAmbulanceToHospital", amb.id, chosen_hospital.id)
                            )
        relocation_destinations = state.hospitals + state.rescue_stations
        for amb in state.ambulances:
            if amb.status == AMBULANCE_STATUS_IDLE and amb.emergency_assigned is None:
                # Chance-based random relocation (if we desired at any pomit , now I have set it to zero ~lougy).
                if random.random() == 0.0 and relocation_destinations:
                    dest = random.choice(relocation_destinations)
                    decisions.append(
                        ("RelocateAmbulance", amb.id, dest.location[0], dest.location[1])
                    )
        if hasattr(state, 'key_zones'):
            uncovered_zones = []
            for zone in state.key_zones:
                times_to_zone = [
                    travel_time(amb.position, zone.location)
                    for amb in state.ambulances
                    if amb.status not in [AMBULANCE_STATUS_BROKEN] 
                ]
                if not times_to_zone:  
                    coverage_time = float('inf')
                else:
                    coverage_time = min(times_to_zone)

                if coverage_time > self.coverage_threshold_minutes:
                    uncovered_zones.append(zone)
            
            if uncovered_zones:
                
                zone_to_cover = uncovered_zones[0]
                
                idle_ambulances = [
                    amb for amb in state.ambulances
                    if amb.status == AMBULANCE_STATUS_IDLE
                    and amb.emergency_assigned is None
                    and amb.status != AMBULANCE_STATUS_BROKEN
                ]
                
                if idle_ambulances:
                    ambulance_to_relocate = min(
                        idle_ambulances,
                        key=lambda amb: travel_time(amb.position, zone_to_cover.location)
                    )
                    
                    if relocation_destinations:
                        best_destination = min(
                            relocation_destinations,
                            key=lambda d: travel_time(zone_to_cover.location, d.location)
                        )
                        decisions.append((
                            "RelocateAmbulance",
                            ambulance_to_relocate.id,
                            best_destination.location[0],
                            best_destination.location[1]
                        ))
        
        # 5) If an ambulance is en route to a hospital that has become full, pick a new hospital.
        for amb in state.ambulances:
            if amb.status == AMBULANCE_STATUS_EN_ROUTE_HOSPITAL:
                current_hospital = next(
                    (h for h in state.hospitals if h.id == amb.hospital_assigned),
                    None
                )
                if current_hospital and current_hospital.free_beds == 0:
                    alternative_hospitals = [
                        h for h in state.hospitals if h.free_beds > 0
                    ]
                    if alternative_hospitals:
                        new_hospital = min(
                            alternative_hospitals,
                            key=lambda h: travel_time(amb.position, h.location)
                        )
                        decisions.append(
                            ("ChangeTargetHospital", amb.id, new_hospital.id)
                        )
        
        return decisions

"""Traffic signal controller and discrete timing plans."""

from enum import Enum
from typing import Dict, Tuple


class SignalPhase(str, Enum):
    """Signal phase states within a two-phase signal cycle."""

    PHASE_A_GREEN = "NS_GREEN"
    PHASE_A_YELLOW = "NS_YELLOW"
    PHASE_A_ALL_RED = "ALL_RED_AFTER_A"
    PHASE_B_GREEN = "EW_GREEN"
    PHASE_B_YELLOW = "EW_YELLOW"
    PHASE_B_ALL_RED = "ALL_RED_AFTER_B"


# Discrete candidate timing plans (green seconds: N/S, E/W)
TIMING_PLANS: Dict[str, Dict[str, int]] = {
    "P1": {"NS": 15, "EW": 45},
    "P2": {"NS": 20, "EW": 40},
    "P3": {"NS": 25, "EW": 35},
    "P4": {"NS": 30, "EW": 30},  # Fixed-time baseline
    "P5": {"NS": 35, "EW": 25},
    "P6": {"NS": 40, "EW": 20},
    "P7": {"NS": 45, "EW": 15},
}


class TrafficSignal:
    """Manages signal phases, clearances, and timing plans for a 4-way intersection."""

    def __init__(
        self,
        initial_plan: str = "P4",
        yellow_duration: int = 3,
        all_red_duration: int = 2,
    ) -> None:
        """Initialize traffic signal controller.

        Args:
            initial_plan: Name of initial timing plan ('P1' - 'P7').
            yellow_duration: Yellow clearance interval in seconds.
            all_red_duration: All-red clearance interval in seconds.
        """
        if initial_plan not in TIMING_PLANS:
            raise ValueError(f"Unknown timing plan '{initial_plan}'. Valid plans: {list(TIMING_PLANS.keys())}")

        self.current_plan_name = initial_plan
        self.next_plan_name = initial_plan
        self.yellow_duration = yellow_duration
        self.all_red_duration = all_red_duration

        self.current_phase = SignalPhase.PHASE_A_GREEN
        self.phase_elapsed_time: float = 0.0
        self.cycle_count: int = 0
        self.just_completed_cycle: bool = False

    @property
    def plan(self) -> Dict[str, int]:
        """Current active timing plan."""
        return TIMING_PLANS[self.current_plan_name]

    def set_next_plan(self, plan_name: str) -> None:
        """Queue the next timing plan to take effect at the start of the next cycle.

        Args:
            plan_name: Candidate plan identifier ('P1' - 'P7').
        """
        if plan_name not in TIMING_PLANS:
            raise ValueError(f"Unknown timing plan '{plan_name}'.")
        self.next_plan_name = plan_name

    def can_proceed(self, approach: str) -> bool:
        """Check if an approach has a green signal to enter the intersection.

        Args:
            approach: 'N', 'S', 'E', or 'W'.
        """
        if approach in ("N", "S"):
            return self.current_phase == SignalPhase.PHASE_A_GREEN
        elif approach in ("E", "W"):
            return self.current_phase == SignalPhase.PHASE_B_GREEN
        return False

    def get_signal_color(self, approach: str) -> str:
        """Return visual signal color ('GREEN', 'YELLOW', 'RED') for an approach.

        Args:
            approach: 'N', 'S', 'E', or 'W'.
        """
        if approach in ("N", "S"):
            if self.current_phase == SignalPhase.PHASE_A_GREEN:
                return "GREEN"
            if self.current_phase == SignalPhase.PHASE_A_YELLOW:
                return "YELLOW"
            return "RED"
        elif approach in ("E", "W"):
            if self.current_phase == SignalPhase.PHASE_B_GREEN:
                return "GREEN"
            if self.current_phase == SignalPhase.PHASE_B_YELLOW:
                return "YELLOW"
            return "RED"
        return "RED"

    def get_feature_encoding(self) -> Tuple[int, float]:
        """Return numerical encoding for ML features (current_phase, elapsed_phase_time).

        Encoding:
            current_phase: 0 = N/S green (Phase A active), 1 = E/W green (Phase B active).
            elapsed_phase_time: seconds elapsed in current principal phase.
        """
        if self.current_phase in (
            SignalPhase.PHASE_A_GREEN,
            SignalPhase.PHASE_A_YELLOW,
            SignalPhase.PHASE_A_ALL_RED,
        ):
            return 0, float(self.phase_elapsed_time)
        else:
            return 1, float(self.phase_elapsed_time)

    def step(self, dt: float = 1.0) -> None:
        """Advance signal state by dt seconds.

        Args:
            dt: Time step duration in seconds.
        """
        self.just_completed_cycle = False
        self.phase_elapsed_time += dt

        if self.current_phase == SignalPhase.PHASE_A_GREEN:
            if self.phase_elapsed_time >= self.plan["NS"]:
                self.current_phase = SignalPhase.PHASE_A_YELLOW
                self.phase_elapsed_time = 0.0

        elif self.current_phase == SignalPhase.PHASE_A_YELLOW:
            if self.phase_elapsed_time >= self.yellow_duration:
                self.current_phase = SignalPhase.PHASE_A_ALL_RED
                self.phase_elapsed_time = 0.0

        elif self.current_phase == SignalPhase.PHASE_A_ALL_RED:
            if self.phase_elapsed_time >= self.all_red_duration:
                self.current_phase = SignalPhase.PHASE_B_GREEN
                self.phase_elapsed_time = 0.0

        elif self.current_phase == SignalPhase.PHASE_B_GREEN:
            if self.phase_elapsed_time >= self.plan["EW"]:
                self.current_phase = SignalPhase.PHASE_B_YELLOW
                self.phase_elapsed_time = 0.0

        elif self.current_phase == SignalPhase.PHASE_B_YELLOW:
            if self.phase_elapsed_time >= self.yellow_duration:
                self.current_phase = SignalPhase.PHASE_B_ALL_RED
                self.phase_elapsed_time = 0.0

        elif self.current_phase == SignalPhase.PHASE_B_ALL_RED:
            if self.phase_elapsed_time >= self.all_red_duration:
                # Cycle complete!
                self.current_phase = SignalPhase.PHASE_A_GREEN
                self.phase_elapsed_time = 0.0
                self.cycle_count += 1
                self.just_completed_cycle = True
                # Apply queued timing plan for next cycle
                self.current_plan_name = self.next_plan_name

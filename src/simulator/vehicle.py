"""Vehicle kinematics and state representation."""

from dataclasses import dataclass
from typing import Optional


@dataclass
class Vehicle:
    """Represents a single vehicle approaching and traversing the intersection."""

    id: int
    approach: str  # 'N', 'S', 'E', or 'W'
    arrival_time: float  # Simulation timestamp when vehicle spawned
    position: float = 0.0  # Distance along approach in meters (0 to stop line + intersection)
    speed: float = 0.0  # Current speed in m/s
    desired_speed: float = 13.89  # Free-flow target speed in m/s (~50 km/h)
    max_accel: float = 2.5  # Max acceleration in m/s^2
    max_decel: float = 4.0  # Comfortable deceleration in m/s^2
    length: float = 4.5  # Vehicle length in meters
    min_gap: float = 2.0  # Minimum bumper-to-bumper gap in meters
    state: str = "approaching"  # 'approaching', 'queued', 'moving', 'exited'
    wait_time: float = 0.0  # Seconds spent stopped (< 0.5 m/s)
    exit_time: Optional[float] = None  # Timestamp when vehicle exited

    @property
    def effective_length(self) -> float:
        """Vehicle physical length plus minimum safe gap."""
        return self.length + self.min_gap

    def update_kinematics(
        self,
        dt: float,
        stop_line_pos: float,
        intersection_end_pos: float,
        can_proceed: bool,
        lead_vehicle: Optional["Vehicle"] = None,
    ) -> None:
        """Update vehicle position and speed for time step dt.

        Args:
            dt: Time step duration in seconds.
            stop_line_pos: Position of the approach stop line in meters.
            intersection_end_pos: Position where intersection ends (cleared).
            can_proceed: True if green or legally permitted to enter intersection.
            lead_vehicle: The vehicle directly ahead on the same lane/approach.
        """
        if self.state == "exited":
            return

        # Determine target stopping barrier ahead
        target_stop_pos = float("inf")

        # 1. Lead vehicle barrier
        if lead_vehicle is not None and lead_vehicle.state != "exited":
            target_stop_pos = lead_vehicle.position - self.effective_length

        # 2. Red signal barrier (only applies if vehicle has not crossed stop line)
        if not can_proceed and self.position <= stop_line_pos:
            target_stop_pos = min(target_stop_pos, stop_line_pos)

        # Distance to effective barrier
        dist_to_barrier = max(0.0, target_stop_pos - self.position)

        # Kinematics: calculate target speed based on barrier
        if dist_to_barrier <= 0.1:
            # Stopped at barrier
            target_speed = 0.0
        else:
            # Safe stopping speed: v^2 = 2 * decel * dist
            safe_speed = (2.0 * self.max_decel * dist_to_barrier) ** 0.5
            target_speed = min(self.desired_speed, safe_speed)

        # Acceleration / deceleration
        if self.speed < target_speed:
            new_speed = min(target_speed, self.speed + self.max_accel * dt)
        else:
            new_speed = max(target_speed, self.speed - self.max_decel * dt)

        # Update position
        avg_speed = (self.speed + new_speed) / 2.0
        new_position = self.position + avg_speed * dt

        # Enforce barrier boundary
        if new_position > target_stop_pos:
            new_position = target_stop_pos
            new_speed = 0.0

        self.speed = max(0.0, new_speed)
        self.position = new_position

        # Update state and waiting time
        if self.position >= intersection_end_pos:
            self.state = "exited"
        elif self.speed < 0.5 and self.position <= stop_line_pos:
            self.state = "queued"
            self.wait_time += dt
        elif self.speed < 0.5 and self.position > stop_line_pos:
            # Stopped inside intersection (rare congestion)
            self.state = "queued"
            self.wait_time += dt
        elif self.position > stop_line_pos:
            self.state = "moving"
        else:
            self.state = "approaching"

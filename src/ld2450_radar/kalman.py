from __future__ import annotations

from dataclasses import dataclass


@dataclass
class _AxisFilter:
    position: float
    velocity: float
    p00: float
    p01: float
    p10: float
    p11: float

    def predict(self, dt_s: float, acceleration_variance: float) -> None:
        self.position += self.velocity * dt_s

        p00 = self.p00 + dt_s * (self.p10 + self.p01) + dt_s**2 * self.p11
        p01 = self.p01 + dt_s * self.p11
        p10 = self.p10 + dt_s * self.p11
        p11 = self.p11

        dt2 = dt_s**2
        dt3 = dt_s**3
        dt4 = dt_s**4
        self.p00 = p00 + acceleration_variance * dt4 / 4.0
        self.p01 = p01 + acceleration_variance * dt3 / 2.0
        self.p10 = p10 + acceleration_variance * dt3 / 2.0
        self.p11 = p11 + acceleration_variance * dt2

    def update(self, measurement: float, measurement_variance: float) -> None:
        innovation = measurement - self.position
        innovation_variance = self.p00 + measurement_variance
        gain_position = self.p00 / innovation_variance
        gain_velocity = self.p10 / innovation_variance

        old_p00 = self.p00
        old_p01 = self.p01
        self.position += gain_position * innovation
        self.velocity += gain_velocity * innovation
        self.p00 -= gain_position * old_p00
        self.p01 -= gain_position * old_p01
        self.p10 -= gain_velocity * old_p00
        self.p11 -= gain_velocity * old_p01

        cross = (self.p01 + self.p10) / 2.0
        self.p01 = cross
        self.p10 = cross


class ConstantVelocityFilter:
    def __init__(
        self,
        x_mm: float,
        y_mm: float,
        position_variance: float,
        velocity_variance: float,
    ) -> None:
        self._x = _AxisFilter(x_mm, 0.0, position_variance, 0.0, 0.0, velocity_variance)
        self._y = _AxisFilter(y_mm, 0.0, position_variance, 0.0, 0.0, velocity_variance)

    @property
    def state(self) -> tuple[float, float, float, float]:
        return self._x.position, self._y.position, self._x.velocity, self._y.velocity

    def predict(self, dt_s: float, acceleration_variance: float) -> None:
        self._x.predict(dt_s, acceleration_variance)
        self._y.predict(dt_s, acceleration_variance)

    def update(self, x_mm: float, y_mm: float, measurement_variance: float) -> None:
        self._x.update(x_mm, measurement_variance)
        self._y.update(y_mm, measurement_variance)
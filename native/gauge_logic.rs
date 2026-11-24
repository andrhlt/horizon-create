//! Java-aligned gauge thresholds and needle state transitions.
//!
//! This module is independent of the Horizon adapter so the typed block
//! entity can reuse the original gauge rules without importing the legacy
//! game module.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum SpeedBand {
    None,
    Slow,
    Medium,
    Fast,
}

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum StressBand {
    None,
    Low,
    Medium,
    High,
    Overstressed,
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct DialState {
    pub previous: f32,
    pub current: f32,
    pub target: f32,
}

pub fn speed_band(rpm: f32) -> SpeedBand {
    match rpm.abs() {
        rpm if rpm >= 100.0 => SpeedBand::Fast,
        rpm if rpm >= 30.0 => SpeedBand::Medium,
        rpm if rpm >= 1.0 => SpeedBand::Slow,
        _ => SpeedBand::None,
    }
}

pub fn is_overstressed(capacity: f32, stress: f32) -> bool {
    stress > capacity
}

pub fn stress_band(rpm: f32, capacity: f32, stress: f32) -> StressBand {
    if rpm == 0.0 {
        return StressBand::None;
    }
    let fraction = stress / if capacity == 0.0 { 1.0 } else { capacity };
    if fraction > 1.0 {
        StressBand::Overstressed
    } else if fraction > 0.75 {
        StressBand::High
    } else if fraction > 0.5 {
        StressBand::Medium
    } else {
        StressBand::Low
    }
}

/// Map absolute RPM to Create's gauge dial position, in dial rotations.
pub fn speed_target(speed: f32) -> f32 {
    let rpm = speed.abs();
    if rpm < 30.0 {
        rpm / 30.0 * 0.45
    } else if rpm < 100.0 {
        0.45 + (rpm - 30.0) / 70.0 * (0.75 - 0.45)
    } else {
        0.75 + (rpm - 100.0) / 156.0 * (1.125 - 0.75)
    }
}

/// Advance one server tick using Create's 1/8 interpolation step.
pub fn advance_dial(state: DialState, target: f32, easing_target: f32) -> DialState {
    let current = state.current + (easing_target - state.current) * 0.125;
    DialState {
        previous: state.current,
        current,
        target,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn speed_bands_match_create_boundaries_and_ignore_direction() {
        assert_eq!(speed_band(0.0), SpeedBand::None);
        assert_eq!(speed_band(0.999), SpeedBand::None);
        assert_eq!(speed_band(-1.0), SpeedBand::Slow);
        assert_eq!(speed_band(29.999), SpeedBand::Slow);
        assert_eq!(speed_band(30.0), SpeedBand::Medium);
        assert_eq!(speed_band(99.999), SpeedBand::Medium);
        assert_eq!(speed_band(-100.0), SpeedBand::Fast);
    }

    #[test]
    fn stress_bands_and_overload_keep_strict_java_comparisons() {
        assert_eq!(stress_band(0.0, 100.0, 120.0), StressBand::None);
        assert_eq!(stress_band(16.0, 100.0, 50.0), StressBand::Low);
        assert_eq!(stress_band(16.0, 100.0, 50.01), StressBand::Medium);
        assert_eq!(stress_band(16.0, 100.0, 75.0), StressBand::Medium);
        assert_eq!(stress_band(16.0, 100.0, 75.01), StressBand::High);
        assert_eq!(stress_band(16.0, 100.0, 100.0), StressBand::High);
        assert_eq!(stress_band(16.0, 100.0, 100.01), StressBand::Overstressed);
        assert!(!is_overstressed(100.0, 100.0));
        assert!(is_overstressed(100.0, 100.01));
    }

    #[test]
    fn speed_dial_uses_piecewise_rpm_scale_and_eases_by_one_eighth() {
        assert_eq!(speed_target(0.0), 0.0);
        assert_eq!(speed_target(30.0), 0.45);
        assert_eq!(speed_target(100.0), 0.75);
        assert_eq!(speed_target(256.0), 1.125);
        assert_eq!(
            advance_dial(
                DialState { previous: 0.0, current: 0.0, target: 0.0 },
                0.45,
                0.45
            ),
            DialState { previous: 0.0, current: 0.05625, target: 0.45 }
        );
    }
}

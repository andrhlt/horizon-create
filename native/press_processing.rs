//! Pure Mechanical Press timing seam.
//!
//! The legacy press owns recipe lookup, basin/world effects and sync. This
//! module owns only the persisted cycle transition so a typed Part can reuse
//! the same speed-dependent behavior without walking the kinetic graph.

pub const CYCLE: i32 = 240;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct Advance {
    pub next: i32,
    pub impact: bool,
}

pub fn advance(ticks: i32, rpm: f32) -> Advance {
    let step = if rpm == 0.0 {
        0
    } else {
        (1.0 + 59.0 * (rpm.abs() / 512.0).min(1.0)) as i32
    };
    let raw = ticks + step;
    Advance {
        next: if ticks < CYCLE / 2 && raw >= CYCLE / 2 {
            CYCLE / 2
        } else {
            raw
        },
        impact: ticks == CYCLE / 2 && rpm != 0.0,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn zero_speed_holds_and_positive_speed_is_clamped_at_impact() {
        assert_eq!(advance(10, 0.0), Advance { next: 10, impact: false });
        assert_eq!(advance(100, 16.0).next, 102);
        assert_eq!(advance(119, 512.0).next, 120);
        assert_eq!(advance(120, 16.0), Advance { next: 122, impact: true });
    }

    #[test]
    fn negative_speed_uses_magnitude_without_overshooting_cycle_boundary() {
        assert_eq!(advance(119, -512.0).next, 120);
        assert_eq!(advance(120, -256.0).impact, true);
    }
}

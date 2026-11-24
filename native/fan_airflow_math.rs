//! Source-aligned fan and Nozzle rules shared by the runtime adapters.
//!
//! World queries, recipe conversion, random rolls, saved timers and entity
//! writes belong to their adapters. This module keeps the small numerical
//! rules identical while those adapters move to the frozen typed API.

pub const FAN_PROCESSING_TIME: i32 = 150;

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct DepotStep {
    pub timer: i32,
    pub complete: bool,
}

/// Create's fan reach, capped at 20 blocks.
pub fn reach(rpm: f32) -> f32 {
    3.0 + 17.0 * (rpm.abs() / 256.0).min(1.0)
}

/// Whether the fan pushes along its facing, accounting for the facing sign.
pub fn pushing(rpm: f32, facing: [i32; 3]) -> bool {
    (rpm > 0.0) == (facing.iter().sum::<i32>() > 0)
}

/// Initial saved Depot timer; Create batches every 16 input items.
pub fn processing_duration(input_count: u32) -> i32 {
    let batches = input_count.max(1).div_ceil(16) as i32;
    FAN_PROCESSING_TIME * batches + 1
}

/// One Create Depot fan-processing state transition.
///
/// A changed item or catalyst starts a fresh recipe. Completion is evaluated
/// when the saved timer is zero, before the timer moves to -1.
pub fn depot_step(
    timer: i32,
    same_item: bool,
    same_catalyst: bool,
    recipe_exists: bool,
    input_count: u32,
) -> DepotStep {
    if !same_item || !same_catalyst {
        return DepotStep {
            timer: if recipe_exists {
                processing_duration(input_count)
            } else {
                -1
            },
            complete: false,
        };
    }
    DepotStep {
        timer: timer - 1,
        complete: timer == 0 && recipe_exists,
    }
}

/// Ease a dropped item toward the fan's airflow, matching the legacy tick.
pub fn fan_item_velocity(
    velocity: [f64; 3],
    airflow: [i32; 3],
    rpm: f32,
    distance_from_fan: f64,
    reach: f32,
) -> [f64; 3] {
    let acceleration =
        f64::from((f64::from(rpm.abs() / 512.0) / (distance_from_fan / f64::from(reach))) as f32);
    std::array::from_fn(|axis| {
        velocity[axis]
            + (f64::from(airflow[axis]) * acceleration - velocity[axis]).clamp(-5.0, 5.0) / 8.0
    })
}

/// Return the velocity change for a Nozzle item or living entity.
///
/// `denominator` is 128 for dropped items and 32 for mobs. Pulling does not
/// affect an entity inside Create's 1.5-block near-field exclusion.
pub fn nozzle_impulse(
    center: [f64; 3],
    position: [f64; 3],
    reach: f64,
    pushing: bool,
    denominator: f64,
    crouching: bool,
) -> Option<[f64; 3]> {
    if crouching {
        return None;
    }
    let diff: [f64; 3] = std::array::from_fn(|axis| position[axis] - center[axis]);
    let distance = diff.iter().map(|value| value * value).sum::<f64>().sqrt();
    if distance > reach || (!pushing && distance < 1.5) {
        return None;
    }
    if distance < 1e-4 {
        return Some([0.0; 3]);
    }
    let sign = if pushing { 1.0 } else { -1.0 };
    let scale = sign * (reach - distance) / denominator / distance;
    Some(diff.map(|value| value * scale))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn fan_range_and_direction_keep_signed_rpm_boundaries() {
        assert_eq!(reach(0.0), 3.0);
        assert_eq!(reach(16.0), 4.0625);
        assert_eq!(reach(256.0), 20.0);
        assert_eq!(reach(-512.0), 20.0);
        assert!(pushing(16.0, [1, 0, 0]));
        assert!(!pushing(-16.0, [1, 0, 0]));
        assert!(pushing(-16.0, [-1, 0, 0]));
    }

    #[test]
    fn depot_processing_batches_and_finishes_on_zero() {
        assert_eq!(processing_duration(1), 151);
        assert_eq!(processing_duration(16), 151);
        assert_eq!(processing_duration(17), 301);
        assert_eq!(
            depot_step(0, true, true, true, 1),
            DepotStep {
                timer: -1,
                complete: true
            }
        );
        assert_eq!(
            depot_step(0, true, true, false, 1),
            DepotStep {
                timer: -1,
                complete: false
            }
        );
        assert_eq!(
            depot_step(0, false, true, true, 17),
            DepotStep {
                timer: 301,
                complete: false
            }
        );
    }

    #[test]
    fn fan_item_velocity_eases_with_clamped_acceleration() {
        assert_eq!(
            fan_item_velocity([0.0; 3], [1, 0, 0], 256.0, 10.0, 20.0),
            [0.125, 0.0, 0.0]
        );
        assert_eq!(
            fan_item_velocity([10.0, 0.0, 0.0], [1, 0, 0], 512.0, 1.0, 20.0),
            [10.625, 0.0, 0.0]
        );
    }

    #[test]
    fn nozzle_push_pull_range_and_crouch_rules_match_create() {
        let center = [0.0; 3];
        assert_eq!(
            nozzle_impulse(center, [2.0, 0.0, 0.0], 20.0, true, 128.0, false),
            Some([0.140625, 0.0, 0.0])
        );
        assert_eq!(
            nozzle_impulse(center, [1.0, 0.0, 0.0], 20.0, false, 128.0, false),
            None
        );
        assert_eq!(
            nozzle_impulse(center, [2.0, 0.0, 0.0], 20.0, false, 128.0, false),
            Some([-0.140625, 0.0, 0.0])
        );
        assert_eq!(
            nozzle_impulse(center, [2.0, 0.0, 0.0], 20.0, true, 32.0, true),
            None
        );
        assert_eq!(
            nozzle_impulse(center, [0.0; 3], 20.0, true, 32.0, false),
            Some([0.0; 3])
        );
        assert_eq!(
            nozzle_impulse(center, [2.0, 0.0, 0.0], 20.0, true, 32.0, false),
            Some([0.5625, 0.0, 0.0])
        );
        assert_eq!(
            nozzle_impulse(center, [20.0, 0.0, 0.0], 20.0, true, 128.0, false),
            Some([0.0, 0.0, 0.0])
        );
    }
}

//! Java-derived source output rules used by the frozen-SDK kinetic adapter.
//!
//! This module deliberately owns no graph traversal or Horizon host access.
//! The APP-2173 adapter supplies the measured block orientation and saved
//! source state, then consumes these outputs when resolving its network.

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Output {
    pub rpm: f32,
    pub capacity: f32,
}

/// Hand Crank output: 32 RPM while its ten-tick use timer is active, with
/// sign determined by the clicked direction and the mounted face.
pub fn hand_crank(face: [i32; 3], in_use: i32, backwards: bool) -> Output {
    let active = in_use > 0;
    let negative_face = face.iter().sum::<i32>() < 0;
    let negative = backwards ^ negative_face;
    Output {
        rpm: if active {
            if negative { -32.0 } else { 32.0 }
        } else {
            0.0
        },
        capacity: 8.0,
    }
}

/// Copper and dyed Valve Handle output. `configured` is the saved signed
/// rotation amount; the source rotates at the original fixed 32 RPM.
pub fn valve_handle(face: [i32; 3], in_use: i32, backwards: bool, configured: i32) -> Output {
    let negative_face = face.iter().sum::<i32>() < 0;
    let negative = backwards ^ (configured < 0) ^ negative_face;
    Output {
        rpm: if in_use > 0 {
            if negative { -32.0 } else { 32.0 }
        } else {
            0.0
        },
        capacity: 8.0,
    }
}

/// A recolored handle has no generator capacity. Java lets the old stroke
/// continue only when its rear link still connects to a driving shaft.
pub fn recolored_valve_handle(rear_linked: bool, saved_rpm: f32) -> Output {
    Output {
        rpm: if rear_linked { saved_rpm } else { 0.0 },
        capacity: 0.0,
    }
}

/// Small and large Water Wheel output follows the sign of FlowScore. A zero
/// score stops the source but retains its family capacity, matching the
/// existing `generated_source` path.
pub fn water_wheel(flow_score: i32, large: bool) -> Output {
    if large {
        Output {
            rpm: flow_score.signum() as f32 * 4.0,
            capacity: 512.0,
        }
    } else {
        Output {
            rpm: flow_score.signum() as f32 * 8.0,
            capacity: 32.0,
        }
    }
}

/// Boiler efficiency from the saved/sample state. Tank size is measured in
/// blocks, supply in mB/tick, and heat follows the original passive/active
/// burner rules.
pub fn boiler_efficiency(
    engines: i32,
    tank_blocks: i32,
    supply: f32,
    active_heat: i32,
    passive_heat: bool,
) -> f32 {
    let size = (tank_blocks / 4).min(18);
    let water = ((supply.ceil() as i32) / 10).min(18);
    if engines <= 0 || size <= 0 || water <= 0 {
        0.0
    } else if passive_heat {
        0.125 / engines as f32
    } else {
        (active_heat.min(water).min(size) as f32 / engines as f32).min(1.0)
    }
}

/// Powered Shaft output for a resolved boiler efficiency and source rotation.
pub fn steam_engine(power: f32, rotation: i32) -> Output {
    if power <= 0.0 || rotation == 0 {
        return Output::default();
    }
    let multiplier = if power >= 1.0 {
        4.0
    } else {
        1.0 + (power * 4.0).floor().min(2.0)
    };
    let rpm = rotation as f32 * 16.0 * multiplier;
    Output {
        rpm,
        capacity: power * 16_384.0 / rpm.abs(),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn crank_and_handle_direction_respect_face_and_saved_direction() {
        assert_eq!(hand_crank([1, 0, 0], 1, false).rpm, 32.0);
        assert_eq!(hand_crank([-1, 0, 0], 1, false).rpm, -32.0);
        assert_eq!(hand_crank([1, 0, 0], 0, true).rpm, 0.0);
        assert_eq!(valve_handle([0, -1, 0], 2, false, 45).rpm, -32.0);
        assert_eq!(valve_handle([0, 1, 0], 2, true, -45).rpm, 32.0);
        assert_eq!(valve_handle([0, 1, 0], 0, false, 45).rpm, 0.0);
        assert_eq!(recolored_valve_handle(true, -32.0).rpm, -32.0);
        assert_eq!(recolored_valve_handle(false, -32.0), Output::default());
    }

    #[test]
    fn water_wheel_score_changes_sign_without_changing_family_capacity() {
        assert_eq!(
            water_wheel(1, false),
            Output {
                rpm: 8.0,
                capacity: 32.0
            }
        );
        assert_eq!(
            water_wheel(-3, false),
            Output {
                rpm: -8.0,
                capacity: 32.0
            }
        );
        assert_eq!(
            water_wheel(0, true),
            Output {
                rpm: 0.0,
                capacity: 512.0
            }
        );
        assert_eq!(
            water_wheel(-1, true),
            Output {
                rpm: -4.0,
                capacity: 512.0
            }
        );
    }

    #[test]
    fn boiler_efficiency_observes_engine_size_water_and_heat_boundaries() {
        assert_eq!(boiler_efficiency(0, 4, 10.0, 1, false), 0.0);
        assert_eq!(boiler_efficiency(1, 3, 100.0, 1, false), 0.0);
        assert_eq!(boiler_efficiency(1, 4, 9.0, 1, false), 0.0);
        assert_eq!(boiler_efficiency(1, 4, 10.0, 1, false), 1.0);
        assert_eq!(boiler_efficiency(2, 8, 20.0, 1, false), 0.5);
        assert_eq!(boiler_efficiency(2, 8, 20.0, 0, true), 0.0625);
    }

    #[test]
    fn steam_shaft_output_preserves_zero_and_capacity_rules() {
        assert_eq!(steam_engine(0.0, 1), Output::default());
        assert_eq!(steam_engine(0.5, 1).rpm, 48.0);
        assert_eq!(steam_engine(1.0, -1).rpm, -64.0);
        assert_eq!(steam_engine(0.5, 1).capacity, 0.5 * 16_384.0 / 48.0);
    }
}

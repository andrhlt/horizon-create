//! The selected motor/shaft/cogwheel subset of the legacy kinetic edge rules.
//!
//! This module has no Horizon host access. The caller supplies block identity,
//! orientation, positions and motor setting, which keeps the SDK adapter thin.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Node {
    Motor { facing: [i32; 3] },
    Shaft { axis: usize },
    Cogwheel { axis: usize, large: bool },
    Millstone,
    Flywheel { axis: usize },
    Gearbox { axis: usize },
    Clutch { axis: usize, powered: bool },
    Gearshift { axis: usize, powered: bool },
}

impl Node {
    fn shaft(self, face: [i32; 3]) -> bool {
        match self {
            Self::Motor { facing } => face == facing,
            Self::Shaft { axis }
            | Self::Cogwheel { axis, .. }
            | Self::Flywheel { axis }
            | Self::Clutch { axis, .. }
            | Self::Gearshift { axis, .. } => face[axis] != 0,
            Self::Gearbox { axis } => face[axis] == 0,
            Self::Millstone => face == [0, -1, 0],
        }
    }

    fn gear(self) -> Option<(usize, bool)> {
        match self {
            Self::Cogwheel { axis, large } => Some((axis, large)),
            Self::Millstone => Some((1, false)),
            _ => None,
        }
    }

    pub fn neighbors(self) -> Vec<[i32; 3]> {
        const DIRECTIONS: [[i32; 3]; 6] = [
            [-1, 0, 0],
            [1, 0, 0],
            [0, -1, 0],
            [0, 1, 0],
            [0, 0, -1],
            [0, 0, 1],
        ];
        const DIAGONALS: [[i32; 3]; 12] = [
            [-1, -1, 0],
            [-1, 1, 0],
            [1, -1, 0],
            [1, 1, 0],
            [-1, 0, -1],
            [-1, 0, 1],
            [1, 0, -1],
            [1, 0, 1],
            [0, -1, -1],
            [0, -1, 1],
            [0, 1, -1],
            [0, 1, 1],
        ];
        let mut result = DIRECTIONS.to_vec();
        if matches!(self, Self::Cogwheel { .. } | Self::Millstone) {
            result.extend(DIAGONALS);
        }
        result
    }

    /// The existing `Kinetic::ratio_to` rules for this three-kind slice.
    /// Ratios are divisors, matching the legacy graph walk's `ratio / edge`.
    pub fn ratio_to(self, other: Self, offset: [i32; 3]) -> Option<f32> {
        let adjacent = offset.iter().map(|v| v.abs()).sum::<i32>() == 1;
        if adjacent && self.shaft(offset) && other.shaft(offset.map(|v| -v)) {
            return Some(1.0);
        }
        let (Some((axis, large)), Some((other_axis, other_large))) = (self.gear(), other.gear())
        else {
            return None;
        };
        match (large, other_large) {
            (true, true)
                if !adjacent
                    && axis != other_axis
                    && offset[axis] != 0
                    && offset[other_axis] != 0 =>
            {
                Some(if offset[axis].signum() == offset[other_axis].signum() {
                    1.0
                } else {
                    -1.0
                })
            }
            (true, false) | (false, true)
                if !adjacent && axis == other_axis && offset[axis] == 0 =>
            {
                Some(if large { -2.0 } else { -0.5 })
            }
            (false, false) if adjacent && axis == other_axis && offset[axis] == 0 => Some(-1.0),
            _ => None,
        }
    }

    /// Direction-dependent transmission modifier from the incoming face to
    /// an outgoing neighbor. `entered` points from this node back to its
    /// predecessor, matching Create's `getRotationSpeedModifier` convention.
    pub fn direction_ratio(self, entered: [i32; 3], outgoing: [i32; 3]) -> f32 {
        if entered == [0; 3] || entered == outgoing {
            return 1.0;
        }
        match self {
            Self::Clutch { powered: true, .. } => 0.0,
            Self::Gearshift { powered: true, .. } => -1.0,
            Self::Gearbox { .. } => gearbox_multiplier(entered, outgoing),
            _ => 1.0,
        }
    }
}

pub fn gearbox_multiplier(from: [i32; 3], to: [i32; 3]) -> f32 {
    if from == [0; 3] || from == to {
        return 1.0;
    }
    if from == to.map(|component| -component) || from.iter().sum::<i32>() == to.iter().sum::<i32>()
    {
        -1.0
    } else {
        1.0
    }
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Source {
    pub speed: f32,
    pub capacity: f32,
}

#[derive(Clone, Copy, Debug, Default, PartialEq)]
pub struct Network {
    pub rpm: f32,
    pub capacity: f32,
    pub stress: f32,
    pub source_conflict: bool,
}

impl Network {
    pub fn speed(self) -> f32 {
        effective_speed(self.rpm, self.capacity, self.stress)
    }
}

pub fn effective_speed(rpm: f32, capacity: f32, stress: f32) -> f32 {
    if stress > capacity { 0.0 } else { rpm }
}

/// Creative Motor's retained generator capacity is 16,384 units per RPM.
pub fn motor_source(speed: f32) -> Source {
    Source {
        speed,
        capacity: speed.abs() * 16_384.0,
    }
}

/// Preserve the legacy source arbitration, capacity sum, and stress formula
/// for the supported motor/shaft/cogwheel/Millstone subset.
pub fn resolve_network(sources: &[Source], impact_per_rpm: f32) -> Network {
    let mut network = Network::default();
    let mut positive = false;
    let mut negative = false;
    for source in sources.iter().filter(|source| source.speed != 0.0) {
        network.capacity += source.capacity;
        if source.speed.is_sign_positive() {
            positive = true;
        } else {
            negative = true;
        }
        if source.speed.abs() > network.rpm.abs() {
            network.rpm = source.speed;
        }
    }
    network.stress = impact_per_rpm * network.rpm.abs();
    network.source_conflict = positive && negative;
    network
}

pub fn motor_speed(facing: [i32; 3], scroll_value: i32) -> f32 {
    (facing.iter().sum::<i32>() * scroll_value.clamp(-256, 256)) as f32
}

/// Convert an axis property using the same x/y/z ordering as `machines.rs`.
pub fn axis_index(axis: &str) -> Option<usize> {
    match axis {
        "x" => Some(0),
        "y" => Some(1),
        "z" => Some(2),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn motor_shaft_and_cogwheel_ratios_match_the_existing_gear_trace() {
        let motor = Node::Motor { facing: [1, 0, 0] };
        let shaft = Node::Shaft { axis: 0 };
        let large = Node::Cogwheel {
            axis: 0,
            large: true,
        };
        let small = Node::Cogwheel {
            axis: 0,
            large: false,
        };
        assert_eq!(motor.ratio_to(shaft, [1, 0, 0]), Some(1.0));
        assert_eq!(shaft.ratio_to(large, [1, 0, 0]), Some(1.0));
        assert_eq!(large.ratio_to(small, [0, 1, 1]), Some(-2.0));
        assert_eq!(small.ratio_to(large, [0, -1, -1]), Some(-0.5));
        assert_eq!(
            Node::Cogwheel {
                axis: 2,
                large: true
            }
            .ratio_to(
                Node::Cogwheel {
                    axis: 0,
                    large: true
                },
                [1, 0, -1]
            ),
            Some(-1.0)
        );
        let millstone = Node::Millstone;
        assert_eq!(
            millstone.ratio_to(Node::Shaft { axis: 1 }, [0, -1, 0]),
            Some(1.0)
        );
        assert_eq!(
            Node::Cogwheel {
                axis: 1,
                large: true
            }
            .ratio_to(millstone, [1, 0, 1]),
            Some(-2.0)
        );
    }

    #[test]
    fn source_capacity_stress_and_overload_use_legacy_boundaries() {
        let source = motor_source(16.0);
        assert_eq!(source.capacity, 262_144.0);
        let exact = resolve_network(
            &[Source {
                capacity: 64.0,
                ..source
            }],
            4.0,
        );
        assert_eq!(exact.stress, exact.capacity);
        assert_eq!(exact.speed(), 16.0);
        let overloaded = resolve_network(
            &[Source {
                capacity: 63.0,
                ..source
            }],
            4.0,
        );
        assert!(overloaded.stress > overloaded.capacity);
        assert_eq!(overloaded.speed(), 0.0);
        assert_eq!(effective_speed(16.0, 63.0, 64.0), 0.0);
        assert_eq!(effective_speed(16.0, 64.0, 64.0), 16.0);
    }

    #[test]
    fn source_capacity_sums_and_opposing_directions_conflict() {
        let network = resolve_network(&[motor_source(16.0), motor_source(-16.0)], 0.0);
        assert_eq!(network.capacity, 524_288.0);
        assert_eq!(network.rpm.abs(), 16.0);
        assert!(network.source_conflict);
    }

    #[test]
    fn signed_motor_settings_are_clamped_and_keep_facing_sign() {
        assert_eq!(motor_speed([1, 0, 0], 64), 64.0);
        assert_eq!(motor_speed([-1, 0, 0], 64), -64.0);
        assert_eq!(motor_speed([1, 0, 0], -24), -24.0);
        assert_eq!(motor_speed([1, 0, 0], 999), 256.0);
    }

    #[test]
    fn transmissions_apply_powered_clutch_and_gearshift_only_across_the_output() {
        let input = [1, 0, 0];
        let output = [0, 0, 1];
        assert_eq!(
            Node::Clutch {
                axis: 0,
                powered: true
            }
            .direction_ratio(input, output),
            0.0
        );
        assert_eq!(
            Node::Gearshift {
                axis: 0,
                powered: true
            }
            .direction_ratio(input, output),
            -1.0
        );
        assert_eq!(
            Node::Gearshift {
                axis: 0,
                powered: true
            }
            .direction_ratio(input, input),
            1.0
        );
        assert_eq!(gearbox_multiplier([1, 0, 0], [0, 0, 1]), -1.0);
        assert_eq!(gearbox_multiplier([1, 0, 0], [0, 0, -1]), 1.0);
    }

    #[test]
    fn gearbox_connects_matching_perpendicular_shafts() {
        let gearbox = Node::Gearbox { axis: 1 };
        assert_eq!(
            gearbox.ratio_to(Node::Shaft { axis: 0 }, [1, 0, 0]),
            Some(1.0)
        );
        assert_eq!(gearbox.ratio_to(Node::Shaft { axis: 1 }, [0, 1, 0]), None);
        assert_eq!(
            Node::Clutch {
                axis: 2,
                powered: false
            }
            .ratio_to(Node::Flywheel { axis: 2 }, [0, 0, 1]),
            Some(1.0)
        );
    }
}

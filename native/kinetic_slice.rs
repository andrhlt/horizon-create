//! The selected motor/shaft/cogwheel subset of the legacy kinetic edge rules.
//!
//! This module has no Horizon host access. The caller supplies block identity,
//! orientation, positions and motor setting, which keeps the SDK adapter thin.

#[derive(Clone, Copy, Debug, PartialEq)]
pub enum Node {
    Motor {
        facing: [i32; 3],
    },
    Shaft {
        axis: usize,
    },
    Cogwheel {
        axis: usize,
        large: bool,
    },
    CrushingWheel {
        axis: usize,
    },
    EncasedCogwheel {
        axis: usize,
        large: bool,
        top_shaft: bool,
        bottom_shaft: bool,
    },
    Millstone,
    MechanicalPress,
    Mixer,
    Fan {
        axis: usize,
    },
    Gauge {
        axis: usize,
    },
    Turntable,
    Flywheel {
        axis: usize,
    },
    Gearbox {
        axis: usize,
    },
    Clutch {
        axis: usize,
        powered: bool,
    },
    Gearshift {
        axis: usize,
        powered: bool,
    },
    SequencedGearshift {
        axis: usize,
        input_side: i32,
        modifier: i32,
    },
    RotationSpeedController {
        axis: usize,
        target: i32,
    },
    ChainDrive {
        shaft_axis: usize,
        link_axis: usize,
        part: i8,
        modifier: f32,
    },
}

impl Node {
    fn shaft(self, face: [i32; 3]) -> bool {
        match self {
            Self::Motor { facing } => face == facing,
            Self::Shaft { axis }
            | Self::Cogwheel { axis, .. }
            | Self::CrushingWheel { axis }
            | Self::Flywheel { axis }
            | Self::Clutch { axis, .. }
            | Self::Gearshift { axis, .. }
            | Self::SequencedGearshift { axis, .. }
            | Self::RotationSpeedController { axis, .. } => face[axis] != 0,
            Self::Fan { axis } => face[axis] != 0,
            Self::EncasedCogwheel {
                axis,
                top_shaft,
                bottom_shaft,
                ..
            } => face[axis] > 0 && top_shaft || face[axis] < 0 && bottom_shaft,
            Self::ChainDrive { shaft_axis, .. } => face[shaft_axis] != 0,
            Self::Gearbox { axis } => face[axis] == 0,
            Self::Millstone => face == [0, -1, 0],
            Self::MechanicalPress => face == [0, 1, 0],
            Self::Mixer => face[1] != 0,
            Self::Gauge { axis } => face[axis] != 0,
            Self::Turntable => face == [0, -1, 0],
        }
    }

    fn gear(self) -> Option<(usize, bool)> {
        match self {
            Self::Cogwheel { axis, large } => Some((axis, large)),
            Self::EncasedCogwheel { axis, large, .. } => Some((axis, large)),
            Self::Millstone | Self::Mixer => Some((1, false)),
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
        if matches!(
            self,
            Self::Cogwheel { .. }
                | Self::EncasedCogwheel { .. }
                | Self::CrushingWheel { .. }
                | Self::Millstone
                | Self::Mixer
                | Self::Turntable
        ) {
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
        if let (
            Self::ChainDrive {
                link_axis,
                part,
                modifier,
                ..
            },
            Self::ChainDrive {
                link_axis: other_link_axis,
                part: other_part,
                modifier: other_modifier,
                ..
            },
        ) = (self, other)
            && adjacent
            && link_axis == other_link_axis
            && offset[link_axis] != 0
            && part != 2
            && other_part != 2
            && (part == 0 || i32::from(part) == offset[link_axis])
            && (other_part == 0 || i32::from(other_part) == -offset[link_axis])
        {
            return Some(modifier / other_modifier);
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
            Self::SequencedGearshift { axis, input_side, modifier }
                if axis < 3 && entered[axis] != 0 =>
            {
                if modifier == 0 {
                    0.0
                } else if entered[axis] == input_side {
                    1.0 / modifier as f32
                } else {
                    modifier as f32
                }
            }
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

pub fn inconsistent_loop_ratio(expected: f32, existing: f32) -> bool {
    (expected - existing).abs() > 1e-5
}

/// Ratio from a motor's root speed to a speed controller's configured output.
pub fn controller_output_ratio(root_speed: f32, target: i32) -> Option<f32> {
    (root_speed != 0.0 && target != 0).then_some(root_speed / target as f32)
}

pub fn controller_links_large_cog(controller: Node, cog: Node, offset: [i32; 3]) -> bool {
    let Node::RotationSpeedController { axis, .. } = controller else {
        return false;
    };
    if offset != [0, 1, 0] {
        return false;
    }
    cog.gear().is_some_and(|(gear_axis, large)| large && gear_axis != 1 && gear_axis != axis)
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
    pub topology_conflict: bool,
}

impl Network {
    pub fn speed(self) -> f32 {
        if self.source_conflict || self.topology_conflict {
            0.0
        } else {
            effective_speed(self.rpm, self.capacity, self.stress)
        }
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
    fn gauges_and_turntable_join_the_kinetic_shaft_and_turntable_adds_stress() {
        let shaft = Node::Shaft { axis: 1 };
        let gauge = Node::Gauge { axis: 1 };
        let table = Node::Turntable;
        assert_eq!(shaft.ratio_to(gauge, [0, 1, 0]), Some(1.0));
        assert_eq!(table.ratio_to(shaft, [0, -1, 0]), Some(1.0));
        assert_eq!(table.ratio_to(shaft, [0, 1, 0]), None);
        assert_eq!(resolve_network(&[motor_source(16.0)], 4.0).stress, 64.0);
    }

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
        assert_eq!(network.speed(), 0.0);
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

    #[test]
    fn chain_links_require_matching_axis_and_open_endpoints() {
        let start = Node::ChainDrive {
            shaft_axis: 0,
            link_axis: 1,
            part: 1,
            modifier: 1.0,
        };
        let end = Node::ChainDrive {
            shaft_axis: 0,
            link_axis: 1,
            part: -1,
            modifier: 1.5,
        };
        assert_eq!(start.ratio_to(end, [0, 1, 0]), Some(1.0 / 1.5));
        assert_eq!(start.ratio_to(end, [0, -1, 0]), None);
        assert_eq!(
            start.ratio_to(
                Node::ChainDrive {
                    shaft_axis: 0,
                    link_axis: 2,
                    part: -1,
                    modifier: 1.5,
                },
                [0, 1, 0]
            ),
            None
        );
    }

    #[test]
    fn encased_cogwheel_shaft_connections_follow_open_halves() {
        let cog = Node::EncasedCogwheel {
            axis: 1,
            large: true,
            top_shaft: false,
            bottom_shaft: true,
        };
        assert!(!cog.shaft([0, 1, 0]));
        assert!(cog.shaft([0, -1, 0]));
        assert_eq!(
            cog.ratio_to(
                Node::Cogwheel {
                    axis: 1,
                    large: false
                },
                [1, 0, 1]
            ),
            Some(-2.0)
        );
    }

    #[test]
    fn loop_validation_uses_the_existing_ratio_tolerance() {
        assert!(!inconsistent_loop_ratio(2.0, 2.0 + 5e-6));
        assert!(inconsistent_loop_ratio(2.0, 2.0 + 2e-5));
    }

    #[test]
    fn controller_ratio_and_loop_conflicts_are_safe() {
        assert_eq!(controller_output_ratio(32.0, 64), Some(0.5));
        assert_eq!(controller_output_ratio(32.0, -64), Some(-0.5));
        assert_eq!(controller_output_ratio(-32.0, 64), Some(-0.5));
        assert_eq!(controller_output_ratio(0.0, 64), None);
        assert_eq!(controller_output_ratio(32.0, 0), None);
        let stopped = Network { rpm: 32.0, capacity: 4096.0, stress: 64.0,
            topology_conflict: true, ..Network::default() };
        assert_eq!(stopped.speed(), 0.0);
    }

    #[test]
    fn speed_controller_links_only_to_perpendicular_horizontal_large_cogs() {
        let controller = Node::RotationSpeedController { axis: 0, target: 32 };
        assert!(controller_links_large_cog(controller,
            Node::Cogwheel { axis: 2, large: true }, [0, 1, 0]));
        assert!(!controller_links_large_cog(controller,
            Node::Cogwheel { axis: 0, large: true }, [0, 1, 0]));
        assert!(!controller_links_large_cog(controller,
            Node::Cogwheel { axis: 2, large: false }, [0, 1, 0]));
        assert!(!controller_links_large_cog(controller,
            Node::Cogwheel { axis: 2, large: true }, [0, -1, 0]));
    }
}

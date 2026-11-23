//! The selected motor/shaft/cogwheel subset of the legacy kinetic edge rules.
//!
//! This module has no Horizon host access. The caller supplies block identity,
//! orientation, positions and motor setting, which keeps the SDK adapter thin.

#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub enum Node {
    Motor { facing: [i32; 3] },
    Shaft { axis: usize },
    Cogwheel { axis: usize, large: bool },
}

impl Node {
    fn shaft(self, face: [i32; 3]) -> bool {
        match self {
            Self::Motor { facing } => face == facing,
            Self::Shaft { axis } | Self::Cogwheel { axis, .. } => face[axis] != 0,
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
        if matches!(self, Self::Cogwheel { .. }) {
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
        let (
            Self::Cogwheel { axis, large },
            Self::Cogwheel {
                axis: other_axis,
                large: other_large,
            },
        ) = (self, other)
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
    }

    #[test]
    fn signed_motor_settings_are_clamped_and_keep_facing_sign() {
        assert_eq!(motor_speed([1, 0, 0], 64), 64.0);
        assert_eq!(motor_speed([-1, 0, 0], 64), -64.0);
        assert_eq!(motor_speed([1, 0, 0], -24), -24.0);
        assert_eq!(motor_speed([1, 0, 0], 999), 256.0);
    }
}

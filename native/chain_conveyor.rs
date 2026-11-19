use horizon_core::geometry::trig::{DEG_TO_RAD, RAD_TO_DEG, atan2, sine_table};

const BRANCH_ANGLE: f32 = 35.0;
const HEIGHT: f64 = 6.0 / 16.0;

pub(super) struct Span {
    pub(super) departure: f32,
    pub(super) arrival: f32,
    pub(super) length: f32,
    pub(super) start: [f64; 3],
    pub(super) end: [f64; 3],
}

impl Span {
    pub(super) fn new(origin: [i32; 3], offset: [i32; 3], reversed: bool) -> Self {
        let direction = atan2(f64::from(offset[0]), f64::from(offset[2])) as f32 * RAD_TO_DEG;
        let branch_angle = if reversed {
            -BRANCH_ANGLE
        } else {
            BRANCH_ANGLE
        };
        let departure = wrap_angle(direction - branch_angle);
        let arrival = wrap_angle(departure + 180.0 + 2.0 * branch_angle);
        let destination = std::array::from_fn(|axis| origin[axis] + offset[axis]);
        let start = anchor(origin, departure, 1.25);
        let end = anchor(destination, arrival, 1.25);
        let length = magnitude(std::array::from_fn(|axis| end[axis] - start[axis])) as f32;
        Self {
            departure,
            arrival,
            length,
            start,
            end,
        }
    }

    pub(super) fn advance(&self, progress: f32, rpm: f32) -> f32 {
        (progress + (rpm / 360.0).abs()).min(self.length)
    }

    pub(super) fn position(&self, progress: f32) -> [f64; 3] {
        let delta = std::array::from_fn(|axis| self.end[axis] - self.start[axis]);
        let length = magnitude(delta);
        let progress = f64::from(progress.min(self.length));
        std::array::from_fn(|axis| self.start[axis] + delta[axis] / length * progress)
    }
}

pub(super) fn chain_cost(offset: [i32; 3]) -> u32 {
    (magnitude(offset.map(f64::from)) / 2.5).round().max(1.0) as u32
}

pub(super) fn reverse_progress(offset: [i32; 3], progress: f32) -> f32 {
    magnitude(offset.map(f64::from)) as f32 - 22.0 / 16.0 - progress
}

pub(super) fn advance_loop(angle: f32, rpm: f32) -> f32 {
    wrap_angle(angle + (rpm / 360.0) / (std::f32::consts::PI * 1.5) * 360.0)
}

pub(super) fn crosses_loop_angle(previous: f32, next: f32, target: f32, reversed: bool) -> bool {
    fn side(angle: f32, target: f32) -> i8 {
        let delta = (angle - target + 180.0).rem_euclid(360.0) - 180.0;
        (delta > 0.0) as i8 - (delta < 0.0) as i8
    }

    let previous = side(previous, target);
    let next = side(next, target);
    if reversed {
        previous > next
    } else {
        previous < next
    }
}

pub(super) fn loop_position(origin: [i32; 3], angle: f32) -> [f64; 3] {
    anchor(origin, angle, 0.875)
}

fn anchor([x, y, z]: [i32; 3], angle: f32, radius: f64) -> [f64; 3] {
    // Java Create rotates these vectors with the 1.21 float-indexed sine table.
    let phase = angle * DEG_TO_RAD * 10430.378_f32;
    let table = sine_table();
    let sin = table[(phase as i32 & 65535) as usize];
    let cos = table[((phase + 16384.0) as i32 & 65535) as usize];
    [
        f64::from(x) + 0.5 + radius * f64::from(sin),
        f64::from(y) + HEIGHT,
        f64::from(z) + 0.5 + radius * f64::from(cos),
    ]
}

fn wrap_angle(angle: f32) -> f32 {
    let angle = angle % 360.0;
    if angle < 0.0 { angle + 360.0 } else { angle }
}

fn magnitude([x, y, z]: [f64; 3]) -> f64 {
    (x * x + y * y + z * z).sqrt()
}

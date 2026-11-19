use horizon_core::geometry::Vec3;

const UP: Vec3 = Vec3::new(0.0, 1.0, 0.0);
const EPSILON: f64 = 1.0e-5;

#[derive(Clone, Copy)]
pub(super) struct End {
    pub(super) pos: [i32; 3],
    pub(super) axis: Vec3,
    pub(super) normal: Vec3,
}

impl End {
    pub(super) fn start(self) -> Vec3 {
        Vec3::new(
            f64::from(self.pos[0]) + 0.5,
            f64::from(self.pos[1]) + if self.axis.y == 0.0 { 0.0 } else { 0.5 },
            f64::from(self.pos[2]) + 0.5,
        )
        .add_vector(self.axis.scale(0.5))
    }

    pub(super) fn across(self, extent: i32) -> Self {
        let shift = self.axis.scale(f64::from(extent)).components();
        Self {
            pos: std::array::from_fn(|index| self.pos[index] + shift[index] as i32),
            ..self
        }
    }
}

pub(super) struct Plan {
    pub(super) ends: [End; 2],
    pub(super) extent: [i32; 2],
    pub(super) curve: Option<Curve>,
}

fn near(a: f64, b: f64) -> bool {
    (a - b).abs() < EPSILON
}

fn intersect(first: Vec3, second: Vec3, a: Vec3, b: Vec3, plane: [usize; 2]) -> Option<[f64; 2]> {
    let det = |a: Vec3, b: Vec3| {
        let a = a.components();
        let b = b.components();
        a[plane[0]] * b[plane[1]] - a[plane[1]] * b[plane[0]]
    };
    let denominator = det(a, b);
    if near(denominator, 0.0) {
        return None;
    }
    let diff = first.vector_to(second);
    Some([det(diff, b) / denominator, det(diff, a) / denominator])
}

pub(super) fn connect(mut first: End, mut second: End, extended: bool) -> Option<Plan> {
    let offset = Vec3::new(
        f64::from(second.pos[0]) - f64::from(first.pos[0]),
        f64::from(second.pos[1]) - f64::from(first.pos[1]),
        f64::from(second.pos[2]) - f64::from(first.pos[2]),
    );
    if first.pos == second.pos || offset.length_squared() > 32.0 * 32.0 {
        return None;
    }
    let mut a = first.axis.normalize();
    let mut b = second.axis.normalize();
    if first.axis.dot(first.start().vector_to(second.start())) < 0.0 {
        first.axis = first.axis.reverse();
        a = a.reverse();
    }
    let intersection = intersect(first.start(), second.start(), a, b, [0, 2]);
    if intersection.map_or_else(|| a.dot(b) > 0.0, |[t, u]| t < 0.0 || u < 0.0) {
        second.axis = second.axis.reverse();
        b = b.reverse();
    }

    let start = first.start();
    let end = second.start();
    let rise = end.y - start.y;
    let abs_rise = rise.abs();
    let slope = first.normal != second.normal;
    let mut straight = false;
    let mut extent = [0; 2];

    if intersection.is_none() {
        let [t, u] = intersect(start, end, a, b.cross(UP), [0, 2])?;
        straight = near(u, 0.0);
        if straight {
            extent[0] = ((offset.length() + 1.0) / first.axis.length()).round() as i32;
        } else {
            if t < 0.0 || !near(rise, 0.0) || a.y != 0.0 {
                return None;
            }
            let min_run = if u.abs() <= 1.0 { 3.0 } else { u.abs() * 2.0 };
            if t.abs() < min_run {
                return None;
            }
            if !extended {
                let slack = ((t.abs() - min_run) / first.axis.length()) as i32;
                extent = [(slack + 1) / 2, slack / 2];
            }
        }
    }

    if slope {
        if !straight
            || near(first.normal.dot(second.normal), 0.0)
            || ((first.axis.y < 0.0 || second.axis.y > 0.0) && rise > 0.0)
            || ((first.axis.y > 0.0 || second.axis.y < 0.0) && rise < 0.0)
        {
            return None;
        }
        straight = false;
        let plane = if near(first.axis.x, 0.0) {
            [1, 2]
        } else {
            [0, 1]
        };
        let [t, u] = intersect(start, end, a, b, plane)?;
        let d1 = t.abs() / first.axis.length();
        let d2 = u.abs() / second.axis.length();
        let size = d1.min(d2);
        if t < 0.0 || u < 0.0 || size < 2.0 {
            return None;
        }
        extent = [
            (d1 - d2).max(0.0).round() as i32,
            (d2 - d1).max(0.0).round() as i32,
        ];
        if !extended {
            extent
                .iter_mut()
                .for_each(|extra| *extra += (size - 2.0) as i32);
        }
    }

    if straight
        && !near(rise, 0.0)
        && (first.axis.y == 0.0 || !near(abs_rise + 1.0, offset.length() / first.axis.length()))
    {
        if first.axis.y != 0.0 && first.axis.y == -second.axis.y {
            return None;
        }
        let min_run =
            (abs_rise * if abs_rise < 4.0 { 4.0 } else { 3.0 }).max(6.0) / first.axis.length();
        if f64::from(extent[0]) < min_run {
            return None;
        }
        let slack = if extended {
            0
        } else {
            (f64::from(extent[0]) - min_run) as i32
        };
        extent = [(slack + 1) / 2, slack / 2];
        straight = false;
    }

    if intersection.is_some() {
        let angle = (b.z.atan2(b.x) - a.z.atan2(a.x)).to_degrees().abs();
        if !(60.0..=300.0).contains(&angle) {
            return None;
        }
        let [t, u] = intersect(start, end, a, b, [0, 2])?;
        let size = t.min(u) - 0.1;
        let square_turn = (angle + 0.25) % 90.0 < 1.0;
        let minimum = if square_turn {
            7.0 + (abs_rise - 3.0).max(0.0) * 2.0
        } else {
            3.25 + (abs_rise - 1.5).max(0.0) * 1.5
        };
        if size < minimum {
            return None;
        }
        let slack = if extended { 0.0 } else { size - minimum };
        extent = [
            ((t - u).max(0.0) / first.axis.length() + slack / first.axis.length()).floor() as i32,
            ((u - t).max(0.0) / second.axis.length() + slack / second.axis.length()).floor() as i32,
        ];
    }

    Some(Plan {
        ends: [first, second],
        extent,
        curve: (!straight).then(|| Curve::new([first.across(extent[0]), second.across(extent[1])])),
    })
}

#[derive(Clone, Copy)]
pub(super) struct Curve {
    pub(super) ends: [End; 2],
    pub(super) starts: [Vec3; 2],
    pub(super) handle: f64,
    pub(super) segments: u32,
    pub(super) length: f64,
}

impl Curve {
    pub(super) fn new(ends: [End; 2]) -> Self {
        Self::with_starts(ends, ends.map(End::start))
    }

    pub(super) fn with_starts(ends: [End; 2], starts: [Vec3; 2]) -> Self {
        let [a, b] = ends.map(|end| end.axis.normalize());
        let [start, end] = starts;
        let distance = start.distance(end);
        let fallback = distance / 3.0;
        let rotation = (-b.z).atan2(-b.x) - a.z.atan2(a.x);
        let circle = f64::from(2.0_f32 * std::f32::consts::PI);
        let mut angle = (rotation + circle) % circle;
        angle = angle.min(circle - angle);
        let handle = if near(angle, 0.0) {
            intersect(start, end, a, b.cross(UP), [0, 2]).map_or(fallback, |[t, u]| {
                let min = t.abs().min(u.abs());
                let max = t.abs().max(u.abs());
                if min > 1.2 && max > min && max / min < 3.0 {
                    max - min
                } else {
                    fallback
                }
            })
        } else {
            intersect(start, end, a.cross(UP), b.cross(UP), [0, 2]).map_or(fallback, |[_, u]| {
                let handle =
                    u.abs() * (4.0 / 3.0) * (std::f64::consts::PI * angle / (2.0 * circle)).tan();
                if near(handle, 0.0) { 1.0 } else { handle }
            })
        };
        let mut result = Self {
            ends,
            starts: [start, end],
            handle,
            segments: 0,
            length: 0.0,
        };
        let mut previous = start;
        for point in 1..=16 {
            let next = result.point(point as f64 / 16.0);
            result.length += next.distance(previous);
            previous = next;
        }
        result.segments = (result.length * 2.0) as u32;
        result
    }

    fn control_points(self) -> [Vec3; 4] {
        let [start, end] = self.starts;
        let first = start.add_vector(self.ends[0].axis.normalize().scale(self.handle));
        let second = end.add_vector(self.ends[1].axis.normalize().scale(self.handle));
        [start, first, second, end]
    }

    pub(super) fn derivative(self, t: f32) -> Vec3 {
        let [start, first, second, end] = self.control_points();
        // Create computes the cubic derivative coefficients in Java float arithmetic.
        start
            .scale(f64::from(-3.0 * t * t + 6.0 * t - 3.0))
            .add_vector(first.scale(f64::from(9.0 * t * t - 12.0 * t + 3.0)))
            .add_vector(second.scale(f64::from(-9.0 * t * t + 6.0 * t)))
            .add_vector(end.scale(f64::from(3.0 * t * t)))
    }

    pub(super) fn point(self, t: f64) -> Vec3 {
        let mix = |a: Vec3, b: Vec3| a.lerp(b, t);
        let [start, first, second, end] = self.control_points();
        let a = mix(start, first);
        let b = mix(first, second);
        let c = mix(second, end);
        mix(mix(a, b), mix(b, c))
    }
}

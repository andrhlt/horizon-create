use horizon_core::geometry::trig::sine_table;

#[cfg(test)]
pub(crate) const PARTS: [&str; 6] = [
    "head",
    "body",
    "right_arm",
    "left_arm",
    "right_leg",
    "left_leg",
];

fn sine(angle: f32) -> f32 {
    sine_table()[((angle * 10430.378_f32) as i32 & 65535) as usize]
}

fn cosine(angle: f32) -> f32 {
    sine_table()[((angle * 10430.378_f32 + 16384.0) as i32 & 65535) as usize]
}

fn radians(degrees: f32) -> f32 {
    degrees * (std::f32::consts::PI / 180.0)
}

pub(crate) fn pose(time: f32, left: bool, rest: [[f32; 9]; 6], head: [f32; 9]) -> [[f32; 9]; 6] {
    let [head_part, body, right_arm, left_arm, right_leg, left_leg] = [0, 1, 2, 3, 4, 5];
    let (arm, other, lead, trail) = if left {
        (left_arm, right_arm, left_leg, right_leg)
    } else {
        (right_arm, left_arm, right_leg, left_leg)
    };
    let sign = if left { -1.0 } else { 1.0 };
    let mut result = rest;
    result[head_part] = head;
    result[head_part][0] = 0.0;
    let cycle = |shift| sine((f64::from((time + shift) * 0.3_f32) / std::f64::consts::PI) as f32);
    let body_swing = sign * radians(15.0 + 10.0 * cycle(10.0));
    let limb_swing = radians(cycle(0.0) * 15.0);
    result[head_part][5] = body_swing;
    result[body][5] = body_swing;

    let sin = sine(body_swing);
    let cos = cosine(body_swing);
    let rotate = |[x, y]: [f32; 2]| [x * cos - y * sin, x * sin + y * cos];
    result[arm][1] -= 3.0;
    let [arm_x, arm_y] = rotate([result[arm][0], result[arm][1]]);
    let pivot = [arm_x + sign * 4.5, arm_y + 2.0];
    result[arm][3] = -radians(150.0);
    result[arm][5] = sign * radians(15.0);

    result[lead][1] -= 0.2;
    result[trail][1] -= 0.8;
    for (part, pitch, roll) in [
        (other, 0.0, -20.0),
        (lead, -25.0, 10.0),
        (trail, 10.0, -10.0),
    ] {
        let [x, y] = rotate([result[part][0], result[part][1]]);
        result[part][0] = x;
        result[part][1] = y;
        result[part][3] = radians(pitch);
        result[part][5] = sign * radians(roll) + 0.5 * body_swing + limb_swing;
    }
    for part in [head_part, body, other, lead, trail] {
        result[part][0] -= pivot[0];
        result[part][1] -= pivot[1];
    }
    result
}

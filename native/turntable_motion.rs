//! Source-derived Turntable motion math for typed runtime adapters.

/// Camera turn in degrees for one client frame. The caller supplies the
/// runtime's tick rate, frame delta, partial tick, and player offset.
pub fn camera_turn(
    rpm: f32,
    tick_rate: f32,
    realtime: f32,
    partial: f32,
    offset: [f64; 3],
) -> f32 {
    let mut speed = rpm * (2.0 / 3.0) * (tick_rate / 20.0) * realtime;
    let distance = offset.iter().map(|n| n * n).sum::<f64>().sqrt();
    if distance > 0.25 {
        speed *= ((0.5 - distance) * 2.0).clamp(0.0, 1.0) as f32;
    }
    speed * partial
}

/// Edge velocity from the original rotating-vector calculation.
pub fn edge_velocity(rpm: f32, offset: [f64; 3]) -> [f64; 3] {
    let degrees = (rpm * 3.0 / 10.0).clamp(-16.0, 16.0);
    let radians = f64::from(degrees).to_radians();
    let (sin, cos) = radians.sin_cos();
    let [x, _, z] = offset;
    [
        x * cos + z * sin - x,
        0.0,
        z * cos - x * sin - z,
    ]
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn camera_turn_fades_at_the_table_edge_and_scales_with_partial_tick() {
        assert_eq!(camera_turn(16.0, 20.0, 1.0, 0.5, [0.0; 3]), 16.0 / 3.0);
        assert_eq!(camera_turn(16.0, 20.0, 1.0, 1.0, [0.5, 0.0, 0.0]), 0.0);
        assert_eq!(camera_turn(16.0, 20.0, 0.5, 1.0, [0.0; 3]), 16.0 / 3.0);
    }

    #[test]
    fn edge_velocity_is_zero_at_center_and_clamps_extreme_rpm() {
        assert_eq!(edge_velocity(16.0, [0.0; 3]), [0.0; 3]);
        let bounded = edge_velocity(100.0, [0.5, 0.0, 0.0]);
        let clamped = edge_velocity(16.0 * 10.0 / 3.0, [0.5, 0.0, 0.0]);
        for (actual, expected) in bounded.into_iter().zip(clamped) {
            assert!((actual - expected).abs() < 1e-12);
        }
        assert!(edge_velocity(-16.0, [0.5, 0.0, 0.0])[2] > 0.0);
        assert!(edge_velocity(16.0, [0.5, 0.0, 0.0])[2] < 0.0);
    }
}

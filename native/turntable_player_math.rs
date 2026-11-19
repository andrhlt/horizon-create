use horizon_core::geometry::Vec3;

pub(super) fn camera_turn(
    rpm: f32,
    tick_rate: f32,
    realtime: f32,
    partial: f32,
    offset: Vec3,
) -> f32 {
    let mut speed = rpm * (2.0 / 3.0) * (tick_rate / 20.0) * realtime;
    let [x, y, z] = offset.components();
    let distance = (x * x + y * y + z * z).sqrt();
    if distance > 0.25 {
        speed *= ((0.5 - distance) * 2.0).clamp(0.0, 1.0) as f32;
    }
    speed * partial
}

pub(super) fn edge_velocity(rpm: f32, origin: Vec3, position: Vec3) -> Vec3 {
    let degrees = (rpm * 3.0 / 10.0).clamp(-16.0, 16.0);
    // Create's Minecraft 1.21.1 uses a float index into the sine table.
    let index = (degrees * horizon_core::geometry::trig::DEG_TO_RAD) * 10_430.378_f32;
    let sine = horizon_core::geometry::trig::sine_table();
    let sin = f64::from(sine[(index as i32 & 65535) as usize]);
    let cos = f64::from(sine[((index + 16_384.0) as i32 & 65535) as usize]);
    let [x, y, z] = origin.vector_to(position).components();
    let rotated = origin.add_vector(Vec3::new(x * cos + z * sin, y, z * cos - x * sin));
    position.vector_to(rotated)
}

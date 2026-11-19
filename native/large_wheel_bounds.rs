fn large_wheel_bounds(block: &str, bounds: &mut [f32; 6]) {
    if matches!(
        block,
        crate::game::create_machines::LARGE_WHEEL | crate::game::create_flywheel::FLYWHEEL
    ) {
        *bounds = [-2.0, -2.0, -2.0, 3.0, 3.0, 3.0];
    }
}

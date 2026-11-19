fn speed_controller_bounds(block: &str, bounds: &mut [f32; 6]) {
    if block == crate::game::create_speed_controller::CONTROLLER {
        bounds[4] = 2.0;
    }
}

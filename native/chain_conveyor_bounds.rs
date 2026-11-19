fn chain_conveyor_bounds(block: &str, bounds: &mut [f32; 6]) {
    if block == crate::game::create_machines::CONVEYOR {
        *bounds = [
            f32::NEG_INFINITY,
            f32::NEG_INFINITY,
            f32::NEG_INFINITY,
            f32::INFINITY,
            f32::INFINITY,
            f32::INFINITY,
        ];
    }
}

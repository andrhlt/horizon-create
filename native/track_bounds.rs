fn track_bounds(
    pos: [i32; 3],
    block: &str,
    entity: &crate::containers::ModBlockEntity,
    bounds: &mut [f32; 6],
) {
    match block {
        crate::game::create_track::TRACK => crate::game::create_track::bounds(entity, bounds),
        crate::game::create_elevator::PULLEY => {
            crate::game::create_elevator::bounds(entity, bounds)
        }
        crate::game::create_rope::PULLEY => crate::game::create_rope::bounds(entity, bounds),
        crate::game::create_hose::HOSE => crate::game::create_hose::bounds(pos, entity, bounds),
        _ => {}
    }
}

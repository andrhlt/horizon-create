fn schematic_capture_voids(
    game: &crate::game::Game<'_>,
    origin: [i32; 3],
    size: [i32; 3],
    template: Tag,
) -> Tag {
    crate::game::structure_blocks::create_schematic_capture::add_void_as_air(
        game, origin, size, template,
    )
}

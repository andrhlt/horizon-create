fn machine_screen_click(
    block: &str,
    data: &[i32],
    at: [f32; 2],
    right: bool,
    button: &mut Option<i32>,
) {
    if block == crate::game::create_factory_gauge::BLOCK && !right {
        *button = crate::game::create_factory_gauge::screen_click(at);
    } else if crate::game::create_toolbox::block(block) && !right {
        *button = crate::game::create_toolbox_menu::screen_click(at);
    } else if block == crate::game::create_station::STATION && !right {
        *button = crate::game::create_station::screen_click(data, at);
    } else if block == crate::game::create_brass_tunnel::TUNNEL && !right {
        *button = crate::game::create_brass_tunnel::screen_click(at);
    } else if block == crate::game::create_display_link::LINK && !right {
        *button = crate::game::create_display_link::screen_click(data, at);
    } else if block == crate::game::create_schematicannon::CANNON && !right {
        *button = crate::game::create_schematicannon::screen_click(at);
    } else if block == crate::game::create_schematic_table::BLOCK && !right {
        *button = crate::game::create_schematic_table::screen_click(at);
    }
}

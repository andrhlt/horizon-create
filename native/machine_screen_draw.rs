fn machine_screen_draw(
    game: &crate::game::Game<'_>,
    block: &str,
    data: &[i32],
    batch: &mut horizon_client::hud::HudBatch,
    origin: [f32; 2],
) {
    if block == crate::game::create_factory_gauge::BLOCK {
        crate::game::create_factory_gauge::draw_screen(game, batch, origin);
    } else if crate::game::create_toolbox::block(block) {
        crate::game::create_toolbox_menu::draw(game, batch, origin);
    } else if block == crate::game::create_station::STATION {
        crate::game::create_station::draw_screen(game, data, batch, origin);
    } else if block == crate::game::create_brass_tunnel::TUNNEL {
        crate::game::create_brass_tunnel::draw_screen(game, data, batch, origin);
    } else if block == crate::game::create_display_link::LINK {
        crate::game::create_display_link::draw_screen(game, data, batch, origin);
    } else if block == crate::game::create_schematic_table::BLOCK {
        crate::game::create_schematic_table::draw(game, batch, origin);
    } else if block == crate::game::create_machines::FROGPORT
        || crate::game::create_postbox::block(block)
    {
        crate::game::create_chain_conveyor_packages::draw_port_screen(game, batch, origin);
    }
}

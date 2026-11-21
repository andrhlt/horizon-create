fn machine_screen_layout(block: &str, screen: &mut Option<crate::mod_api::NativeScreen>) {
    if block == crate::game::create_factory_gauge::BLOCK {
        *screen = Some(crate::game::create_factory_gauge::layout());
    } else if crate::game::create_toolbox::block(block) {
        *screen = Some(crate::game::create_toolbox_menu::layout());
    } else if block == crate::game::create_station::STATION {
        *screen = Some(crate::game::create_station::layout());
    } else if block == crate::game::create_brass_tunnel::TUNNEL {
        *screen = Some(crate::game::create_brass_tunnel::layout());
    } else if block == crate::game::create_display_link::LINK {
        *screen = Some(crate::game::create_display_link::layout());
    } else if block == crate::game::create_schematicannon::CANNON {
        *screen = Some(crate::game::create_schematicannon::layout());
    } else if block == crate::game::create_schematic_table::BLOCK {
        *screen = Some(crate::game::create_schematic_table::layout());
    } else if block == crate::game::create_machines::FROGPORT
        || crate::game::create_postbox::block(block)
    {
        *screen = Some(crate::game::create_chain_conveyor_packages::port_layout());
    }
}

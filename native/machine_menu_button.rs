fn machine_menu_button(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    entity: &mut crate::containers::ModBlockEntity,
    id: i32,
) {
    if entity.id == crate::game::create_factory_gauge::ENTITY {
        crate::game::create_factory_gauge::menu_button(game, pos, id);
    } else if entity.id == crate::game::create_toolbox::ENTITY {
        crate::game::create_toolbox_menu::menu_button(game, pos, entity, id);
    } else if entity.id == crate::game::create_station::STATION {
        crate::game::create_station::menu_button(game, pos, entity, id);
    } else if entity.id == crate::game::create_brass_tunnel::TUNNEL {
        crate::game::create_brass_tunnel::menu_button(game, pos, entity, id);
    } else if entity.id == crate::game::create_display_link::LINK {
        crate::game::create_display_link::menu_button(game, pos, entity, id);
    }
}

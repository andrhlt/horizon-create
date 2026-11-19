fn toolbox_radial_tick(game: &mut crate::game::Game<'_>) {
    crate::game::create_toolbox_menu::client_tick(game);
    crate::game::create_toolbox_radial::client_tick(game);
    crate::game::create_toolbox_animation::tick(game);
}

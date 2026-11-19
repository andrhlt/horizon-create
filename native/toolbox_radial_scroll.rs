fn toolbox_radial_scroll(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    scroll: [f64; 2],
    canceled: &mut bool,
) {
    crate::game::create_toolbox_radial::scroll(game, screen, scroll[1], canceled);
}

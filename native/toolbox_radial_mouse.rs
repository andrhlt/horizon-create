fn toolbox_radial_mouse(
    game: &crate::game::Game<'_>,
    screen: &horizon_client::mod_api::NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    crate::game::create_toolbox_menu::confirm_click(game, screen, button, canceled);
    crate::game::create_toolbox_radial::click(game, screen, button, canceled);
}

fn toolbox_menu_click(
    menu: &mut horizon_client::menu::Menu,
    env: &horizon_client::menu::Env<'_>,
    state: &mut horizon_world::nbt::Compound,
    slot: i32,
    button: i32,
    input: horizon_client::menu::Input,
    handled: &mut bool,
) {
    crate::game::create_toolbox_menu::click(menu, env, state, slot, button, input, handled);
}

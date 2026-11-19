fn machine_screen_tooltip(block: &str, at: [f32; 2], lines: &mut Vec<String>) {
    if crate::game::create_toolbox::block(block) {
        crate::game::create_toolbox_menu::tooltip(at, lines);
    } else if block == crate::game::create_brass_tunnel::TUNNEL {
        crate::game::create_brass_tunnel::tooltip(at, lines);
    }
}

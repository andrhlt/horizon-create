fn windmill_data_loaded(game: &mut crate::game::Game<'_>, pos: [i32; 3]) {
    crate::game::create_bearing::windmill_loaded(game, pos);
    crate::game::create_machines::motor_setting_changed(game, pos);
}

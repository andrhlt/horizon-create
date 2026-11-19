fn copycat_data_loaded(game: &mut crate::game::Game<'_>, pos: [i32; 3]) {
    game.refresh_copycat_panel_material(pos);
}

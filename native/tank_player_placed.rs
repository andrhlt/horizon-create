fn tank_player_placed(game: &mut crate::game::Game<'_>, pos: [i32; 3]) {
    crate::game::create_fluid_tank::placed(game, pos);
}

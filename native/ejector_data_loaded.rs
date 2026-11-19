fn ejector_data_loaded(game: &mut crate::game::Game<'_>, pos: [i32; 3]) {
    if game.native_block(pos) == crate::game::create_ejector::EJECTOR {
        game.native_update_output_neighbors(game.native_dimension(), pos);
    }
}

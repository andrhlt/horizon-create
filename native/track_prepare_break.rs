fn track_prepare_break(game: &mut crate::game::Game<'_>, pos: [i32; 3], canceled: &bool) {
    if !*canceled
        && game.native_authoritative()
        && game.native_block(pos) == crate::game::create_track::TRACK
    {
        crate::game::create_track::prepare_break(game, pos);
    }
}

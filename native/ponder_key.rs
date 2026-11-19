fn ponder_key(game: &Game<'_>, key: &str, canceled: &mut bool) {
    crate::game::create_ponder::key(game, key, canceled);
}

fn train_trapdoor_targetable(game: &crate::game::Game<'_>, targetable: bool) -> bool {
    targetable
        || crate::game::create_train_trapdoor_exact::client_pick(game, false, None)
            .is_some_and(|hit| game.before_block(hit.distance))
}

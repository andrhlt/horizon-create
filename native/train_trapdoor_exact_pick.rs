fn train_trapdoor_exact_pick(
    game: &crate::game::Game<'_>,
    attacking: bool,
    picked: Option<ObjectHit>,
) -> Option<ObjectHit> {
    crate::game::create_train_trapdoor_exact::client_pick(game, attacking, picked)
}

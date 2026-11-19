fn train_trapdoor_pick(
    game: &crate::game::Game<'_>,
    picked: Option<(f64, Option<i32>)>,
) -> Option<(f64, Option<i32>)> {
    crate::game::create_train::pick_trapdoor(game, picked)
}

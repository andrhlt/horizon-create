fn train_loaded_tick(loaded_after: u32, game: &mut crate::game::Game<'_>) {
    use crate::game::create_train::{TickPhase, tick};
    tick(game, TickPhase::Restored(loaded_after));
}

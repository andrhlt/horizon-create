fn train_tick(game: &mut crate::game::Game<'_>, running: bool) {
    if running {
        use crate::game::create_train::{TickPhase, tick};
        tick(game, TickPhase::Early);
    }
}

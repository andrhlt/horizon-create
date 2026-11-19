fn after_block_entity_ticks(game: &mut crate::game::Game<'_>, result: Result<()>) -> Result<()> {
    use crate::game::create_train::{TickPhase, tick};
    crate::game::create_train_portable_items::end_block_phase(game);
    if result.is_ok() {
        crate::game::create_fluid_tank::trace_storage(game, "tick");
        crate::game::create_linked_controller::post_tick(game);
        tick(game, TickPhase::AfterBlocks);
        crate::game::create_chain_conveyor_box_visual::tick(game);
    }
    result
}

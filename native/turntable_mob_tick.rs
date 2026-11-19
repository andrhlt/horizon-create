fn turntable_mob_tick(game: &mut Game<'_>, entity: u32) {
    crate::game::create_turntable::tick_mob(game, entity);
}

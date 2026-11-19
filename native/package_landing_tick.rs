fn package_landing_tick(game: &mut Game<'_>, entity: u32, kind: &str) {
    if kind == crate::game::create_package_style::ENTITY {
        crate::game::create_package_landing::tick(game, entity);
    }
}

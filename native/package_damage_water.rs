fn package_damage_water(game: &mut Game<'_>, entity: u32, kind: &str) {
    if kind == crate::game::create_package_style::ENTITY {
        crate::game::create_package_damage::tick(game, entity);
    }
}

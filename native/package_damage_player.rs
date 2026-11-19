fn package_damage_player(game: &mut Game<'_>, index: usize) -> std::ops::ControlFlow<bool> {
    use crate::game::{create_package_damage, create_package_style};
    use std::ops::ControlFlow::{Break, Continue};

    let Some(victim) = game
        .mobs
        .get(index)
        .filter(|mob| mob.kind.id == create_package_style::ENTITY)
    else {
        return Continue(());
    };
    let id = victim.id;
    if game.may_build() && create_package_damage::can_hurt(game, id) {
        create_package_damage::spill_now(game, id);
    }
    Break(false)
}

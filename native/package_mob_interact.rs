fn package_mob_interact(
    game: &mut Game<'_>,
    target: Option<InteractTarget>,
) -> std::ops::ControlFlow<Result<bool>> {
    use std::ops::ControlFlow::{Break, Continue};

    let Some(index) = game.mob_interaction_target(target) else {
        return Continue(());
    };
    if super::create_stock_keeper_screen::use_mob(game, index) {
        game.swing_arm();
        return Break(Ok(true));
    }
    let package = &game.mobs[index];
    if package.kind.id != super::create_package_style::ENTITY {
        return Continue(());
    }
    if !game.native_authoritative() || game.held().is_some() {
        return Break(Ok(false));
    }
    let Some(stack) = package.extra.main_hand_stack().cloned() else {
        return Break(Ok(false));
    };
    let position = [package.position.x, package.position.y, package.position.z]
        .map(|value| value.floor() + 0.5);
    let id = package.id;
    if !game.native_remove_mob(game.native_dimension(), id) {
        return Break(Ok(false));
    }
    *game.held_mut() = Some(stack);
    let pitch = 0.75 + game.world.random.next_float();
    game.native_play_sound_in_place("minecraft:entity.item.pickup", position, 7, 0.2, pitch);
    game.swing_arm();
    Break(Ok(true))
}

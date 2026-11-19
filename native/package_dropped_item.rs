fn package_dropped_item(
    game: &mut crate::game::Game<'_>,
    entity: u32,
    item: &str,
    position: [f64; 3],
) -> std::ops::ControlFlow<()> {
    use crate::game::{create_package_style, create_package_world};
    use std::ops::ControlFlow::{Break, Continue};

    if !game.native_authoritative() || create_package_style::dimensions(item).is_none() {
        return Continue(());
    }
    let Some(drop) = game.dropped.iter().find(|drop| drop.id == entity) else {
        return Continue(());
    };
    if drop.pickup_delay == 32767 {
        return Continue(());
    }
    let stack = drop.stack.clone();
    let before = drop.velocity.components();
    let motion = before.map(|value| value * 1.5);
    let Some(package) = create_package_world::spawn(game, &stack, position, motion, None) else {
        return Continue(());
    };

    let chute_pos =
        [position[0], position[1] + 0.5, position[2]].map(|coordinate| coordinate.floor() as i32);
    if matches!(
        game.native_block(chute_pos).as_str(),
        "create:chute" | "create:smart_chute"
    ) && let Some(mob) = game.mobs.iter_mut().find(|mob| mob.id == package)
    {
        let yaw = (mob.yaw as i32 / 90 * 90) as f32;
        mob.yaw = yaw;
        mob.previous_yaw = yaw;
        mob.body_yaw = yaw;
        mob.previous_body_yaw = yaw;
        mob.head_yaw = yaw;
        mob.previous_head_yaw = yaw;
    }

    game.dropped.retain(|drop| drop.id != entity);
    game.forget_entity(entity);
    if std::env::var_os("HORIZON_CREATE_PACKAGE_TRACE").is_some() {
        let [x, y, z] = before;
        eprintln!("CREATE_PACKAGE_ITEM_DROP {package},{x:.12},{y:.12},{z:.12}");
    }
    Break(())
}

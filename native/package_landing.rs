use horizon_core::geometry::Vec3;

use crate::mobs::Mob;

use super::{
    Game, create_belt, create_depot, create_ejector, create_funnel, create_machines,
    create_package_style::ENTITY,
};

/// A fresh Package starts with the Java insertion delay at 30. Keep the
/// number of elapsed delay units in the unused per-species scratch slot.
const INSERTION_RECOVERY: usize = 0;

pub(super) fn tick(game: &mut Game<'_>, id: u32) {
    let Some(index) = game
        .mobs
        .iter()
        .position(|mob| mob.id == id && mob.kind.id == ENTITY && mob.alive() && !mob.removed)
    else {
        return;
    };
    let mob = &mut game.mobs[index];
    let remaining = &mut mob.extra.ints[INSERTION_RECOVERY];
    *remaining = (*remaining - 1).max(0);
    if land(game, index) || enter_funnel(game, index) {
        game.native_remove_mob(game.native_dimension(), id);
    }
}

fn center_package(mob: &mut Mob, target: Vec3) -> bool {
    mob.position = mob
        .position
        .add_vector(mob.position.vector_to(target).scale(0.2));
    mob.velocity = mob.velocity.multiply(Vec3::new(0.75, 1.0, 0.75));
    let aligned = ((mob.yaw as i32) / 90 * 90) as f32;
    mob.yaw += (aligned - mob.yaw) * 0.5;
    mob.body_yaw = mob.yaw;
    mob.head_yaw = mob.yaw;
    let recovered = &mut mob.extra.ints[INSERTION_RECOVERY];
    *recovered = (*recovered + 3).min(30);
    *recovered == 30
}

fn land(game: &mut Game<'_>, index: usize) -> bool {
    let mob = &game.mobs[index];
    let [x, y, z] = mob.position.components();
    let Some(support) = mob.supporting.filter(|_| mob.on_ground) else {
        return false;
    };
    let receiver_cell = [x.floor() as i32, y.floor() as i32, z.floor() as i32];
    let chute_cell = [
        x.floor() as i32,
        (y + 0.5).floor() as i32 - 1,
        z.floor() as i32,
    ];
    let receiver = game.native_block(support);
    let (height, contacts) = match receiver.as_str() {
        create_depot::DEPOT | create_ejector::EJECTOR if support == receiver_cell => {
            (13.0 / 16.0, 1)
        }
        create_belt::BELT
            if support == receiver_cell
                && game.native_block_property(support, "slope").as_deref()
                    == Some("horizontal") =>
        {
            (13.0 / 16.0, 2)
        }
        _ if support == chute_cell && create_machines::chute_has_open_top(game, support) => {
            (1.0, 1)
        }
        _ => return false,
    };
    let target = Vec3::new(
        f64::from(support[0]) + 0.5,
        f64::from(support[1]) + height,
        f64::from(support[2]) + 0.5,
    );
    // On a horizontal Belt, fall-contact and entity-inside both center the Package.
    for _ in 0..contacts {
        let mob = &mut game.mobs[index];
        // Landing already zeroed the vertical movement before gravity was applied.
        if !center_package(mob, target) {
            continue;
        }
        let Some(mut stack) = mob.extra.main_hand_stack().cloned() else {
            return false;
        };
        let position = mob.position.components();
        let inserted = match receiver.as_str() {
            create_depot::DEPOT => {
                create_depot::receive_landed_stack(game, support, stack).is_none()
            }
            create_belt::BELT => create_belt::receive_landed_package(game, support, stack),
            create_ejector::EJECTOR => {
                create_ejector::receive_landed_stack(game, support, &stack) == stack.count
            }
            _ => {
                let block = game.world.block(support[0], support[1], support[2]);
                create_machines::chute_landing(game, block, position, &mut stack);
                stack.count == 0
            }
        };
        if inserted {
            return true;
        }
    }
    false
}

fn enter_funnel(game: &mut Game<'_>, index: usize) -> bool {
    let mob = &game.mobs[index];
    // The original block callback visits the full cells overlapped by the Package.
    let inset = Vec3::new(1e-7, 1e-7, 1e-7);
    let bounds = mob.bounds().deflate(inset);
    let min = bounds.min_position().components().map(|n| n.floor() as i32);
    let max = bounds.max_position().components().map(|n| n.floor() as i32);
    for z in min[2]..=max[2] {
        for y in min[1]..=max[1] {
            for x in min[0]..=max[0] {
                let pos = [x, y, z];
                let state = game.world.block(x, y, z);
                if !game
                    .native_state_block(state)
                    .is_some_and(create_funnel::is_funnel_item)
                {
                    continue;
                }
                let mob = &game.mobs[index];
                let at = mob.position;
                let Some(stack) = mob.extra.main_hand_stack().cloned() else {
                    return false;
                };
                let Some((face, target)) = create_funnel::package_opening(game, pos, at, &stack)
                else {
                    continue;
                };
                let mob = &mut game.mobs[index];
                // Funnel's original slowdown precedes gravity and normal drag.
                let gravity =
                    if mob.fluids.in_water || mob.fluids.in_lava || mob.fluids.modded.is_some() {
                        0.0
                    } else {
                        mob.effective_gravity() * f64::from(0.98_f32)
                    };
                mob.velocity.y = (mob.velocity.y + gravity) * 0.1875 - gravity;
                if center_package(mob, target)
                    && create_funnel::offer(game, pos, face, stack).is_none()
                {
                    return true;
                }
            }
        }
    }
    false
}

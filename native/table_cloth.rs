use horizon_core::geometry::Direction;
use horizon_world::level::PlaceContext;
use crate::items::ItemStack;
use super::Game;

fn is_cloth(name: &str) -> bool {
    matches!(name,
        "create:white_table_cloth" | "create:orange_table_cloth" | "create:magenta_table_cloth"
        | "create:light_blue_table_cloth" | "create:yellow_table_cloth" | "create:lime_table_cloth"
        | "create:pink_table_cloth" | "create:gray_table_cloth" | "create:light_gray_table_cloth"
        | "create:cyan_table_cloth" | "create:purple_table_cloth" | "create:blue_table_cloth"
        | "create:brown_table_cloth" | "create:green_table_cloth" | "create:red_table_cloth"
        | "create:black_table_cloth" | "create:andesite_table_cloth" | "create:brass_table_cloth"
        | "create:copper_table_cloth")
}

fn placement_edge(game: &Game<'_>, pos: [i32; 3], hit: [f64; 3]) -> Option<Direction> {
    Direction::ALL.into_iter().filter(|side| {
        let [x, y, z] = side.normal();
        y == 0 && game.res.behaviours().is_replaceable(game.world.block(pos[0] + x, pos[1], pos[2] + z))
    }).min_by(|a, b| {
        let distance = |side: Direction| pos.into_iter().zip(side.normal()).zip(hit)
            .map(|((at, normal), point)| (f64::from(at) + 0.5 + f64::from(normal) * 0.5 - point).powi(2))
            .sum::<f64>();
        distance(*a).total_cmp(&distance(*b))
    })
}

pub(super) fn redirect_placement(game: &Game<'_>, context: &mut PlaceContext) {
    if context.sneaking || !game.may_build() || context.face == Direction::Down || !is_cloth(&context.item) {
        return;
    }
    let origin = context.clicked_pos;
    let pos = [origin.x, origin.y, origin.z];
    if !is_cloth(&game.native_block(pos)) {
        return;
    }
    if let Some(side) = placement_edge(game, pos, context.hit.components()) {
        context.face = side;
    }
}

pub(super) fn blocked(game: &mut Game<'_>, pos: [i32; 3], face: [i32; 3], stack: &ItemStack) -> bool {
    if face == [0, -1, 0] || game.native_sneaking() || !game.may_build()
        || !is_cloth(stack.item.as_ref()) || !is_cloth(&game.native_block(pos)) {
        return false;
    }
    let blocked = placement_edge(game, pos, pos.map(|p| f64::from(p) + 0.5)).is_none();
    if blocked {
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    blocked
}

pub(super) const ENTITY: &str = "create:table_cloth";

pub(super) fn stateful(block: &str, stateful: &mut bool) {
    *stateful |= is_cloth(block);
}

pub(super) fn entity_from_state(
    block: &str,
    properties: &horizon_world::block_state_properties::BlockProperties,
    entity: &mut Option<(String, horizon_world::nbt::Compound)>,
) {
    if is_cloth(block) && properties.get("entity").is_some_and(|v| v == "true") && entity.is_none() {
        *entity = Some((ENTITY.into(), Default::default()));
    }
}

fn stacks(nbt: &horizon_world::nbt::Compound) -> Vec<ItemStack> {
    use horizon_world::nbt::Tag;
    match nbt.get(&"Items".into()) {
        Some(Tag::List(items)) => items.iter().filter_map(|item| match item {
            Tag::Compound(data) => ItemStack::from_nbt(data),
            _ => None,
        }).collect(),
        _ => Vec::new(),
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], face: [i32; 3]) -> bool {
    use horizon_world::nbt::Tag;
    use horizon_world::level::flags;
    if face == [0, -1, 0] || !is_cloth(&game.native_block(pos)) || !game.may_build() {
        return false;
    }
    let held = game.held().cloned();
    if held.as_ref().is_some_and(|stack| is_cloth(stack.item.as_ref())) {
        return false;
    }
    let active = game.native_block_property(pos, "entity").as_deref() == Some("true");
    if !active && (game.native_sneaking() || held.is_none()) {
        return false;
    }
    if game.hand != horizon_client::first_person::Hand::Main {
        return true;
    }
    if !game.native_authoritative() {
        return true;
    }
    game.ensure_stateful_entity_table();
    if !active && !game.native_set_block_property_with(pos, "entity", "true", flags::UPDATE_ALL) {
        return true;
    }
    let facing = ((f64::from(game.yaw) / 90.0 + 0.5).floor() as i32 + 2).rem_euclid(4);
    let changed = game.native_with_mod_block_entity(pos, |entity| {
        let mut items = stacks(&entity.nbt);
        let returned = if let Some(mut stack) = held.clone() {
            if items.len() >= 4 { return None; }
            stack.count = 1;
            items.push(stack);
            entity.nbt.insert("Facing".into(), Tag::Int(facing));
            None
        } else {
            if items.is_empty() { return None; }
            items.pop()
        };
        let empty = items.is_empty();
        entity.nbt.insert("Items".into(), Tag::List(items.iter().map(super::create_depot::encode).collect()));
        Some((returned, empty))
    }).flatten();
    let Some((returned, empty)) = changed else { return true; };
    if held.is_some() {
        if let Some(stack) = game.held_mut() {
            stack.count -= 1;
            if stack.count == 0 { *game.held_mut() = None; }
        }
    } else if let Some(stack) = returned {
        *game.held_mut() = Some(stack);
    }
    let sound = if held.is_some() { "minecraft:entity.item_frame.add_item" } else { "minecraft:entity.item_frame.remove_item" };
    game.native_play_sound_in_place(sound, pos.map(|n| f64::from(n) + 0.5), 4, 0.5, 1.0);
    if empty {
        game.world.block_entities.remove(&(pos[0], pos[1], pos[2]));
        game.native_set_block_property_with(pos, "entity", "false", flags::UPDATE_ALL);
    } else {
        game.native_block_entity_sync(pos);
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    game.swing_arm();
    true
}

pub(super) fn remove(level: &mut super::GameLevel<'_>, pos: horizon_core::position::BlockPos, side_effects: bool) {
    if !side_effects || !level.native_authoritative { return; }
    let Some(horizon_client::containers::BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z)) else { return; };
    if entity.id != ENTITY { return; }
    let items = stacks(&entity.nbt).into_iter().map(Some).collect();
    level.drop_lost_contents(pos, items);
}

pub(super) fn render(game: &Game<'_>, pos: [i32; 3], entity: &horizon_client::containers::ModBlockEntity, draw: &mut super::native_block_entity_draw::BlockEntityDraw) {
    use horizon_assets::item_model::DisplayContext;
    let items = stacks(&entity.nbt);
    if items.is_empty() { return; }
    let facing = super::create_machines::int(&entity.nbt, "Facing").unwrap_or(0).rem_euclid(4);
    let rotation = 180.0 - facing as f32 * 90.0;
    draw.push();
    draw.rotate_about([0.0, 1.0, 0.0], rotation, [0.5, 0.5, 0.5]);
    for (i, stack) in items.iter().enumerate() {
        draw.push();
        draw.translate([0.5, 3.0 / 16.0, 0.5]);
        if items.len() > 1 {
            let angle = i as f32 * 360.0 / items.len() as f32 + 45.0;
            draw.rotate_about([0.0, 1.0, 0.0], angle, [0.0; 3]);
            draw.translate([0.0, if i % 2 == 0 { -0.005 } else { 0.0 }, 5.0 / 16.0]);
            draw.rotate_about([0.0, 1.0, 0.0], -angle, [0.0; 3]);
        }
        let block = game.items().get(&stack.item).is_some_and(|info| info.block.is_some());
        if block {
            draw.translate([0.0, 1.0 / 16.0, 0.0]);
            draw.scale([0.755; 3]);
        } else {
            let camera = game.player.as_ref().map_or([0.0; 3], |p| [p.position.x, p.position.y, p.position.z]);
            let x = f64::from(pos[0]) + 0.5 - camera[0];
            let z = f64::from(pos[2]) + 0.5 - camera[2];
            draw.rotate_about([0.0, 1.0, 0.0], -rotation + 180.0 + (x.atan2(z).to_degrees() as f32 + 180.0), [0.0; 3]);
            draw.translate([0.0, 3.0 / 32.0, -1.0 / 16.0]);
            draw.scale([0.5; 3]);
        }
        game.native_draw_item(draw, stack, DisplayContext::Fixed, None, 0);
        draw.pop();
    }
    draw.pop();
}

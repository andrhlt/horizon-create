use horizon_assets::item_model::DisplayContext;
use horizon_core::position::BlockPos;
use horizon_world::nbt::{Compound, JavaString, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;

use super::create_ejector::{self, EJECTOR};
use super::create_machines::{float, int, mod_entity, offset, set_float};
use super::create_spout::{self, Action as SpoutAction};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const DEPOT: &str = "create:depot";
pub(super) const NIXIE: &str = "create:nixie_tube";

pub(super) fn nixie_palette(block: &str) -> Option<(u32, u32)> {
    Some(match block {
        "create:white_nixie_tube" => (0xedeae5, 0xbbb6b0),
        "create:nixie_tube" => (0xee9246, 0xd94927),
        "create:magenta_nixie_tube" => (0xf062b0, 0xc04488),
        "create:light_blue_nixie_tube" => (0x69ced2, 0x508aa5),
        "create:yellow_nixie_tube" => (0xe6d756, 0xe9ac29),
        "create:lime_nixie_tube" => (0xa3df55, 0x4fb16f),
        "create:pink_nixie_tube" => (0xd5a8cb, 0xb86b95),
        "create:gray_nixie_tube" => (0x5d666f, 0x313538),
        "create:light_gray_nixie_tube" => (0x95969b, 0x707070),
        "create:cyan_nixie_tube" => (0x3eabb4, 0x3c7872),
        "create:purple_nixie_tube" => (0x9f54ae, 0x63366c),
        "create:blue_nixie_tube" => (0x5391e1, 0x504b90),
        "create:brown_nixie_tube" => (0xac855c, 0x68533e),
        "create:green_nixie_tube" => (0x208a46, 0x1d6045),
        "create:red_nixie_tube" => (0xb13937, 0x632737),
        "create:black_nixie_tube" => (0x45403b, 0x21201f),
        _ => return None,
    })
}

pub(super) fn nixie_click(game: &mut Game<'_>, pos: [i32; 3], canceled: &mut bool) {
    use horizon_client::first_person::Hand;
    use horizon_world::level::flags;

    if *canceled
        || !game.native_authoritative()
        || game.hand != Hand::Main
        || game.native_sneaking()
        || nixie_palette(&game.native_block(pos)).is_none()
        || mod_entity(game, pos).is_none()
    {
        return;
    }
    let Some(held) = game.held() else {
        if !mod_entity(game, pos).is_some_and(|tube| tube.nbt.contains_key(&"CustomText".into())) {
            return;
        }
        let power = game.native_neighbor_signal(game.dim.id(), pos);
        game.native_with_mod_block_entity(pos, |tube| {
            for key in ["RawCustomText", "CustomText", "CustomTextIndex"] {
                tube.nbt.remove(&key.into());
            }
            tube.nbt.insert("RedstoneStrength".into(), Tag::Int(power));
        });
        game.native_block_entity_sync(pos);
        *canceled = true;
        return;
    };
    if held.item.as_ref() == "minecraft:name_tag" {
        if let Some(name) = held.custom_name() {
            let serialized = serde_json::from_str::<serde_json::Value>(&name).map_or_else(
                |_| serde_json::json!({"text": name}).to_string(),
                |value| value.to_string(),
            );
            super::create_display_link::publish_nixie_text(game, pos, &serialized);
            *canceled = true;
        }
        return;
    }
    let Some(color) = held
        .item
        .strip_prefix("minecraft:")
        .and_then(|id| id.strip_suffix("_dye"))
    else {
        return;
    };
    let target = if color == "orange" {
        NIXIE.to_owned()
    } else {
        format!("create:{color}_nixie_tube")
    };
    if nixie_palette(&target).is_none() {
        return;
    }
    let Some(mut replacement) = game.native_default_state(&target) else {
        return;
    };
    for key in ["double_face", "facing", "waterlogged"] {
        let Some(value) = game.native_block_property(pos, key) else {
            return;
        };
        let Some(state) = game
            .with_level(|_, level, _| level.native_state_with_property(replacement, key, &value))
        else {
            return;
        };
        replacement = state;
    }
    for at in super::create_display_link::nixie_row(game, pos) {
        if game.world.block(at[0], at[1], at[2]) == replacement {
            continue;
        }
        let retained = mod_entity(game, at).cloned();
        if game.native_set_block(game.native_dimension(), at, replacement, flags::UPDATE_ALL)
            && let Some(retained) = retained
        {
            game.native_with_mod_block_entity(at, |tube| *tube = retained);
            game.native_block_entity_sync(at);
        }
    }
    *canceled = true;
}

pub(super) fn compound<'a>(parent: &'a Compound, key: &str) -> Option<&'a Compound> {
    if let Tag::Compound(value) = parent.get(&JavaString::from(key))? {
        Some(value)
    } else {
        None
    }
}

fn legacy_stack(entity: &ModBlockEntity) -> Option<ItemStack> {
    ItemStack::from_nbt(compound(compound(&entity.nbt, "HeldItem")?, "Item")?)
}

pub(super) fn encode(stack: &ItemStack) -> Tag {
    let Tag::List(mut items) = horizon_client::save::encode_items(&[Some(stack.clone())]) else {
        return Tag::Compound(Compound::new());
    };
    items
        .pop()
        .unwrap_or_else(|| Tag::Compound(Compound::new()))
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3], face: [i32; 3], canceled: &mut bool) {
    if *canceled || face != [0, 1, 0] || !matches!(game.native_block(pos).as_str(), DEPOT | EJECTOR)
    {
        return;
    }
    // A top-face use consumes the first hand in Java. Do not swap the
    // Depot's contents back out when a client also sends the off-hand use.
    if game.hand != horizon_client::first_person::Hand::Main {
        *canceled = true;
        return;
    }
    if game.native_block(pos) == EJECTOR
        && !mod_entity(game, pos).is_some_and(create_ejector::charged)
    {
        return;
    }
    let held = game.held().cloned();
    if game.native_sneaking()
        && held
            .as_ref()
            .is_some_and(|stack| super::create_press::assembly_operator(&stack.item))
    {
        return;
    }
    let Some(old) = game.native_with_mod_block_entity(pos, |depot| {
        // A player can use a newly placed Depot before its first tick sizes the container.
        if depot.items.is_empty() {
            depot.items.push(None);
        }
        let old = depot
            .items
            .first()
            .and_then(Option::as_ref)
            .cloned()
            .or_else(|| legacy_stack(depot));
        depot.nbt.remove(&JavaString::from("HeldItem"));
        let mut pickup = vec![old];
        for slot in depot.items.iter_mut().skip(1) {
            pickup.push(slot.take());
        }
        depot.items[0] = held.clone();
        set_float(&mut depot.nbt, "BeltPosition", 0.25);
        depot.nbt.remove(&JavaString::from("PressLocked"));
        super::create_fan::clear(&mut depot.nbt);
        pickup
    }) else {
        return;
    };
    if old.iter().all(Option::is_none) && held.is_none() {
        return;
    }
    *game.held_mut() = None;
    for left in old
        .into_iter()
        .flatten()
        .filter_map(|stack| game.give(stack))
        .collect::<Vec<_>>()
    {
        let block = BlockPos::new(pos[0], pos[1], pos[2]);
        game.with_level(|_, level, _| level.drop_lost_contents(block, vec![Some(left)]));
    }
    game.native_block_entity_sync(pos);
    if held.is_some() {
        play_slide(game, pos);
    }
    game.swing_arm();
    *canceled = true;
}

pub(super) fn play_slide(game: &mut Game<'_>, pos: [i32; 3]) {
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    game.native_play_sound_in_place("create:depot_slide", at, 4, 0.125, 1.5);
}

fn play_plop(game: &mut Game<'_>, pos: [i32; 3]) {
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    game.native_play_sound_in_place("create:depot_plop", at, 4, 0.25, 1.25);
}

pub(super) fn receiver_empty(entity: &ModBlockEntity) -> bool {
    !entity.items.is_empty()
        && entity.items.iter().all(Option::is_none)
        && legacy_stack(entity).is_none()
}

/// Belt transfers offer a whole stack, unlike the hopper's one-item moves.
pub(super) fn receive_stack(
    game: &mut Game<'_>,
    pos: [i32; 3],
    stack: ItemStack,
) -> Option<ItemStack> {
    receive_stack_at(game, pos, stack, 0.0)
}

pub(super) fn receive_landed_stack(
    game: &mut Game<'_>,
    pos: [i32; 3],
    stack: ItemStack,
) -> Option<ItemStack> {
    let count = stack.count;
    let remaining = receive_stack_at(game, pos, stack, 0.5);
    if remaining.as_ref().map_or(0, |stack| stack.count) < count {
        game.native_block_entity_sync(pos);
        play_plop(game, pos);
    }
    remaining
}

fn receive_stack_at(
    game: &mut Game<'_>,
    pos: [i32; 3],
    mut stack: ItemStack,
    belt_position: f32,
) -> Option<ItemStack> {
    let limit = game.native_max_stack_size(&stack.item).unwrap_or(64);
    let inserted = game
        .native_with_mod_block_entity(pos, |entity| {
            if !matches!(entity.id.as_str(), DEPOT | EJECTOR)
                || entity.id == EJECTOR && !create_ejector::charged(entity)
                || !receiver_empty(entity)
            {
                return 0;
            }
            let count = stack.count.min(limit);
            entity.items[0] = Some(ItemStack {
                count,
                ..stack.clone()
            });
            set_float(&mut entity.nbt, "BeltPosition", belt_position);
            count
        })
        .unwrap_or(0);
    stack.count -= inserted;
    (stack.count != 0).then_some(stack)
}

pub(super) fn tick_depot(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    if entity.items.is_empty() {
        return;
    }
    if entity.items[0].is_none() {
        let legacy = legacy_stack(entity);
        if legacy.is_some()
            && game.native_block(offset(pos, [0, 2, 0])) == super::create_spout::SPOUT
            && let Some(position) =
                compound(&entity.nbt, "HeldItem").and_then(|saved| float(saved, "Pos"))
        {
            set_float(&mut entity.nbt, "BeltPosition", position);
        }
        entity.items[0] = legacy;
    }
    entity.nbt.remove(&JavaString::from("HeldItem"));
    if entity.items[0].is_none() {
        super::create_machines::collect_landed_items(game, pos, &mut entity.items[0], DEPOT);
        if entity.items[0].is_some() {
            set_float(&mut entity.nbt, "BeltPosition", 0.5);
            play_plop(game, pos);
        }
    }
    if entity.items[0].is_some() {
        let position = float(&entity.nbt, "BeltPosition").unwrap_or(0.0);
        let difference = 0.5 - position;
        if difference > 1.0 / 512.0 {
            set_float(&mut entity.nbt, "BeltPosition", position + difference / 4.0);
        }
        let centered = difference < 1.0 / 16.0;
        let above = offset(pos, [0, 1, 0]);
        let pulled = centered
            && super::create_belt_funnel::outlet(game, above).is_some_and(|face| {
                super::create_belt_funnel::pull_first(game, above, face, &mut entity.items)
            });
        if centered && !pulled {
            let spout = offset(pos, [0, 2, 0]);
            let spout_locked = int(&entity.nbt, "SpoutLocked") == Some(1);
            let action = create_spout::offer(
                game,
                spout,
                entity.items[0].as_mut().expect("held item"),
                spout_locked,
            );
            if matches!(action, SpoutAction::Hold) {
                entity.nbt.insert("SpoutLocked".into(), Tag::Byte(1));
            } else {
                entity.nbt.remove(&"SpoutLocked".into());
            }
            if let SpoutAction::Output(output) = action {
                if entity.items[0]
                    .as_ref()
                    .is_some_and(|stack| stack.count == 0)
                {
                    entity.items[0] = Some(output);
                } else {
                    let limit = game.native_max_stack_size(&output.item).unwrap_or(64);
                    let remaining =
                        super::create_machines::insert(&mut entity.items[1..], &output, limit);
                    if remaining != 0 {
                        let position = pos.map(|n| f64::from(n) + 0.5);
                        game.add_item_entity(
                            ItemStack {
                                count: remaining,
                                ..output
                            },
                            position,
                            None,
                            10,
                        );
                    }
                }
            }
            super::create_press::receive(game, pos, entity);
        } else if !centered {
            entity.nbt.remove(&"SpoutLocked".into());
        }
    } else {
        entity.nbt.remove(&JavaString::from("BeltPosition"));
        entity.nbt.remove(&"SpoutLocked".into());
        entity.nbt.remove(&JavaString::from("PressLocked"));
        super::create_fan::clear(&mut entity.nbt);
    }
    // Compare an encoded stack so a same-size replacement also updates viewers.
    let shown = entity.items[0].as_ref().map(encode);
    let key = JavaString::from("DepotItem");
    if shown.as_ref() == entity.nbt.get(&key) {
        return;
    }
    match shown {
        Some(shown) => {
            entity.nbt.insert(key, shown);
        }
        None => {
            entity.nbt.remove(&key);
        }
    }
    game.native_block_entity_sync(pos);
}

pub(super) fn has_output(level: &GameLevel<'_>, state: BlockStateId, out: &mut bool) {
    *out |= level
        .registry
        .state(state)
        .is_some_and(|block| matches!(block.name.as_str(), DEPOT | EJECTOR));
}

pub(super) fn output(level: &GameLevel<'_>, pos: BlockPos, state: BlockStateId, out: &mut i32) {
    let Some(block) = level.registry.state(state) else {
        return;
    };
    if !matches!(block.name.as_str(), DEPOT | EJECTOR) {
        return;
    }
    let Some(BlockEntity::Mod(depot)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    else {
        return;
    };
    let saved = legacy_stack(depot);
    let held = depot
        .items
        .first()
        .and_then(Option::as_ref)
        .or(saved.as_ref());
    let max = if block.name == EJECTOR {
        let configured = create_ejector::stack_size(Some(depot)) as u32;
        if configured == 0 { 64 } else { configured }
    } else {
        held.map_or(64, |stack| {
            level
                .items
                .get(&stack.item)
                .map_or(64, |item| item.max_stack)
                .max(1)
        })
    };
    let count = held.map_or(0, |stack| stack.count)
        + depot
            .items
            .iter()
            .skip(1)
            .flatten()
            .map(|stack| stack.count)
            .sum::<u32>();
    *out = if count == 0 {
        0
    } else {
        ((count * 14) / max + 1).min(15) as i32
    };
}

pub(super) fn tick_nixies(game: &mut Game<'_>) {
    let ticking = game.block_ticking_area();
    let nixies: Vec<_> = game
        .world
        .block_entity_tickers()
        .iter()
        .filter_map(|entry| {
            let (x, y, z) = entry.0;
            let pos = [x, y, z];
            let entity = mod_entity(game, pos)?;
            (ticking(x, z) && entity.id == NIXIE && !entity.nbt.contains_key(&"CustomText".into()))
                .then(|| (pos, int(&entity.nbt, "RedstoneStrength").unwrap_or(0)))
        })
        .collect();
    for (pos, before) in nixies {
        let power = game.native_neighbor_signal(game.dim.id(), pos);
        if power == before {
            continue;
        }
        game.native_with_mod_block_entity(pos, |entity| {
            entity
                .nbt
                .insert("RedstoneStrength".into(), Tag::Int(power));
        });
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Option<Compound> {
    let mut result = Compound::new();
    match entity.id.as_str() {
        DEPOT => {
            let item = entity.items.first().and_then(Option::as_ref);
            let wire = item
                .map(encode)
                .or_else(|| legacy_stack(entity).as_ref().map(encode))
                .unwrap_or_else(|| Tag::Compound(Compound::new()));
            result.insert("DepotItem".into(), wire);
        }
        NIXIE => {
            let power = int(&entity.nbt, "RedstoneStrength").unwrap_or(0);
            result.insert("RedstoneStrength".into(), Tag::Int(power));
            for key in ["CustomText", "CustomTextIndex"] {
                if let Some(value) = entity.nbt.get(&key.into()) {
                    result.insert(key.into(), value.clone());
                }
            }
        }
        _ => return None,
    }
    Some(result)
}

pub(super) fn render(
    game: &Game<'_>,
    block: &str,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    if block == DEPOT {
        let Some(stack) = compound(&entity.nbt, "DepotItem").and_then(ItemStack::from_nbt) else {
            return;
        };
        draw.push();
        draw.translate([0.5, 0.886, 0.5]);
        draw.rotate_about([1.0, 0.0, 0.0], 90.0, [0.0; 3]);
        draw.scale([0.55; 3]);
        game.native_draw_item(draw, &stack, DisplayContext::Fixed, None, 0);
        draw.pop();
    } else if let Some((bright, dark)) = nixie_palette(block) {
        let power = int(&entity.nbt, "RedstoneStrength").unwrap_or(0);
        let face = game.native_block_state_property(state, "double_face");
        let yaw = match game.native_block_state_property(state, "facing") {
            Some("north") => 90.0,
            Some("east") => 180.0,
            Some("west") => 0.0,
            _ => -90.0,
        };
        let (yaw, roll, height) = match face {
            Some("wall") => (yaw, -90.0, 0.15),
            Some("wall_reversed") => (yaw + 180.0, 90.0, 0.15),
            Some("ceiling") => (yaw, 0.0, 0.25),
            _ => (yaw, 0.0, 0.15),
        };
        let custom = super::create_display_link::nixie_text(&entity.nbt);
        let start = if custom.is_some() {
            int(&entity.nbt, "CustomTextIndex").unwrap_or(0).max(0) as usize * 2
        } else {
            0
        };
        let text = custom.unwrap_or_else(|| format!("{power:02}"));
        for (i, digit) in text.chars().skip(start).take(2).enumerate() {
            let digit = digit.to_string();
            let x = (game.native_text_width(&digit) - 0.5) / -2.0;
            let text = horizon_client::text::Text::from(digit);
            draw.push();
            draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.5; 3]);
            draw.rotate_about([0.0, 0.0, 1.0], roll, [0.5; 3]);
            draw.translate([0.25 + i as f32 * 0.5, 0.5 + height, 0.5]);
            draw.scale([0.05, -0.05, 0.05]);
            game.native_draw_text(draw, &text, [x, 0.0], bright, true, 0);
            draw.push();
            draw.translate([0.5, 0.5, -0.0625]);
            game.native_draw_text(draw, &text, [x, 0.0], dark, true, 0);
            draw.pop();
            draw.scale([-1.0, 1.0, 1.0]);
            game.native_draw_text(draw, &text, [x, 0.0], dark, true, 0);
            draw.pop();
        }
        static TRACE: std::sync::OnceLock<bool> = std::sync::OnceLock::new();
        if *TRACE.get_or_init(|| std::env::var_os("HORIZON_CREATE_NIXIE_TRACE").is_some()) {
            eprintln!("CREATE_NIXIE_PALETTE {block},{bright:06x},{dark:06x}");
        }
    }
}

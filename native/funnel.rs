use horizon_core::geometry::{Direction, Vec3};
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, PlacementContext, flags};
use horizon_world::nbt::Tag;
use horizon_world::registry::BlockStateId;

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::create_belt::BELT;
use super::create_belt_funnel;
use super::create_fan::facing;
use super::create_item_filters::accepts;
use super::create_machines::{int, mod_entity, offset};
use super::{Game, GameLevel};

pub(super) const ANDESITE: &str = "create:andesite_funnel";
pub(super) const BRASS: &str = "create:brass_funnel";

pub(super) fn is_funnel_item(item: &str) -> bool {
    matches!(item, ANDESITE | BRASS)
}

fn collecting(game: &mut Game<'_>, pos: [i32; 3], state: BlockStateId) -> Option<Direction> {
    if !matches!(game.native_state_block(state), Some(ANDESITE | BRASS))
        || game.native_block_state_property(state, "extracting") == Some("true")
        || create_belt_funnel::power(game, pos)
    {
        return None;
    }
    facing(game, state)
}

pub(super) fn package_opening(
    game: &mut Game<'_>,
    pos: [i32; 3],
    at: Vec3,
    stack: &ItemStack,
) -> Option<(Direction, Vec3)> {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let face = collecting(game, pos, state)?;
    let normal = face.normal();
    let axis = normal.iter().position(|&value| value != 0)?;
    let mouth: [f64; 3] =
        std::array::from_fn(|i| f64::from(pos[i]) + 0.5 - f64::from(normal[i]) / 8.0);
    if ((at.components()[axis] - mouth[axis]) < 0.0) == (normal[axis] > 0)
        || !mod_entity(game, pos).is_some_and(|funnel| accepts(game.items(), &funnel.nbt, stack))
    {
        return None;
    }
    let y_offset = if face == Direction::Up { 0.25 } else { -0.5 };
    Some((face, Vec3::new(mouth[0], mouth[1] + y_offset, mouth[2])))
}

pub(super) fn offer(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: Direction,
    stack: ItemStack,
) -> Option<ItemStack> {
    if !mod_entity(game, pos).is_some_and(|funnel| accepts(game.items(), &funnel.nbt, &stack)) {
        return Some(stack);
    }
    let target = offset(pos, face.opposite().normal());
    let remainder = if game.native_block(target) == BELT {
        let Some((start, index, movement, speed)) = super::create_belt::feed_point(game, target)
        else {
            return Some(stack);
        };
        // A funnel inserts through the belt segment's inventory, which uses
        // the top insertion position regardless of the attached face.
        if !super::create_belt::can_feed(game, start, index, movement, Direction::Up, speed) {
            return Some(stack);
        }
        super::create_belt::feed(
            game,
            start,
            index,
            movement,
            Direction::Up,
            speed,
            stack.clone(),
        );
        None
    } else {
        super::create_creative_crate::insert(game, target, face, stack.clone())
    };
    let moved = stack.count - remainder.as_ref().map_or(0, |rest| rest.count);
    if moved > 0 {
        super::create_smart_observer::funnel_transfer(
            game,
            pos,
            &ItemStack {
                count: moved,
                ..stack
            },
        );
        if face.normal()[1] == 0 {
            super::create_funnel_flap::received(game, pos);
        }
    }
    remainder
}

pub(super) fn loose_items(game: &mut Game<'_>) {
    for i in (0..game.dropped.len()).rev() {
        let item = &game.dropped[i];
        let at = [item.position.x, item.position.y, item.position.z];
        let pos = at.map(|n| n.floor() as i32);
        let state = game.world.block(pos[0], pos[1], pos[2]);
        let Some(face) = collecting(game, pos, state) else {
            continue;
        };
        let normal = face.normal();
        let projected: f64 = (0..3)
            .map(|axis| (at[axis] - f64::from(pos[axis]) - 0.5) * f64::from(normal[axis]))
            .sum();
        if projected < -0.25 {
            continue;
        }
        let stack = game.dropped[i].stack.clone();
        let remainder = offer(game, pos, face, stack);
        if let Some(remainder) = remainder {
            game.dropped[i].stack = remainder;
        } else {
            game.remove_dropped(i);
        }
    }
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let powered = create_belt_funnel::power(game, pos);
    if (game.native_block_property(pos, "powered").as_deref() == Some("true")) != powered {
        game.native_set_block_property_with(
            pos,
            "powered",
            if powered { "true" } else { "false" },
            2,
        );
    }
    if powered {
        entity.nbt.insert("TransferCooldown".into(), Tag::Int(0));
        return;
    }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    if game.native_block_state_property(state, "extracting") != Some("true") {
        return;
    }
    let Some(face) = facing(game, state) else {
        return;
    };
    let cooldown = int(&entity.nbt, "TransferCooldown").unwrap_or(0);
    if cooldown > 0 {
        entity
            .nbt
            .insert("TransferCooldown".into(), Tag::Int(cooldown - 1));
        return;
    }

    let [x, y, z] = pos.map(f64::from);
    let lower = [x, if face == Direction::Up { y } else { y - 1.0 }, z];
    if !game
        .native_item_entities(game.native_dimension(), lower, [x + 1.0, y + 1.0, z + 1.0])
        .is_empty()
    {
        return;
    }
    let supply = offset(pos, face.opposite().normal());
    let block = game.native_block(pos);
    let (limit, exact) = create_belt_funnel::amount(&block, entity);
    let Some(stack) = create_belt_funnel::extract(game, supply, face, entity, limit, exact) else {
        return;
    };
    let normal = face.normal().map(f64::from);
    let away = if face == Direction::Up {
        0.15
    } else if face == Direction::Down {
        0.5
    } else {
        0.25
    };
    let mut drop = [
        x + 0.5 + normal[0] * away,
        y + 0.5 + normal[1] * away,
        z + 0.5 + normal[2] * away,
    ];
    if normal[1] == 0.0 {
        drop[1] -= 0.45;
    }
    let motion = [0.0, if face == Direction::Up { 0.25 } else { 0.0 }, 0.0];
    super::create_smart_observer::funnel_transfer(game, pos, &stack);
    super::create_funnel_flap::pushed(game, pos, entity);
    game.add_item_entity(stack, drop, Some(motion), 10);
    entity.nbt.insert(
        "TransferCooldown".into(),
        Tag::Int(create_belt_funnel::COOLDOWN),
    );
}

fn label(face: Direction) -> &'static str {
    match face {
        Direction::Up => "up",
        Direction::Down => "down",
        Direction::North => "north",
        Direction::South => "south",
        Direction::East => "east",
        Direction::West => "west",
    }
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    ctx: &PlacementContext,
) -> Option<BlockStateId> {
    let mut placed = level.registry.state(state)?.clone();
    if !matches!(placed.name.as_str(), ANDESITE | BRASS) {
        return None;
    }
    placed
        .properties
        .insert("facing".into(), label(ctx.face).into());
    placed
        .properties
        .insert("extracting".into(), (!ctx.sneaking).to_string());
    let pos = ctx.pos;
    let occupying = level
        .registry
        .state(level.world.block(pos.x, pos.y, pos.z))?;
    placed.properties.insert(
        "waterlogged".into(),
        (occupying.name == "minecraft:water").to_string(),
    );
    level.registry.id(&placed)
}

pub(super) fn shape_after_neighbour(
    level: &GameLevel<'_>,
    pos: BlockPos,
    state: BlockStateId,
    direction: Direction,
) -> Option<BlockStateId> {
    let current = level.registry.state(state)?;
    let (plain, mounted, on_belt) = match current.name.as_str() {
        ANDESITE => (ANDESITE, create_belt_funnel::ANDESITE, false),
        BRASS => (BRASS, create_belt_funnel::BRASS, false),
        create_belt_funnel::ANDESITE => (ANDESITE, create_belt_funnel::ANDESITE, true),
        create_belt_funnel::BRASS => (BRASS, create_belt_funnel::BRASS, true),
        _ => return None,
    };
    let face = current.properties.get("facing")?;
    if !on_belt && (direction != Direction::Down || matches!(face.as_str(), "up" | "down")) {
        return Some(state);
    }
    let below = level
        .registry
        .state(level.world.block(pos.x, pos.y - 1, pos.z))?;
    let is_belt = below.name == BELT;
    let valid_belt = is_belt
        && matches!(
            below.properties.get("slope").map(String::as_str),
            Some("horizontal" | "upward" | "downward")
        );
    let supported = valid_belt
        || matches!(
            below.name.as_str(),
            super::create_depot::DEPOT
                | super::create_ejector::EJECTOR
                | super::create_item_drain::DRAIN
        )
        || (below.name == super::create_saw::SAW
            && below
                .properties
                .get("facing")
                .is_some_and(|side| side == "up"));
    let was_extracting = if on_belt {
        current
            .properties
            .get("shape")
            .is_some_and(|shape| shape == "pushing")
    } else {
        current
            .properties
            .get("extracting")
            .is_some_and(|value| value == "true")
    };
    let (block, key, value) = if supported {
        let aligned = valid_belt
            && below.properties.get("facing").is_some_and(|belt_face| {
                matches!(belt_face.as_str(), "east" | "west")
                    == matches!(face.as_str(), "east" | "west")
            });
        let shape = if aligned {
            if current
                .properties
                .get("shape")
                .is_some_and(|shape| shape == "extended")
            {
                return Some(state);
            }
            "retracted"
        } else if was_extracting {
            "pushing"
        } else {
            "pulling"
        };
        (mounted, "shape", shape)
    } else if on_belt {
        (
            plain,
            "extracting",
            if was_extracting { "true" } else { "false" },
        )
    } else {
        return Some(state);
    };
    let mut updated = if current.name == block {
        current.clone()
    } else {
        let mut updated = level
            .registry
            .state(level.registry.default_state(block)?)?
            .clone();
        for key in ["facing", "powered", "waterlogged"] {
            if let Some(value) = current.properties.get(key) {
                updated.properties.insert(key.into(), value.clone());
            }
        }
        updated
    };
    if current.name == block
        && current
            .properties
            .get(key)
            .is_some_and(|current| current == value)
    {
        return Some(state);
    }
    updated.properties.insert(key.into(), value.into());
    level.registry.id(&updated)
}

fn place_belt_funnel(
    game: &mut Game<'_>,
    clicked: [i32; 3],
    normal: [i32; 3],
    block: &str,
) -> bool {
    if !game.may_build() {
        return false;
    }
    let pos = offset(clicked, normal);
    let below = offset(pos, Direction::Down.normal());
    let support = game.native_block(below);
    let transport_belt = support == BELT
        && matches!(
            game.native_block_property(below, "slope").as_deref(),
            Some("horizontal" | "upward" | "downward")
        );
    let stationary = normal[1] == 0
        && matches!(
            support.as_str(),
            super::create_depot::DEPOT | super::create_ejector::EJECTOR
        );
    if !transport_belt && !stationary {
        return false;
    }
    let old = game.world.block(pos[0], pos[1], pos[2]);
    if !game.res.behaviours().is_replaceable(old) {
        return false;
    }
    let face = if normal[1] == 0 {
        Direction::ALL
            .into_iter()
            .find(|face| face.normal() == normal)
    } else {
        [
            Direction::South,
            Direction::West,
            Direction::North,
            Direction::East,
        ]
        .get((game.yaw / 90.0).round().rem_euclid(4.0) as usize)
        .copied()
    };
    let Some(face) = face else { return false };
    let belt_is_x = game
        .native_block_property(below, "facing")
        .is_some_and(|facing| matches!(facing.as_str(), "east" | "west"));
    let sneaking = game.keys.held(super::Mapping::Sneak);
    let shape = if transport_belt && belt_is_x == (face.normal()[0] != 0) {
        "retracted"
    } else if sneaking {
        "pulling"
    } else {
        "pushing"
    };
    let wet = game.native_block(pos) == "minecraft:water";
    let target = if block == BRASS {
        create_belt_funnel::BRASS
    } else {
        create_belt_funnel::ANDESITE
    };
    let Some(placement) = game.with_level(|_, level, _| {
        let mut state = level
            .registry
            .state(level.registry.default_state(target)?)?
            .clone();
        state.properties.insert("shape".into(), shape.into());
        state.properties.insert("facing".into(), label(face).into());
        state
            .properties
            .insert("waterlogged".into(), wet.to_string());
        let state = level.registry.id(&state)?;
        level
            .is_unobstructed(BlockPos::new(pos[0], pos[1], pos[2]), state)
            .then_some(state)
    }) else {
        return false;
    };
    if game.native_set_block(game.native_dimension(), pos, placement, flags::UPDATE_ALL) {
        game.consume_held();
        return true;
    }
    false
}

pub(super) fn wrench_mode(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> bool {
    let (key, next) = match block {
        ANDESITE | BRASS => {
            let extracting =
                game.native_block_property(pos, "extracting").as_deref() == Some("true");
            ("extracting", if extracting { "false" } else { "true" })
        }
        create_belt_funnel::ANDESITE | create_belt_funnel::BRASS => {
            let next = match game.native_block_property(pos, "shape").as_deref() {
                Some("pulling") => "pushing",
                Some("pushing") => "pulling",
                Some("extended") => "retracted",
                Some("retracted") => {
                    let below = offset(pos, [0, -1, 0]);
                    if game.native_block(below) == BELT
                        && game.native_block_property(below, "slope").as_deref()
                            != Some("horizontal")
                    {
                        return true;
                    }
                    "extended"
                }
                _ => return false,
            };
            ("shape", next)
        }
        _ => return false,
    };
    if game.native_authoritative() {
        game.native_set_block_property_with(pos, key, next, flags::UPDATE_ALL);
        if next == "extended" {
            award_funnel_kiss(game, pos);
        }
    }
    true
}

fn award_funnel_kiss(game: &mut Game<'_>, pos: [i32; 3]) {
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(direction) = facing(game, state) else {
        return;
    };
    let [x, y, z] = offset(pos, direction.normal());
    let other = game.world.block(x, y, z);
    if matches!(
        game.native_state_block(other),
        Some(create_belt_funnel::ANDESITE | create_belt_funnel::BRASS)
    ) && game.native_block_state_property(other, "shape") == Some("extended")
        && facing(game, other) == Some(direction.opposite())
    {
        let player = game.native_acting_id();
        game.native_trigger_criterion(player, "create:belt_funnel_kiss_builtin", |_| true);
    }
}

pub(super) fn use_item(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    held: &ItemStack,
) -> bool {
    if held.item.as_ref() == "create:wrench" {
        return false;
    }
    if matches!(held.item.as_ref(), ANDESITE | BRASS)
        && place_belt_funnel(game, pos, face, &held.item)
    {
        return true;
    }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let Some(direction) = collecting(game, pos, state) else {
        return false;
    };
    if direction.normal() != face {
        return false;
    }
    let remainder = offer(game, pos, direction, held.clone());
    if remainder
        .as_ref()
        .is_some_and(|rest| rest.count == held.count)
    {
        return false;
    }
    *game.held_mut() = remainder;
    true
}

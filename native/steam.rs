use std::collections::BTreeSet;

use horizon_core::geometry::Direction;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;

use super::Game;
use super::create_depot::compound;
use super::create_fluid_tank::{CREATIVE, TANK};
use super::create_machines::{float, int, mod_entity, offset, set_float};

pub(super) const ENGINE: &str = "create:steam_engine";
pub(super) const SHAFT: &str = "create:powered_shaft";
const SAMPLE_RATE: i32 = 5;
const WINDOW: usize = 10;

fn facing(game: &Game<'_>, pos: [i32; 3]) -> Option<Direction> {
    match game.native_block_property(pos, "face")?.as_str() {
        "floor" => Some(Direction::Up),
        "ceiling" => Some(Direction::Down),
        "wall" => super::create_fan::facing(game, game.world.block(pos[0], pos[1], pos[2])),
        _ => None,
    }
}

fn attached_engines(game: &Game<'_>, parts: &[[i32; 3]]) -> BTreeSet<[i32; 3]> {
    let mut attached = BTreeSet::new();
    for &pos in parts {
        for direction in Direction::ALL {
            let engine = offset(pos, direction.normal());
            if game.native_block(engine) == ENGINE && facing(game, engine) == Some(direction) {
                attached.insert(engine);
            }
        }
    }
    attached
}

fn attached_whistles(game: &Game<'_>, parts: &[[i32; 3]]) -> BTreeSet<[i32; 3]> {
    let mut attached = BTreeSet::new();
    for &tank in parts {
        for direction in Direction::ALL {
            let at = offset(tank, direction.normal());
            if game.native_block(at) == super::create_steam_whistle::WHISTLE
                && super::create_steam_whistle_audio::attached(game, at)
                    == Some(direction.opposite())
            {
                attached.insert(at);
            }
        }
    }
    attached
}

fn heat(game: &Game<'_>, root: [i32; 3], width: usize) -> (i32, bool) {
    let mut active = 0;
    let mut passive = false;
    for x in 0..width as i32 {
        for z in 0..width as i32 {
            let heater = offset(root, [x, -1, z]);
            let name = game.native_block(heater);
            match name.as_str() {
                "create:blaze_burner" => {
                    match game.native_block_property(heater, "blaze").as_deref() {
                        Some("seething") => active += 2,
                        Some("kindled" | "fading") => active += 1,
                        Some("smouldering") => passive = true,
                        _ => {}
                    }
                }
                "create:lit_blaze_burner" => passive = true,
                "minecraft:campfire" | "minecraft:soul_campfire"
                    if game.native_block_property(heater, "lit").as_deref() == Some("true") =>
                {
                    passive = true;
                }
                "minecraft:magma_block"
                | "minecraft:lava"
                | "minecraft:fire"
                | "minecraft:soul_fire" => {
                    passive = true;
                }
                _ => {}
            }
        }
    }
    (active, passive && active == 0)
}

pub(super) fn accepts_water(game: &Game<'_>, root: [i32; 3]) -> bool {
    mod_entity(game, root)
        .and_then(|entity| compound(&entity.nbt, "Boiler"))
        .is_some_and(|boiler| {
            int(boiler, "Engines").unwrap_or(0) + int(boiler, "Whistles").unwrap_or(0) > 0
        })
}

pub(super) fn boiler_fill(game: &mut Game<'_>, root: [i32; 3], id: &str, amount: i32, execute: bool) -> i32 {
    if !matches!(id, "minecraft:water" | "minecraft:flowing_water") { return 0; }
    let amount = amount.max(0);
    if execute { feed_water(game, root, amount); }
    amount
}

pub(super) fn feed_water(game: &mut Game<'_>, root: [i32; 3], amount: i32) {
    game.native_with_mod_block_entity(root, |entity| {
        let gathered = int(&entity.nbt, "BoilerIntake").unwrap_or(0);
        entity
            .nbt
            .insert("BoilerIntake".into(), Tag::Int(gathered + amount));
    });
}

pub(super) fn boiler(
    game: &mut Game<'_>,
    root: [i32; 3],
    entity: &mut ModBlockEntity,
    width: usize,
    parts: &[[i32; 3]],
) {
    let previous = entity
        .nbt
        .insert("LastKnownPos".into(), Tag::IntArray(root.to_vec()));
    if matches!(previous, Some(Tag::IntArray(previous)) if previous.as_slice() != root) {
        // A moved tank drops its old controller for one tick before reconnecting.
        let mut boiler = Compound::new();
        set_float(&mut boiler, "Supply", 0.0);
        boiler.insert("Engines".into(), Tag::Int(0));
        boiler.insert("ActiveHeat".into(), Tag::Int(0));
        boiler.insert("PassiveHeat".into(), Tag::Byte(0));
        entity.nbt.insert("Boiler".into(), Tag::Compound(boiler));
        entity.nbt.remove(&"BoilerIntake".into());
        entity.nbt.remove(&"BoilerWindow".into());
        entity.nbt.remove(&"BoilerSample".into());
        entity.nbt.remove(&"BoilerIndex".into());
        return;
    }
    let engines = attached_engines(game, parts).len() as i32;
    let whistles = attached_whistles(game, parts).len() as i32;
    let mut boiler = compound(&entity.nbt, "Boiler").cloned().unwrap_or_default();
    let was_active = int(&boiler, "Engines").unwrap_or(0) + int(&boiler, "Whistles").unwrap_or(0) > 0;
    if !was_active && engines + whistles > 0 {
        entity.nbt.insert("Window".into(), Tag::Byte(0));
    }
    if engines + whistles == 0 {
        if int(&boiler, "Engines").unwrap_or(0) + int(&boiler, "Whistles").unwrap_or(0) > 0 {
            entity.nbt.remove(&"BoilerIntake".into());
            entity.nbt.remove(&"BoilerWindow".into());
            entity.nbt.remove(&"BoilerSample".into());
            entity.nbt.remove(&"BoilerIndex".into());
            entity.nbt.remove(&"Boiler".into());
        }
        return;
    }

    let (active, passive) = heat(game, root, width);
    boiler.insert("Engines".into(), Tag::Int(engines));
    boiler.insert("Whistles".into(), Tag::Int(whistles));
    boiler.insert("ActiveHeat".into(), Tag::Int(active));
    boiler.insert("PassiveHeat".into(), Tag::Byte(i8::from(passive)));

    let remaining = int(&entity.nbt, "BoilerSample").unwrap_or(1) - 1;
    if remaining > 0 {
        entity
            .nbt
            .insert("BoilerSample".into(), Tag::Int(remaining));
    } else {
        let previous = float(&boiler, "Supply").unwrap_or(0.0);
        let mut window = match entity.nbt.get(&"BoilerWindow".into()) {
            Some(Tag::IntArray(values)) if values.len() == WINDOW => values.clone(),
            _ => vec![(previous * SAMPLE_RATE as f32) as i32; WINDOW],
        };
        let index = (int(&entity.nbt, "BoilerIndex").unwrap_or(0) as usize) % WINDOW;
        window[index] = int(&entity.nbt, "BoilerIntake").unwrap_or(0);
        let next = (index + 1) % WINDOW;
        let supply = if entity.id == CREATIVE {
            200.0
        } else if next == 0 {
            *window.iter().max().expect("boiler sample window") as f32 / SAMPLE_RATE as f32
        } else {
            previous.max(window[index] as f32 / SAMPLE_RATE as f32)
        };
        set_float(&mut boiler, "Supply", supply);
        entity
            .nbt
            .insert("BoilerWindow".into(), Tag::IntArray(window));
        entity
            .nbt
            .insert("BoilerIndex".into(), Tag::Int(next as i32));
        entity
            .nbt
            .insert("BoilerSample".into(), Tag::Int(SAMPLE_RATE));
        entity.nbt.remove(&"BoilerIntake".into());
    }
    entity.nbt.insert("Boiler".into(), Tag::Compound(boiler));
}

fn efficiency(game: &Game<'_>, tank: [i32; 3]) -> f32 {
    if !matches!(game.native_block(tank).as_str(), TANK | CREATIVE) {
        return 0.0;
    }
    let Some((_, parts)) = super::create_fluid_tank::parts(game, tank) else {
        return 0.0;
    };
    let Some(boiler) = parts
        .first()
        .and_then(|root| mod_entity(game, *root))
        .and_then(|entity| compound(&entity.nbt, "Boiler"))
    else {
        return 0.0;
    };
    let engines = int(boiler, "Engines").unwrap_or(0);
    let size = (parts.len() as i32 / 4).min(18);
    let water = (float(boiler, "Supply").unwrap_or(0.0).ceil() as i32 / 10).min(18);
    if engines == 0 || size == 0 || water == 0 {
        0.0
    } else if int(boiler, "PassiveHeat") == Some(1) {
        0.125 / engines as f32
    } else {
        let heat = int(boiler, "ActiveHeat").unwrap_or(0).min(water).min(size);
        (heat as f32 / engines as f32).min(1.0)
    }
}

pub(super) fn shaft_power(game: &Game<'_>, pos: [i32; 3], axis: usize) -> (f32, f32, i32) {
    for direction in Direction::ALL {
        if direction.normal()[axis] != 0 {
            continue;
        }
        let engine = offset(pos, direction.opposite().normal().map(|n| n * 2));
        if game.native_block(engine) != ENGINE || facing(game, engine) != Some(direction) {
            continue;
        }
        let tank = offset(engine, direction.opposite().normal());
        let power = efficiency(game, tank);
        let direction = if axis == 1 || power == 0.0 {
            1
        } else {
            let horizontal = if direction.normal()[1] != 0 {
                super::create_fan::facing(game, game.world.block(engine[0], engine[1], engine[2]))
                    .unwrap_or(direction)
            } else {
                direction
            };
            horizontal.normal().iter().sum::<i32>()
        };
        let mut rotation = if axis == 2 { -direction } else { direction };
        if mod_entity(game, engine).is_some_and(|e| int(&e.nbt, "ScrollValue") == Some(1)) {
            rotation *= -1;
        }
        let multiplier = if power >= 1.0 {
            4.0
        } else {
            1.0 + (power * 4.0).floor().min(2.0)
        };
        let speed = if power > 0.0 {
            rotation as f32 * 16.0 * multiplier
        } else {
            0.0
        };
        return (speed, power, rotation);
    }
    (0.0, 0.0, 1)
}

pub(super) fn generator(game: &Game<'_>, pos: [i32; 3], axis: usize) -> (f32, f32) {
    let (rpm, power, _) = shaft_power(game, pos, axis);
    let capacity = if rpm == 0.0 {
        0.0
    } else {
        power * 16384.0 / rpm.abs()
    };
    (rpm, capacity)
}

const PISTON: &str = "create:block/steam_engine/piston";
const LINKAGE: &str = "create:block/steam_engine/linkage";
const CONNECTOR: &str = "create:block/steam_engine/shaft_connector";

pub(super) fn models(models: &mut Vec<String>) {
    models.extend([PISTON, LINKAGE, CONNECTOR].map(String::from));
}

fn target_shaft(game: &Game<'_>, engine: [i32; 3]) -> Option<([i32; 3], usize)> {
    let facing = facing(game, engine)?;
    let shaft = offset(engine, facing.normal().map(|n| n * 2));
    if game.native_block(shaft) != SHAFT {
        return None;
    }
    let axis = super::create_machines::axis_index(&game.native_block_property(shaft, "axis")?)?;
    (facing.normal()[axis] == 0).then_some((shaft, axis))
}

pub(super) fn tick_engine(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let (axis, speed) = target_shaft(game, pos).map_or((-1, 0.0), |(shaft, axis)| {
        (axis as i32, super::create_machines::rpm_at(game, shaft))
    });
    if int(&entity.nbt, "VisualAxis") != Some(axis)
        || float(&entity.nbt, "VisualSpeed") != Some(speed)
    {
        entity.nbt.insert("VisualAxis".into(), Tag::Int(axis));
        set_float(&mut entity.nbt, "VisualSpeed", speed);
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut tag = Compound::new();
    tag.insert(
        "VisualAxis".into(),
        Tag::Int(int(&entity.nbt, "VisualAxis").unwrap_or(-1)),
    );
    set_float(
        &mut tag,
        "VisualSpeed",
        float(&entity.nbt, "VisualSpeed").unwrap_or(0.0),
    );
    tag
}

pub(super) fn render(
    game: &Game<'_>,
    pos: [i32; 3],
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    use super::create_visuals::wheel_angle;
    use horizon_core::geometry::trig;

    let Some(axis) = int(&entity.nbt, "VisualAxis").filter(|axis| (0..3).contains(axis)) else {
        return;
    };
    let Some(facing) = facing(game, pos) else {
        return;
    };
    let axis = axis as usize;
    let normal = facing.normal();
    let shaft = offset(pos, normal.map(|n| n * 2));
    let parity = (shaft[(axis + 1) % 3] + shaft[(axis + 2) % 3]) % 2;
    let phase =
        if parity == 0 { 22.5 } else { 0.0 } + if shaft[axis] % 2 == 0 { 180.0 } else { 0.0 };
    let rpm = float(&entity.nbt, "VisualSpeed").unwrap_or(0.0);
    let mut angle = wheel_angle(draw.game_time, draw.partial, rpm, phase).to_radians();
    if axis != 1 && ((normal[0] != 0) ^ normal.iter().sum::<i32>().is_positive()) {
        angle = -angle;
    }
    if axis == 0 && facing == Direction::Down {
        angle = -angle;
    }

    let sin = trig::sin(f64::from(angle));
    let cos = trig::cos(f64::from(angle));
    let rod = 14.0_f32 / 16.0;
    let crank = 6.0_f32 / 16.0;
    let piston = crank * sin - (rod * rod - (crank * cos).powi(2)).sqrt();
    let linkage = ((piston - crank * sin).abs() / rod)
        .clamp(-1.0, 1.0)
        .acos()
        .to_degrees()
        * if cos >= 0.0 { 1.0 } else { -1.0 };

    const X: [f32; 3] = [1.0, 0.0, 0.0];
    const Y: [f32; 3] = [0.0, 1.0, 0.0];
    const CENTER: [f32; 3] = [0.5; 3];

    let (yaw, pitch) = match facing {
        Direction::Up => (0.0, 0.0),
        Direction::Down => (0.0, 180.0),
        Direction::South => (0.0, 90.0),
        Direction::West => (90.0, 90.0),
        Direction::North => (180.0, 90.0),
        Direction::East => (270.0, 90.0),
    };
    draw.push();
    draw.rotate_about(Y, yaw, CENTER);
    draw.rotate_about(X, pitch, CENTER);
    if (normal[1] == 0 && axis == 1) || (normal[1] != 0 && axis == 2) {
        draw.rotate_about(Y, -90.0, CENTER);
    }
    draw.push();
    draw.translate([0.0, piston + 20.0 / 16.0, 0.0]);
    game.native_draw_model(draw, PISTON, 0xffffff);
    draw.translate([0.0, 1.0, 0.0]);
    draw.rotate_about(X, linkage, [0.0, 4.0 / 16.0, 0.5]);
    game.native_draw_model(draw, LINKAGE, 0xffffff);
    draw.pop();
    draw.translate([0.0, 2.0, 0.0]);
    draw.rotate_about(X, -(angle.to_degrees() + 90.0), CENTER);
    game.native_draw_model(draw, CONNECTOR, 0xffffff);
    draw.pop();
}

fn place_state(
    game: &mut Game<'_>,
    pos: [i32; 3],
    id: &str,
    properties: &[(&str, &str)],
    replace_shaft: bool,
) -> Option<horizon_world::registry::BlockStateId> {
    use horizon_core::position::BlockPos;
    use horizon_world::level::LevelAccess;

    let occupying = game.native_block(pos);
    game.with_level(|behaviours, level, _| {
        if !replace_shaft && !behaviours.is_replaceable(level.world.block(pos[0], pos[1], pos[2])) {
            return None;
        }
        let mut state = level
            .registry
            .state(level.registry.default_state(id)?)?
            .clone();
        for &(name, value) in properties {
            state.properties.insert(name.into(), value.into());
        }
        state.properties.insert(
            "waterlogged".into(),
            (occupying == "minecraft:water").to_string(),
        );
        let state = level.registry.id(&state)?;
        level
            .is_unobstructed(BlockPos::new(pos[0], pos[1], pos[2]), state)
            .then_some(state)
    })
}

fn orient_shaft(game: &Game<'_>, motor: Direction) -> &'static str {
    let pitch = f64::from(game.pitch).to_radians();
    let yaw = f64::from(game.yaw).to_radians();
    let look = [
        pitch.cos() * yaw.sin(),
        pitch.sin(),
        pitch.cos() * yaw.cos(),
    ]
    .map(f64::abs);
    let dir = motor.normal();
    let axis = (0..3)
        .filter(|&i| dir[i] == 0)
        .max_by(|&a, &b| look[a].total_cmp(&look[b]))
        .expect("perpendicular axis");
    ["x", "y", "z"][axis]
}

pub(super) fn use_item(
    game: &mut Game<'_>,
    clicked: [i32; 3],
    normal: [i32; 3],
    held: &crate::items::ItemStack,
) -> bool {
    use horizon_world::level::flags;

    match (held.item.as_ref(), game.native_block(clicked).as_str()) {
        (ENGINE, TANK | CREATIVE) => {
            let pos = offset(clicked, normal);
            let (face, horizontal) = match normal {
                [0, 1, 0] => ("floor", None),
                [0, -1, 0] => ("ceiling", None),
                [0, 0, 1] => ("wall", Some("south")),
                [0, 0, -1] => ("wall", Some("north")),
                [1, 0, 0] => ("wall", Some("east")),
                [-1, 0, 0] => ("wall", Some("west")),
                _ => return false,
            };
            let facing = horizontal.unwrap_or_else(|| {
                ["south", "west", "north", "east"]
                    [(game.yaw / 90.0).round().rem_euclid(4.0) as usize]
            });
            let Some(state) = place_state(
                game,
                pos,
                ENGINE,
                &[("face", face), ("facing", facing)],
                false,
            ) else {
                return false;
            };
            if !game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL) {
                return false;
            }
            game.consume_held();
            let shaft = offset(pos, normal.map(|n| n * 2));
            if game.native_block(shaft) == super::create_machines::SHAFT
                && let Some(axis) = game.native_block_property(shaft, "axis")
                && super::create_machines::axis_index(&axis).is_some_and(|axis| normal[axis] == 0)
                && let Some(state) = place_state(game, shaft, SHAFT, &[("axis", &axis)], true)
            {
                game.native_set_block(game.native_dimension(), shaft, state, flags::UPDATE_ALL);
            }
            true
        }
        (super::create_machines::SHAFT, ENGINE) => {
            let Some(direction) = facing(game, clicked) else {
                return false;
            };
            let shaft = offset(clicked, direction.normal().map(|n| n * 2));
            let axis = orient_shaft(game, direction);
            let Some(state) = place_state(game, shaft, SHAFT, &[("axis", axis)], false) else {
                return false;
            };
            if !game.native_set_block(game.native_dimension(), shaft, state, flags::UPDATE_ALL) {
                return false;
            }
            game.consume_held();
            true
        }
        _ => false,
    }
}

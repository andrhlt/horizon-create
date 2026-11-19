use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};

use super::create_bearing::{self as bearing, capture, capture_excluding, relative};
use super::create_fan::facing;
use super::create_machines::{float, int, offset, set_float};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

pub(super) const CLOCKWORK: &str = "create:clockwork_bearing";
pub(super) const TOP: &str = "create:block/bearing/top";

const HOUR: &str = "HourBlocks";
const MINUTE: &str = "MinuteBlocks";
const HOUR_ANGLE: &str = "HourAngle";
const MINUTE_ANGLE: &str = "MinuteAngle";
const SCHEDULED: &str = "AssembleNextTick";

struct Geometry {
    base: [i32; 3],
    face: Direction,
    axis: usize,
}

impl Geometry {
    fn from_face(base: [i32; 3], face: Direction) -> Self {
        let axis = face.normal().iter().position(|&step| step != 0).unwrap();
        Self { base, face, axis }
    }

    fn at(game: &Game<'_>, pos: [i32; 3]) -> Option<Self> {
        let face = facing(game, game.world.block(pos[0], pos[1], pos[2]))?;
        Some(Self::from_face(pos, face))
    }

    fn anchor(&self, offset: i32) -> [i32; 3] {
        std::array::from_fn(|i| self.base[i] + (offset + 1) * self.face.normal()[i])
    }

    fn sign(&self) -> i32 {
        self.face.normal()[self.axis]
    }
}

fn take_hand(entity: &mut ModBlockEntity, key: &str) -> Vec<Compound> {
    let Some(Tag::List(blocks)) = entity.nbt.remove(&key.into()) else {
        return Vec::new();
    };
    blocks
        .into_iter()
        .filter_map(|block| match block {
            Tag::Compound(block) => Some(block),
            _ => None,
        })
        .collect()
}

fn save_hand(entity: &mut ModBlockEntity, key: &str, blocks: Vec<Compound>) {
    if !blocks.is_empty() {
        entity.nbt.insert(
            key.into(),
            Tag::List(blocks.into_iter().map(Tag::Compound).collect()),
        );
    }
}

fn reset(entity: &mut ModBlockEntity, running: bool) {
    entity
        .nbt
        .insert("Running".into(), Tag::Byte(i8::from(running)));
    set_float(&mut entity.nbt, HOUR_ANGLE, 0.0);
    set_float(&mut entity.nbt, MINUTE_ANGLE, 0.0);
}

fn assemble(game: &mut Game<'_>, geo: &Geometry, entity: &mut ModBlockEntity) {
    let hour_anchor = geo.anchor(0);
    let mut hour = capture(game, geo.base, hour_anchor);
    if hour.is_empty() {
        return;
    }
    let Some(air) = game.native_default_state("minecraft:air") else {
        return;
    };
    let hour_world: Vec<_> = hour
        .iter()
        .map(|block| offset(hour_anchor, relative(block)))
        .collect();
    let minute_offset = (0..16)
        .find(|&i| !hour_world.contains(&geo.anchor(i)))
        .unwrap_or(0);
    let minute_anchor = geo.anchor(minute_offset);
    let mut minute = if minute_offset > 0 {
        capture_excluding(
            game,
            geo.base,
            minute_anchor,
            [minute_anchor],
            hour_world.iter().copied(),
        )
    } else {
        Vec::new()
    };
    let dimension = game.native_dimension();
    for pos in hour_world.into_iter().chain(
        minute
            .iter()
            .map(|block| offset(minute_anchor, relative(block))),
    ) {
        game.native_set_block(
            dimension,
            pos,
            air,
            flags::UPDATE_ALL | flags::UPDATE_SKIP_BLOCK_ENTITY_SIDEEFFECTS,
        );
    }
    bearing::show_saved_displays(game, hour_anchor, &mut hour, geo.axis, 0.0, 0.0);
    bearing::show_saved_displays(game, minute_anchor, &mut minute, geo.axis, 0.0, 0.0);
    save_hand(entity, HOUR, hour);
    save_hand(entity, MINUTE, minute);
    entity
        .nbt
        .insert("MinuteOffset".into(), Tag::Int(minute_offset));
    reset(entity, true);
}

fn disassemble(game: &mut Game<'_>, geo: &Geometry, entity: &mut ModBlockEntity) {
    let hour = take_hand(entity, HOUR);
    let minute = take_hand(entity, MINUTE);
    let mut hands = [
        (HOUR, HOUR_ANGLE, geo.anchor(0), hour),
        (
            MINUTE,
            MINUTE_ANGLE,
            geo.anchor(int(&entity.nbt, "MinuteOffset").unwrap_or(0)),
            minute,
        ),
    ];
    for (_, angle_key, anchor, blocks) in &mut hands {
        if blocks.is_empty() {
            continue;
        }
        let angle = f64::from(float(&entity.nbt, angle_key).unwrap_or(0.0)).to_radians();
        for block in blocks {
            bearing::resolve_saved_display(game, *anchor, block, geo.axis, angle);
            restore_block(game, *anchor, geo.axis, block);
        }
        game.native_play_sound_in_place(
            "create:contraption_disassemble",
            anchor.map(|coordinate| f64::from(coordinate) + 0.5),
            4,
            0.35,
            0.75,
        );
    }
    entity.nbt.remove(&"MinuteOffset".into());
    reset(entity, false);
}

fn restore_block(game: &mut Game<'_>, anchor: [i32; 3], axis: usize, block: &Compound) {
    let pos = offset(anchor, relative(block));
    let dimension = game.native_dimension();
    if let Some(state) = block
        .get(&"BlockState".into())
        .and_then(|tag| game.state_from_nbt(tag))
    {
        let existing = game.world.block(pos[0], pos[1], pos[2]);
        let behaviours = game.res.behaviours();
        let obstructed = behaviours.facts(existing).hardness < 0.0
            || behaviours
                .collision_shape(state)
                .is_some_and(|shape| shape.is_empty())
                && behaviours
                    .collision_shape(existing)
                    .is_some_and(|shape| !shape.is_empty());
        if !obstructed {
            if !behaviours.is_air(existing) {
                game.native_machine_destroy_block(pos, None, false);
            }
            if bearing::restore(game, anchor, std::slice::from_ref(block), axis, 0.0) {
                return;
            }
        }
        let at = BlockPos::new(pos[0], pos[1], pos[2]);
        game.with_level(|_, level, _| level.drop_resources_now(at, state));
    }
    if let Some(id) = int(block, "Display") {
        game.native_remove_entity(dimension, id as u32);
    }
}

fn clock_targets(day: i32, sign: i32, mode: i32) -> (f32, f32) {
    let hours = (day / 1000 + 6) % 24;
    let minutes = (day % 1000) * 60 / 1000;
    let cycle = if mode == 2 { 24 } else { 12 };
    let hour = (sign * -360) as f32 / cycle as f32 * (hours % cycle) as f32;
    let minute = (sign * -360) as f32 / 60.0 * minutes as f32;
    if mode == 1 {
        (minute, hour)
    } else {
        (hour, minute)
    }
}

fn next_angle(angle: f32, target: f32, speed: f32) -> f32 {
    if speed == 0.0 {
        return angle;
    }
    let delta =
        ((f64::from(target) % 360.0 - f64::from(angle) % 360.0) % 360.0 + 540.0) % 360.0 - 180.0;
    let advanced = (angle + (delta as f32).clamp(-speed, speed)) % 360.0;
    // Java's FloatTag stores either signed zero using its positive-zero tag.
    if advanced == 0.0 { 0.0 } else { advanced }
}

pub(super) fn schedule_assembly(entity: &mut ModBlockEntity) {
    entity.nbt.insert(SCHEDULED.into(), Tag::Byte(1));
}

pub(super) fn tick(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    previous: f32,
    rpm: f32,
) {
    let Some(geo) = Geometry::at(game, pos) else {
        return;
    };
    let running = int(&entity.nbt, "Running") == Some(1);
    let scheduled = entity.nbt.remove(&SCHEDULED.into()) == Some(Tag::Byte(1));
    if previous != rpm {
        schedule_assembly(entity);
    }
    if scheduled {
        if running && rpm == 0.0 {
            disassemble(game, &geo, entity);
        } else if !running {
            assemble(game, &geo, entity);
        }
    } else if running {
        let scale = if game.native_dimension() == "minecraft:overworld" {
            1
        } else {
            24
        };
        let day = (game.world.day_time.wrapping_mul(scale) % 24000) as i32;
        let mode = int(&entity.nbt, "ScrollValue").unwrap_or(0);
        let (hour, minute) = clock_targets(day, geo.sign(), mode);
        let speed = (rpm * 3.0 / 10.0).abs();
        let offset = int(&entity.nbt, "MinuteOffset").unwrap_or(0);
        for (blocks_key, angle_key, anchor, target, limit) in [
            (HOUR, HOUR_ANGLE, geo.anchor(0), hour, speed / 2.0),
            (MINUTE, MINUTE_ANGLE, geo.anchor(offset), minute, speed),
        ] {
            let mut blocks = take_hand(entity, blocks_key);
            let previous = float(&entity.nbt, angle_key).unwrap_or(0.0);
            let current = next_angle(previous, target, limit);
            bearing::show_saved_displays(game, anchor, &mut blocks, geo.axis, previous, current);
            set_float(&mut entity.nbt, angle_key, current);
            save_hand(entity, blocks_key, blocks);
        }
    }
    if running || scheduled || previous != rpm {
        game.native_block_entity_sync(pos);
    }
}

pub(super) fn set_mode(game: &mut Game<'_>, pos: [i32; 3], mode: i32) {
    let updated = game.native_with_mod_block_entity(pos, |entity| {
        if entity.id != CLOCKWORK || int(&entity.nbt, "ScrollValue").unwrap_or(0) == mode {
            return false;
        }
        entity
            .nbt
            .insert("ScrollValue".into(), Tag::Int(mode.clamp(0, 2)));
        true
    });
    if updated == Some(true) {
        game.native_block_entity_sync(pos);
    }
}

fn with_entity(
    game: &mut Game<'_>,
    pos: [i32; 3],
    apply: impl FnOnce(&mut Game<'_>, &mut ModBlockEntity),
) -> bool {
    let key = (pos[0], pos[1], pos[2]);
    let Some(mut entry) = game.world.block_entities.remove(&key) else {
        return false;
    };
    if let BlockEntity::Mod(entity) = &mut entry
        && entity.id == CLOCKWORK
    {
        apply(game, entity);
    }
    game.world.block_entities.insert(key, entry);
    game.world.modified.insert((pos[0] >> 4, pos[2] >> 4));
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn stop_after_wrench(game: &mut Game<'_>, pos: [i32; 3], prior: &str) {
    let Some(face) = Direction::ALL
        .into_iter()
        .find(|&side| super::create_fluids::name(side) == prior)
    else {
        return;
    };
    with_entity(game, pos, |game, entry| {
        if int(&entry.nbt, "Running") == Some(1) {
            disassemble(game, &Geometry::from_face(pos, face), entry);
        }
    });
}

struct RemovedClockwork {
    world: usize,
    geometry: Geometry,
    saved: Compound,
}

thread_local! {
    static REMOVED: std::cell::RefCell<Vec<RemovedClockwork>> =
        const { std::cell::RefCell::new(Vec::new()) };
}

pub(super) fn queue_removal(
    level: &GameLevel<'_>,
    pos: BlockPos,
    old: BlockStateId,
    side_effects: bool,
) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    let Some(state) = level
        .registry
        .state(old)
        .filter(|state| state.name == CLOCKWORK)
    else {
        return;
    };
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    else {
        return;
    };
    if int(&entity.nbt, "Running") != Some(1) {
        return;
    }
    let Some(face) = Direction::ALL.into_iter().find(|&side| {
        state
            .properties
            .get("facing")
            .is_some_and(|name| name == super::create_fluids::name(side))
    }) else {
        return;
    };
    let world = std::ptr::from_ref(&*level.world) as usize;
    let geometry = Geometry::from_face([pos.x, pos.y, pos.z], face);
    let saved = entity.nbt.clone();
    REMOVED.with_borrow_mut(|queue| {
        queue.push(RemovedClockwork {
            world,
            geometry,
            saved,
        })
    });
}

pub(super) fn restore_removed(game: &mut Game<'_>) {
    let world = std::ptr::from_ref(&game.world) as usize;
    let removed = REMOVED.with_borrow_mut(|queue| {
        queue
            .extract_if(.., |entry| entry.world == world)
            .collect::<Vec<_>>()
    });
    for removal in removed {
        let mut entity = ModBlockEntity::default();
        entity.nbt = removal.saved;
        disassemble(game, &removal.geometry, &mut entity);
    }
}

pub(super) fn click(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != CLOCKWORK
        || !game.may_build()
        || game.native_sneaking()
        || game.held().is_some()
    {
        return false;
    }
    if game.hand != horizon_client::first_person::Hand::Main {
        return true;
    }
    let Some(geo) = Geometry::at(game, pos) else {
        return false;
    };
    let used = with_entity(game, pos, |game, entity| {
        if int(&entity.nbt, "Running") == Some(1) {
            disassemble(game, &geo, entity);
        } else {
            schedule_assembly(entity);
        }
    });
    if used {
        game.swing_arm();
    }
    used
}

pub(super) fn update_tag(entity: &ModBlockEntity) -> Compound {
    let mut visual = Compound::new();
    for name in [HOUR_ANGLE, MINUTE_ANGLE, "Running", "ScrollValue", "Speed"] {
        if let Some(value) = entity.nbt.get(&name.into()) {
            visual.insert(name.into(), value.clone());
        }
    }
    visual
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let angle = float(&entity.nbt, HOUR_ANGLE).unwrap_or(0.0);
    let rpm = float(&entity.nbt, "Speed").unwrap_or(0.0);
    bearing::render_top(game, state, (angle, rpm), TOP, draw);
}

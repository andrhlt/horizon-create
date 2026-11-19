use horizon_core::position::BlockPos;
use horizon_core::random::RandomSource;

use horizon_world::level::{LevelEvent, flags};
use horizon_world::nbt::{Compound, Tag};
use serde::{Deserialize, Serialize};

use super::Game;
use super::create_bearing::{relative, rotate};
use super::create_depot::compound;
use super::create_elevator_floors::CONTACT;
use super::create_elevator_indicator::{play, trace_sound};
use super::create_machines::{float, int, mod_entity, offset, set_float, string};
use super::create_rope::Payload;
use super::native_entities::NativeDisplay;
use crate::containers::ModBlockEntity;

const CHANNEL: &str = "create:elevator_door_close";
const OPEN: &str = "minecraft:block.iron_door.open";
const CLOSE: &str = "minecraft:block.iron_door.close";
const PROGRESS: &str = "CreateElevatorDoorProgress";
const WORLD_START_TICK: &str = "CreateWorldDoorMotionTick";
const WORLD_START_PROGRESS: &str = "CreateWorldDoorMotionStart";
const WORLD_START_TARGET: &str = "CreateWorldDoorMotionOpen";
const WORLD_PREVIOUS_PROGRESS: &str = "CreateWorldDoorPreviousProgress";
const WORLD_CHASE_TARGET: &str = "CreateWorldDoorChaseTarget";
const TARGET_OPEN: &str = "CreateElevatorDoorTarget";
const COLLISION: &str = "CreateElevatorCollision";

#[derive(Clone, Copy, Default, PartialEq, Eq, Serialize, Deserialize)]
#[serde(rename_all = "UPPERCASE")]
pub(super) enum DoorMode {
    #[default]
    All,
    North,
    East,
    South,
    West,
    None,
}

impl DoorMode {
    pub(super) const VALUES: [Self; 6] = [
        Self::All,
        Self::North,
        Self::East,
        Self::South,
        Self::West,
        Self::None,
    ];

    fn key(self) -> &'static str {
        ["ALL", "NORTH", "EAST", "SOUTH", "WEST", "NONE"][self as usize]
    }

    pub(super) fn label(self) -> &'static str {
        ["Open All", "North", "East", "South", "West", "None"][self as usize]
    }

    pub(super) fn description(self) -> &'static str {
        match self {
            Self::All => "Open All Doors",
            Self::North => "North Side Only",
            Self::East => "East Side Only",
            Self::South => "South Side Only",
            Self::West => "West Side Only",
            Self::None => "Keep Doors Closed",
        }
    }

    pub(super) fn scroll(self, direction: f64) -> Self {
        Self::VALUES[(self as i32 + if direction < 0.0 { 1 } else { -1 }).clamp(0, 5) as usize]
    }

    pub(super) fn scroll_pitch(self) -> f32 {
        1.5 + 0.1 * self as usize as f32 / Self::VALUES.len() as f32
    }

    fn matches(self, face: Face) -> bool {
        matches!(self, Self::All) || self.key().eq_ignore_ascii_case(face.name())
    }
}

pub(super) fn mode(game: &Game<'_>, pos: [i32; 3]) -> DoorMode {
    mod_entity(game, pos)
        .and_then(|entity| string(&entity.nbt, "DoorControl"))
        .and_then(|key| DoorMode::VALUES.into_iter().find(|mode| mode.key() == key))
        .unwrap_or_default()
}

pub(super) fn write_mode(game: &mut Game<'_>, pos: [i32; 3], mode: DoorMode) {
    game.native_with_mod_block_entity(pos, |entity| {
        entity
            .nbt
            .insert("DoorControl".into(), Tag::String(mode.key().into()));
    });
}

pub(super) fn sliding(name: &str) -> bool {
    matches!(
        name,
        "create:andesite_door"
            | "create:brass_door"
            | "create:copper_door"
            | "create:train_door"
            | "create:framed_glass_door"
    )
}

#[derive(Clone, Copy)]
struct Face(usize);

impl Face {
    fn from_name(name: &str) -> Option<Self> {
        ["north", "east", "south", "west"]
            .iter()
            .position(|&s| s == name)
            .map(Self)
    }

    fn name(self) -> &'static str {
        ["north", "east", "south", "west"][self.0]
    }

    fn normal(self) -> [i32; 3] {
        [[0, 0, -1], [1, 0, 0], [0, 0, 1], [-1, 0, 0]][self.0]
    }

    fn axis(self) -> usize {
        [2, 0][self.0 % 2]
    }
}

struct Door {
    name: String,
    rel: [i32; 3],
    facing: Face,
    right: bool,
    open: bool,
    lower: bool,
    folded_model: Option<&'static str>,
}

impl Door {
    fn read(block: &Compound) -> Option<Self> {
        let state = compound(block, "BlockState")?;
        let name = string(state, "Name")?;
        if !sliding(&name) {
            return None;
        }
        let props = compound(state, "Properties")?;
        let folded_model = folding_model(&name);
        Some(Self {
            name,
            rel: relative(block),
            facing: Face::from_name(&string(props, "facing")?)?,
            right: string(props, "hinge").as_deref() == Some("right"),
            open: string(props, "open").as_deref() == Some("true"),
            lower: string(props, "half").as_deref() == Some("lower"),
            folded_model,
        })
    }

    // Java derives the outward side from the door plane and the cabin's bounds.
    fn outward(&self, center: [f64; 3]) -> Face {
        let axis = self.facing.axis();
        let plane = f64::from(self.rel[axis]) + 0.5
            - f64::from(self.facing.normal()[axis]) * f64::from(0.45_f32);
        Face(match (axis, plane < center[axis]) {
            (0, false) => 1,
            (0, true) => 3,
            (_, false) => 2,
            (_, true) => 0,
        })
    }

    fn slide_direction(&self) -> [i32; 3] {
        Face((self.facing.0 + if self.right { 1 } else { 3 }) % 4).normal()
    }

    fn shape(&self, open: bool) -> [f64; 6] {
        door_bounds(self.facing, self.right, open, self.folded_model.is_some())
    }
}

pub(super) fn folding_model(name: &str) -> Option<&'static str> {
    match name {
        "create:andesite_door" => Some("create:andesite_door_fold"),
        "create:copper_door" => Some("create:copper_door_fold"),
        _ => None,
    }
}

fn door_bounds(facing: Face, right: bool, open: bool, folding: bool) -> [f64; 6] {
    let face = facing.0;
    let hinge = usize::from(right);
    if !open {
        return [
            [0, 0, 13, 16, 16, 16],
            [0, 0, 0, 3, 16, 16],
            [0, 0, 0, 16, 16, 3],
            [13, 0, 0, 16, 16, 16],
        ][face]
            .map(|n| f64::from(n) / 16.0);
    }
    let index = [[7, 3], [0, 6], [5, 1], [2, 4]][face][hinge];
    let dims = if folding {
        [
            [0, 0, -3, 9, 16, 3],
            [-3, 0, 0, 3, 16, 9],
            [7, 0, 13, 16, 16, 19],
            [13, 0, 7, 19, 16, 16],
            [7, 0, -3, 16, 16, 3],
            [13, 0, 0, 19, 16, 9],
            [0, 0, 13, 9, 16, 19],
            [-3, 0, 7, 3, 16, 16],
        ]
    } else {
        [
            [0, 0, -13, 3, 16, 3],
            [-13, 0, 0, 3, 16, 3],
            [13, 0, 13, 16, 16, 29],
            [13, 0, 13, 29, 16, 16],
            [13, 0, -13, 16, 16, 3],
            [13, 0, 0, 29, 16, 3],
            [0, 0, 13, 3, 16, 29],
            [-13, 0, 13, 3, 16, 16],
        ]
    };
    dims[index].map(|n| f64::from(n) / 16.0)
}

pub(super) fn train_door_pick_shape(
    name: &str,
    open: bool,
    right: bool,
    facing: &str,
) -> Option<([f64; 3], [f64; 3])> {
    let shape = door_bounds(
        Face::from_name(facing)?,
        right,
        open,
        folding_model(name).is_some(),
    );
    Some((
        [shape[0], shape[1], shape[2]],
        [shape[3], shape[4], shape[5]],
    ))
}

pub(super) fn train_door_shape(cell: &Compound) -> Option<(bool, [f64; 3], [f64; 3])> {
    let door = Door::read(cell)?;
    let shape = door.shape(door.open);
    Some((
        door.open,
        [shape[0], shape[1], shape[2]],
        [shape[3], shape[4], shape[5]],
    ))
}

pub(super) fn toggle_train_door(blocks: &mut [Tag], pos: [i32; 3]) {
    let Some(door) = blocks.iter().find_map(|block| match block {
        Tag::Compound(cell) if relative(cell) == pos => Door::read(cell),
        _ => None,
    }) else {
        return;
    };

    // Java checks the adjacent leaf against the clicked leaf's new open state.
    let mate_side = Face((door.facing.0 + if door.right { 3 } else { 1 }) % 4);
    let mate_pos = offset(pos, mate_side.normal());
    let paired = blocks.iter().any(|block| {
        let Tag::Compound(cell) = block else {
            return false;
        };
        relative(cell) == mate_pos
            && Door::read(cell).is_some_and(|mate| {
                mate.name == door.name
                    && mate.facing.0 == door.facing.0
                    && mate.right != door.right
                    && mate.lower == door.lower
                    && mate.open == door.open
            })
    });
    let vertical = [0, if door.lower { 1 } else { -1 }, 0];
    let targets = [pos, offset(pos, vertical)];
    let mate_targets = [mate_pos, offset(mate_pos, vertical)];
    for block in blocks {
        if let Tag::Compound(cell) = block
            && (targets.contains(&relative(cell))
                || paired && mate_targets.contains(&relative(cell)))
            && let Some(leaf) = Door::read(cell)
        {
            write_open(cell, &leaf, !leaf.open);
        }
    }
}

fn property(state: &mut Compound, name: &str, value: &str) {
    if let Some(Tag::Compound(properties)) = state.get_mut(&"Properties".into()) {
        properties.insert(name.into(), Tag::String(value.into()));
    }
}

fn write_open(block: &mut Compound, door: &Door, open: bool) {
    if let Some(Tag::Compound(state)) = block.get_mut(&"BlockState".into()) {
        property(state, "open", if open { "true" } else { "false" });
    }
    let shape = door.shape(open);
    let bits = shape
        .into_iter()
        .enumerate()
        .map(|(i, n)| (n + f64::from(door.rel[i % 3])).to_bits() as i64)
        .collect();
    block.insert(COLLISION.into(), Tag::LongArray(bits));
}

pub(super) fn capture(blocks: &mut [Compound]) {
    for block in blocks {
        if let Some(door) = Door::read(block) {
            set_float(block, PROGRESS, if door.open { 1.0 } else { 0.0 });
        }
    }
}

pub(super) fn display_state(block: &Compound, state: &Compound) -> Compound {
    if float(block, PROGRESS).is_none() {
        return state.clone();
    }
    if let Some(door) = Door::read(block)
        && let Some(model) = door.folded_model
    {
        let pane = if door.lower ^ door.right {
            "left"
        } else {
            "right"
        };
        return Compound::from([
            ("Name".into(), Tag::String(model.into())),
            (
                "Properties".into(),
                Tag::Compound(Compound::from([("pane".into(), Tag::String(pane.into()))])),
            ),
        ]);
    }
    let mut model = state.clone();
    property(&mut model, "open", "false");
    property(&mut model, "visible", "true");
    model
}

fn set_landing_door(game: &mut Game<'_>, pos: [i32; 3], facing: Face, open: bool) {
    let name = game.native_block(pos);
    if !name.ends_with("_door") {
        return;
    }
    let Some(door_face) = game
        .native_block_property(pos, "facing")
        .and_then(|d| Face::from_name(&d))
    else {
        return;
    };
    if door_face.axis() != facing.axis()
        || game.native_block_property(pos, "open").as_deref()
            == Some(if open { "true" } else { "false" })
    {
        return;
    }
    let lower = game.native_block_property(pos, "half").as_deref() == Some("lower");
    let other = offset(pos, [0, if lower { 1 } else { -1 }, 0]);
    let value = if open { "true" } else { "false" };
    let at = pos.map(|n| f64::from(n) + 0.5);
    if !sliding(&name) {
        let block = BlockPos::new(pos[0], pos[1], pos[2]);
        let (changed, sound) = game.with_level(|behaviours, level, ticks| {
            let previous = level.events.len();
            let changed = behaviours.set_door_open(level, ticks, block, open);
            let sound = level.events[previous..]
                .iter()
                .find_map(|event| match event {
                    LevelEvent::Sound {
                        pos,
                        sound,
                        volume,
                        pitch,
                    } if *pos == block => Some((sound.clone(), *volume, *pitch)),
                    _ => None,
                });
            (changed, sound)
        });
        if changed && game.native_block(other) == name {
            game.native_set_block_property(other, "open", value);
        }
        if let Some((sound, volume, pitch)) = sound {
            let id = if sound.contains(':') {
                sound.to_string()
            } else {
                format!("minecraft:{sound}")
            };
            trace_sound(game, &id, at, volume, pitch);
        }
        return;
    }
    let mate = matching_world_mate(game, pos, &name, door_face, lower, open);
    for leaf in [Some(pos), mate].into_iter().flatten() {
        set_world_leaf(game, leaf, &name, lower, open);
    }
    // Java plays the other leaf's cue first, as setOpen recurses into it.
    for leaf in [mate, Some(pos)].into_iter().flatten() {
        let at = leaf.map(|n| f64::from(n) + 0.5);
        let pitch = 0.9 + 0.1 * game.world.random.next_float();
        let sound = if open { OPEN } else { CLOSE };
        play(game, sound, at, 1.0, pitch);
        let event = if open {
            "minecraft:block_open"
        } else {
            "minecraft:block_close"
        };
        game.post_block_game_event(event, leaf, None, None);
    }
}

fn matching_world_mate(
    game: &Game<'_>,
    pos: [i32; 3],
    name: &str,
    facing: Face,
    lower: bool,
    open: bool,
) -> Option<[i32; 3]> {
    let hinge = game.native_block_property(pos, "hinge")?;
    let side = Face((facing.0 + if hinge == "left" { 1 } else { 3 }) % 4);
    let mate = offset(pos, side.normal());
    (game.native_block(mate) == name
        && game.native_block_property(mate, "facing").as_deref() == Some(facing.name())
        && game.native_block_property(mate, "hinge").as_deref()
            == Some(if hinge == "left" { "right" } else { "left" })
        && game.native_block_property(mate, "half").as_deref()
            == Some(if lower { "lower" } else { "upper" })
        && game.native_block_property(mate, "open").as_deref()
            != Some(if open { "true" } else { "false" }))
    .then_some(mate)
}

fn world_other_half(game: &Game<'_>, pos: [i32; 3], name: &str, lower: bool) -> Option<[i32; 3]> {
    let other = offset(pos, [0, if lower { 1 } else { -1 }, 0]);
    (game.native_block(other) == name
        && game.native_block_property(other, "half").as_deref()
            == Some(if lower { "upper" } else { "lower" }))
    .then_some(other)
}

fn set_world_leaf(game: &mut Game<'_>, pos: [i32; 3], name: &str, lower: bool, open: bool) {
    let other = world_other_half(game, pos, name, lower);
    if let Some(base) = if lower { Some(pos) } else { other } {
        let tick = game.world.game_time;
        game.native_with_mod_block_entity(base, |entity| {
            stamp_world_door_motion(&mut entity.nbt, tick, open);
        });
        game.native_block_entity_sync(base);
    }
    for half in [Some(pos), other].into_iter().flatten() {
        let value = if open { "true" } else { "false" };
        game.native_set_block_property_with(half, "open", value, flags::UPDATE_CLIENTS);
        if open {
            game.native_set_block_property_with(half, "visible", "false", flags::UPDATE_CLIENTS);
        }
    }
}

pub(super) fn use_world_door(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let name = game.native_block(pos);
    if !sliding(&name) {
        return false;
    }
    let Some(facing) = game
        .native_block_property(pos, "facing")
        .and_then(|d| Face::from_name(&d))
    else {
        return false;
    };
    let lower = game.native_block_property(pos, "half").as_deref() == Some("lower");
    let open = game.native_block_property(pos, "open").as_deref() == Some("false");
    let mate = matching_world_mate(game, pos, &name, facing, lower, open);
    let event = if open {
        "minecraft:block_open"
    } else {
        "minecraft:block_close"
    };

    for leaf in [Some(pos), mate].into_iter().flatten() {
        set_world_leaf(game, leaf, &name, lower, open);
        game.post_block_game_event(event, leaf, None, None);
    }
    if open {
        let leaf = mate.unwrap_or(pos);
        let pitch = 0.9 + 0.1 * game.world.random.next_float();
        play(game, OPEN, leaf.map(|n| f64::from(n) + 0.5), 1.0, pitch);
        game.post_block_game_event(event, leaf, None, None);
    }
    true
}

pub(super) fn new_world_door(open: bool) -> Compound {
    let mut nbt = Compound::new();
    set_float(&mut nbt, PROGRESS, if open { 1.0 } else { 0.0 });
    nbt
}

pub(super) fn world_door_update(entity: &ModBlockEntity, tag: &mut Option<Compound>) {
    for key in [WORLD_START_TICK, WORLD_START_PROGRESS, WORLD_START_TARGET] {
        if let Some(value) = entity.nbt.get(&key.into()) {
            tag.get_or_insert_with(Compound::new)
                .insert(key.into(), value.clone());
        }
    }
}

fn chase_progress(prior: f32, open: bool) -> f32 {
    if open {
        (prior + 0.15).min(1.0)
    } else {
        (prior - 0.15).max(0.0)
    }
}

fn world_door_progress(nbt: &Compound, tick: i64, open: bool) -> (f32, f32) {
    let Some(Tag::Long(start)) = nbt.get(&WORLD_START_TICK.into()) else {
        let settled = if open { 1.0 } else { 0.0 };
        return (settled, settled);
    };
    let initial = float(nbt, WORLD_START_PROGRESS).unwrap_or(if open { 0.0 } else { 1.0 });
    // Java ticks the door animation in the same level tick as the use.
    let elapsed = tick.saturating_sub(*start).saturating_add(1).clamp(0, 8);
    let mut current = initial;
    let mut previous = initial;
    for _ in 0..elapsed {
        previous = current;
        current = chase_progress(current, open);
    }
    (previous, current)
}

fn world_door_target(nbt: &Compound) -> Option<bool> {
    if let Some(Tag::Byte(open)) = nbt.get(&WORLD_START_TARGET.into()) {
        Some(*open != 0)
    } else {
        None
    }
}

fn stamp_world_door_motion(nbt: &mut Compound, tick: i64, open: bool) {
    if world_door_target(nbt) == Some(open) {
        return;
    }
    let (_, prior) = world_door_progress(nbt, tick.saturating_sub(1), !open);
    set_float(nbt, WORLD_START_PROGRESS, prior);
    nbt.insert(WORLD_START_TICK.into(), Tag::Long(tick));
    nbt.insert(WORLD_START_TARGET.into(), Tag::Byte(i8::from(open)));
}

pub(super) fn sync_world_door_motion(
    game: &mut Game<'_>,
    pos: (i32, i32, i32),
    previous: Option<horizon_world::registry::BlockStateId>,
    state: horizon_world::registry::BlockStateId,
) {
    use horizon_client::containers::BlockEntity;

    let Some(previous) = previous else { return };
    let Some(name) = game.native_state_block(state) else {
        return;
    };
    if !sliding(name)
        || game.native_state_block(previous) != Some(name)
        || game.native_block_state_property(state, "half") != Some("lower")
    {
        return;
    }
    let open = game.native_block_state_property(state, "open") == Some("true");
    if open == (game.native_block_state_property(previous, "open") == Some("true")) {
        return;
    }
    let tick = game.world.game_time;
    if let Some(BlockEntity::Mod(entity)) = game.world.block_entities.get_mut(&pos) {
        // The state and its authoritative animation tag can reach the client
        // on separate frames. Start from the retained pose at the state edge.
        stamp_world_door_motion(&mut entity.nbt, tick, open);
    }
}

pub(super) fn render_world_door(
    game: &Game<'_>,
    pos: [i32; 3],
    name: &str,
    state: horizon_world::registry::BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    if game.native_block_state_property(state, "visible") != Some("false") {
        return;
    }
    let Some(facing) = game
        .native_block_state_property(state, "facing")
        .and_then(Face::from_name)
    else {
        return;
    };
    let right = game.native_block_state_property(state, "hinge") == Some("right");
    let open = game.native_block_state_property(state, "open") == Some("true");
    let (previous, current) = if world_door_target(&entity.nbt).is_some_and(|target| target != open)
    {
        let prior =
            float(&entity.nbt, WORLD_START_PROGRESS).unwrap_or(if open { 1.0 } else { 0.0 });
        (prior, prior)
    } else {
        world_door_progress(&entity.nbt, draw.game_time, open)
    };
    let openness = previous + (current - previous) * draw.partial;
    let trace = std::env::var_os("HORIZON_CREATE_WORLD_DOOR_TRACE").is_some();
    let mut door = Door {
        name: name.to_owned(),
        rel: pos,
        facing,
        right,
        open,
        lower: true,
        folded_model: folding_model(name),
    };
    if let Some(model) = door.folded_model {
        for lower in [true, false] {
            door.lower = lower;
            let pose = folding_pose(&door, openness, [0.0, if lower { 0.0 } else { 1.0 }, 0.0]);
            let [_, sin, _, cos] = pose.left_rotation;
            let degrees = 2.0 * sin.atan2(cos).to_degrees();
            draw.push();
            draw.translate(pose.translation);
            draw.rotate_about([0.0, 1.0, 0.0], degrees, [0.0; 3]);
            let pane = if lower ^ right { "left" } else { "right" };
            let before = if trace { draw.vertices_mut().len() } else { 0 };
            game.native_draw_block(draw, model, &[("pane", pane)]);
            if trace {
                let (sin, cos) = (degrees.to_radians() * 0.5).sin_cos();
                trace_world_panel(
                    draw,
                    &door,
                    pane,
                    pose.translation,
                    [sin, cos],
                    before,
                    (previous, current),
                );
            }
            draw.pop();
        }
    } else {
        let movement = door.slide_direction();
        let normal = facing.normal();
        let slide = openness * openness * 13.0 / 16.0;
        let depth = (openness * 10.0).min(1.0) / 32.0;
        for (height, half) in [(0.0, "lower"), (1.0 - 1.0 / 512.0, "upper")] {
            let mut offset =
                std::array::from_fn(|i| movement[i] as f32 * slide + normal[i] as f32 * depth);
            offset[1] += height;
            draw.push();
            draw.translate(offset);
            let before = if trace { draw.vertices_mut().len() } else { 0 };
            game.native_draw_block(
                draw,
                name,
                &[
                    ("facing", facing.name()),
                    ("half", half),
                    ("hinge", if right { "right" } else { "left" }),
                    ("open", "false"),
                    ("visible", "true"),
                ],
            );
            if trace {
                door.lower = half == "lower";
                trace_world_panel(
                    draw,
                    &door,
                    half,
                    offset,
                    [0.0, 1.0],
                    before,
                    (previous, current),
                );
            }
            draw.pop();
        }
    }
    if trace {
        let [x, y, z] = pos;
        eprintln!(
            "CREATE_WORLD_DOOR_DRAW {name},{},{x},{y},{z},{previous},{current}",
            draw.game_time
        );
    }
}

fn trace_world_panel(
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
    door: &Door,
    pane: &str,
    shift: [f32; 3],
    rotation: [f32; 2],
    before: usize,
    (previous, current): (f32, f32),
) {
    let [x, y, z] = door.rel;
    let [tx, ty, tz] = shift;
    let [sin, cos] = rotation;
    let tick = draw.game_time;
    let partial = draw.partial;
    let vertices = draw.vertices_mut().len() - before;
    eprintln!(
        "CREATE_WORLD_DOOR_PANEL {},{tick},{x},{y},{z},{},{},{pane},{partial},{tx},{ty},{tz},{sin},{cos},{vertices},{previous},{current}",
        door.name, door.open, door.lower
    );
}

pub(super) fn restore_world_doors(game: &mut Game<'_>, chunk: [i32; 2]) {
    use horizon_client::containers::BlockEntity;

    let [x, z] = chunk.map(|coord| f64::from(coord) * 16.0 + 8.0);
    let positions: Vec<_> = game
        .world
        .block_entities
        .mods_near(x, z, 0.0)
        .filter(|pos| {
            matches!(game.world.block_entities.get(pos), Some(BlockEntity::Mod(entity))
                     if sliding(&entity.id))
        })
        .copied()
        .collect();
    for (x, y, z) in positions {
        let pos = [x, y, z];
        let open = game.native_block_property(pos, "open").as_deref() == Some("true");
        game.native_with_mod_block_entity(pos, |entity| {
            // Java rebuilds the animation from the saved block's OPEN flag.
            // Neither an old interpolation interval nor its target is saved.
            for key in [
                WORLD_START_TICK,
                WORLD_START_PROGRESS,
                WORLD_START_TARGET,
                WORLD_PREVIOUS_PROGRESS,
                WORLD_CHASE_TARGET,
            ] {
                entity.nbt.remove(&key.into());
            }
            set_float(&mut entity.nbt, PROGRESS, if open { 1.0 } else { 0.0 });
        });
    }
}

fn world_door_animation_settled(previous: f32, current: f32, target: f32) -> bool {
    // Java's LerpedFloat requires both the interpolated endpoints and the
    // chase target to agree. The first tick at zero is still interpolating.
    (previous - current).abs() < 1.0e-5 && (current - target).abs() < 1.0e-5
}

pub(super) fn tick_world_door(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let open = game.native_block_property(pos, "open").as_deref() == Some("true");
    let target = if open { 1.0 } else { 0.0 };
    let prior = float(&entity.nbt, PROGRESS).unwrap_or(target);
    let previous = float(&entity.nbt, WORLD_PREVIOUS_PROGRESS).unwrap_or(prior);
    let previous_target = float(&entity.nbt, WORLD_CHASE_TARGET).unwrap_or(prior);
    let progress = chase_progress(prior, open);
    let was_settled = world_door_animation_settled(previous, prior, previous_target);
    let settled = world_door_animation_settled(prior, progress, target);
    if progress != prior {
        set_float(&mut entity.nbt, PROGRESS, progress);
    }
    if prior != previous || progress != prior {
        set_float(&mut entity.nbt, WORLD_PREVIOUS_PROGRESS, prior);
    }
    if target != previous_target {
        set_float(&mut entity.nbt, WORLD_CHASE_TARGET, target);
    }
    if open
        || was_settled
        || !settled
        || game.native_block_property(pos, "visible").as_deref() != Some("false")
    {
        return;
    }
    let name = game.native_block(pos);
    let upper = world_other_half(game, pos, &name, true);
    for half in [Some(pos), upper].into_iter().flatten() {
        game.native_set_block_property_with(half, "visible", "true", flags::UPDATE_ALL);
    }
    play(game, CLOSE, pos.map(|n| f64::from(n) + 0.5), 0.5, 1.0);
}

/// `SlidingDoorBlock.neighborChanged`: paired halves share either leaf's signal.
pub(super) fn world_door_neighbor(
    level: &mut super::GameLevel<'_>,
    ticks: &mut horizon_world::level::Ticks,
    pos: BlockPos,
    state: horizon_world::registry::BlockStateId,
) -> bool {
    use horizon_world::level::LevelAccess;
    let Some(block) = level.registry.state(state) else {
        return false;
    };
    if !sliding(&block.name) {
        return false;
    }
    let name = block.name.clone();
    let Some(facing) = block
        .properties
        .get("facing")
        .and_then(|s| Face::from_name(s))
    else {
        return true;
    };
    let lower = block.properties.get("half").is_some_and(|v| v == "lower");
    let open = block.properties.get("open").is_some_and(|v| v == "true");
    let prior_power = block.properties.get("powered").is_some_and(|v| v == "true");
    let right = block.properties.get("hinge").is_some_and(|v| v == "right");
    let side = Face((facing.0 + if right { 3 } else { 1 }) % 4);
    let [dx, _, dz] = side.normal();
    let mate_pos = pos.offset(dx, 0, dz);
    let mate_state = level.block_state(mate_pos);
    let mate = level.registry.state(mate_state).filter(|other| {
        other.name == name
            && other
                .properties
                .get("facing")
                .is_some_and(|v| v == facing.name())
            && other
                .properties
                .get("hinge")
                .is_some_and(|v| v == if right { "left" } else { "right" })
            && other
                .properties
                .get("half")
                .is_some_and(|v| v == if lower { "lower" } else { "upper" })
            && other
                .properties
                .get("open")
                .is_some_and(|v| (v == "true") == open)
    });
    let mate_pos = mate.map(|_| mate_pos);
    let vertical = if lower { 1 } else { -1 };
    let blocks = level.behaviours;
    let powered = blocks.has_neighbor_signal(level, ticks, pos)
        || blocks.has_neighbor_signal(level, ticks, pos.offset(0, vertical, 0))
        || mate_pos.is_some_and(|other| {
            blocks.has_neighbor_signal(level, ticks, other)
                || blocks.has_neighbor_signal(level, ticks, other.offset(0, vertical, 0))
        });
    if powered == prior_power {
        return true;
    }
    let value = if powered { "true" } else { "false" };
    let changed_open = powered != open;
    let update = |level: &super::GameLevel<'_>, state| {
        let mut next = level
            .native_state_with_property(state, "powered", value)
            .unwrap_or(state);
        next = level
            .native_state_with_property(next, "open", value)
            .unwrap_or(next);
        if powered {
            next = level
                .native_state_with_property(next, "visible", "false")
                .unwrap_or(next);
        }
        next
    };
    if changed_open {
        // Stamp before publishing OPEN, so both the owner and remote renderers
        // start the same motion on the state transition.
        let tick = level.world.game_time;
        for leaf in [Some(pos), mate_pos].into_iter().flatten() {
            let base = if lower { leaf } else { leaf.offset(0, -1, 0) };
            let key = (base.x, base.y, base.z);
            if let Some(crate::containers::BlockEntity::Mod(entity)) =
                level.world.block_entities.get_mut(&key)
            {
                stamp_world_door_motion(&mut entity.nbt, tick, powered);
                level.world.modified.insert((base.x >> 4, base.z >> 4));
                if let Some(log) = level.world.block_log.as_mut() {
                    log.push(key);
                }
            }
        }
        if let Some(other) = mate_pos {
            let next = update(level, mate_state);
            blocks.set_block(level, ticks, other, next, flags::UPDATE_CLIENTS);
        }
    }
    let next = update(level, state);
    blocks.set_block(level, ticks, pos, next, flags::UPDATE_CLIENTS);
    if changed_open {
        let sound = if powered { OPEN } else { CLOSE };
        let at = [pos.x, pos.y, pos.z].map(|n| f64::from(n) + 0.5);
        let pitch = 0.9 + 0.1 * level.world.random.next_float();
        if level.native_play_sound(sound, at, 4, 1.0, pitch)
            && std::env::var_os("HORIZON_CREATE_ELEVATOR_TRACE").is_some()
        {
            let [x, y, z] = at;
            eprintln!(
                "CREATE_ELEVATOR_SOUND {},{sound},{x},{y},{z},1,{pitch}",
                level.world.game_time
            );
        }
        level.events.push(LevelEvent::GameEvent {
            pos,
            event: if powered {
                "minecraft:block_open"
            } else {
                "minecraft:block_close"
            },
            state: None,
        });
    }
    true
}

/// A freestanding Create door's lower half does not require a supporting block.
pub(super) fn world_door_survives(
    level: &super::GameLevel<'_>,
    state: horizon_world::registry::BlockStateId,
) -> Option<bool> {
    let block = level.registry.state(state)?;
    (sliding(&block.name) && block.properties.get("half").is_some_and(|v| v == "lower"))
        .then_some(true)
}

fn center(blocks: &[Compound]) -> [f64; 3] {
    let (mut min, mut max) = ([0; 3], [1; 3]);
    for pos in blocks.iter().map(relative) {
        for axis in 0..3 {
            min[axis] = min[axis].min(pos[axis]);
            max[axis] = max[axis].max(pos[axis] + 1);
        }
    }
    std::array::from_fn(|axis| f64::from(min[axis] + max[axis]) / 2.0)
}

pub(super) fn tick(
    game: &mut Game<'_>,
    payload: &mut Payload,
    landing: Option<[i32; 3]>,
    at: [f64; 3],
    pulley: &mut Compound,
) {
    let Some(first) = payload
        .blocks
        .iter()
        .position(|block| Door::read(block).is_some())
    else {
        return;
    };
    let motion = match pulley.get(&"DoorMotion".into()) {
        Some(Tag::Double(bits)) => f64::from_bits(*bits),
        _ => 0.0,
    };
    let can_open = int(pulley, "DoorArrived") == Some(1) || motion.abs() < 1.0 / 128.0;
    if motion != 0.0 {
        pulley.insert("CabinHasMoved".into(), Tag::Byte(1));
    }
    let has_moved = int(pulley, "CabinHasMoved") == Some(1);
    // Create's movement context remembers its active contact until the door
    // can no longer open. That includes the first tick after leaving a floor.
    let mode = if can_open {
        let cached = match pulley.get(&"DoorContact".into()) {
            Some(Tag::IntArray(pos)) => pos.as_slice().try_into().ok(),
            _ => None,
        };
        cached
            .filter(|&pos| game.native_block(pos) == CONTACT)
            .or(landing.filter(|&pos| game.native_block(pos) == CONTACT))
            .map_or(DoorMode::None, |pos| {
                pulley.insert("DoorContact".into(), Tag::IntArray(pos.to_vec()));
                mode(game, pos)
            })
    } else {
        pulley.remove(&"DoorContact".into());
        DoorMode::None
    };
    let center = center(&payload.blocks);
    for index in first..payload.blocks.len() {
        let Some(door) = Door::read(&payload.blocks[index]) else {
            continue;
        };
        if !door.lower {
            continue;
        }
        let facing = door.outward(center);
        let should_open = mode.matches(facing);
        if should_open && !has_moved {
            continue;
        }
        let block = &mut payload.blocks[index];
        let prior = int(block, TARGET_OPEN);
        block.insert(TARGET_OPEN.into(), Tag::Byte(i8::from(should_open)));
        if door.open != should_open && prior != Some(i32::from(should_open)) {
            write_open(block, &door, should_open);
            let top = offset(door.rel, [0, 1, 0]);
            if let Some(upper) = payload.blocks.iter_mut().find(|cell| relative(cell) == top)
                && let Some(other) = Door::read(upper)
            {
                write_open(upper, &other, should_open);
            }
            let pos = std::array::from_fn(|i| at[i] + f64::from(door.rel[i]) + 0.5);
            set_landing_door(
                game,
                offset(pos.map(|n| n.floor() as i32), facing.normal()),
                facing,
                should_open,
            );
            if should_open {
                play(game, OPEN, pos, 0.125, 1.0);
            }
        }
    }
}

pub(super) fn animate(game: &mut Game<'_>, payload: &mut Payload, at: [f64; 3]) {
    for block in &mut payload.blocks {
        let Some(door) = Door::read(block) else {
            continue;
        };
        let prior = float(block, PROGRESS).unwrap_or(if door.open { 1.0 } else { 0.0 });
        let next = if door.open {
            (prior + 0.15).min(1.0)
        } else {
            (prior - 0.15).max(0.0)
        };
        set_float(block, PROGRESS, next);
        if !door.open && door.lower && prior > 0.0 && next == 0.0 {
            let pos = std::array::from_fn(|i| at[i] + f64::from(door.rel[i]) + 0.5);
            send_close(game, pos);
        }
        let Some(id) = int(block, "Display") else {
            continue;
        };
        let pose = if door.folded_model.is_some() {
            folding_pose(&door, next, door.rel.map(f64::from))
        } else {
            let slide = door.slide_direction();
            let normal = door.facing.normal();
            let translation = std::array::from_fn(|axis| {
                door.rel[axis] as f32
                    + slide[axis] as f32 * next * next * 13.0 / 16.0
                    + normal[axis] as f32 * (next * 10.0).min(1.0) / 32.0
            });
            NativeDisplay {
                translation,
                interpolation: 1,
                ..NativeDisplay::default()
            }
        };
        game.native_set_display(game.native_dimension(), id as u32, &pose);
    }
}

// Create plays the cabin's closing thud locally when its panel animation settles.
fn send_close(game: &mut Game<'_>, at: [f64; 3]) {
    let Ok(data) = serde_json::to_vec(&at) else {
        return;
    };
    for player in game.native_server_players() {
        if player.dimension == game.native_dimension()
            && at
                .into_iter()
                .zip(player.position)
                .map(|(a, b)| (a - b).powi(2))
                .sum::<f64>()
                <= 256.0
        {
            let _ = game.native_net_send_to_player(player.uuid, CHANNEL, &data);
        }
    }
}

pub(super) fn receive_from_server(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel == CHANNEL
        && let Ok(at) = serde_json::from_slice(data)
    {
        game.native_play_local_sound(CLOSE, at, 0.125, 1.0, 0);
    }
}

// Use the two captured halves' displays for the original two full-height
// panels. Their shared hinge is at the lower block's position.
fn folding_pose(door: &Door, openness: f32, mut origin: [f64; 3]) -> NativeDisplay {
    let value = f64::from(openness);
    let base = [90.0_f64, 0.0, -90.0, 180.0][door.facing.0].to_radians();
    let sign = if door.right { -1.0 } else { 1.0 };
    let first = (91.0 * sign * value * value).to_radians();
    let second = if door.lower {
        0.0
    } else {
        (-181.0 * sign * value * value).to_radians()
    };
    let yaw = base + first + second;
    let center = [0.5, 0.0, 0.5];
    let rotated = rotate(center, 1, base);
    let normal = door.facing.normal();
    origin[1] -= if door.lower {
        1.0 / 512.0
    } else {
        1.0 + 1.0 / 512.0
    };
    for axis in 0..3 {
        origin[axis] +=
            center[axis] - rotated[axis] + f64::from(normal[axis]) * (value * 10.0).min(1.0) / 32.0;
    }
    let shifts = [
        rotate([0.0, 0.0, if door.right { 1.0 } else { 0.0 }], 1, base),
        rotate(
            [0.0, 0.0, if door.lower { 0.0 } else { sign / 2.0 }],
            1,
            base + first,
        ),
        rotate([0.0, 0.0, if door.right { -0.5 } else { 0.0 }], 1, yaw),
    ];
    let translation =
        std::array::from_fn(|i| (origin[i] + shifts.iter().map(|v| v[i]).sum::<f64>()) as f32);
    let (sin, cos) = (yaw / 2.0).sin_cos();
    NativeDisplay {
        translation,
        left_rotation: [0.0, sin as f32, 0.0, cos as f32],
        interpolation: 1,
        ..NativeDisplay::default()
    }
}

/// Update mounted doors before the carriage advances. A slowly moving door
/// retains its last station until it has picked up enough speed to close.
pub(super) fn tick_train(
    game: &mut Game<'_>,
    data: &mut Compound,
    station: Option<[i32; 3]>,
    speed: f64,
    pose: super::create_train::Pose,
) -> bool {
    const STATION: &str = "CreateTrainDoorStation";
    let station = if speed.abs() < 1.0 / 128.0 {
        let cached = match data.get(&STATION.into()) {
            Some(Tag::IntArray(pos)) => pos.as_slice().try_into().ok(),
            _ => None,
        };
        let station = station
            .or(cached)
            .filter(|&pos| game.native_block(pos) == super::create_station::STATION);
        if let Some(pos) = station {
            data.insert(STATION.into(), Tag::IntArray(pos.to_vec()));
        }
        station
    } else {
        data.remove(&STATION.into());
        None
    };
    let mode = station.map_or(DoorMode::None, |pos| mode(game, pos));
    let Some(Tag::List(blocks)) = data.get_mut(&"Blocks".into()) else {
        return false;
    };
    let cells: Vec<_> = blocks
        .iter()
        .filter_map(|tag| match tag {
            Tag::Compound(cell) => Some(cell.clone()),
            _ => None,
        })
        .collect();
    let center = center(&cells);
    let mut changes = Vec::new();
    let mut targets = Vec::new();
    for cell in &cells {
        let Some(door) = Door::read(cell) else {
            continue;
        };
        if !door.lower {
            continue;
        }
        let normal = door.outward(center).normal();
        let world = pose.rotation * glam::Vec3::from_array(normal.map(|n| n as f32));
        let face = if world.x.abs() > world.z.abs() {
            Face(if world.x > 0.0 { 1 } else { 3 })
        } else {
            Face(if world.z > 0.0 { 2 } else { 0 })
        };
        let open = mode.matches(face);
        targets.push((door.rel, open));
        if door.open != open && int(cell, TARGET_OPEN) != Some(i32::from(open)) {
            changes.push((door.rel, open, Some(face)));
            changes.push((offset(door.rel, [0, 1, 0]), open, None));
        }
    }
    let mut changed = false;
    for tag in blocks {
        let Tag::Compound(cell) = tag else { continue };
        let Some(door) = Door::read(cell) else {
            continue;
        };
        if let Some((_, open)) = targets.iter().find(|(pos, _)| *pos == door.rel) {
            cell.insert(TARGET_OPEN.into(), Tag::Byte(i8::from(*open)));
        }
        if let Some((_, open, face)) = changes.iter().find(|(pos, _, _)| *pos == door.rel) {
            write_open(cell, &door, *open);
            changed = true;
            if let Some(face) = face {
                let center = pose.position(
                    glam::Vec3::from_array(door.rel.map(|n| n as f32)) + glam::Vec3::Y * 0.5,
                );
                let platform = offset(
                    center.map(|coordinate| coordinate.floor() as i32),
                    face.normal(),
                );
                set_landing_door(game, platform, *face, *open);
                if *open {
                    play(game, OPEN, center, 0.125, 1.0);
                }
            }
        }
        // Train doors use the same client-side linear chaser as elevator doors.
        let open = changes
            .iter()
            .find(|(pos, _, _)| *pos == door.rel)
            .map_or(door.open, |(_, open, _)| *open);
        let prior = float(cell, PROGRESS).unwrap_or(if door.open { 1.0 } else { 0.0 });
        let next = if open {
            (prior + 0.15).min(1.0)
        } else {
            (prior - 0.15).max(0.0)
        };
        set_float(cell, PROGRESS, next);
        let settling = int(cell, "CreateTrainDoorSettling") == Some(1);
        if settling && !open && door.lower {
            let center = pose
                .position(glam::Vec3::from_array(door.rel.map(|n| n as f32)) + glam::Vec3::Y * 0.5);
            send_close(game, center);
        }
        cell.insert(
            "CreateTrainDoorSettling".into(),
            Tag::Byte(i8::from(!open && prior > 0.0 && next == 0.0)),
        );
        if next != prior {
            changed = true;
        }
    }
    changed
}

pub(super) fn restore_train_panel(block: &mut Compound) {
    let Some(door) = Door::read(block) else {
        return;
    };
    set_float(block, PROGRESS, if door.open { 1.0 } else { 0.0 });
    block.remove(&"CreateTrainDoorSettling".into());
}

pub(super) fn train_visual(block: &Compound) -> Option<(Compound, NativeDisplay)> {
    let door = Door::read(block)?;
    let progress = float(block, PROGRESS)?;
    let state = compound(block, "BlockState")?;
    let pose = if door.folded_model.is_some() {
        folding_pose(&door, progress, [0.0; 3])
    } else {
        let slide = door.slide_direction();
        let normal = door.facing.normal();
        NativeDisplay {
            translation: std::array::from_fn(|axis| {
                slide[axis] as f32 * progress * progress * 13.0 / 16.0
                    + normal[axis] as f32 * (progress * 10.0).min(1.0) / 32.0
            }),
            interpolation: 1,
            ..NativeDisplay::default()
        }
    };
    Some((display_state(block, state), pose))
}

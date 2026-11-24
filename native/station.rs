use horizon_core::geometry::Vec3;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::Game;
use super::create_machines::{int, mod_entity, offset};
use super::create_track::{self, TRACK};

pub(super) const STATION: &str = "create:track_station";
pub(super) const SELECTED: &str = "create:track_targeting_item_selected_pos";
pub(super) const DIRECTION: &str = "create:track_targeting_item_selected_direction";

fn block_pos(tag: &Tag) -> Option<[i32; 3]> {
    match tag {
        Tag::IntArray(parts) => parts.as_slice().try_into().ok(),
        Tag::List(parts) => match parts.as_slice() {
            [Tag::Int(x), Tag::Int(y), Tag::Int(z)] => Some([*x, *y, *z]),
            _ => None,
        },
        _ => None,
    }
}

fn selected(stack: &ItemStack) -> Option<[i32; 3]> {
    block_pos(stack.data()?.other(SELECTED)?)
}

fn clear(game: &mut Game<'_>) {
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(SELECTED, None);
        held.data_mut().set_other(DIRECTION, None);
        held.tidy();
    }
}

fn within(pos: [i32; 3], brick: [i32; 3]) -> bool {
    let squared = |i: usize| (i64::from(pos[i]) - i64::from(brick[i])).pow(2);
    squared(0) + squared(1) + squared(2) < 16 * 16
}

pub(super) fn valid_track(game: &Game<'_>, pos: [i32; 3]) -> Option<Vec3> {
    if game.native_block(pos) != TRACK {
        return None;
    }
    let shape = game.native_block_property(pos, "shape")?;
    let axis = create_track::track_axis(&shape)?;
    let step = axis.components().map(|p| p as i32);
    let connects = [step, step.map(|p| -p)].into_iter().any(|direction| {
        let next = offset(pos, direction);
        game.native_block(next) == TRACK
            && game
                .native_block_property(next, "shape")
                .is_some_and(|next_shape| {
                    next_shape.starts_with("cr_")
                        || create_track::track_axis(&next_shape).is_some_and(|other| {
                            axis.horizontal().cross(other.horizontal()).length_squared() < 1.0e-6
                        })
                })
    });
    let curved = mod_entity(game, pos).is_some_and(|entity| {
        matches!(entity.nbt.get(&"Connections".into()),
        Some(Tag::List(connections)) if !connections.is_empty())
    });
    (connects || curved).then_some(axis)
}

pub(super) fn target(game: &Game<'_>, pos: [i32; 3]) -> Option<([i32; 3], bool)> {
    let entity = mod_entity(game, pos).filter(|entity| entity.id == STATION)?;
    targeting_position(&entity.nbt, pos)
}

fn available(game: &Game<'_>, track: [i32; 3], kind: &str) -> bool {
    !game.world.block_entities.iter().any(|(&(x, y, z), _)| {
        let pos = [x, y, z];
        if !within(pos, track) {
            return false;
        }
        target(game, pos).is_some_and(|(selected, _)| track == selected)
            || kind == STATION
                && mod_entity(game, pos)
                    .filter(|entity| entity.id == super::create_train_signal::SIGNAL)
                    .and_then(|entity| targeting_position(&entity.nbt, pos))
                    .is_some_and(|(selected, _)| track == selected)
    })
}

fn write_target(game: &mut Game<'_>, pos: [i32; 3], track: [i32; 3], front: bool) {
    let delta = (0..3).map(|i| track[i] - pos[i]).collect();
    game.native_with_mod_block_entity(pos, |entity| {
        entity
            .nbt
            .insert("TargetTrack".into(), Tag::IntArray(delta));
        entity
            .nbt
            .insert("TargetDirection".into(), Tag::Byte(i8::from(front)));
    });
    game.native_block_entity_sync(pos);
}

pub(super) fn use_item(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    stack: &ItemStack,
) -> bool {
    let kind = stack.item.as_ref();
    if !matches!(kind, STATION | super::create_train_signal::SIGNAL | super::create_track_observer::OBSERVER) {
        return false;
    }
    let pending = selected(stack);
    if game.native_sneaking() && pending.is_some() {
        clear(game);
        return true;
    }
    if game.native_block(pos) == TRACK {
        if let Some(axis) = valid_track(game, pos)
            && available(game, pos, kind)
        {
            let front = axis.dot(create_track::face_vector(game.yaw)) < 0.0;
            if let Some(held) = game.held_mut() {
                held.data_mut()
                    .set_other(SELECTED, Some(Tag::IntArray(pos.to_vec())));
                held.data_mut()
                    .set_other(DIRECTION, Some(Tag::Byte(i8::from(front))));
            }
        }
        return true;
    }
    let Some(track) = pending else { return true };
    let hit = game.world.block(pos[0], pos[1], pos[2]);
    let at = if game.res.behaviours().is_replaceable(hit) {
        pos
    } else {
        offset(pos, face)
    };
    let prior = game.world.block(at[0], at[1], at[2]);
    if !within(track, at)
        || valid_track(game, track).is_none()
        || !available(game, track, kind)
        || !game.res.behaviours().is_replaceable(prior)
    {
        return true;
    }
    let front = matches!(
        stack.data().and_then(|data| data.other(DIRECTION)),
        Some(Tag::Byte(1))
    );
    if let Some(default) = game.native_default_state(kind) {
        let state = if kind == super::create_train_signal::SIGNAL {
            let powered = if game.native_neighbor_signal(game.native_dimension(), at) != 0 {
                "true"
            } else {
                "false"
            };
            game.with_level(|_, level, _| {
                level.native_state_with_property(default, "powered", powered)
            })
            .unwrap_or(default)
        } else if kind == STATION && game.native_state_block(prior) == Some("minecraft:water") {
            game.with_level(|_, level, _| {
                level.native_state_with_property(default, "waterlogged", "true")
            })
            .unwrap_or(default)
        } else {
            default
        };
        if game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL) {
            write_target(game, at, track, front);
            clear(game);
            game.consume_held();
        }
    }
    true
}

pub(super) fn new_tag() -> Compound {
    Compound::from([("TargetDirection".into(), Tag::Byte(0))])
}

const CASING: &str = "create:railway_casing";
pub(super) const SMALL_BOGEY: &str = "create:small_bogey";
pub(super) const LARGE_BOGEY: &str = "create:large_bogey";
const ASSEMBLY_LIMIT: i32 = 128;
pub(super) const MAX_BOGEYS: usize = 20;

pub(super) fn targeting_position(nbt: &Compound, pos: [i32; 3]) -> Option<([i32; 3], bool)> {
    let delta = block_pos(nbt.get(&"TargetTrack".into())?)?;
    Some((offset(pos, delta), int(nbt, "TargetDirection") == Some(1)))
}

fn assembling(game: &Game<'_>, pos: [i32; 3]) -> bool {
    game.native_block_property(pos, "assembling").as_deref() == Some("true")
}

pub(super) fn assembly_axis(game: &Game<'_>, target: [i32; 3], front: bool) -> Option<[i32; 3]> {
    let axis = valid_track(game, target)?;
    if axis.length_squared() != 1.0 || axis.y != 0.0 {
        return None;
    }
    let sign = if front { 1.0 } else { -1.0 };
    Some(axis.scale(sign).components().map(|v| v as i32))
}

pub(super) fn along(start: [i32; 3], step: [i32; 3], distance: i32) -> [i32; 3] {
    offset(start, step.map(|v| v * distance))
}

fn assembly_length(game: &Game<'_>, origin: [i32; 3], axis: [i32; 3]) -> i32 {
    let Some(shape) = game.native_block_property(origin, "shape") else {
        return 0;
    };
    let wet = game.native_block_property(origin, "waterlogged");
    for distance in 1..ASSEMBLY_LIMIT {
        let at = along(origin, axis, distance);
        if game.native_block(at) != TRACK
            || game.native_block_property(at, "shape").as_deref() != Some(shape.as_str())
            || game.native_block_property(at, "waterlogged") != wet
        {
            return distance - 1;
        }
    }
    ASSEMBLY_LIMIT - 1
}

fn bogey_at(at: [i32; 3]) -> [i32; 3] {
    offset(at, [0, 1, 0])
}

fn is_bogey(game: &Game<'_>, at: [i32; 3]) -> bool {
    matches!(game.native_block(at).as_str(), SMALL_BOGEY | LARGE_BOGEY)
}

fn set_bogey(game: &mut Game<'_>, at: [i32; 3], bogey: &str, axis: &str, wet: bool) -> bool {
    let Some(state) = game.native_default_state(bogey) else {
        return false;
    };
    let Some(state) = game.with_level(|_, level, _| {
        let state = level.native_state_with_property(state, "axis", axis)?;
        level.native_state_with_property(state, "waterlogged", if wet { "true" } else { "false" })
    }) else {
        return false;
    };
    game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL)
}

pub(super) fn use_track(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) -> bool {
    if game.native_block(at) != TRACK || game.native_sneaking() {
        return false;
    }
    let station = game
        .world
        .block_entities
        .iter()
        .filter_map(|(&(x, y, z), _)| {
            let pos = [x, y, z];
            assembling(game, pos).then_some(pos)
        })
        .find_map(|pos| {
            let (origin, front) = target(game, pos)?;
            let axis = assembly_axis(game, origin, front)?;
            let distance = (0..3)
                .map(|index| (at[index] - origin[index]) * axis[index])
                .sum::<i32>();
            (distance > 0
                && along(origin, axis, distance) == at
                && distance <= assembly_length(game, origin, axis))
            .then_some((origin, axis, distance))
        });
    let Some((origin, axis, distance)) = station else {
        return false;
    };
    let length = assembly_length(game, origin, axis);
    let rail_axis = if axis[0] != 0 { "x" } else { "z" };
    let loaded = (1..=length).filter(|&index| is_bogey(game, bogey_at(along(origin, axis, index))));
    let tracks: Vec<_> = loaded.collect();
    let allowed = (distance == 1 || distance >= 4 && !tracks.is_empty())
        && tracks.iter().all(|index| (distance - index).abs() > 2);
    if !allowed {
        for near in [-1, 0, 1] {
            let bogey = bogey_at(along(at, axis, near));
            let bigger = match game.native_block(bogey).as_str() {
                SMALL_BOGEY => LARGE_BOGEY,
                LARGE_BOGEY => SMALL_BOGEY,
                _ => continue,
            };
            let wet = game.native_block_property(bogey, "waterlogged").as_deref() == Some("true");
            if set_bogey(game, bogey, bigger, rail_axis, wet) {
                return true;
            }
        }
        return false;
    }
    if !game.creative && stack.item.as_ref() != CASING {
        return false;
    }
    let target = bogey_at(at);
    let above = game.world.block(target[0], target[1], target[2]);
    if !game.res.behaviours().is_replaceable(above) {
        return false;
    }
    let wet = game.native_block_property(at, "waterlogged").as_deref() == Some("true");
    if set_bogey(game, target, SMALL_BOGEY, rail_axis, wet) {
        game.consume_held();
        return true;
    }
    false
}

pub(super) fn tick(game: &Game<'_>, pos: [i32; 3], entity: &mut crate::containers::ModBlockEntity) {
    let mode = assembling(game, pos);
    let track = targeting_position(&entity.nbt, pos)
        .and_then(|(track, front)| Some((track, assembly_axis(game, track, front)?)));
    let bogeys = if mode {
        track.map_or(0, |(origin, axis)| {
            (1..=assembly_length(game, origin, axis))
                .filter(|&i| is_bogey(game, bogey_at(along(origin, axis, i))))
                .take(MAX_BOGEYS)
                .count()
        })
    } else {
        0
    };
    let present = super::create_train::at_station(game, pos);
    entity.data.resize(5, 0);
    entity.data[0] = i32::from(mode);
    entity.data[1] = i32::from(track.is_some());
    entity.data[2] = i32::from(present.is_some());
    entity.data[3] = bogeys as i32;
    entity.data[4] =
        i32::from(present.is_some_and(|id| super::create_train_conductor::has_schedule(game, id)));
}

const ASSEMBLY_BUTTON: [f32; 4] = [84.0, 65.0, 24.0, 16.0];
const DISASSEMBLY_BUTTON: [f32; 4] = [94.0, 65.0, 24.0, 16.0];
const SCHEDULE_BUTTON: [f32; 4] = [73.0, 65.0, 18.0, 18.0];
const FINISH_BUTTON: [f32; 4] = [94.0, 154.0, 24.0, 16.0];
const BACK_BUTTON: [f32; 4] = [73.0, 154.0, 16.0, 16.0];
const STATION_TEXTURE: &str = "create:gui/schedule_2";
const ASSEMBLY_TEXTURE: &str = "create:gui/assemble";
const ICONS: &str = "create:gui/icons";
const WIDGETS: &str = "create:gui/widgets";

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.hand != super::Hand::Main || game.native_sneaking() || game.native_block(pos) != STATION
    {
        return false;
    }
    if super::create_postbox::select_station(game, pos) {
        return true;
    }
    game.open_menu(pos);
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 200.0,
        height: 178.0,
        slots: vec![None],
        inventory_x: 12.0,
        inventory_y: 800.0,
        own_labels: true,
        own_background: true,
    }
}

pub(super) fn draw_screen(
    game: &Game<'_>,
    data: &[i32],
    draw: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    let center = |game: &Game<'_>,
                  draw: &mut horizon_client::hud::HudBatch,
                  label: &str,
                  at: f32,
                  color: u32| {
        game.native_text(
            draw,
            label,
            [x + (200.0 - game.native_text_width(label)) / 2.0, y + at],
            color,
            false,
        );
    };
    if data.first() == Some(&1) {
        game.native_sprite(
            draw,
            ASSEMBLY_TEXTURE,
            [0.0, 0.0, 200.0, 178.0],
            [x, y, 200.0, 178.0],
        );
        super::create_station_name::assembly_mode();
        center(game, draw, "Train Assembly", 4.0, 0x0E2233);
        let count = data.get(3).copied().unwrap_or(0);
        let description = match count {
            0 => "No Bogeys".to_owned(),
            1 => "1 Bogey".to_owned(),
            _ => format!("{count} Bogeys"),
        };
        center(game, draw, &description, 47.0, 0xD0D0D0);
        for (row, line) in [
            (62.0, "Use Train Casing on tracks"),
            (73.0, "to add bogeys."),
            (94.0, "Glue the carriage to its bogeys."),
            (116.0, "Add Train Controls facing front."),
        ] {
            game.native_text(draw, line, [x + 28.0, y + row], 0xD0D0D0, false);
        }
        let [bx, by, w, h] = BACK_BUTTON;
        horizon_client::widgets::record("Back", [x + bx, y + by, w, h], true);
        game.native_sprite(draw, ICONS, [128.0, 128.0, w, h], [x + bx, y + by, w, h]);
        let [bx, by, w, h] = FINISH_BUTTON;
        horizon_client::widgets::record("Assemble Train", [x + bx, y + by, w, h], count > 0);
        if count > 0 {
            game.native_sprite(
                draw,
                STATION_TEXTURE,
                [64.0, 239.0, w, h],
                [x + bx, y + by, w, h],
            );
        }
    } else {
        game.native_sprite(
            draw,
            STATION_TEXTURE,
            [0.0, 111.0, 200.0, 127.0],
            [x, y, 200.0, 127.0],
        );
        super::create_station_name::draw(game, draw, [x, y]);
        let present = data.get(2) == Some(&1);
        center(
            game,
            draw,
            if present {
                "Train at Station"
            } else {
                "Station is Idle"
            },
            47.0,
            0xD0D0D0,
        );
        if present {
            let [bx, by, w, h] = SCHEDULE_BUTTON;
            let active = data.get(4) == Some(&1);
            let at = [x + bx, y + by, w, h];
            let label = game.translate("create.station.remove_schedule", "Retrieve Schedule");
            let [mx, my] = game.native_cursor();
            let hovered = mx >= at[0] && mx < at[0] + w && my >= at[1] && my < at[1] + h;
            let source = if !active {
                90.0
            } else if hovered {
                18.0
            } else {
                0.0
            };
            horizon_client::widgets::record(&label, at, active);
            game.native_sprite(draw, WIDGETS, [source, 0.0, w, h], at);
            game.native_sprite(
                draw,
                ICONS,
                [192.0, 48.0, 16.0, 16.0],
                [at[0] + 1.0, at[1] + 1.0, 16.0, 16.0],
            );
        }
        if data.get(1) == Some(&1) {
            let (label, button, sprite_x) = if present {
                ("Disassemble Train", DISASSEMBLY_BUTTON, 39.0)
            } else {
                ("Create New Train", ASSEMBLY_BUTTON, 14.0)
            };
            let [bx, by, w, h] = button;
            horizon_client::widgets::record(label, [x + bx, y + by, w, h], true);
            game.native_sprite(
                draw,
                STATION_TEXTURE,
                [sprite_x, 239.0, w, h],
                [x + bx, y + by, w, h],
            );
        }
    }
}

pub(super) fn screen_click(data: &[i32], [x, y]: [f32; 2]) -> Option<i32> {
    let hit = |[left, top, width, height]: [f32; 4]| {
        x >= left && x < left + width && y >= top && y < top + height
    };
    if data.first() == Some(&1) {
        if data.get(3).is_some_and(|&count| count > 0) && hit(FINISH_BUTTON) {
            return Some(2);
        }
        return hit(BACK_BUTTON).then_some(1);
    }
    if data.get(2) == Some(&1) && data.get(4) == Some(&1) && hit(SCHEDULE_BUTTON) {
        return Some(4);
    }
    if data.get(1) == Some(&1) {
        return if data.get(2) == Some(&1) {
            hit(DISASSEMBLY_BUTTON).then_some(3)
        } else {
            hit(ASSEMBLY_BUTTON).then_some(0)
        };
    }
    None
}

pub(super) fn menu_button(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut crate::containers::ModBlockEntity,
    button: i32,
) {
    if button == 4 {
        if let Some(id) = super::create_train::at_station(game, pos) {
            super::create_train_conductor::retrieve(game, id, pos);
        }
        return;
    }
    let change = match button {
        0 if !assembling(game, pos) => targeting_position(&entity.nbt, pos)
            .is_some_and(|(track, front)| assembly_axis(game, track, front).is_some())
            .then_some(true),
        1 if assembling(game, pos) => Some(false),
        2 if assembling(game, pos) => {
            let Some((origin, axis)) = targeting_position(&entity.nbt, pos)
                .and_then(|(track, front)| Some((track, assembly_axis(game, track, front)?)))
            else {
                return;
            };
            let bogeys: Vec<_> = (1..=assembly_length(game, origin, axis))
                .filter(|&i| is_bogey(game, bogey_at(along(origin, axis, i))))
                .take(MAX_BOGEYS)
                .collect();
            match super::create_train::assemble(game, pos, origin, axis, &bogeys) {
                Ok(()) => Some(false),
                Err(error) => {
                    game.message = Some((error.into(), std::time::Instant::now()));
                    None
                }
            }
        }
        3 => super::create_train::at_station(game, pos)
            .filter(|&id| super::create_train::disassemble(game, id))
            .map(|_| true),
        _ => None,
    };
    if let Some(assembling) = change {
        game.native_set_block_property(
            pos,
            "assembling",
            if assembling { "true" } else { "false" },
        );
        tick(game, pos, entity);
        game.native_block_entity_sync(pos);
    }
}

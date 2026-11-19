use std::cell::RefCell;
use std::collections::BTreeSet;

use horizon_client::hud::HudBatch;
use horizon_client::mod_api::NativeScreenView;
use horizon_client::text::{Style, Text};
use horizon_world::nbt::{Compound, Tag};
use serde::{Deserialize, Serialize};

use super::Game;
use super::create_bearing::relative;
use super::create_contraption_controls::CONTROLS;
use super::create_depot::compound;
use super::create_elevator::PULLEY;
use super::create_elevator_doors::{DoorMode, write_mode};
use super::create_elevator_indicator::{self as indicator, Control};
use super::create_machines::{int, mod_entity, string};
use super::create_rope::{self as rope, Payload};
use crate::containers::ModBlockEntity;

pub(super) const CONTACT: &str = "create:elevator_contact";
const CHANNEL: &str = "create:elevator_floors";
const EDITOR: &str = "create:elevator_contact";
const PULLEY_TAG: &str = "CreateElevatorControl";
const LOCAL_TAG: &str = "CreateControlPos";
const YAW_TAG: &str = "CreateControlYaw";

#[derive(Clone, Serialize, Deserialize, PartialEq, Eq)]
pub(super) struct Floor {
    pub y: i32,
    pub short: String,
    pub long: String,
}

#[derive(Serialize, Deserialize)]
enum ClientMessage {
    Edit {
        pos: [i32; 3],
        names: [String; 2],
        mode: DoorMode,
    },
    Confirm {
        control: u32,
        target: Option<i32>,
    },
}

#[derive(Serialize, Deserialize)]
enum ServerMessage {
    Edit {
        pos: [i32; 3],
        names: [String; 2],
        mode: DoorMode,
    },
    Controls {
        tick: i64,
        controls: Vec<Control>,
    },
}

struct Editor {
    pos: [i32; 3],
    names: [String; 2],
    mode: DoorMode,
    focus: usize,
    all: bool,
    submit: bool,
    scroll_pitch: Option<f32>,
}

thread_local! {
    static CLIENT_EDITOR: RefCell<Option<Editor>> = const { RefCell::new(None) };
    static VIEWING_CONTROLS: RefCell<BTreeSet<u128>> = const { RefCell::new(BTreeSet::new()) };
}

fn floor_names(game: &Game<'_>, pos: [i32; 3]) -> [String; 2] {
    let entity = mod_entity(game, pos);
    ["ShortName", "LongName"].map(|key| {
        entity
            .and_then(|entity| string(&entity.nbt, key))
            .unwrap_or_default()
    })
}

fn floor_positions(entity: &ModBlockEntity) -> impl Iterator<Item = [i32; 3]> + '_ {
    let floors = match entity.nbt.get(&"Floors".into()) {
        Some(Tag::List(floors)) => floors.as_slice(),
        _ => &[],
    };
    floors.iter().filter_map(|floor| match floor {
        Tag::IntArray(pos) => pos.as_slice().try_into().ok(),
        _ => None,
    })
}

fn floors(game: &Game<'_>, pulley: [i32; 3]) -> Vec<Floor> {
    mod_entity(game, pulley)
        .into_iter()
        .flat_map(floor_positions)
        .filter(|&pos| game.native_block(pos) == CONTACT)
        .map(|pos| {
            let [short, long] = floor_names(game, pos);
            Floor {
                y: pos[1],
                short,
                long,
            }
        })
        .collect()
}

fn write_names(game: &mut Game<'_>, pos: [i32; 3], names: [String; 2]) {
    game.native_with_mod_block_entity(pos, |entity| {
        for (key, name) in ["ShortName", "LongName"].into_iter().zip(names) {
            entity
                .nbt
                .insert(key.into(), Tag::String(name.as_str().into()));
        }
    });
    game.native_block_entity_sync(pos);
}

pub(super) fn init_names(game: &mut Game<'_>, positions: &[[i32; 3]]) {
    let mut names: Vec<_> = positions
        .iter()
        .map(|&pos| floor_names(game, pos))
        .collect();
    let mut previous: Option<i32> = None;
    for i in 0..names.len() {
        let mut current = names[i][0].parse::<i32>().ok();
        if !names[i][0].trim().is_empty() && current.is_none() {
            continue;
        }
        if let Some(previous) = previous {
            current = Some(previous.wrapping_add(1));
        }
        let mut next = None;
        for [short, _] in &mut names[i + 1..] {
            if let Ok(number) = short.parse::<i32>() {
                if current.is_some_and(|current| current >= number) {
                    short.clear();
                } else {
                    next = Some(number);
                }
                break;
            }
        }
        let number = current
            .or_else(|| next.map(|next| next.wrapping_sub(1)))
            .unwrap_or(0);
        names[i][0] = number.to_string();
        previous = Some(number);
    }
    for (&pos, names) in positions.iter().zip(names) {
        if floor_names(game, pos) != names {
            write_names(game, pos, names);
        }
    }
}

pub(super) fn floor_reached(game: &mut Game<'_>, positions: &[[i32; 3]], y: i32) {
    let Some(&floor) = positions.iter().find(|pos| pos[1] == y) else {
        return;
    };
    let [short, _] = floor_names(game, floor);
    for &pos in positions {
        if mod_entity(game, pos)
            .and_then(|e| string(&e.nbt, "LastReportedCurrentFloor"))
            .as_deref()
            == Some(&short)
        {
            continue;
        }
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.insert(
                "LastReportedCurrentFloor".into(),
                Tag::String(short.as_str().into()),
            );
        });
        game.native_block_entity_sync(pos);
    }
}

fn control(game: &Game<'_>, id: u32) -> Option<([i32; 3], [i32; 3])> {
    let raw = game.persist.raw.get(&id)?;
    let Tag::IntArray(pulley) = raw.get(PULLEY_TAG)? else {
        return None;
    };
    let Tag::IntArray(local) = raw.get(LOCAL_TAG)? else {
        return None;
    };
    Some((
        pulley.as_slice().try_into().ok()?,
        local.as_slice().try_into().ok()?,
    ))
}

pub(super) fn move_controls(game: &mut Game<'_>, pulley: [i32; 3], payload: &Payload, y: f64) {
    let dim = game.native_dimension();
    for block in &payload.blocks {
        let Some(state) = compound(block, "BlockState") else {
            continue;
        };
        if string(state, "Name").as_deref() != Some(CONTROLS) {
            continue;
        }
        let rel = relative(block);
        let yaw = match compound(state, "Properties")
            .and_then(|properties| string(properties, "facing"))
            .as_deref()
        {
            Some("east") => -90,
            Some("south") => 180,
            Some("west") => 90,
            _ => 0,
        };
        let x = f64::from(pulley[0] + rel[0]) + 0.5;
        let y = y + f64::from(rel[1]);
        let z = f64::from(pulley[2] + rel[2]) + 0.5;
        let id = game.others.iter().find_map(|entity| {
            (control(game, entity.id) == Some((pulley, rel))).then_some(entity.id)
        });
        if let Some(id) = id {
            game.native_move_entity(dim, id, [x, y, z], 0.0, 0.0);
            if let Some(Tag::Compound(data)) = game.persist.raw.get_mut(&id) {
                data.insert(YAW_TAG.into(), Tag::Int(yaw));
            }
            continue;
        }
        let data = Compound::from([
            ("width".into(), Tag::Float(0.75_f32.to_bits())),
            ("height".into(), Tag::Float(0.875_f32.to_bits())),
            ("response".into(), Tag::Byte(1)),
            (
                "Tags".into(),
                Tag::List(vec![Tag::String("create_elevator_controls".into())]),
            ),
            (PULLEY_TAG.into(), Tag::IntArray(pulley.to_vec())),
            (LOCAL_TAG.into(), Tag::IntArray(rel.to_vec())),
            (YAW_TAG.into(), Tag::Int(yaw)),
        ]);
        game.native_summon(dim, "minecraft:interaction", [x, y, z], data);
    }
}

pub(super) fn remove_controls(game: &mut Game<'_>, pulley: [i32; 3]) {
    let ids: Vec<_> = game
        .others
        .iter()
        .filter_map(|other| (control(game, other.id)?.0 == pulley).then_some(other.id))
        .collect();
    for id in ids {
        game.native_remove_entity(game.native_dimension(), id);
    }
}

pub(super) fn publish_controls(game: &mut Game<'_>) {
    let tick = game.world.game_time;
    let mut controls = Vec::new();
    let mut stale = Vec::new();
    for entity in &game.others {
        let Some((pulley, local)) = control(game, entity.id) else {
            continue;
        };
        if game.world.loaded(pulley[0], pulley[2])
            && (game.native_block(pulley) != PULLEY || rope::payload(game, pulley).is_none())
        {
            stale.push(entity.id);
        } else if let Some(pulley_entity) = mod_entity(game, pulley) {
            let position = entity.position.components();
            let current = (position[1] - f64::from(local[1]) + 0.5).floor() as i32
                + int(&pulley_entity.nbt, "FloorDelta").unwrap_or_default();
            let target = int(&pulley_entity.nbt, "TargetFloor").unwrap_or(current);
            let yaw = match game.persist.raw.get(&entity.id) {
                Some(Tag::Compound(raw)) => int(raw, YAW_TAG).unwrap_or_default() as f32,
                _ => 0.0,
            };
            controls.push(Control {
                id: entity.id,
                position,
                yaw,
                current,
                target,
                floors: floors(game, pulley),
            });
        }
    }
    for id in stale {
        game.native_remove_entity(game.native_dimension(), id);
    }
    let players = game.native_server_players();
    VIEWING_CONTROLS.with_borrow_mut(|viewers| {
        viewers.retain(|uuid| players.iter().any(|player| player.uuid == *uuid));
    });
    for player in players {
        if player.dimension != game.native_dimension() {
            continue;
        }
        let controls: Vec<_> = controls
            .iter()
            .filter(|control| nearby(player.position, control.position, 50.0))
            .cloned()
            .collect();
        let send_update = VIEWING_CONTROLS.with_borrow_mut(|viewers| {
            if controls.is_empty() {
                viewers.remove(&player.uuid)
            } else {
                viewers.insert(player.uuid);
                true
            }
        });
        if send_update {
            send(
                game,
                player.uuid,
                ServerMessage::Controls { tick, controls },
            );
        }
    }
}

pub(super) fn clear_controls() {
    indicator::update(0, Vec::new());
}

fn nearby(from: [f64; 3], to: [f64; 3], radius: f64) -> bool {
    from.into_iter()
        .zip(to)
        .map(|(a, b)| (a - b).powi(2))
        .sum::<f64>()
        <= radius * radius
}

fn send(game: &mut Game<'_>, player: u128, message: ServerMessage) {
    if let Ok(data) = serde_json::to_vec(&message) {
        let _ = game.native_net_send_to_player(player, CHANNEL, &data);
    }
}

fn send_action(game: &mut Game<'_>, message: ClientMessage) -> bool {
    serde_json::to_vec(&message)
        .is_ok_and(|data| game.native_net_send_to_server(CHANNEL, &data).is_ok())
}

pub(super) fn open_contact(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != CONTACT {
        return false;
    }
    if let Some(player) = game.native_acting_player() {
        let names = floor_names(game, pos);
        let mode = super::create_elevator_doors::mode(game, pos);
        send(game, player.uuid, ServerMessage::Edit { pos, names, mode });
    }
    true
}

pub(super) fn receive_from_server(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL {
        return;
    }
    match serde_json::from_slice(data) {
        Ok(ServerMessage::Controls { tick, controls }) => indicator::update(tick, controls),
        Ok(ServerMessage::Edit { pos, names, mode }) if game.native_mod_screen_open(EDITOR) => {
            CLIENT_EDITOR.with_borrow_mut(|state| {
                *state = Some(Editor {
                    pos,
                    names,
                    mode,
                    focus: 0,
                    all: true,
                    submit: false,
                    scroll_pitch: None,
                });
            });
        }
        _ => {}
    }
}

pub(super) fn receive_from_client(game: &mut Game<'_>, uuid: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 1024 {
        return;
    }
    let Some(player) = game
        .native_server_players()
        .into_iter()
        .find(|player| player.uuid == uuid && player.dimension == game.native_dimension())
    else {
        return;
    };
    match serde_json::from_slice(data) {
        Ok(ClientMessage::Edit { pos, names, mode }) => {
            if nearby(player.position, pos.map(|n| f64::from(n) + 0.5), 8.0)
                && game.native_block(pos) == CONTACT
                && names[0].encode_utf16().count() <= 4
                && names[1].encode_utf16().count() <= 30
                && names
                    .iter()
                    .all(|name| name.chars().all(|c| !c.is_control()))
            {
                write_mode(game, pos, mode);
                write_names(game, pos, names);
            }
        }
        Ok(ClientMessage::Confirm {
            control: id,
            target,
        }) => {
            if let Some((pulley, at)) = reachable_control(game, id, player.position) {
                indicator::confirm(game, at);
                if let Some(target) =
                    target.filter(|y| floors(game, pulley).iter().any(|f| f.y == *y))
                {
                    game.native_with_mod_block_entity(pulley, |entity| {
                        if int(&entity.nbt, "TargetFloor") != Some(target) {
                            entity.nbt.insert("SelectedFloor".into(), Tag::Int(target));
                        }
                    });
                }
            }
        }
        _ => {}
    }
}

fn reachable_control(game: &Game<'_>, id: u32, from: [f64; 3]) -> Option<([i32; 3], [f64; 3])> {
    let (pulley, _) = control(game, id)?;
    let entity = game.others.iter().find(|entity| entity.id == id)?;
    let at = entity.position.components();
    nearby(from, at, 8.0).then_some((pulley, at))
}

pub(super) fn wheel(game: &mut Game<'_>, steps: f32, claimed: &mut bool) {
    if *claimed || steps == 0.0 || game.spectator() {
        return;
    }
    let Some((id, _)) = game.interaction_hit() else {
        return;
    };
    let steps = steps.signum() as i32 * steps.abs().ceil() as i32;
    *claimed = indicator::scroll(game, id as u32, steps);
}

pub(super) fn click_controls(game: &mut Game<'_>) -> bool {
    if game.spectator() {
        return false;
    }
    let Some(hit) = game.remote_object_hit(false) else {
        return false;
    };
    if !game.before_block(hit.distance)
        || game
            .mob_hit()
            .is_some_and(|(_, distance, _)| distance <= hit.distance)
    {
        return false;
    }
    let id = hit.id as u32;
    let Some(target) = indicator::choose(id) else {
        return false;
    };
    send_action(
        game,
        ClientMessage::Confirm {
            control: id,
            target,
        },
    )
}

fn panel(screen: &NativeScreenView<'_>) -> [f32; 2] {
    let [x, y, w, h] = screen.rect;
    [x + (w - 263.0) / 2.0, y + (h - 82.0) / 2.0]
}

pub(super) fn draw_editor(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    let [x, y] = panel(screen);
    let _ = game.native_sprite(
        batch,
        "create:gui/display_link",
        [20.0, 172.0, 233.0, 82.0],
        [x, y, 233.0, 82.0],
    );
    let title = "Elevator Contact";
    game.native_text(
        batch,
        title,
        [x + (225.0 - game.native_text_width(title)) / 2.0, y + 6.0],
        0x2F3738,
        false,
    );
    CLIENT_EDITOR.with_borrow(|state| {
        let Some(editor) = state else {
            return;
        };
        for (field, at) in [
            [
                x + 36.0 - game.native_text_width(&editor.names[0]) / 2.0,
                y + 30.0,
            ],
            [x + 63.0, y + 30.0],
        ]
        .into_iter()
        .enumerate()
        {
            let mut text = editor.names[field].clone();
            if editor.focus == field && !editor.all {
                text.push('_');
            }
            let color = if editor.focus == field && editor.all {
                0xA0D2FF
            } else {
                0xFFFFFF
            };
            game.native_text(batch, &text, at, color, false);
        }
        let hovered = door_widget_hovered(screen);
        if hovered {
            game.native_fill(batch, [x + 58.0, y + 57.0, 53.0, 16.0], 0x44FFFFFF);
        }
        game.native_text(
            batch,
            editor.mode.label(),
            [x + 62.0, y + 63.0],
            0xFFFFFF,
            true,
        );
    });
    let _ = game.native_item(batch, "create:train_door", [x + 37.0, y + 58.0], 16.0);
    game.native_text(batch, "✓", [x + 205.0, y + 61.0], 0xFFFFFF, false);
    if door_widget_hovered(screen) {
        CLIENT_EDITOR.with_borrow(|state| {
            if let Some(editor) = state {
                draw_door_tooltip(game, screen, batch, editor.mode);
            }
        });
    }
}

fn draw_door_tooltip(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    batch: &mut HudBatch,
    selected: DoorMode,
) {
    let mut lines = vec![(Text::literal("Onboard Door Control"), 0xFFA0D2FF)];
    for mode in DoorMode::VALUES {
        let (arrow, color) = if mode == selected {
            ("->", 0xFFFFFFFF)
        } else {
            (">", 0xFFAAAAAA)
        };
        lines.push((
            Text::literal(format!("{arrow} {}", mode.description())),
            color,
        ));
    }
    let index = ((game.yaw / 90.0 + 0.5).floor() as i32).rem_euclid(4) as usize;
    let direction = [
        DoorMode::South,
        DoorMode::West,
        DoorMode::North,
        DoorMode::East,
    ][index];
    lines.push((
        Text::literal(format!("You are facing: {}", direction.label())),
        0xFFFFDB89,
    ));
    lines.push((
        Text::styled(
            "Scroll to Select",
            Style {
                italic: Some(true),
                ..Style::default()
            },
        ),
        0xFF555555,
    ));
    game.draw_tooltip_lines(batch, &lines, screen.mouse[0], screen.mouse[1]);
}

fn door_widget_hovered(screen: &NativeScreenView<'_>) -> bool {
    let [x, y] = panel(screen);
    (x + 58.0..x + 111.0).contains(&screen.mouse[0])
        && (y + 57.0..y + 73.0).contains(&screen.mouse[1])
}

pub(super) fn editor_scroll(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    dy: f64,
    canceled: &mut bool,
) {
    if game.native_mod_screen() != Some(EDITOR) || dy == 0.0 || !door_widget_hovered(screen) {
        return;
    }
    CLIENT_EDITOR.with_borrow_mut(|state| {
        if let Some(editor) = state {
            let mode = editor.mode.scroll(dy);
            if mode != editor.mode {
                editor.mode = mode;
                editor
                    .scroll_pitch
                    .get_or_insert_with(|| mode.scroll_pitch());
            }
        }
    });
    *canceled = true;
}

pub(super) fn editor_mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    canceled: &mut bool,
) {
    if game.native_mod_screen() != Some(EDITOR) || button != 0 {
        return;
    }
    let [left, top] = panel(screen);
    let [x, y] = [screen.mouse[0] - left, screen.mouse[1] - top];
    CLIENT_EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        if (23.0..=42.0).contains(&y) {
            if (21.0..=51.0).contains(&x) {
                editor.focus = 0;
                editor.all = false;
            }
            if (57.0..=204.0).contains(&x) {
                editor.focus = 1;
                editor.all = false;
            }
        }
        if (200.0..=218.0).contains(&x) && (58.0..=76.0).contains(&y) {
            editor.submit = true;
        }
    });
    *canceled = true;
}

pub(super) fn editor_key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    if game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    CLIENT_EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        match key {
            "key.keyboard.enter" | "key.keyboard.keypad.enter" => editor.submit = true,
            "key.keyboard.tab" => {
                editor.focus = 1 - editor.focus;
                editor.all = true;
            }
            "key.keyboard.a" if modifiers & 10 != 0 => editor.all = true,
            "key.keyboard.backspace" | "key.keyboard.delete" => {
                if editor.all {
                    editor.names[editor.focus].clear();
                } else {
                    editor.names[editor.focus].pop();
                }
                editor.all = false;
            }
            _ => return,
        }
        *canceled = true;
    });
}

pub(super) fn editor_char(game: &Game<'_>, c: char, canceled: &mut bool) {
    if game.native_mod_screen() != Some(EDITOR) || c.is_control() {
        return;
    }
    CLIENT_EDITOR.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        let text = &mut editor.names[editor.focus];
        if editor.all {
            text.clear();
            editor.all = false;
        }
        if text.encode_utf16().count() + c.len_utf16() <= [4, 30][editor.focus] {
            text.push(c);
        }
    });
    *canceled = true;
}

pub(super) fn editor_tick(game: &mut Game<'_>) {
    if game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    let pitch = CLIENT_EDITOR.with_borrow_mut(|state| state.as_mut()?.scroll_pitch.take());
    if let Some(pitch) = pitch {
        game.audio
            .play_on(0, "create:scroll_value", None, 0.25, pitch);
    }
    let editor = CLIENT_EDITOR.with_borrow_mut(|state| {
        if state.as_ref().is_some_and(|editor| editor.submit) {
            state.take()
        } else {
            None
        }
    });
    if let Some(editor) = editor {
        send_action(
            game,
            ClientMessage::Edit {
                pos: editor.pos,
                names: editor.names,
                mode: editor.mode,
            },
        );
        game.native_mod_screen_close(EDITOR);
    }
}

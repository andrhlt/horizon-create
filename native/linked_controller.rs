use std::cell::{Cell, RefCell};
use std::collections::HashMap;

use horizon_world::nbt::{Compound, Tag};
use winit::keyboard::KeyCode;

use super::{Game, Screen};
use super::create_machines::{int, mod_entity};

const ITEM: &str = "create:linked_controller";
const COMPONENT: &str = "create:linked_controller_items";
const LINK: &str = "create:redstone_link";
const CHANNEL: &str = "create:linked_controller_bind";
const INPUT: &str = "create:linked_controller_input";
const MOUNT_CHANNEL: &str = "create:linked_controller_lectern";
const MOUNT_BLOCK: &str = "create:lectern_controller";

thread_local! {
    static BIND: Cell<Option<[i32; 3]>> = const { Cell::new(None) };
    static ACTIVE: Cell<bool> = const { Cell::new(false) };
    static HELD: Cell<u8> = const { Cell::new(0) };
    static KEEPALIVE: Cell<u8> = const { Cell::new(0) };
    static MOUNT: Cell<Option<[i32; 3]>> = const { Cell::new(None) };
    static SESSIONS: RefCell<HashMap<Option<u128>, (String, [i32; 3])>> = RefCell::new(HashMap::new());
    static INPUTS: RefCell<HashMap<Option<u128>, Input>> = RefCell::new(HashMap::new());
}

struct Input {
    dimension: String,
    pos: [i32; 3],
    pairs: Vec<[Option<crate::items::ItemStack>; 2]>,
    pending: Vec<[Option<crate::items::ItemStack>; 2]>,
    remaining: u8,
}

pub(super) fn register(types: &mut Vec<String>) {
    types.push(COMPONENT.into());
}

fn controller(game: &Game<'_>) -> bool {
    game.stack_in(game.selected).is_some_and(|s| s.item.as_ref() == ITEM)
        || game.offhand.as_ref().is_some_and(|s| s.item.as_ref() == ITEM)
}

fn in_range(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some(eye) = game.eye_position() else { return false; };
    let reach = 0.4 * game.interaction_range("minecraft:block_interaction_range", 4.5, 5.0);
    eye.into_iter().zip(pos).map(|(v, p)| (v - f64::from(p) - 0.5).powi(2)).sum::<f64>() < reach * reach
}

fn session_valid(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != MOUNT_BLOCK || !in_range(game, pos) || game.spectator() { return false; }
    let user = game.acting_player_uuid();
    mod_entity(game, pos).is_some_and(|entity| entity.id == MOUNT_BLOCK
        && matches!(entity.nbt.get(&"User".into()), Some(Tag::IntArray(owner)) if owner.as_slice() == user))
}

pub(super) fn use_mount(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != MOUNT_BLOCK || game.native_sneaking() || !in_range(game, pos) { return false; }
    if !game.native_authoritative() { return true; }
    let id = game.lan_acting_uuid;
    if mod_entity(game, pos).is_none_or(|entity| entity.id != MOUNT_BLOCK) { return true; }
    let occupied = SESSIONS.with_borrow(|sessions| sessions.contains_key(&id) || sessions.values().any(|(dimension, at)| dimension == game.native_dimension() && *at == pos));
    if occupied { return true; }
    let owner = game.acting_player_uuid();
    game.native_with_mod_block_entity(pos, |entity| { entity.nbt.insert("User".into(), Tag::IntArray(owner.to_vec())); });
    game.native_block_entity_sync(pos);
    SESSIONS.with_borrow_mut(|sessions| { sessions.insert(id, (game.native_dimension().to_owned(), pos)); });
    if let Some(uuid) = id {
        if let Ok(data) = serde_json::to_vec(&Some(pos)) { let _ = game.native_net_send_to_player(uuid, MOUNT_CHANNEL, &data); }
    } else if !ACTIVE.get() && BIND.get().is_none() {
        MOUNT.set(Some(pos)); ACTIVE.set(true);
    }
    true
}

fn stop_session(game: &mut Game<'_>, id: Option<u128>, pos: [i32; 3], release: bool) {
    SESSIONS.with_borrow_mut(|sessions| { sessions.remove(&id); });
    if release { INPUTS.with_borrow_mut(|inputs| { if let Some(input) = inputs.get_mut(&id) { input.remaining = 0; } }); }
    if id.is_none() && MOUNT.get() == Some(pos) { MOUNT.set(None); ACTIVE.set(false); HELD.set(0); }
    let owner = id.map(horizon_client::lan::playerdata::uuid_ints).unwrap_or_else(|| game.acting_player_uuid());
    game.native_with_mod_block_entity(pos, |entity| {
        if matches!(entity.nbt.get(&"User".into()), Some(Tag::IntArray(current)) if current.as_slice() == owner) {
            entity.nbt.remove(&"User".into());
        }
    });
    game.native_block_entity_sync(pos);
    if let Some(uuid) = id {
        if let Ok(data) = serde_json::to_vec(&Option::<[i32; 3]>::None) { let _ = game.native_net_send_to_player(uuid, MOUNT_CHANNEL, &data); }
    }
}

pub(super) fn receive_mount(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != MOUNT_CHANNEL { return; }
    let Ok(pos) = serde_json::from_slice::<Option<[i32; 3]>>(data) else { return; };
    if let Some(pos) = pos {
        if !ACTIVE.get() && BIND.get().is_none() { MOUNT.set(Some(pos)); ACTIVE.set(true); }
    } else if MOUNT.get().is_some() { stop(game); }
}

pub(super) fn use_link(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != LINK || game.native_sneaking()
        || !game.held().is_some_and(|stack| stack.item.as_ref() == ITEM)
        || !game.may_build() { return false; }
    if game.lan_acting.is_none() && ACTIVE.get() { stop(game); return true; }
    // A guest's use is handled on its client, not on the host's input state.
    if game.lan_acting.is_none() && game.remote.is_none() {
        BIND.set(if BIND.get().is_some() { None } else { Some(pos) });
    }
    true
}

pub(super) fn use_air(game: &mut Game<'_>) -> bool {
    if game.native_sneaking() || !game.held().is_some_and(|s| s.item.as_ref() == ITEM) { return false; }
    if game.lan_acting.is_none() && game.remote.is_none() { toggle(game); }
    true
}

fn toggle(game: &mut Game<'_>) {
    if ACTIVE.get() || BIND.get().is_some() { stop(game); } else { ACTIVE.set(true); }
}

fn stop(game: &mut Game<'_>) {
    BIND.set(None);
    ACTIVE.set(false);
    if HELD.replace(0) != 0 { send_input(game, 0); }
    if let Some(pos) = MOUNT.replace(None) {
        if game.remote.is_some() {
            let _ = game.native_net_send_to_server(MOUNT_CHANNEL, &[]);
        } else { stop_session(game, None, pos, true); }
    }
    KEEPALIVE.set(0);
}

pub(super) fn remote_use(game: &mut Game<'_>) {
    if game.remote.is_none() || game.hands_busy()
        || game.native_sneaking() || !controller(game) || game.spectator() { return; }
    let hit = game.native_raycast(6.0);
    if let Some(hit) = hit {
        if hit.block == LINK {
            if ACTIVE.get() { stop(game); } else {
                let pos = [hit.block_x, hit.block_y, hit.block_z];
                BIND.set(if BIND.get().is_some() { None } else { Some(pos) });
            }
        }
    } else { toggle(game); }
}

fn send_input(game: &mut Game<'_>, mask: u8) {
    if game.remote.is_some() {
        let mut packet = vec![mask];
        if let Some(pos) = MOUNT.get() { for coordinate in pos { packet.extend_from_slice(&coordinate.to_be_bytes()); } }
        let _ = game.native_net_send_to_server(INPUT, &packet);
    } else { apply_input(game, mask, MOUNT.get()); }
}

fn apply_input(game: &mut Game<'_>, mask: u8, mount: Option<[i32; 3]>) {
    if mount.is_some_and(|pos| !session_valid(game, pos)) { return; }
    let Some(body) = game.player.as_ref() else { return; };
    let uuid = game.lan_acting_uuid;
    let dimension = game.dim.id().to_owned();
    let pos = [body.position.x, body.position.y, body.position.z].map(|n| n.floor() as i32);
    let alive = body.health.health() > 0.0;
    let changed = INPUTS.with_borrow_mut(|inputs| {
        if mask == 0 || game.spectator() || !alive {
            if let Some(input) = inputs.get_mut(&uuid) { input.remaining = 0; }
            return false;
        }
        let entries = if let Some(pos) = mount {
            mod_entity(game, pos).and_then(|entity| match entity.nbt.get(&"ControllerData".into()) {
                Some(Tag::List(entries)) => Some(entries.clone()), _ => None,
            }).unwrap_or_default()
        } else {
            let stack = game.stack_in(game.selected).filter(|s| s.item.as_ref() == ITEM)
                .or_else(|| game.offhand.as_ref().filter(|s| s.item.as_ref() == ITEM));
            let Some(stack) = stack else {
                if let Some(input) = inputs.get_mut(&uuid) { input.remaining = 0; }
                return false;
            };
            match game.native_component(stack, COMPONENT) {
                Ok(Some(Tag::List(entries))) => entries.clone(), _ => Vec::new(),
            }
        };
        let slot = |index: usize| entries.iter().find_map(|entry| {
            let Tag::Compound(entry) = entry else { return None; };
            if int(entry, "slot") != Some(index as i32) { return None; }
            let Tag::Compound(item) = entry.get(&"item".into())? else { return None; };
            crate::items::ItemStack::from_nbt(item)
        });
        let pairs: Vec<_> = (0..6).filter(|i| mask & (1 << i) != 0)
            .map(|i| [slot(i * 2), slot(i * 2 + 1)]).collect();
        let old = inputs.remove(&uuid);
        let changed = old.as_ref().is_none_or(|input| input.remaining == 0
            || pairs.iter().any(|pair| !input.pairs.contains(pair)));
        let mut pending = old.as_ref().map_or_else(Vec::new, |input| input.pending.clone());
        if let Some(old) = old {
            pending.extend(old.pairs.into_iter().filter(|pair| !pairs.contains(pair)));
        }
        inputs.insert(uuid, Input { dimension, pos, pairs, pending, remaining: 30 });
        changed
    });
    if changed { super::create_redstone_link::controller_update(game); }
}

pub(super) fn sources(game: &Game<'_>, include_pending: bool) -> Vec<([i32; 3], [Option<crate::items::ItemStack>; 2])> {
    INPUTS.with_borrow(|inputs| {
        let dimension = game.native_dimension();
        let mut sources = Vec::new();
        for input in inputs.values().filter(|input| input.dimension == dimension) {
            if input.remaining > 0 || include_pending {
                sources.extend(input.pairs.iter().cloned().map(|pair| (input.pos, pair)));
            }
            if include_pending {
                sources.extend(input.pending.iter().cloned().map(|pair| (input.pos, pair)));
            }
        }
        sources
    })
}

pub(super) fn post_tick(game: &mut Game<'_>) {
    let dimension = game.native_dimension();
    let sessions: Vec<_> = SESSIONS.with_borrow(|sessions| sessions.iter()
        .filter(|(_, (world, _))| world == dimension)
        .map(|(id, (_, pos))| (*id, *pos)).collect());
    for (id, pos) in sessions {
        if let Some(uuid) = id {
            if let Some(conn) = game.native_conn(uuid) {
                let valid = game.for_player(super::commands::Target::Guest(conn), |actor| {
                    actor.native_dimension() == dimension && session_valid(actor, pos)
                }).unwrap_or(false);
                if !valid { stop_session(game, Some(uuid), pos, true); }
            } else { stop_session(game, Some(uuid), pos, false); }
        } else if !session_valid(game, pos) { stop_session(game, None, pos, true); }
    }
    let changed = INPUTS.with_borrow_mut(|inputs| {
        let mut changed = false;
        for input in inputs.values_mut().filter(|input| input.dimension == dimension) {
            if !input.pending.is_empty() { input.pending.clear(); changed = true; }
            if input.remaining > 0 { input.remaining -= 1; }
            if input.remaining == 0 { changed = true; }
        }
        inputs.retain(|_, input| input.dimension != dimension || input.remaining > 0);
        changed
    });
    if changed { super::create_redstone_link::controller_update(game); }
}

pub(super) fn clear() {
    BIND.set(None);
    ACTIVE.set(false);
    HELD.set(0);
    KEEPALIVE.set(0);
    MOUNT.set(None);
    SESSIONS.with_borrow_mut(|sessions| sessions.clear());
    INPUTS.with_borrow_mut(|inputs| inputs.clear());
}

pub(super) fn tick(game: &mut Game<'_>) {
    if !ACTIVE.get() && BIND.get().is_none() { return; }
    let valid_item = if let Some(pos) = MOUNT.get() { game.native_block(pos) == MOUNT_BLOCK && in_range(game, pos) } else { controller(game) };
    if game.screen != Screen::Playing || !valid_item || game.spectator()
        || game.player.as_ref().is_none_or(|player| player.health.health() <= 0.0) {
        stop(game);
        return;
    }
    if HELD.get() != 0 {
        let next = KEEPALIVE.get().saturating_sub(1);
        KEEPALIVE.set(next);
        if next == 0 { send_input(game, HELD.get()); KEEPALIVE.set(5); }
    }
}

pub(super) fn receive(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel == MOUNT_CHANNEL {
        if !data.is_empty() { return; }
        let Some((dimension, pos)) = SESSIONS.with_borrow(|sessions| sessions.get(&Some(player)).cloned()) else { return; };
        let Some(conn) = game.native_conn(player) else { return; };
        game.for_player(super::commands::Target::Guest(conn), |actor| {
            if actor.native_dimension() == dimension { stop_session(actor, Some(player), pos, true); }
        });
        return;
    }
    if channel == INPUT {
        if !matches!(data.len(), 1 | 13) || data[0] & !0x3f != 0 { return; }
        let mount = if data.len() == 13 {
            Some(std::array::from_fn(|i| i32::from_be_bytes(data[1 + i * 4..5 + i * 4].try_into().unwrap())))
        } else { None };
        let Some(conn) = game.native_conn(player) else { return; };
        game.for_player(super::commands::Target::Guest(conn), |actor| apply_input(actor, data[0], mount));
        return;
    }
    if channel != CHANNEL || data.len() > 128 { return; }
    let Ok((pos, button)) = serde_json::from_slice::<([i32; 3], usize)>(data) else { return; };
    let Some(conn) = game.native_conn(player) else { return; };
    game.for_player(super::commands::Target::Guest(conn), |actor| bind(actor, pos, button));
}

fn bind(game: &mut Game<'_>, pos: [i32; 3], button: usize) {
    if button >= 6 || game.spectator() || !controller(game) { return; }
    let Some(eye) = game.eye_position() else { return; };
    let distance: f64 = eye.into_iter().zip(pos).map(|(v, p)| {
        let low = f64::from(p);
        (v - v.clamp(low, low + 1.0)).powi(2)
    }).sum();
    if distance > 36.0 || game.native_block(pos) != LINK { return; }
    let Some(link) = mod_entity(game, pos).filter(|entity| entity.id == LINK) else { return; };
    let frequencies = ["FrequencyFirst", "FrequencyLast"].map(|key| {
        let Tag::Compound(data) = link.nbt.get(&key.into())? else { return None; };
        let stack = crate::items::ItemStack::from_nbt(data)?;
        Some(crate::save::item_to_nbt(&stack))
    });
    let main = game.stack_in(game.selected).is_some_and(|s| s.item.as_ref() == ITEM);
    let Some(mut stack) = (if main { game.stack_in(game.selected) } else { game.offhand.as_ref() }).cloned() else { return; };
    let mut entries = match game.native_component(&stack, COMPONENT) {
        Ok(Some(Tag::List(entries))) => entries.clone(),
        Ok(None) => Vec::new(),
        _ => return,
    };
    entries.retain(|entry| match entry {
        Tag::Compound(entry) => !int(entry, "slot").is_some_and(|slot| slot == (button * 2) as i32 || slot == (button * 2 + 1) as i32),
        _ => true,
    });
    for (index, item) in frequencies.into_iter().enumerate() {
        if let Some(item) = item {
            entries.push(Tag::Compound(Compound::from([
                ("slot".into(), Tag::Int((button * 2 + index) as i32)),
                ("item".into(), item),
            ])));
        }
    }
    if game.native_set_component(&mut stack, COMPONENT, Tag::List(entries)).is_err() { return; }
    if main { *game.stack_in_mut(game.selected) = Some(stack); } else { game.offhand = Some(stack); }
    game.guest_inventory_resend |= game.lan_acting.is_some();
}

pub(super) fn key(game: &mut Game<'_>, key: KeyCode, pressed: bool, repeat: bool) -> bool {
    if BIND.get().is_none() && !ACTIVE.get() { return false; }
    let valid_item = if let Some(pos) = MOUNT.get() { game.native_block(pos) == MOUNT_BLOCK && in_range(game, pos) } else { controller(game) };
    if game.screen != Screen::Playing || !valid_item || game.spectator() {
        stop(game);
        return false;
    }
    if key == KeyCode::Escape && pressed { stop(game); return false; }
    let button = match key {
        KeyCode::KeyW => 0, KeyCode::KeyS => 1, KeyCode::KeyA => 2,
        KeyCode::KeyD => 3, KeyCode::Space => 4, KeyCode::ShiftLeft => 5,
        _ => return false,
    };
    if let Some(pos) = BIND.get() {
        if pressed && !repeat {
            BIND.set(None);
            if game.remote.is_some() {
                if let Ok(packet) = serde_json::to_vec(&(pos, button)) {
                    let _ = game.native_net_send_to_server(CHANNEL, &packet);
                }
            } else { bind(game, pos, button); }
        }
    } else if !repeat {
        let bit = 1 << button;
        let before = HELD.get();
        let after = if pressed { before | bit } else { before & !bit };
        if before != after { HELD.set(after); send_input(game, after); KEEPALIVE.set(5); }
    }
    true
}

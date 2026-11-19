use std::cell::Cell;

use horizon_core::geometry::Vec3;
use horizon_items::firework::DYE_FIREWORK_COLORS;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_bearing::relative;
use super::create_machines::{mod_entity, offset, string};
use super::create_rope::{self as rope, Payload};

const VEHICLE: &str = "CreateElevatorSeatVehicle";
const HITBOX: &str = "CreateElevatorSeatHitbox";
const PULLEY: &str = "CreateElevatorSeatPulley";
const TRAIN: &str = "CreateTrainSeatCarriage";
const VEHICLE_TICK: &str = "CreateElevatorSeatTick";
const POSE_CHANNEL: &str = "create:elevator_rider_pose";

thread_local! {
    static RIDER_POSE: Cell<Option<RiderPose>> = const { Cell::new(None) };
}

#[derive(Clone, Copy)]
struct RiderPose {
    vehicle: u32,
    position: Vec3,
    applied: Option<Vec3>,
}

// A static SeatEntity has a 0.35f passenger point above its origin and
// raises the passenger by another 1/16. The contraption's moving attachment
// is 1/2 above the saved seat block. Horizon applies the player attachment.
const STATIC_ATTACHMENT: f64 = 0.0625 + 0.35_f32 as f64;
const MOVING_ATTACHMENT: f64 = 0.5;

fn position(tag: &Tag, key: &str) -> Option<[i32; 3]> {
    let Some(Tag::IntArray(values)) = tag.get(key) else {
        return None;
    };
    values.as_slice().try_into().ok()
}

fn train_owner(tag: &Tag) -> Option<[i32; 4]> {
    let Some(Tag::IntArray(values)) = tag.get(TRAIN) else {
        return None;
    };
    values.as_slice().try_into().ok()
}

fn center(origin: [f64; 3], relative: [i32; 3], height: f64) -> [f64; 3] {
    [
        origin[0] + f64::from(relative[0]) + 0.5,
        origin[1] + f64::from(relative[1]) + height,
        origin[2] + f64::from(relative[2]) + 0.5,
    ]
}

pub(super) fn is_seat(name: &str) -> bool {
    name.strip_prefix("create:")
        .and_then(|name| name.strip_suffix("_seat"))
        .is_some_and(|color| DYE_FIREWORK_COLORS.iter().any(|(name, _)| *name == color))
}

pub(super) fn dye_static(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if !game.native_authoritative() || game.native_sneaking() {
        return false;
    }
    let current = game.native_block(at);
    if !is_seat(&current) {
        return false;
    }
    let Some(stack) = game.held() else {
        return false;
    };
    let Some((color, _)) = DYE_FIREWORK_COLORS.iter().find(|(name, _)| {
        game.items().item_in_tag(&format!("c:dyes/{name}"), &stack.item)
    }) else {
        return false;
    };
    let next = format!("create:{color}_seat");
    if next == current || !is_seat(&next) {
        return false;
    }
    let Some(state) = game.native_default_state(&next) else {
        return false;
    };
    let Some(waterlogged) = game.native_block_property(at, "waterlogged") else {
        return false;
    };
    let state = game.with_level(|_, level, _| {
        level.native_state_with_property(state, "waterlogged", &waterlogged)
    });
    state.is_some_and(|state| {
        game.native_set_block(game.native_dimension(), at, state, flags::UPDATE_ALL)
    })
}

fn block_is_seat(block: &Compound) -> bool {
    super::create_depot::compound(block, "BlockState")
        .and_then(|state| string(state, "Name"))
        .is_some_and(|name| is_seat(&name))
}

fn seat_tags(kind: &str, seat: [i32; 3], pulley: Option<[i32; 3]>, tag_name: &str) -> Compound {
    let mut tag = Compound::from([
        (kind.into(), Tag::IntArray(seat.to_vec())),
        ("Tags".into(), Tag::List(vec![Tag::String(tag_name.into())])),
    ]);
    if let Some(pulley) = pulley {
        tag.insert(PULLEY.into(), Tag::IntArray(pulley.to_vec()));
    }
    tag
}

fn vehicle(game: &Game<'_>, at: [i32; 3], pulley: Option<[i32; 3]>) -> Option<u32> {
    game.armor_stands.iter().find_map(|stand| {
        let tag = game.persist.raw.get(&stand.id)?;
        (position(tag, VEHICLE) == Some(at)
            && position(tag, PULLEY) == pulley
            && train_owner(tag).is_none())
        .then_some(stand.id)
    })
}

pub(super) fn static_vehicle_position(game: &Game<'_>, id: u32) -> Option<[i32; 3]> {
    let data = game.persist.raw.get(&id)?;
    if position(data, PULLEY).is_some() || train_owner(data).is_some() {
        return None;
    }
    position(data, VEHICLE)
}

pub(super) fn occupied_static(game: &Game<'_>, at: [i32; 3]) -> bool {
    vehicle(game, at, None).is_some()
}

fn board(
    game: &mut Game<'_>,
    at: [i32; 3],
    pulley: Option<[i32; 3]>,
    attachment: [f64; 3],
) -> bool {
    if game.player.is_none() || game.riding.is_some() || vehicle(game, at, pulley).is_some() {
        return false;
    }

    // A marker armor stand is a tracked, invisible carrier with a zero-height
    // attachment on both server and client. The separate Interaction below
    // covers the seat's click volume and never carries a rider.
    let tag = seat_tags(VEHICLE, at, pulley, "create_elevator_seat_vehicle");
    board_vehicle(game, attachment, tag)
}

fn spawn_vehicle(game: &mut Game<'_>, attachment: [f64; 3], mut tag: Compound) -> Option<u32> {
    for flag in ["Marker", "Invisible", "NoGravity", "Invulnerable"] {
        tag.insert(flag.into(), Tag::Byte(1));
    }
    game.native_summon(
        game.native_dimension(),
        "minecraft:armor_stand",
        attachment,
        tag,
    )
}

fn board_vehicle(game: &mut Game<'_>, attachment: [f64; 3], tag: Compound) -> bool {
    let Some(id) = spawn_vehicle(game, attachment, tag) else {
        return false;
    };
    let Some(seat) = game.seat(id) else {
        discard_vehicle(game, id);
        return false;
    };
    if !game.native_may_board(id) {
        discard_vehicle(game, id);
        return false;
    }
    game.board_seat(id, seat);
    true
}

fn can_board_mob(game: &Game<'_>, id: u32) -> bool {
    let Some(mob) = game.mobs.iter().find(|mob| mob.id == id && mob.alive() && !mob.removed) else {
        return false;
    };
    let ineligible = game.world_tables.as_ref()
        .and_then(|tables| tables.pack_tags.get("entity_type"))
        .and_then(|tags| tags.get("create:ignore_seat"))
        .is_some_and(|kinds| kinds.contains(&mob.kind.id));
    mob.extra.mount.is_none()
        && mob.species() != horizon_client::mobs::Species::Shulker
        && !ineligible
}

pub(super) fn board_landing_mob(game: &mut Game<'_>, mob: u32, at: [i32; 3], continuing_y: f64) {
    if !game.native_authoritative() || !is_seat(&game.native_block(at))
        || occupied_static(game, at) || !can_board_mob(game, mob)
    {
        return;
    }
    let Some(rider) = game.mobs.iter().find(|rider| rider.id == mob) else {
        return;
    };
    if rider.position.components().map(|coordinate| coordinate.floor() as i32) != at {
        return;
    }

    let attachment = center(at.map(f64::from), [0; 3], STATIC_ATTACHMENT);
    let tag = seat_tags(VEHICLE, at, None, "create_elevator_seat_vehicle");
    let Some(vehicle) = spawn_vehicle(game, attachment, tag) else {
        return;
    };
    if !game.try_mount_mob(mob, vehicle) {
        discard_vehicle(game, vehicle);
        return;
    }
    if let Some(rider) = game.mobs.iter_mut().find(|rider| rider.id == mob) {
        rider.velocity.y = continuing_y;
        rider.extra.sitting_pose = rider.extra.tame;
        rider.needs_sync = true;
    }
    let raw = game.persist.raw.entry(mob).or_insert_with(|| Tag::Compound(Compound::new()));
    if let Tag::Compound(data) = raw {
        data.insert("CreateSeat".into(), Tag::IntArray(at.to_vec()));
        data.insert("CreateSeatAt".into(), Tag::Long(game.world.game_time));
    }
}

pub(super) fn tick_static_mob_riders(game: &mut Game<'_>) {
    let mut removed = Vec::new();
    for mob in &mut game.mobs {
        let Some(id) = mob.extra.mount else {
            continue;
        };
        let Some(vehicle) = game.persist.raw.get(&id) else {
            continue;
        };
        let Some(at) = position(vehicle, VEHICLE) else {
            continue;
        };
        if position(vehicle, PULLEY).is_some() || train_owner(vehicle).is_some() {
            continue;
        }
        mob.velocity.y = -mob.effective_gravity() * f64::from(0.98_f32);
        removed.push((id, at));
    }
    for (id, at) in removed {
        if game.world.loaded(at[0], at[2]) && !is_seat(&game.native_block(at)) {
            discard_vehicle(game, id);
        }
    }
}

fn dismount_mob_riders(game: &mut Game<'_>, vehicle: u32) {
    for mob in &mut game.mobs {
        if mob.extra.mount == Some(vehicle) {
            mob.extra.mount = None;
            mob.extra.passenger = false;
            mob.extra.sitting_pose = false;
            mob.needs_sync = true;
            if let Some(Tag::Compound(data)) = game.persist.raw.get_mut(&mob.id) {
                data.remove(&"CreateSeat".into());
                data.remove(&"CreateSeatAt".into());
            }
        }
    }
}

fn discard_vehicle(game: &mut Game<'_>, id: u32) {
    dismount_mob_riders(game, id);
    game.armor_stands.retain(|stand| stand.id != id);
    game.persist.raw.remove(&id);
}

pub(super) fn board_static(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if (game.serving.is_none() && game.options.dedicated.is_none())
        || !is_seat(&game.native_block(at))
        || game.keys.held(super::Mapping::Sneak)
    {
        return false;
    }
    if let Some(vehicle) = vehicle(game, at, None) {
        let mob_occupied = game.mobs.iter().any(|mob| mob.extra.mount == Some(vehicle));
        if !mob_occupied || game.player.is_none() || game.riding.is_some()
            || !game.native_may_board(vehicle)
        {
            return false;
        }
        let Some(seat) = game.seat(vehicle) else {
            return false;
        };
        dismount_mob_riders(game, vehicle);
        game.board_seat(vehicle, seat);
    } else if !board(
        game,
        at,
        None,
        center(at.map(f64::from), [0; 3], STATIC_ATTACHMENT),
    ) {
        return false;
    }
    for mob in &game.mobs {
        if let Some(tag @ Tag::Compound(_)) = game.persist.raw.get_mut(&mob.id) {
            if position(tag, "CreateSeat") != Some(at) {
                continue;
            }
            if let Tag::Compound(data) = tag {
                data.remove(&"CreateSeat".into());
                data.remove(&"CreateSeatAt".into());
            }
        }
    }
    true
}

pub(super) fn board_moving(game: &mut Game<'_>, id: u32) -> bool {
    let Some(tag) = game.persist.raw.get(&id) else {
        return false;
    };
    if let Some(owner) = train_owner(tag) {
        let Some(at) = position(tag, HITBOX) else {
            return false;
        };
        return board_train(game, id, owner, at);
    }
    let (Some(at), Some(pulley)) = (position(tag, HITBOX), position(tag, PULLEY)) else {
        return false;
    };
    let Some(mut payload) = rope::payload(game, pulley) else {
        return false;
    };
    let Some(block) = payload
        .blocks
        .iter_mut()
        .find(|block| relative(block) == at && block_is_seat(block))
    else {
        return false;
    };
    let Some(hitbox) = game.others.iter().find(|target| target.id == id) else {
        return false;
    };
    let mut attachment = hitbox.position.components();
    attachment[1] += MOVING_ATTACHMENT;
    if !board(game, at, Some(pulley), attachment) {
        return false;
    }
    // Java lets the first player take a seat occupied by a mob, leaving
    // the mob where it was seated. A second player cannot take it.
    if block.remove(&"SeatOccupant".into()).is_some() {
        rope::save_payload(game, pulley, payload);
    }
    true
}

pub(super) fn interaction_bounds(
    game: &Game<'_>,
    id: u32,
) -> Option<([f64; 3], [f64; 3], [f64; 3])> {
    position(game.persist.raw.get(&id)?, HITBOX)?;
    let entity = game.others.iter().find(|entity| entity.id == id)?;
    let shape = entity.interaction.as_ref()?;
    let [x, y, z] = entity.position.components();
    let half = f64::from(shape.width) / 2.0;
    Some((
        [x - half, y, z - half],
        [x + half, y + f64::from(shape.height), z + half],
        [x, y, z],
    ))
}

pub(super) fn dismount(game: &mut Game<'_>) -> bool {
    let Some(id) = game.riding else {
        return false;
    };
    let Some(tag) = game.persist.raw.get(&id) else {
        return false;
    };
    let Some(at) = position(tag, VEHICLE) else {
        return false;
    };
    let owner = train_owner(tag);
    let moving = position(tag, PULLEY).is_some() || owner.is_some();
    let Some(mut seat) = game.seat(id) else {
        return false;
    };
    if !game.native_may_leave(id) {
        return true;
    }
    game.riding = None;
    if let Some(owner) = owner
        && let Some((_, hitbox)) = train_hitbox(game, owner, at)
    {
        seat.position = hitbox.add_vector(Vec3::new(0.0, MOVING_ATTACHMENT, 0.0));
    }
    let destination_y = if moving {
        // AbstractContraptionEntity dismounts at getPassengerPosition,
        // before positionRider subtracts 1/8 from it.
        seat.player_seat().y + 0.125
    } else {
        // SeatEntity centers its 0.35f AABB on the seat origin and adds 0.5.
        f64::from(at[1]) + f64::from(0.35_f32) / 2.0 + 0.5
    };
    if let Some(player) = game.player.as_mut() {
        game.previous_position = player.position;
        player.position = Vec3::new(seat.position.x, destination_y, seat.position.z);
        player.velocity = Vec3::ZERO;
        player.ground.on_ground = false;
        player.fall_distance = 0.0;
        player.teleported = true;
    }
    discard_vehicle(game, id);
    true
}

fn move_vehicle(game: &mut Game<'_>, id: u32, at: [f64; 3]) {
    let Some(stand) = game.armor_stands.iter_mut().find(|stand| stand.id == id) else {
        return;
    };
    stand.previous = stand.position;
    stand.position = Vec3::new(at[0], at[1], at[2]);
    if stand.previous == stand.position {
        return;
    }

    let rider = game.lan.as_ref().and_then(|host| {
        host.hub
            .guests
            .iter()
            .find_map(|guest| (guest.placed && guest.vehicle == Some(id)).then_some(guest.uuid))
    });
    // Vanilla armor stand movement is quantized, sent at the entity's update
    // interval, and interpolated by world ticks. The local rider needs the
    // server's exact attachment even when the rest of the world is frozen.
    if let Some(rider) = rider {
        let mut data = [0; 28];
        data[..4].copy_from_slice(&id.to_le_bytes());
        for (coordinate, bytes) in at.into_iter().zip(data[4..].chunks_exact_mut(8)) {
            bytes.copy_from_slice(&coordinate.to_le_bytes());
        }
        let _ = game.native_net_send_to_player(rider, POSE_CHANNEL, &data);
    }
}

pub(super) fn receive_rider_pose(channel: &str, data: &[u8]) {
    if channel != POSE_CHANNEL {
        return;
    }
    let Ok(data) = <&[u8; 28]>::try_from(data) else {
        return;
    };
    let (id, coordinates) = data.split_first_chunk::<4>().unwrap();
    let position: [f64; 3] = std::array::from_fn(|axis| {
        let offset = axis * 8;
        f64::from_le_bytes(coordinates[offset..offset + 8].try_into().unwrap())
    });
    if position
        .into_iter()
        .any(|coordinate| !coordinate.is_finite())
    {
        return;
    }
    let vehicle = u32::from_le_bytes(*id);
    let applied = RIDER_POSE
        .get()
        .filter(|pose| pose.vehicle == vehicle)
        .and_then(|pose| pose.applied);
    RIDER_POSE.set(Some(RiderPose {
        vehicle,
        position: Vec3::new(position[0], position[1], position[2]),
        applied,
    }));
}

pub(super) fn apply_rider_pose(game: &mut Game<'_>) {
    let Some(mut pose) = RIDER_POSE.get() else {
        return;
    };
    if game.riding != Some(pose.vehicle) {
        clear_rider_pose();
        return;
    }
    if let Some(stand) = game
        .armor_stands
        .iter_mut()
        .find(|stand| stand.id == pose.vehicle)
    {
        stand.previous = pose.applied.unwrap_or(stand.position);
        stand.position = pose.position;
        pose.applied = Some(pose.position);
        RIDER_POSE.set(Some(pose));
    }
}

pub(super) fn clear_rider_pose() {
    RIDER_POSE.set(None);
}

pub(super) fn train_player_count(game: &Game<'_>, train: u32) -> i32 {
    let Some(owner) = game.persist.uuid_of(train) else {
        return 0;
    };
    let rides_train = |id| {
        game.persist
            .raw
            .get(&id)
            .is_some_and(|tag| train_owner(tag) == Some(owner) && position(tag, VEHICLE).is_some())
    };
    let host = i32::from(game.player.is_some() && game.riding.is_some_and(rides_train));
    let guests = game.lan.as_ref().map_or(0, |lan| {
        lan.hub
            .guests
            .iter()
            .filter(|guest| guest.placed && guest.vehicle.is_some_and(rides_train))
            .count() as i32
    });
    host + guests
}

fn train_vehicle(game: &Game<'_>, owner: [i32; 4], at: [i32; 3]) -> Option<u32> {
    game.armor_stands.iter().find_map(|stand| {
        let tag = game.persist.raw.get(&stand.id)?;
        (train_owner(tag) == Some(owner) && position(tag, VEHICLE) == Some(at)).then_some(stand.id)
    })
}

fn board_train(game: &mut Game<'_>, hitbox: u32, owner: [i32; 4], at: [i32; 3]) -> bool {
    if game.player.is_none()
        || game.riding.is_some()
        || train_vehicle(game, owner, at).is_some()
        || game.inventory[game.selected]
            .as_ref()
            .is_some_and(|held| held.item.as_ref() == "create:wrench")
        || !super::create_train::has_seat(game, owner, at)
    {
        return false;
    }
    let Some(entity) = game.others.iter().find(|entity| entity.id == hitbox) else {
        return false;
    };
    let mut attachment = entity.position.components();
    attachment[1] += MOVING_ATTACHMENT;
    let mut tag = seat_tags(VEHICLE, at, None, "create_train_seat_vehicle");
    tag.insert(TRAIN.into(), Tag::IntArray(owner.to_vec()));
    if !board_vehicle(game, attachment, tag) {
        return false;
    }
    super::create_train::clear_seat_occupant(game, owner, at);
    true
}

pub(super) fn attach_train(game: &mut Game<'_>, train: u32, anchor: [i32; 3], blocks: &[Compound]) {
    let Some(owner) = game.persist.uuid_of(train) else {
        return;
    };
    for block in blocks.iter().filter(|block| block_is_seat(block)) {
        let at = relative(block);
        let Some(id) = vehicle(game, offset(anchor, at), None) else {
            continue;
        };
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            tag.insert(VEHICLE.into(), Tag::IntArray(at.to_vec()));
            tag.insert(TRAIN.into(), Tag::IntArray(owner.to_vec()));
        }
    }
}

fn train_hitbox(game: &Game<'_>, owner: [i32; 4], at: [i32; 3]) -> Option<(u32, Vec3)> {
    game.others.iter().find_map(|entity| {
        let tag = game.persist.raw.get(&entity.id)?;
        (train_owner(tag) == Some(owner) && position(tag, HITBOX) == Some(at))
            .then_some((entity.id, entity.position))
    })
}

pub(super) fn move_train(
    game: &mut Game<'_>,
    train: u32,
    blocks: &[Tag],
    locate: impl Fn([i32; 3]) -> [f64; 3],
    seat_pose: impl Fn([i32; 3]) -> [f64; 3],
) {
    let Some(owner) = game.persist.uuid_of(train) else {
        return;
    };
    let dimension = game.native_dimension();
    for block in blocks {
        let Tag::Compound(block) = block else {
            continue;
        };
        if !block_is_seat(block) {
            continue;
        }
        let at = relative(block);
        let attachment = locate(at);
        if let Some((hitbox, _)) = train_hitbox(game, owner, at) {
            game.native_move_entity(dimension, hitbox, attachment, 0.0, 0.0);
        } else {
            let mut tag = seat_tags(HITBOX, at, None, "create_train_seat");
            tag.insert(TRAIN.into(), Tag::IntArray(owner.to_vec()));
            tag.insert("width".into(), Tag::Float(0.875_f32.to_bits()));
            tag.insert("height".into(), Tag::Float(0.375_f32.to_bits()));
            game.native_summon(dimension, "minecraft:interaction", attachment, tag);
        }
        if let Some(vehicle) = train_vehicle(game, owner, at) {
            let mut passenger = seat_pose(at);
            passenger[1] += MOVING_ATTACHMENT;
            move_vehicle(game, vehicle, passenger);
        }
    }
}

pub(super) fn land_train(
    game: &mut Game<'_>,
    train: u32,
    anchor: [i32; 3],
    blocks: &[Compound],
    angle: f64,
) {
    let Some(owner) = game.persist.uuid_of(train) else {
        return;
    };
    use super::create_bearing::rotate;
    for block in blocks.iter().filter(|block| block_is_seat(block)) {
        let at = relative(block);
        let Some(vehicle) = train_vehicle(game, owner, at) else {
            continue;
        };
        let seat = offset(
            anchor,
            rotate(at.map(f64::from), 1, angle).map(|part| part.round() as i32),
        );
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&vehicle) {
            tag.remove(&TRAIN.into());
            tag.insert(VEHICLE.into(), Tag::IntArray(seat.to_vec()));
        }
        move_vehicle(
            game,
            vehicle,
            center(seat.map(f64::from), [0; 3], STATIC_ATTACHMENT),
        );
    }
}

pub(super) fn attach_cabin(
    game: &mut Game<'_>,
    pulley: [i32; 3],
    anchor: [i32; 3],
    payload: &Payload,
) {
    for block in payload.blocks.iter().filter(|block| block_is_seat(block)) {
        let at = relative(block);
        let Some(id) = vehicle(game, offset(anchor, at), None) else {
            continue;
        };
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            tag.insert(VEHICLE.into(), Tag::IntArray(at.to_vec()));
            tag.insert(PULLEY.into(), Tag::IntArray(pulley.to_vec()));
        }
        move_vehicle(
            game,
            id,
            center(anchor.map(f64::from), at, MOVING_ATTACHMENT),
        );
    }
    move_cabin(game, pulley, payload, anchor.map(f64::from));
}

pub(super) fn move_cabin(
    game: &mut Game<'_>,
    pulley: [i32; 3],
    payload: &Payload,
    location: [f64; 3],
) {
    for block in payload.blocks.iter().filter(|block| block_is_seat(block)) {
        let at = relative(block);
        let hitbox = game.others.iter().find_map(|entity| {
            let tag = game.persist.raw.get(&entity.id)?;
            (position(tag, HITBOX) == Some(at) && position(tag, PULLEY) == Some(pulley))
                .then_some(entity.id)
        });
        let base = center(location, at, 0.0);
        if let Some(id) = hitbox {
            game.native_move_entity(game.native_dimension(), id, base, 0.0, 0.0);
        } else {
            let mut tag = seat_tags(HITBOX, at, Some(pulley), "create_elevator_seat");
            tag.insert("width".into(), Tag::Float(0.875_f32.to_bits()));
            tag.insert("height".into(), Tag::Float(0.375_f32.to_bits()));
            game.native_summon(game.native_dimension(), "minecraft:interaction", base, tag);
        }
    }
}

pub(super) fn advance_riders(game: &mut Game<'_>) {
    let tick = game.world.game_time;
    let movement: Vec<_> = game
        .armor_stands
        .iter()
        .filter_map(|stand| {
            let tag = game.persist.raw.get(&stand.id)?;
            let seat = position(tag, VEHICLE)?;
            let pulley = position(tag, PULLEY)?;
            if matches!(tag.get(VEHICLE_TICK), Some(Tag::Long(at)) if *at == tick) {
                return None;
            }
            let Some(Tag::Double(bits)) = mod_entity(game, pulley)?.nbt.get(&"CabinY".into())
            else {
                return None;
            };
            let base = [
                f64::from(pulley[0]),
                f64::from_bits(*bits),
                f64::from(pulley[2]),
            ];
            Some((stand.id, center(base, seat, MOVING_ATTACHMENT)))
        })
        .collect();
    // Java ticks riders before applying the pulley movement. Only advance
    // once per world tick, including when the LAN processes a frozen level.
    for (id, at) in movement {
        move_vehicle(game, id, at);
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            tag.insert(VEHICLE_TICK.into(), Tag::Long(tick));
        }
    }
}

pub(super) fn land_cabin(
    game: &mut Game<'_>,
    pulley: [i32; 3],
    anchor: [i32; 3],
    payload: &Payload,
) {
    for block in payload.blocks.iter().filter(|block| block_is_seat(block)) {
        let at = relative(block);
        let Some(id) = vehicle(game, at, Some(pulley)) else {
            continue;
        };
        if let Some(Tag::Compound(tag)) = game.persist.raw.get_mut(&id) {
            tag.remove(&PULLEY.into());
            tag.insert(VEHICLE.into(), Tag::IntArray(offset(anchor, at).to_vec()));
        }
        move_vehicle(
            game,
            id,
            center(anchor.map(f64::from), at, STATIC_ATTACHMENT),
        );
    }
}

pub(super) fn prune(game: &mut Game<'_>) {
    let riders = game.guest_vehicles();
    let unused: Vec<_> = game
        .armor_stands
        .iter()
        .filter_map(|stand| {
            let tag = game.persist.raw.get(&stand.id)?;
            let at = position(tag, VEHICLE)?;
            let mob_seated = game.mobs.iter().any(|mob| {
                mob.extra.mount == Some(stand.id) && mob.alive() && !mob.removed
            });
            let seated = Some(stand.id) == game.riding || riders.contains(&stand.id) || mob_seated;
            let seat_exists = if let Some(train) = train_owner(tag) {
                super::create_train::has_seat(game, train, at)
            } else if let Some(pulley) = position(tag, PULLEY) {
                !game.world.loaded(pulley[0], pulley[2]) || rope::payload(game, pulley).is_some()
            } else {
                !game.world.loaded(at[0], at[2]) || is_seat(&game.native_block(at))
            };
            // The last ride tick positions a mob before its Seat is removed.
            (!seated || (!seat_exists && !mob_seated)).then_some(stand.id)
        })
        .collect();
    for id in unused {
        discard_vehicle(game, id);
    }

    let unused: Vec<_> = game
        .others
        .iter()
        .filter_map(|target| {
            let tag = game.persist.raw.get(&target.id)?;
            let seat = position(tag, HITBOX)?;
            if let Some(train) = train_owner(tag) {
                return (!super::create_train::has_seat(game, train, seat)).then_some(target.id);
            }
            let pulley = position(tag, PULLEY)?;
            (game.world.loaded(pulley[0], pulley[2]) && rope::payload(game, pulley).is_none())
                .then_some(target.id)
        })
        .collect();
    for id in unused {
        game.native_remove_entity(game.native_dimension(), id);
    }
}

use super::{
    Game, GameLevel, create_fluids::name as direction_name,
    native_block_entity_draw::BlockEntityDraw,
};
use crate::{
    containers::{BlockEntity, ModBlockEntity},
    items::ItemStack,
};
use horizon_core::{geometry::Direction, position::BlockPos};
use horizon_world::{
    fluid::{FluidKind, FluidState},
    level::PlacementContext,
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

pub(super) const BLOCK: &str = "create:factory_gauge";
pub(super) const ENTITY: &str = "create:factory_panel";
const PANEL: &str = "create:block/factory_gauge/panel";

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
    fluid: FluidState,
) -> Option<BlockStateId> {
    let mut placed = level.registry.state(state)?.clone();
    if placed.name != BLOCK {
        return None;
    }
    let outward = if context.replace_clicked {
        context.nearest_looking_direction().opposite()
    } else {
        context.face
    };
    let yaw = (f64::from(context.yaw) / 90.0 + 0.5).floor() as i64 & 3;
    let horizontal = [
        Direction::South,
        Direction::West,
        Direction::North,
        Direction::East,
    ][yaw as usize];
    let (face, facing) = match outward {
        Direction::Up => ("floor", horizontal),
        Direction::Down => ("ceiling", horizontal.opposite()),
        side => ("wall", side),
    };
    placed.properties.insert("face".into(), face.into());
    placed
        .properties
        .insert("facing".into(), direction_name(facing).into());
    placed.properties.insert(
        "waterlogged".into(),
        (fluid.kind() == FluidKind::Water && fluid.is_source()).to_string(),
    );
    level.registry.id(&placed)
}

fn angles(face: &str, facing: &str) -> (f32, f32) {
    let x = match face {
        "wall" => 90.0,
        "ceiling" => 180.0,
        _ => 0.0,
    };
    let y = match facing {
        "south" => 0.0,
        "west" => 90.0,
        "north" => 180.0,
        "east" => 270.0,
        _ => 0.0,
    };
    (x, y + if face == "ceiling" { 180.0 } else { 0.0 })
}

fn rotate_y(v: [f64; 3], degrees: f64) -> [f64; 3] {
    let (s, c) = degrees.to_radians().sin_cos();
    [v[0] * c + v[2] * s, v[1], -v[0] * s + v[2] * c]
}
fn rotate_x(v: [f64; 3], degrees: f64) -> [f64; 3] {
    let (s, c) = degrees.to_radians().sin_cos();
    [v[0], v[1] * c - v[2] * s, v[1] * s + v[2] * c]
}

fn selected_slot(game: &Game<'_>, at: [i32; 3], point: [f64; 3]) -> (i32, i32) {
    let face = game.native_block_property(at, "face").unwrap_or_default();
    let facing = game.native_block_property(at, "facing").unwrap_or_default();
    let (x, y) = angles(&face, &facing);
    let mut local = std::array::from_fn(|i| point[i] - f64::from(at[i]) - 0.5);
    local = rotate_y(local, -f64::from(y));
    local = rotate_x(local, -f64::from(x));
    local = rotate_y(local, -180.0);
    (i32::from(local[0] >= 0.0), i32::from(local[2] >= 0.0))
}

fn slot_name(x: i32, z: i32) -> &'static str {
    match (x, z) {
        (1, 1) => "top_left",
        (0, 1) => "top_right",
        (1, 0) => "bottom_left",
        _ => "bottom_right",
    }
}

fn frequency(stack: &ItemStack) -> Option<Tag> {
    horizon_client::block_entity_item::data(stack)
        .and_then(|(_, data)| data.get("Freq"))
        .cloned()
}

pub(super) fn placed(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) {
    let Some(hit) = game.pick() else {
        return;
    };
    let (x, z) = selected_slot(game, at, hit.point);
    let freq = frequency(stack);
    game.native_with_mod_block_entity(at, |entity| {
        if let Some(freq) = freq {
            entity.nbt.insert(
                slot_name(x, z).into(),
                Tag::Compound(Compound::from([("Freq".into(), freq)])),
            );
        }
        entity.nbt.insert("PanelX".into(), Tag::Int(x));
        entity.nbt.insert("PanelZ".into(), Tag::Int(z));
    });
    game.native_block_entity_sync(at);
}

pub(super) fn add_panel(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) -> bool {
    if &*stack.item != BLOCK || game.native_block(at) != BLOCK || !game.native_authoritative() {
        return false;
    }
    let Some(hit) = game.pick().filter(|hit| hit.pos == at) else {
        return false;
    };
    let Some(freq) = frequency(stack) else {
        game.guest_inventory_resend |= game.lan_acting.is_some();
        return true;
    };
    let (x, z) = selected_slot(game, at, hit.point);
    let name = slot_name(x, z);
    let mut added = false;
    game.native_with_mod_block_entity(at, |entity| {
        if entity.nbt.contains_key(&name.into()) {
            return;
        }
        // Earlier placed gauges recorded their first slot separately.
        let old_x = match entity.nbt.get(&"PanelX".into()) {
            Some(Tag::Int(v)) => *v,
            _ => -1,
        };
        let old_z = match entity.nbt.get(&"PanelZ".into()) {
            Some(Tag::Int(v)) => *v,
            _ => -1,
        };
        if (old_x, old_z) == (x, z) {
            return;
        }
        entity.nbt.insert(
            name.into(),
            Tag::Compound(Compound::from([("Freq".into(), freq)])),
        );
        added = true;
    });
    if added {
        game.native_block_entity_sync(at);
        game.consume_held();
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    true
}

pub(super) fn render(
    game: &Game<'_>,
    state: BlockStateId,
    entity: &ModBlockEntity,
    draw: &mut BlockEntityDraw,
) {
    let Some(state) = game.pack.assets.registry.state(state) else {
        return;
    };
    let face = state.properties.get("face").map_or("floor", String::as_str);
    let facing = state
        .properties
        .get("facing")
        .map_or("south", String::as_str);
    let (x, y) = angles(face, facing);
    let old = |key: &str| match entity.nbt.get(&key.into()) {
        Some(Tag::Int(v)) => *v,
        _ => -1,
    };
    let old_slot = (old("PanelX"), old("PanelZ"));
    for (sx, sz) in [(1, 1), (0, 1), (1, 0), (0, 0)] {
        if !entity.nbt.contains_key(&slot_name(sx, sz).into()) && old_slot != (sx, sz) {
            continue;
        }
        draw.push();
        draw.rotate_about([0.0, 1.0, 0.0], y, [0.5; 3]);
        draw.rotate_about([1.0, 0.0, 0.0], x, [0.5; 3]);
        draw.rotate_about([0.0, 1.0, 0.0], 180.0, [0.5; 3]);
        draw.translate([sx as f32 * 0.5, 0.0, sz as f32 * 0.5]);
        game.native_draw_model(draw, PANEL, 0xffffff);
        draw.pop();
    }
}

pub(super) fn set_filter(game: &mut Game<'_>, at: [i32; 3], stack: &ItemStack) -> bool {
    if !game.native_authoritative()
        || game.native_block(at) != BLOCK
        || matches!(
            stack.item.as_ref(),
            "create:factory_gauge"
                | "create:wrench"
                | "create:mechanical_arm"
                | "create:filter"
                | "create:attribute_filter"
                | "create:package_filter"
        )
    {
        return false;
    }
    let Some(hit) = game.pick().filter(|hit| hit.pos == at) else {
        return false;
    };
    let (x, z) = selected_slot(game, at, hit.point);
    let name = slot_name(x, z);
    let mut changed = false;
    let mut filter = super::create_depot::encode(stack);
    if let Tag::Compound(fields) = &mut filter {
        fields.remove(&"Slot".into());
    }
    game.native_with_mod_block_entity(at, |entity| {
        let Some(Tag::Compound(panel)) = entity.nbt.get_mut(&name.into()) else {
            return;
        };
        if panel
            .get(&"Filter".into())
            .and_then(|tag| match tag {
                Tag::Compound(data) => ItemStack::from_nbt(data),
                _ => None,
            })
            .is_some()
        {
            return;
        }
        panel.insert("Filter".into(), filter);
        changed = true;
    });
    if changed {
        game.native_block_entity_sync(at);
        game.guest_inventory_resend |= game.lan_acting.is_some();
    }
    changed
}

pub(super) fn reject_untuned(stack: &ItemStack) -> bool {
    &*stack.item == BLOCK
        && stack
            .data()
            .and_then(|data| data.other("minecraft:block_entity_data"))
            .is_none()
}

fn support_direction(level: &GameLevel<'_>, state: BlockStateId) -> Option<Direction> {
    let state = level
        .registry
        .state(state)
        .filter(|state| state.name == BLOCK)?;
    match state.properties.get("face")?.as_str() {
        "floor" => Some(Direction::Down),
        "ceiling" => Some(Direction::Up),
        "wall" => Direction::ALL
            .into_iter()
            .find(|side| {
                direction_name(*side) == state.properties.get("facing").map_or("", String::as_str)
            })
            .map(Direction::opposite),
        _ => None,
    }
}

fn has_collision(level: &GameLevel<'_>, at: BlockPos, state: BlockStateId) -> bool {
    let mut scene = horizon_client::collisions::SceneCollisions {
        world: &*level.world,
        binding: level.collision,
        subject: None,
    };
    level
        .collision
        .collision_shape(&mut scene, state, [at.x, at.y, at.z])
        .is_ok_and(|shape| !shape.is_empty())
}

pub(super) fn survive(level: &GameLevel<'_>, at: BlockPos, state: BlockStateId) -> Option<bool> {
    let support = support_direction(level, state)?;
    let [x, y, z] = support.normal();
    let at = at.offset(x, y, z);
    Some(has_collision(
        level,
        at,
        level.world.block(at.x, at.y, at.z),
    ))
}

pub(super) fn update_support(
    level: &GameLevel<'_>,
    state: BlockStateId,
    direction: Direction,
    neighbour_pos: BlockPos,
    neighbour: BlockStateId,
) -> Option<BlockStateId> {
    if support_direction(level, state)? != direction
        || has_collision(level, neighbour_pos, neighbour)
    {
        return None;
    }
    // The updater destroys an air result and restores water for a waterlogged block.
    level.registry.default_state("minecraft:air")
}

fn panel_count(nbt: &Compound) -> usize {
    let count = [(1, 1), (0, 1), (1, 0), (0, 0)]
        .into_iter()
        .filter(|&(x, z)| nbt.contains_key(&slot_name(x, z).into()))
        .count();
    if count == 0 && nbt.contains_key(&"PanelX".into()) && nbt.contains_key(&"PanelZ".into()) {
        1
    } else {
        count
    }
}

pub(super) fn remove(level: &mut GameLevel<'_>, pos: BlockPos, side_effects: bool) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    else {
        return;
    };
    if entity.id != ENTITY {
        return;
    }
    let extra = panel_count(&entity.nbt).saturating_sub(1);
    if extra > 0 {
        level.drop_lost_contents(pos, vec![Some(ItemStack::new(BLOCK, extra as u32))]);
    }
}

pub(super) fn break_panel(game: &mut Game<'_>, at: [i32; 3], canceled: &mut bool) {
    if *canceled || !game.native_authoritative() || game.native_block(at) != BLOCK {
        return;
    }
    let Some(hit) = game.pick().filter(|hit| hit.pos == at) else {
        return;
    };
    let (x, z) = selected_slot(game, at, hit.point);
    let mut removed = false;
    game.native_with_mod_block_entity(at, |entity| {
        if panel_count(&entity.nbt) < 2 {
            return;
        }
        if entity.nbt.remove(&slot_name(x, z).into()).is_none() {
            return;
        }
        let old_x = match entity.nbt.get(&"PanelX".into()) {
            Some(Tag::Int(v)) => *v,
            _ => -1,
        };
        let old_z = match entity.nbt.get(&"PanelZ".into()) {
            Some(Tag::Int(v)) => *v,
            _ => -1,
        };
        if (old_x, old_z) == (x, z) {
            entity.nbt.remove(&"PanelX".into());
            entity.nbt.remove(&"PanelZ".into());
        }
        removed = true;
    });
    if !removed {
        return;
    }
    if !game.creative {
        game.pop_resource(at, ItemStack::new(BLOCK, 1));
    }
    game.native_block_entity_sync(at);
    *canceled = true;
}

#[derive(Clone)]
struct PanelSession {
    pos: [i32; 3],
    slot: &'static str,
    frequency: Tag,
    connecting: bool,
    dimension: String,
}

thread_local! {
    static SESSIONS: std::cell::RefCell<std::collections::HashMap<[i32; 4], PanelSession>> =
        std::cell::RefCell::new(std::collections::HashMap::new());
}

pub(super) fn open_config(game: &mut Game<'_>, at: [i32; 3], point: [f64; 3]) -> bool {
    if !game.native_authoritative()
        || game.hand != horizon_client::first_person::Hand::Main
        || game.native_block(at) != BLOCK
        || game.held().is_some()
        || game.native_sneaking()
    {
        return false;
    }
    let (x, z) = selected_slot(game, at, point);
    let name = slot_name(x, z);
    let Some(panel) = super::create_machines::mod_entity(game, at)
        .and_then(|entity| super::create_depot::compound(&entity.nbt, name))
    else {
        return false;
    };
    if super::create_depot::compound(panel, "Filter")
        .and_then(ItemStack::from_nbt)
        .is_none()
    {
        return false;
    }
    let Some(freq) = panel.get(&"Freq".into()).cloned() else {
        return false;
    };
    let session = PanelSession {
        pos: at,
        slot: name,
        frequency: freq,
        connecting: false,
        dimension: game.native_dimension().to_owned(),
    };
    SESSIONS.with_borrow_mut(|sessions| {
        sessions.insert(game.acting_player_uuid(), session);
    });
    game.open_menu(at);
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 200.0,
        height: 160.0,
        slots: vec![None],
        inventory_x: 12.0,
        inventory_y: 800.0,
        own_labels: true,
        own_background: true,
    }
}

pub(super) fn draw_screen(
    game: &Game<'_>,
    batch: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    game.native_sprite(
        batch,
        "create:gui/factory_gauge",
        [32.0, 0.0, 192.0, 96.0],
        [x, y, 192.0, 96.0],
    );
    game.native_sprite(
        batch,
        "create:gui/factory_gauge",
        [32.0, 176.0, 200.0, 64.0],
        [x, y + 96.0, 200.0, 64.0],
    );
    horizon_client::widgets::record("Add new connection", [x + 31.0, y + 47.0, 18.0, 18.0], true);
    game.native_text(batch, "+", [x + 36.0, y + 51.0], 0xFFFFFF, false);
}

thread_local! {
    static CLOSE_AFTER_CONNECT: std::cell::Cell<bool> = const { std::cell::Cell::new(false) };
}

pub(super) fn screen_click([x, y]: [f32; 2]) -> Option<i32> {
    if x >= 31.0 && x < 49.0 && y >= 47.0 && y < 65.0 {
        CLOSE_AFTER_CONNECT.set(true);
        Some(0)
    } else {
        None
    }
}

pub(super) fn close_after_connect(game: &mut Game<'_>) {
    if !CLOSE_AFTER_CONNECT.replace(false)
        || game.remote.is_none()
        || game.screen != super::Screen::Inventory
    {
        return;
    }
    game.close_container();
    game.screen = super::Screen::Playing;
    game.capture(true);
}

pub(super) fn menu_button(game: &mut Game<'_>, pos: [i32; 3], button: i32) {
    if button != 0 {
        return;
    }
    let player = game.acting_player_uuid();
    let valid = SESSIONS.with_borrow_mut(|sessions| {
        let Some(session) = sessions
            .get_mut(&player)
            .filter(|session| session.pos == pos)
        else {
            return false;
        };
        session.connecting = true;
        true
    });
    if !valid {
        return;
    }
}

pub(super) fn connect_link(game: &mut Game<'_>, at: [i32; 3]) -> bool {
    if !game.native_authoritative() {
        return false;
    }
    let player = game.acting_player_uuid();
    let session = SESSIONS.with_borrow_mut(|sessions| {
        if sessions
            .get(&player)
            .is_some_and(|session| session.connecting)
        {
            sessions.remove(&player)
        } else {
            None
        }
    });
    let Some(session) = session else {
        return false;
    };
    if game.native_block(at) != super::create_display_link::LINK
        || game.native_dimension() != session.dimension
        || game.native_block(session.pos) != BLOCK
    {
        return true;
    }
    let panel_is_current = super::create_machines::mod_entity(game, session.pos)
        .and_then(|entity| super::create_depot::compound(&entity.nbt, session.slot))
        .is_some_and(|panel| panel.get(&"Freq".into()) == Some(&session.frequency));
    if !panel_is_current {
        return true;
    }
    let face = game
        .native_block_property(session.pos, "face")
        .unwrap_or_default();
    let facing = game
        .native_block_property(session.pos, "facing")
        .unwrap_or_default();
    let direction = match face.as_str() {
        "floor" => "up",
        "ceiling" => "down",
        _ => facing.as_str(),
    };
    let axis = match direction {
        "up" | "down" => 1,
        "east" | "west" => 0,
        _ => 2,
    };
    let diff: [i32; 3] = std::array::from_fn(|i| at[i] - session.pos[i]);
    if game.native_block_property(at, "facing").as_deref() != Some(direction)
        || diff[axis] != 0
        || diff.iter().map(|v| i64::from(*v).pow(2)).sum::<i64>() >= 256
    {
        return true;
    }
    let entry = Tag::compound([
        ("pos", Tag::IntArray(session.pos.to_vec())),
        ("slot", Tag::String(session.slot.into())),
    ]);
    game.native_with_mod_block_entity(at, |entity| {
        let links = entity
            .nbt
            .entry("LinkedGauges".into())
            .or_insert_with(|| Tag::List(Vec::new()));
        if let Tag::List(links) = links
            && !links.contains(&entry)
        {
            links.push(entry);
        }
    });
    game.native_block_entity_sync(at);
    true
}

pub(super) fn container(block: &str, container: &mut Option<crate::containers::ModContainer>) {
    if block != BLOCK {
        return;
    }
    *container = Some(crate::containers::ModContainer {
        slots: 1,
        faces: std::array::from_fn(|_| Vec::new()),
        inputs: Vec::new(),
        outputs: Vec::new(),
        menu: Some(BLOCK.to_owned()),
    });
}

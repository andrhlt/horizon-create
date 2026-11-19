use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;
use horizon_world::level::flags;
use horizon_world::nbt::{Compound, Tag};

use crate::containers::ModBlockEntity;
use crate::items::ItemStack;

use super::create_depot::{DEPOT, compound, nixie_palette};
use super::create_machines::{int, mod_entity, offset};
use super::create_smart_observer::{OBSERVER, observed_pos};
use super::create_threshold_switch::delta;
use super::{Game, Hand};

pub(super) const LINK: &str = "create:display_link";
pub(super) const SELECTION: &str = "create:click_to_link_data";
const COUNT: &str = "create:content_observer_source_count_items";
const ITEM_NAMES: &str = "create:depot_source_combine_item_names";
const GAUGE_STATUS: &str = "create:gauge_status";
const OBSERVED_TRAIN: &str = "create:observed_train_name";
const COUNT_LABEL: &str = "Amount of matching Items";
const ITEM_NAMES_LABEL: &str = "Combine Item Names";
const GAUGE_STATUS_LABEL: &str = "Factory gauge status";
const OBSERVED_TRAIN_LABEL: &str = "Detected Train Name";
const PREVIOUS_ROW: [f32; 4] = [35.0, 78.0, 24.0, 18.0];
const NEXT_ROW: [f32; 4] = [176.0, 78.0, 24.0, 18.0];
const SOURCE_BUTTON: [f32; 4] = [30.0, 42.0, 174.0, 22.0];

fn string(data: &Compound, key: &str) -> Option<String> {
    match data.get(&key.into())? {
        Tag::String(value) => Some(value.to_string_lossy()),
        _ => None,
    }
}

fn coords(value: &Tag) -> Option<[i32; 3]> {
    match value {
        Tag::IntArray(values) => values.as_slice().try_into().ok(),
        Tag::List(values) => match values.as_slice() {
            [Tag::Int(x), Tag::Int(y), Tag::Int(z)] => Some([*x, *y, *z]),
            _ => None,
        },
        _ => None,
    }
}

fn facing(side: &str) -> Direction {
    match side {
        "down" => Direction::Down,
        "east" => Direction::East,
        "north" => Direction::North,
        "south" => Direction::South,
        "west" => Direction::West,
        _ => Direction::Up,
    }
}

fn side_name(face: [i32; 3]) -> &'static str {
    match face {
        [0, -1, 0] => "down",
        [1, 0, 0] => "east",
        [0, 0, -1] => "north",
        [0, 0, 1] => "south",
        [-1, 0, 0] => "west",
        _ => "up",
    }
}

fn source_face(game: &Game<'_>, pos: [i32; 3]) -> Direction {
    facing(
        &game
            .native_block_property(pos, "facing")
            .unwrap_or_default(),
    )
    .opposite()
}

fn powered(game: &mut Game<'_>, pos: [i32; 3], source: Direction) -> bool {
    game.with_level(|behaviours, level, ticks| {
        Direction::ALL
            .into_iter()
            .filter(|&side| side != source)
            .any(|side| {
                let [x, y, z] = offset(pos, delta(side));
                behaviours.signal_at(level, ticks, BlockPos::new(x, y, z), side) > 0
            })
    })
}

fn other_chest(game: &Game<'_>, pos: [i32; 3]) -> Option<[i32; 3]> {
    let id = game.native_block(pos);
    if !matches!(id.as_str(), "minecraft:chest" | "minecraft:trapped_chest") {
        return None;
    }
    let direction = game.native_block_property(pos, "facing")?;
    let [x, _, z] = delta(facing(&direction));
    let (side, other_type) = match game.native_block_property(pos, "type")?.as_str() {
        "left" => ([-z, 0, x], "right"),
        "right" => ([z, 0, -x], "left"),
        _ => return None,
    };
    let other = offset(pos, side);
    (game.native_block(other) == id
        && game.native_block_property(other, "facing").as_deref() == Some(&direction)
        && game.native_block_property(other, "type").as_deref() == Some(other_type))
    .then_some(other)
}

fn observed_count(game: &Game<'_>, observer: [i32; 3], filter: &Compound) -> u32 {
    let pos = observed_pos(game, observer);
    [Some(pos), other_chest(game, pos)]
        .into_iter()
        .flatten()
        .map(|[x, y, z]| {
            game.world
                .block_entities
                .get(&(x, y, z))
                .map_or(0, |entity| {
                    entity
                        .slots()
                        .iter()
                        .flatten()
                        .filter(|item| {
                            super::create_item_filters::accepts(game.items(), filter, item)
                        })
                        .map(|item| item.count)
                        .sum::<u32>()
                })
        })
        .sum()
}

pub(super) fn nixie_text(data: &Compound) -> Option<String> {
    let text = serde_json::from_str::<serde_json::Value>(&string(data, "CustomText")?).ok()?;
    Some(
        text.as_str()
            .or_else(|| text.get("text")?.as_str())?
            .to_owned(),
    )
}

pub(super) fn nixie_row(game: &Game<'_>, mut pos: [i32; 3]) -> Vec<[i32; 3]> {
    if nixie_palette(&game.native_block(pos)).is_none() {
        return Vec::new();
    }
    let state = game.world.block(pos[0], pos[1], pos[2]);
    let geometry = ["double_face", "facing", "waterlogged"];
    let same_tube = |at: [i32; 3]| {
        let other = game.world.block(at[0], at[1], at[2]);
        nixie_palette(&game.native_block(at)).is_some()
            && geometry.iter().all(|key| {
                game.native_block_state_property(other, key)
                    == game.native_block_state_property(state, key)
            })
    };
    let left = match game.native_block_state_property(state, "double_face") {
        Some("wall") => Direction::Up,
        Some("wall_reversed") => Direction::Down,
        _ => facing(
            game.native_block_state_property(state, "facing")
                .unwrap_or("north"),
        )
        .opposite(),
    };
    while same_tube(offset(pos, delta(left))) {
        pos = offset(pos, delta(left));
    }
    let mut row = Vec::new();
    while same_tube(pos) {
        row.push(pos);
        pos = offset(pos, delta(left.opposite()));
    }
    row
}

pub(super) fn publish_nixie_text(game: &mut Game<'_>, pos: [i32; 3], serialized: &str) {
    for (index, pos) in nixie_row(game, pos).into_iter().enumerate() {
        let index = index as i32;
        let mut changed = false;
        game.native_with_mod_block_entity(pos, |tube| {
            if string(&tube.nbt, "RawCustomText").as_deref() != Some(serialized)
                || int(&tube.nbt, "CustomTextIndex") != Some(index)
            {
                let text = Tag::String(serialized.into());
                tube.nbt.insert("CustomText".into(), text.clone());
                tube.nbt.insert("RawCustomText".into(), text);
                tube.nbt.insert("CustomTextIndex".into(), Tag::Int(index));
                changed = true;
            }
        });
        if changed {
            game.native_block_entity_sync(pos);
        }
    }
}

fn active(data: &Compound) -> Option<&'static str> {
    let configured = compound(data, "Source").and_then(|source| string(source, "Id"));
    match configured.as_deref() {
        Some(COUNT) => Some(COUNT),
        Some(ITEM_NAMES) => Some(ITEM_NAMES),
        Some(GAUGE_STATUS) => Some(GAUGE_STATUS),
        Some(OBSERVED_TRAIN) => Some(OBSERVED_TRAIN),
        _ => None,
    }
}

fn item_names(game: &Game<'_>, mut pos: [i32; 3], side: Direction) -> String {
    let mut names = String::new();
    for _ in 0..32 {
        let Some(depot) = mod_entity(game, pos).filter(|entity| entity.id == DEPOT) else {
            break;
        };
        if let Some(item) = depot.items.first().and_then(Option::as_ref)
            && super::create_machines::float(&depot.nbt, "BeltPosition").unwrap_or(0.5) >= 0.25
        {
            let id = item.item.as_ref();
            let name = id.split_once(':').map_or(id, |(_, tail)| tail);
            names.push_str(&name.replace('_', " "));
        }
        pos = offset(pos, delta(side));
    }
    names
}

fn target(game: &Game<'_>, pos: [i32; 3], data: &Compound) -> Option<([i32; 3], i32)> {
    let at = offset(pos, coords(data.get(&"TargetOffset".into())?)?);
    let count = if nixie_palette(&game.native_block(at)).is_some() {
        1
    } else {
        super::create_display_board::rows(game, at)?
    };
    Some((at, count))
}

fn source_at(game: &Game<'_>, pos: [i32; 3], data: &Compound) -> Option<&'static str> {
    if let Some(Tag::List(panels)) = data.get(&"LinkedGauges".into())
        && let Some(first) = panels.first()
    {
        let source = first.get("pos").and_then(coords)?;
        return (game.native_block(source) == super::create_factory_gauge::BLOCK)
            .then_some(GAUGE_STATUS);
    }
    match game
        .native_block(offset(pos, delta(source_face(game, pos))))
        .as_str()
    {
        OBSERVER => Some(COUNT),
        DEPOT => Some(ITEM_NAMES),
        super::create_factory_gauge::BLOCK => Some(GAUGE_STATUS),
        super::create_track_observer::OBSERVER => Some(OBSERVED_TRAIN),
        _ => None,
    }
}

fn gauge_rows(game: &mut Game<'_>, data: &Compound, limit: usize) -> Vec<String> {
    let Some(Tag::List(positions)) = data.get(&"LinkedGauges".into()) else {
        return Vec::new();
    };
    let format = compound(data, "Source")
        .and_then(|source| int(source, "Format"))
        .unwrap_or(0);
    let panels: Vec<_> = positions
        .iter()
        .filter_map(|position| {
            let pos = position.get("pos").and_then(coords)?;
            let Tag::String(slot) = position.get("slot")? else {
                return None;
            };
            let slot = slot.to_string_lossy();
            if !matches!(
                slot.as_ref(),
                "top_left" | "top_right" | "bottom_left" | "bottom_right"
            ) {
                return None;
            }
            let entity = mod_entity(game, pos)
                .filter(|entity| entity.id == super::create_factory_gauge::ENTITY)?;
            let panel = compound(&entity.nbt, &slot)?;
            let filter = compound(panel, "Filter").and_then(ItemStack::from_nbt)?;
            let Tag::IntArray(freq) = panel.get(&"Freq".into())? else {
                return None;
            };
            let frequency: [i32; 4] = freq.as_slice().try_into().ok()?;
            Some((panel.clone(), filter, frequency))
        })
        .take(limit)
        .collect();
    panels
        .into_iter()
        .map(|(panel, filter, frequency)| {
            let summary = super::create_stock_network::summary(game, frequency, false);
            let amount: u32 = summary
                .items
                .iter()
                .filter(|item| super::create_machines::same_stack(item, &filter))
                .map(|item| item.count)
                .sum();
            let number = if format == 0 && amount >= 1_000_000 {
                format!("{}m ", amount / 1_000_000)
            } else if format == 0 && amount >= 1000 {
                format!("{}k ", amount / 1000)
            } else {
                format!("{amount} ")
            };
            let target = int(&panel, "FilterAmount").unwrap_or(0);
            let symbol = if target == 0 {
                " "
            } else if int(&panel, "Satisfied") == Some(1) {
                "✔"
            } else if int(&panel, "LastPromised").unwrap_or(0) != 0 {
                "↑"
            } else {
                "▪"
            };
            let name = game
                .stack_display_name(&filter)
                .plain()
                .trim_start_matches('[')
                .trim_end_matches(']')
                .to_owned();
            format!("{number}{symbol} {name} ")
        })
        .collect()
}

fn observed_train_text(game: &Game<'_>, id: Option<u32>, data: &Compound) -> String {
    let Some(train) = id.and_then(|id| super::create_train::carriage(game, id)) else { return String::new() };
    let name = string(train, "Name").unwrap_or_else(|| game.translate("create.train.unnamed", "Unnamed Train"));
    let label = compound(data, "Source").and_then(|source| string(source, "Label")).unwrap_or_default();
    if label.is_empty() { name } else { format!("{label} {name}") }
}

fn publish_observed_train(game: &mut Game<'_>, pos: [i32; 3], data: &Compound, train: Option<u32>) {
    let Some((target, _)) = target(game, pos, data) else { return };
    let value = observed_train_text(game, train, data);
    if nixie_palette(&game.native_block(target)).is_some() {
        publish_nixie_text(game, target, &serde_json::json!({ "text": value }).to_string());
    } else {
        super::create_display_board::publish(game, target, int(data, "TargetLine").unwrap_or(0), &value);
    }
}

// The observer passes the current identity directly: its block entity is
// temporarily borrowed out of the level while its own tick is running.
pub(super) fn observed_train_changed(game: &mut Game<'_>, observer: [i32; 3], train: Option<u32>) {
    let links: Vec<_> = game.world.block_entities.iter().filter_map(|(&(x, y, z), entity)| {
        let crate::containers::BlockEntity::Mod(entity) = entity else { return None };
        let pos = [x, y, z];
        (entity.id == LINK && active(&entity.nbt) == Some(OBSERVED_TRAIN)
            && offset(pos, delta(source_face(game, pos))) == observer).then(|| (pos, entity.nbt.clone()))
    }).collect();
    for (pos, data) in links {
        let side = source_face(game, pos);
        if !powered(game, pos, side) { publish_observed_train(game, pos, &data, train); }
    }
}

fn refresh(game: &mut Game<'_>, pos: [i32; 3], data: &Compound) {
    let Some((target, target_rows)) = target(game, pos, data) else {
        return;
    };
    let side = source_face(game, pos);
    let source_pos = offset(pos, delta(side));
    if active(data) == Some(OBSERVED_TRAIN) {
        let train = mod_entity(game, source_pos).and_then(|entity| int(&entity.nbt, "ObservedTrain"))
            .and_then(|id| u32::try_from(id).ok());
        publish_observed_train(game, pos, data, train);
        return;
    }
    if active(data) == Some(GAUGE_STATUS) {
        let start = int(data, "TargetLine").unwrap_or(0).max(0);
        let rows = gauge_rows(game, data, target_rows.max(0) as usize);
        if nixie_palette(&game.native_block(target)).is_some() {
            let text = rows.first().map_or("", String::as_str);
            publish_nixie_text(
                game,
                target,
                &serde_json::json!({ "text": text }).to_string(),
            );
        } else {
            for row in 0..(target_rows - start).max(0) {
                let text = rows.get(row as usize).map_or("", String::as_str);
                super::create_display_board::publish(game, target, start + row, text);
            }
        }
        return;
    }
    let value = match active(data) {
        Some(COUNT) => {
            let Some(source) = mod_entity(game, source_pos).filter(|entity| entity.id == OBSERVER)
            else {
                return;
            };
            observed_count(game, source_pos, &source.nbt).to_string()
        }
        Some(ITEM_NAMES) => item_names(game, source_pos, side),
        _ => return,
    };
    if nixie_palette(&game.native_block(target)).is_some() {
        publish_nixie_text(
            game,
            target,
            &serde_json::json!({ "text": value }).to_string(),
        );
    } else {
        super::create_display_board::publish(
            game,
            target,
            int(data, "TargetLine").unwrap_or(0),
            &value,
        );
    }
}

fn screen_data(game: &Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    entity.data.resize(5, 0);
    entity.data[0] = i32::from(active(&entity.nbt).is_some());
    entity.data[2] = match source_at(game, pos, &entity.nbt) {
        Some(COUNT) => 1,
        Some(ITEM_NAMES) => 2,
        Some(GAUGE_STATUS) => 3,
        Some(OBSERVED_TRAIN) => 4,
        _ => 0,
    };
    entity.data[3] = int(&entity.nbt, "TargetLine").unwrap_or(0);
    entity.data[4] = target(game, pos, &entity.nbt).map_or(0, |(_, rows)| rows);
}

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    screen_data(game, pos, entity);
    let active = entity.data[0] != 0;
    let side = source_face(game, pos);
    let is_powered = powered(game, pos, side);
    let previous = game.native_block_property(pos, "powered").as_deref() == Some("true");
    if is_powered != previous {
        game.native_set_block_property(pos, "powered", if is_powered { "true" } else { "false" });
    }
    if !active {
        return;
    }
    entity.data[1] += 1;
    let refresh_ticks = if entity.data[2] == 4 { 400 } else { 100 };
    if previous && !is_powered || entity.data[1] >= refresh_ticks {
        entity.data[1] = 0;
        if !is_powered {
            refresh(game, pos, &entity.nbt);
        }
    }
}

fn clear(game: &mut Game<'_>) {
    if let Some(held) = game.held_mut() {
        held.data_mut().set_other(SELECTION, None);
    }
}

pub(super) fn use_item(
    game: &mut Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    stack: &ItemStack,
) -> bool {
    if stack.item.as_ref() != LINK || game.hand != Hand::Main {
        return false;
    }
    let dimension = game.native_dimension();
    let selection = stack.data().and_then(|data| data.other(SELECTION));
    if game.native_sneaking() && selection.is_some() {
        clear(game);
        return true;
    }
    let Some(Tag::Compound(selection)) = selection else {
        let block = game.native_block(pos);
        if (nixie_palette(&block).is_some() || block == super::create_display_board::BOARD)
            && let Some(held) = game.held_mut()
        {
            held.data_mut().set_other(
                SELECTION,
                Some(Tag::Compound(Compound::from([
                    ("Pos".into(), Tag::IntArray(pos.to_vec())),
                    ("Dimension".into(), Tag::String(dimension.into())),
                ]))),
            );
        }
        return true;
    };
    let Some(target) = selection.get(&"Pos".into()).and_then(coords) else {
        return true;
    };
    let hit = game.world.block(pos[0], pos[1], pos[2]);
    let place = if game.res.behaviours().is_replaceable(hit) {
        pos
    } else {
        offset(pos, face)
    };
    let distance_squared = (0..3)
        .map(|i| (i64::from(target[i]) - i64::from(place[i])).pow(2))
        .sum::<i64>();
    if string(selection, "Dimension").as_deref() != Some(dimension)
        || distance_squared >= 64 * 64
        || !game
            .res
            .behaviours()
            .is_replaceable(game.world.block(place[0], place[1], place[2]))
    {
        return true;
    }
    let Some(state) = game.native_default_state(LINK).and_then(|state| {
        game.with_level(|_, level, _| {
            level.native_state_with_property(state, "facing", side_name(face))
        })
    }) else {
        return true;
    };
    if game.native_set_block(dimension, place, state, flags::UPDATE_ALL) {
        let target_offset: [i32; 3] = std::array::from_fn(|i| target[i] - place[i]);
        game.native_with_mod_block_entity(place, |entity| {
            entity
                .nbt
                .insert("TargetOffset".into(), Tag::IntArray(target_offset.to_vec()));
            entity.nbt.insert("TargetLine".into(), Tag::Int(0));
        });
        game.native_block_entity_sync(place);
        clear(game);
        game.consume_held();
    }
    true
}

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.hand != Hand::Main || game.native_sneaking() || game.native_block(pos) != LINK {
        return false;
    }
    if mod_entity(game, pos).is_some_and(|entity| entity.nbt.contains_key(&"TargetOffset".into())) {
        game.open_menu(pos);
    }
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 235.0,
        height: 162.0,
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
    batch: &mut horizon_client::hud::HudBatch,
    [x, y]: [f32; 2],
) {
    game.native_sprite(
        batch,
        "create:gui/display_link",
        [0.0, 0.0, 235.0, 162.0],
        [x, y, 235.0, 162.0],
    );
    let centered = |batch: &mut horizon_client::hud::HudBatch, label: &str, row: f32, color| {
        game.native_text(
            batch,
            label,
            [x + (235.0 - game.native_text_width(label)) / 2.0, y + row],
            color,
            false,
        );
    };
    centered(batch, "Display Link", 4.0, 0x592424);
    let source = match data.get(2) {
        Some(1) => COUNT_LABEL,
        Some(2) => ITEM_NAMES_LABEL,
        Some(3) => GAUGE_STATUS_LABEL,
        Some(4) => OBSERVED_TRAIN_LABEL,
        _ => "No Display Source",
    };
    let [left, top, width, height] = SOURCE_BUTTON;
    let rows = data.get(4).copied().unwrap_or_default();
    if rows != 0 && source != "No Display Source" {
        horizon_client::widgets::record(source, [x + left, y + top, width, height], true);
    }
    centered(batch, source, top + 7.0, 0xFFFFFF);
    if rows > 1 {
        let selected = data.get(3).copied().unwrap_or_default();
        let label = format!("Row {} of {rows}", selected + 1);
        centered(batch, &label, 84.0, 0xFFFFFF);
        for (label, arrow, button, active) in [
            ("Previous Row", "<", PREVIOUS_ROW, selected > 0),
            ("Next Row", ">", NEXT_ROW, selected < rows - 1),
        ] {
            let [left, top, width, height] = button;
            horizon_client::widgets::record(label, [x + left, y + top, width, height], active);
            game.native_text(
                batch,
                arrow,
                [x + left + 8.0, y + top + 5.0],
                if active { 0xFFFFFF } else { 0xA0A0A0 },
                false,
            );
        }
    }
    if data.first() == Some(&1) {
        centered(batch, "Active", 112.0, 0xC5F398);
    }
}

pub(super) fn screen_click(data: &[i32], [x, y]: [f32; 2]) -> Option<i32> {
    let rows = data.get(4).copied().unwrap_or_default();
    let active = data.get(2).copied().unwrap_or_default() != 0;
    let contains = |[left, top, width, height]: [f32; 4]| {
        (left..left + width).contains(&x) && (top..top + height).contains(&y)
    };
    if active && rows > 0 && contains(SOURCE_BUTTON) {
        Some(0)
    } else if rows > 1 && contains(PREVIOUS_ROW) {
        Some(1)
    } else if rows > 1 && contains(NEXT_ROW) {
        Some(2)
    } else {
        None
    }
}

pub(super) fn menu_button(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    button: i32,
) {
    let Some((_, rows)) = target(game, pos, &entity.nbt) else {
        return;
    };
    match button {
        0 => {
            let Some(source) = source_at(game, pos, &entity.nbt) else {
                return;
            };
            entity.nbt.insert(
                "Source".into(),
                Tag::Compound(Compound::from([
                    ("Id".into(), Tag::String(source.into())),
                    ("Label".into(), Tag::String("".into())),
                ])),
            );
        }
        1 | 2 => {
            let before = int(&entity.nbt, "TargetLine").unwrap_or_default();
            let after = (before + if button == 1 { -1 } else { 1 }).clamp(0, rows - 1);
            entity.nbt.insert("TargetLine".into(), Tag::Int(after));
        }
        _ => return,
    }
    screen_data(game, pos, entity);
    entity.data[1] = 0;
    let side = source_face(game, pos);
    if !powered(game, pos, side) {
        refresh(game, pos, &entity.nbt);
    }
    game.native_block_entity_sync(pos);
}

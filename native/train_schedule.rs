use std::cell::RefCell;
use std::collections::BTreeMap;
use std::sync::Arc;

use horizon_client::first_person::Hand;
use horizon_client::hud::{HudBatch, rgba};
use horizon_client::mod_api::NativeScreenView;
use horizon_world::nbt::{self, Compound, Limits, Tag};

use crate::{items::ItemStack, save::item_to_nbt};

use super::{Game, commands::Target};
use super::create_train_schedule_suggestions::{Catalog, Dropdown};

const SCHEDULE: &str = "create:schedule";
const COMPONENT: &str = "create:train_schedule";
const EDITOR: &str = "create:schedule_editor";
const CHANNEL: &str = "create:schedule_editor";
const ATLAS: &str = "create:gui/schedule";
const WIDGETS: &str = "create:gui/widgets";
const ICONS: &str = "create:gui/icons";
const INSTRUCTION_ATLAS: &str = "create:gui/schedule_2";
const INVENTORY_ATLAS: &str = "create:gui/player_inventory";
const FIELD_ATLAS: &str = "create:gui/display_link";
const STATION: &str = "create:track_station";
const WIDTH: f32 = 256.0;
const HEIGHT: f32 = 226.0;
const ROW_TOP: f32 = 25.0;
const VIEW_TOP: f32 = 16.0;
const VIEW_BOTTOM: f32 = 189.0;
const DURATION_AREA: [f32; 4] = [77.0, 87.0, 31.0, 18.0];
const ACTION_TYPE_AREA: [f32; 4] = [56.0, 65.0, 143.0, 16.0];
const CARGO_OPERATOR_AREA: [f32; 4] = [77.0, 87.0, 24.0, 18.0];
const CARGO_AMOUNT_AREA: [f32; 4] = [106.0, 87.0, 41.0, 18.0];
const CARGO_MEASURE_AREA: [f32; 4] = [148.0, 87.0, 50.0, 18.0];
const FREQUENCY_STATE_AREA: [f32; 4] = [97.0, 87.0, 101.0, 18.0];
const LINK_ITEM: &str = "create:redstone_link";
const CONDITIONAL_AREA: [f32; 4] = [113.0, 87.0, 85.0, 18.0];
const THROTTLE_AREA: [f32; 4] = [77.0, 87.0, 50.0, 18.0];
const TIME_UNIT_AREA: [f32; 4] = [113.0, 87.0, 85.0, 18.0];
const MAX_DURATION: i32 = 120;
const HOUR_AREA: [f32; 4] = [77.0, 87.0, 16.0, 18.0];
const MINUTE_AREA: [f32; 4] = [95.0, 87.0, 16.0, 18.0];
const ROTATION_AREA: [f32; 4] = [129.0, 87.0, 62.0, 18.0];

#[derive(Clone, Copy)]
struct Delay {
    value: i32,
    unit: i32,
}

impl Default for Delay {
    fn default() -> Self {
        Self { value: 5, unit: 1 }
    }
}

impl Delay {
    fn valid(self) -> bool {
        (0..=MAX_DURATION).contains(&self.value) && (0..=2).contains(&self.unit)
    }
}

#[derive(Clone, Copy, PartialEq)]
enum ActionKind {
    Destination,
    Deliver,
    Retrieve,
    Title,
    Throttle,
}

impl ActionKind {
    const ALL: [Self; 5] = [
        Self::Destination, Self::Deliver, Self::Retrieve, Self::Title, Self::Throttle,
    ];

    fn declaration(self) -> (&'static str, &'static str) {
        match self {
            Self::Destination => ("destination", "Travel to Station"),
            Self::Deliver => ("package_delivery", "Deliver Package"),
            Self::Retrieve => ("package_retrieval", "Retrieve Package"),
            Self::Title => ("rename", "Update Schedule Title"),
            Self::Throttle => ("throttle", "Limit Max Speed"),
        }
    }

    fn decode(id: &str) -> Option<Self> {
        let name = id.strip_prefix("create:")?;
        Self::ALL.into_iter().find(|kind| kind.declaration().0 == name)
    }

    fn label(self, game: &Game<'_>) -> String {
        let (id, name) = self.declaration();
        game.translate(&format!("create.schedule.instruction.{id}"), name)
    }

    fn text(self) -> bool {
        matches!(self, Self::Destination | Self::Retrieve | Self::Title)
    }

    fn has_conditions(self) -> bool {
        matches!(self, Self::Destination | Self::Retrieve | Self::Deliver)
    }

    fn draw_icon(self, game: &Game<'_>, batch: &mut HudBatch, at: [f32; 2]) {
        match self {
            Self::Destination => game.native_item(batch, STATION, at, 16.0),
            Self::Deliver => game.native_item_model(batch, SCHEDULE, "create:white_postbox", at, 16.0),
            Self::Retrieve => game.native_item_model(batch, SCHEDULE, "create:cardboard_package_12x12", at, 16.0),
            Self::Title => game.native_item(batch, "minecraft:name_tag", at, 16.0),
            Self::Throttle => game.native_item(batch, "create:controls", at, 16.0),
        };
    }
}

#[derive(Clone, Copy, PartialEq)]
enum ConditionKind {
    Delay,
    TimeOfDay,
    FluidThreshold,
    ItemThreshold,
    RedstoneLink,
    PlayerCount,
    Idle,
    Unloaded,
    Powered,
}

impl ConditionKind {
    const ALL: [Self; 9] = [
        Self::Delay, Self::TimeOfDay, Self::FluidThreshold, Self::ItemThreshold,
        Self::RedstoneLink, Self::PlayerCount, Self::Idle, Self::Unloaded, Self::Powered,
    ];

    fn declaration(self) -> (&'static str, &'static str) {
        match self {
            Self::Delay => ("delay", "Scheduled Delay"),
            Self::TimeOfDay => ("time_of_day", "Time of Day"),
            Self::FluidThreshold => ("fluid_threshold", "Fluid Cargo Condition"),
            Self::ItemThreshold => ("item_threshold", "Item Cargo Condition"),
            Self::RedstoneLink => ("redstone_link", "Redstone Link"),
            Self::PlayerCount => ("player_count", "Players Seated"),
            Self::Idle => ("idle", "Cargo Inactivity"),
            Self::Unloaded => ("unloaded", "Chunk Unloaded"),
            Self::Powered => ("powered", "Station Powered"),
        }
    }

    fn decode(id: &str) -> Option<Self> {
        let name = id.strip_prefix("create:")?;
        Self::ALL.into_iter().find(|kind| kind.declaration().0 == name)
    }

    fn label(self, game: &Game<'_>) -> String {
        let (id, name) = self.declaration();
        game.translate(&format!("create.schedule.condition.{id}"), name)
    }

    fn cargo_sample_key(self) -> Option<&'static str> {
        match self {
            Self::FluidThreshold => Some("Bucket"),
            Self::ItemThreshold => Some("Item"),
            _ => None,
        }
    }
}

#[derive(Clone, Copy)]
struct TimeOfDay {
    hour: i32,
    minute: i32,
    rotation: i32,
}

impl TimeOfDay {
    fn label(self, game: &Game<'_>, pad_hour: bool) -> String {
        let hour = if self.hour % 12 == 0 { 12 } else { self.hour % 12 };
        let suffix = if self.hour < 12 {
            game.translate("create.generic.daytime.am", "am")
        } else {
            game.translate("create.generic.daytime.pm", "pm")
        };
        let hour12 = if pad_hour { format!("{hour:02}") } else { hour.to_string() };
        let hour24 = if pad_hour { format!("{:02}", self.hour) } else { self.hour.to_string() };
        game.translate("create.schedule.condition.time_of_day.digital_format", "%1$s:%3$s %4$s")
            .replace("%1$s", &hour12)
            .replace("%2$s", &hour24)
            .replace("%3$s", &format!("{:02}", self.minute))
            .replace("%4$s", &suffix)
    }

    fn rotation_label(self, game: &Game<'_>) -> String {
        let (key, label) = [
            ("every_24", "Every Day"), ("every_12", "Every 12:00"),
            ("every_6", "Every 6:00"), ("every_4", "Every 4:00"),
            ("every_3", "Every 3:00"), ("every_2", "Every 2:00"),
            ("every_1", "Every 1:00"), ("every_0_45", "Every 0:45"),
            ("every_0_30", "Every 0:30"), ("every_0_15", "Every 0:15"),
        ][self.rotation as usize];
        game.translate(&format!("create.schedule.condition.time_of_day.rotation.{key}"), label)
    }

    fn icon(self, game: &Game<'_>, batch: &mut HudBatch, [x, y]: [f32; 2]) {
        let minutes = (self.hour + 12) % 24 * 60 + self.minute;
        let frame = minutes * 64 / (24 * 60);
        game.native_sprite(batch, &format!("item/clock_{frame:02}"),
            [0.0, 0.0, 16.0, 16.0], [x, y, 16.0, 16.0]);
    }
}

#[derive(Clone, Copy, Default)]
struct PlayerCount {
    count: i32,
    exact: i32,
}

impl PlayerCount {
    fn summary(self, game: &Game<'_>) -> String {
        let (key, fallback) = if self.count == 1 {
            ("create.schedule.condition.player_count.summary", "%1$s Player")
        } else {
            ("create.schedule.condition.player_count.summary_plural", "%1$s Players")
        };
        game.translate(key, fallback).replace("%1$s", &self.count.to_string())
    }

    fn comparison(self, game: &Game<'_>) -> String {
        if self.exact == 0 {
            game.translate("create.schedule.condition.player_count.exactly", "Exactly")
        } else {
            game.translate("create.schedule.condition.player_count.or_above", "Or above")
        }
    }
}

#[derive(Clone, Copy)]
struct CargoThreshold {
    kind: ConditionKind,
    amount: i32,
    operator: i32,
    measure: i32,
    sampled: bool,
}

impl CargoThreshold {
    const OPERATORS: [&str; 3] = [">", "<", "="];

    fn summary(self) -> String {
        let unit = match (self.kind, self.measure) {
            (ConditionKind::FluidThreshold, _) => "b",
            (_, 1) => "▤",
            _ => "",
        };
        format!("{} {}{unit}", Self::OPERATORS[self.operator as usize], self.amount)
    }

    fn measure(self, game: &Game<'_>) -> String {
        match (self.kind, self.measure) {
            (ConditionKind::FluidThreshold, _) => game.translate("create.schedule.condition.threshold.buckets", "Buckets"),
            (_, 1) => game.translate("create.schedule.condition.threshold.stacks", "Stacks"),
            _ => game.translate("create.schedule.condition.threshold.items", "Items"),
        }
    }
}

#[derive(Clone, Copy)]
enum Condition {
    Delay(Delay),
    Idle(Delay),
    Cargo(CargoThreshold),
    PlayerCount(PlayerCount),
    RedstoneLink(i32),
    TimeOfDay(TimeOfDay),
    Powered,
    Other(ConditionKind),
}

impl Condition {
    fn new(kind: ConditionKind) -> Self {
        match kind {
            ConditionKind::Delay => Self::Delay(Delay::default()),
            ConditionKind::Idle => Self::Idle(Delay::default()),
            ConditionKind::FluidThreshold | ConditionKind::ItemThreshold => Self::Cargo(CargoThreshold {
                kind, amount: 10, operator: 0, measure: 0, sampled: false,
            }),
            ConditionKind::TimeOfDay => Self::TimeOfDay(TimeOfDay { hour: 8, minute: 0, rotation: 5 }),
            ConditionKind::RedstoneLink => Self::RedstoneLink(0),
            ConditionKind::PlayerCount => Self::PlayerCount(PlayerCount::default()),
            ConditionKind::Powered => Self::Powered,
            kind => Self::Other(kind),
        }
    }

    fn kind(self) -> ConditionKind {
        match self {
            Self::Delay(_) => ConditionKind::Delay,
            Self::Idle(_) => ConditionKind::Idle,
            Self::Cargo(cargo) => cargo.kind,
            Self::TimeOfDay(_) => ConditionKind::TimeOfDay,
            Self::PlayerCount(_) => ConditionKind::PlayerCount,
            Self::RedstoneLink(_) => ConditionKind::RedstoneLink,
            Self::Powered => ConditionKind::Powered,
            Self::Other(kind) => kind,
        }
    }

    fn ghost_slots(self) -> usize {
        match self {
            Self::Cargo(_) => 1,
            Self::RedstoneLink(_) => 2,
            _ => 0,
        }
    }

    fn summary(self, game: &Game<'_>) -> String {
        match self {
            Self::Cargo(cargo) => cargo.summary(),
            Self::Delay(delay) => timed_label(game, delay, "create.schedule.condition.delay_short", "Wait: %1$s"),
            Self::Idle(delay) => timed_label(game, delay, "create.schedule.condition.idle_short", "Cargo Idle: %1$s"),
            Self::TimeOfDay(time) => time.label(game, false),
            Self::PlayerCount(players) => players.summary(game),
            Self::RedstoneLink(1) => game.translate("create.schedule.condition.redstone_link_off", "Link Off"),
            Self::RedstoneLink(_) => game.translate("create.schedule.condition.redstone_link_on", "Link On"),
            other => other.kind().label(game),
        }
    }
}

#[derive(Clone, Copy)]
enum ConditionSlot {
    Existing { group: usize, term: usize },
    Append { group: usize },
    Alternative,
}

#[derive(Clone)]
struct Stop {
    raw: Tag,
    destination: Option<String>,
    conditions: Vec<Vec<Option<Condition>>>,
}

impl Stop {
    fn read(raw: Tag) -> Self {
        let destination = raw.get("Instruction").and_then(|instruction| {
            if !matches!(instruction.get("Id"), Some(Tag::String(id)) if id.to_string_lossy() == "create:destination") {
                return None;
            }
            let Tag::String(text) = instruction.get("Data")?.get("Text")? else {
                return None;
            };
            text.to_string().ok()
        });
        let conditions = read_conditions(&raw);
        Self { raw, destination, conditions }
    }

    fn instruction(&self) -> Option<&Tag> {
        self.raw.get("Instruction")
    }

    fn kind(&self) -> Option<ActionKind> {
        let Tag::String(id) = self.instruction()?.get("Id")? else {
            return None;
        };
        ActionKind::decode(&id.to_string_lossy())
    }

    fn has_conditions(&self) -> bool {
        self.kind().is_none_or(ActionKind::has_conditions)
    }

    fn height(&self) -> f32 {
        if self.has_conditions() {
            let rows = self.conditions.iter().map(Vec::len).max().unwrap_or(0);
            46.0 + rows as f32 * 18.0
        } else {
            26.0
        }
    }

    fn title(&self, game: &Game<'_>) -> String {
        match self.kind() {
            Some(ActionKind::Destination) => self.destination.as_deref()
                .filter(|filter| !filter.is_empty())
                .map(String::from)
                .unwrap_or_else(|| ActionKind::Destination.label(game)),
            Some(ActionKind::Title) => self.text().unwrap_or_default(),
            Some(ActionKind::Throttle) => format!("{}%", self.throttle()),
            Some(kind) => kind.label(game),
            None => match self.instruction().and_then(|instruction| instruction.get("Id")) {
                Some(Tag::String(id)) => id.to_string_lossy(),
                _ => String::new(),
            },
        }
    }

    fn text(&self) -> Option<String> {
        let Tag::String(text) = self.instruction()?.get("Data")?.get("Text")? else {
            return None;
        };
        text.to_string().ok()
    }

    fn throttle(&self) -> i32 {
        match self.instruction().and_then(|instruction| instruction.get("Data"))
            .and_then(|data| data.get("Value"))
        {
            Some(Tag::Int(value)) => *value,
            _ => 100,
        }
    }

    fn set_action(&mut self, draft: Draft) {
        let changed_kind = self.kind() != Some(draft.kind);
        let Tag::Compound(raw) = &mut self.raw else {
            return;
        };
        if changed_kind {
            let id = format!("create:{}", draft.kind.declaration().0);
            let instruction = Tag::compound([
                ("Id", Tag::String(id.as_str().into())),
                ("Data", Tag::Compound(Compound::new())),
            ]);
            raw.insert("Instruction".into(), instruction);
        }
        if let Some(Tag::Compound(data)) = raw.get_mut(&"Instruction".into())
            .and_then(|tag| tag.get_mut("Data"))
        {
            if draft.kind.text() {
                data.insert("Text".into(), Tag::String(draft.filter.as_str().into()));
            } else if draft.kind == ActionKind::Throttle {
                data.insert("Value".into(), Tag::Int(draft.throttle));
            }
        }
        if draft.kind.has_conditions() {
            raw.entry("Conditions".into()).or_insert_with(|| Tag::List(Vec::new()));
        } else {
            raw.remove(&"Conditions".into());
        }
        self.destination = (draft.kind == ActionKind::Destination).then_some(draft.filter);
        self.conditions = read_conditions(&self.raw);
    }

    fn condition_tag(&self, slot: ConditionSlot) -> Option<&Tag> {
        let ConditionSlot::Existing { group, term } = slot else { return None; };
        let Tag::List(groups) = self.raw.get("Conditions")? else { return None; };
        let Tag::List(conditions) = groups.get(group)? else { return None; };
        conditions.get(term)
    }

    fn condition_sample(&self, slot: ConditionSlot, kind: Condition, index: usize) -> Option<ItemStack> {
        let condition = self.condition_tag(slot)?;
        let data = condition.get("Data")?;
        let sample = if let Condition::Cargo(cargo) = kind {
            data.get(cargo.kind.cargo_sample_key()?)?
        } else {
            let Tag::List(frequencies) = data.get("Frequency").or_else(|| condition.get("Frequency"))? else {
                return None;
            };
            frequencies.get(index)?
        };
        let Tag::Compound(sample) = sample else { return None; };
        ItemStack::from_nbt(sample)
    }

    fn set_condition(&mut self, slot: ConditionSlot, value: Condition, fields: &ConditionFields) {
        let Some(Tag::List(groups)) = self.raw.get_mut("Conditions") else {
            return;
        };
        if matches!(slot, ConditionSlot::Alternative) {
            groups.push(Tag::List(vec![Tag::Compound(Compound::new())]));
        }
        let (column, term) = match slot {
            ConditionSlot::Existing { group, term } => (group, Some(term)),
            ConditionSlot::Append { group } => (group, None),
            ConditionSlot::Alternative => (groups.len() - 1, Some(0)),
        };
        let Some(Tag::List(group)) = groups.get_mut(column) else { return; };
        let term = term.unwrap_or_else(|| {
            group.push(Tag::Compound(Compound::new()));
            group.len() - 1
        });
        let Some(Tag::Compound(condition)) = group.get_mut(term) else { return; };
        let id = format!("create:{}", value.kind().declaration().0);
        if !matches!(condition.get(&"Id".into()), Some(Tag::String(old)) if old.to_string_lossy() == id) {
            condition.clear();
            condition.insert("Id".into(), Tag::String(id.as_str().into()));
        }
        if matches!(value, Condition::RedstoneLink(_)) {
            condition.remove(&"Frequency".into());
        }
        let data = condition.entry("Data".into()).or_insert_with(|| Tag::Compound(Compound::new()));
        if let Tag::Compound(data) = data {
            match value {
                Condition::Delay(delay) | Condition::Idle(delay) => {
                    data.insert("Value".into(), Tag::Int(delay.value));
                    data.insert("TimeUnit".into(), Tag::Int(delay.unit));
                }
                Condition::Cargo(cargo) => {
                    if let Some(key) = cargo.kind.cargo_sample_key() {
                        data.insert(key.into(), sample_tag(fields.samples[0].as_ref()));
                    }
                    let text = &fields.text;
                    let threshold = if text.parse::<i32>().is_ok() { text.as_str() } else { "0" };
                    data.insert("Threshold".into(), Tag::String(threshold.into()));
                    data.insert("Operator".into(), Tag::Int(cargo.operator));
                    data.insert("Measure".into(), Tag::Int(cargo.measure));
                }
                Condition::RedstoneLink(inverted) => {
                    let samples = fields.samples.iter().map(|sample| sample_tag(sample.as_ref())).collect();
                    data.insert("Frequency".into(), Tag::List(samples));
                    data.insert("Inverted".into(), Tag::Int(inverted));
                }
                Condition::PlayerCount(players) => {
                    data.insert("Count".into(), Tag::Int(players.count));
                    data.insert("Exact".into(), Tag::Int(players.exact));
                }
                Condition::TimeOfDay(time) => {
                    data.insert("Hour".into(), Tag::Int(time.hour));
                    data.insert("Minute".into(), Tag::Int(time.minute));
                    data.insert("Rotation".into(), Tag::Int(time.rotation));
                }
                _ => (),
            }
        }
        self.conditions = read_conditions(&self.raw);
    }

    fn removable(&self, group: usize) -> bool {
        self.conditions.len() > 1 || self.conditions.get(group).is_some_and(|terms| terms.len() > 1)
    }

    fn remove_condition(&mut self, column: usize, term: usize) {
        if !self.removable(column) { return; }
        if let Some(Tag::List(groups)) = self.raw.get_mut("Conditions")
            && let Some(Tag::List(group)) = groups.get_mut(column)
            && term < group.len()
        {
            group.remove(term);
            if group.is_empty() {
                groups.remove(column);
            }
            self.conditions = read_conditions(&self.raw);
        }
    }
}

struct Schedule {
    cyclic: bool,
    stops: Vec<Stop>,
    other_data: Compound,
}

impl Schedule {
    fn progress(&self) -> usize {
        match self.other_data.get(&"Progress".into()) {
            Some(Tag::Int(progress)) if *progress > 0 => *progress as usize,
            _ => 0,
        }
    }

    fn set_progress(&mut self, index: usize) {
        if index == 0 {
            self.other_data.remove(&"Progress".into());
        } else {
            self.other_data.insert("Progress".into(), Tag::Int(index as i32));
        }
    }

    fn clamp_progress(&mut self) {
        let progress = self.progress();
        let last = self.stops.len().saturating_sub(1);
        if progress > last {
            self.set_progress(last);
        }
    }
}

impl Default for Schedule {
    fn default() -> Self {
        Self { cyclic: true, stops: Vec::new(), other_data: Compound::new() }
    }
}

struct Draft {
    row: Option<usize>,
    kind: ActionKind,
    filter: String,
    throttle: i32,
    focused: bool,
    selected_all: bool,
    suggestion: usize,
    suggestions_hidden: bool,
}

struct ConditionFields {
    samples: [Option<ItemStack>; 2],
    text: String,
    focused: bool,
    selected_all: bool,
}

impl ConditionFields {
    fn new(text: String, samples: [Option<ItemStack>; 2]) -> Self {
        Self { samples, text, focused: false, selected_all: false }
    }
}

fn sample_tag(item: Option<&ItemStack>) -> Tag {
    let Some(item) = item else { return Tag::Compound(Compound::new()); };
    let mut sample = item.clone();
    sample.count = 1;
    item_to_nbt(&sample)
}

struct Editor {
    schedule: Schedule,
    stations: Catalog,
    draft: Option<Draft>,
    condition_draft: Option<(usize, ConditionSlot, Condition)>,
    condition_fields: ConditionFields,
    condition_columns: BTreeMap<usize, usize>,
    scroll: f32,
    previous_scroll: f32,
    scroll_target: f32,
    closing: bool,
}

impl Editor {
    fn editing(&self) -> bool {
        self.draft.is_some() || self.condition_draft.is_some()
    }

    fn suggestions(&self, draft: &Draft) -> Vec<&str> {
        if !draft.focused || draft.suggestions_hidden || draft.kind != ActionKind::Destination {
            return Vec::new();
        }
        let prior = self.schedule.stops.iter().enumerate()
            .filter(|(row, _)| Some(*row) != draft.row)
            .filter_map(|(_, stop)| stop.destination.as_deref());
        let prefix = if draft.selected_all { "" } else { draft.filter.as_str() };
        self.stations.suggestions(prior, prefix)
    }

    fn content_end(&self) -> f32 {
        let size: f32 = self.schedule.stops.iter().map(|stop| stop.height() + 10.0).sum();
        ROW_TOP + size - if size > 0.0 { 1.0 } else { 0.0 }
    }

    fn rows(&self) -> impl Iterator<Item = (f32, &Stop)> {
        self.schedule.stops.iter().scan(ROW_TOP, |y, stop| {
            let top = *y;
            *y += stop.height() + 10.0;
            Some((top, stop))
        })
    }

    fn scroll_limit(&self) -> f32 {
        (self.content_end() - ROW_TOP - 132.0).max(0.0)
    }

    fn start_draft(&mut self, row: Option<usize>) {
        let stop = row.map(|i| &self.schedule.stops[i]);
        let kind = stop.and_then(Stop::kind).unwrap_or(ActionKind::Destination);
        let filter = stop.and_then(Stop::text).unwrap_or_default();
        let throttle = stop.map_or(100, Stop::throttle).clamp(5, 100);
        self.draft = Some(Draft {
            row, kind, filter, throttle, focused: false, selected_all: false,
            suggestion: 0, suggestions_hidden: false,
        });
    }

    fn confirm_draft(&mut self) {
        if let Some(draft) = self.draft.take() {
            if let Some(row) = draft.row {
                self.schedule.stops[row].set_action(draft);
            } else {
                let mut stop = new_stop("");
                stop.set_action(draft);
                self.schedule.stops.push(stop);
            }
        }
    }

    fn duplicate(&mut self, row: usize) {
        self.schedule.stops.insert(row, self.schedule.stops[row].clone());
        self.condition_columns.clear();
    }

    fn move_row(&mut self, row: usize, to: usize) {
        self.schedule.stops.swap(row, to);
        self.condition_columns.clear();
    }

    fn remove(&mut self, row: usize) {
        self.schedule.stops.remove(row);
        self.condition_columns.clear();
        let limit = self.scroll_limit();
        self.scroll = self.scroll.min(limit);
        self.previous_scroll = self.previous_scroll.min(limit);
        self.scroll_target = self.scroll_target.min(limit);
    }
}

thread_local! {
    static STATE: RefCell<Option<Editor>> = const { RefCell::new(None) };
}

pub(super) fn register(types: &mut Vec<String>) {
    types.push(COMPONENT.to_owned());
}

fn valid_filter(filter: &str) -> bool {
    filter.encode_utf16().count() <= 32
        && filter.matches('*').count() <= 3
        && !filter.chars().any(char::is_control)
}

fn new_stop(destination: &str) -> Stop {
    let delay = Delay::default();
    let instruction = Tag::compound([
        ("Id", Tag::String("create:destination".into())),
        ("Data", Tag::compound([("Text", Tag::String(destination.into()))])),
    ]);
    let condition = Tag::compound([
        ("Id", Tag::String("create:delay".into())),
        ("Data", Tag::compound([("TimeUnit", Tag::Int(delay.unit)), ("Value", Tag::Int(delay.value))])),
    ]);
    Stop::read(Tag::compound([
        ("Instruction", instruction),
        ("Conditions", Tag::List(vec![Tag::List(vec![condition])])),
    ]))
}

fn read_conditions(entry: &Tag) -> Vec<Vec<Option<Condition>>> {
    let Some(Tag::List(groups)) = entry.get("Conditions") else {
        return Vec::new();
    };
    groups.iter().map(|group| {
        let Tag::List(conditions) = group else { return Vec::new(); };
        conditions.iter().map(read_condition).collect()
    }).collect()
}

fn read_condition(condition: &Tag) -> Option<Condition> {
    let Tag::String(id) = condition.get("Id")? else {
        return None;
    };
    let kind = ConditionKind::decode(&id.to_string_lossy())?;
    let data = condition.get("Data")?;
    let number = |key, fallback| match data.get(key) {
        Some(Tag::Int(value)) => *value,
        _ => fallback,
    };
    match kind {
        ConditionKind::FluidThreshold | ConditionKind::ItemThreshold => {
            let amount = match data.get("Threshold") {
                Some(Tag::String(text)) => text.to_string_lossy().parse().unwrap_or(0),
                _ => 0,
            };
            let sampled = kind.cargo_sample_key().and_then(|key| data.get(key))
                .is_some_and(|tag| matches!(tag, Tag::Compound(data) if data.contains_key(&"id".into())));
            Some(Condition::Cargo(CargoThreshold {
                kind, amount, operator: number("Operator", 0).clamp(0, 2),
                measure: number("Measure", 0).clamp(0, i32::from(kind == ConditionKind::ItemThreshold)),
                sampled,
            }))
        }
        ConditionKind::Delay | ConditionKind::Idle => {
            let delay = Delay { value: number("Value", 5), unit: number("TimeUnit", 1) };
            let condition = if kind == ConditionKind::Idle { Condition::Idle(delay) } else { Condition::Delay(delay) };
            delay.valid().then_some(condition)
        }
        ConditionKind::RedstoneLink => Some(Condition::RedstoneLink(i32::from(number("Inverted", 0) == 1))),
        ConditionKind::PlayerCount => Some(Condition::PlayerCount(PlayerCount {
            count: number("Count", 0).clamp(0, 20),
            exact: number("Exact", 0).clamp(0, 1),
        })),
        ConditionKind::TimeOfDay => Some(Condition::TimeOfDay(TimeOfDay {
            hour: number("Hour", 8).clamp(0, 23),
            minute: number("Minute", 0).clamp(0, 59),
            rotation: number("Rotation", 5).clamp(0, 9),
        })),
        kind => Some(Condition::new(kind)),
    }
}

fn read_document(tag: Tag) -> Option<Schedule> {
    let Tag::Compound(mut data) = tag else {
        return None;
    };
    let Tag::Byte(cyclic) = data.remove(&"Cyclic".into())? else {
        return None;
    };
    let Tag::List(entries) = data.remove(&"Entries".into())? else {
        return None;
    };
    let stops = entries.into_iter().map(Stop::read).collect();
    Some(Schedule { cyclic: cyclic != 0, stops, other_data: data })
}

fn schedule_tag(schedule: &Schedule) -> Tag {
    let mut data = schedule.other_data.clone();
    let entries = schedule.stops.iter().map(|stop| stop.raw.clone()).collect();
    data.insert("Cyclic".into(), Tag::Byte(i8::from(schedule.cyclic)));
    data.insert("Entries".into(), Tag::List(entries));
    Tag::Compound(data)
}

const PACKET_LIMITS: Limits = Limits {
    max_bytes: 30_000,
    max_nodes: 1_000_000,
    max_depth: 512,
};

fn encode(schedule: &Schedule) -> Result<Vec<u8>, nbt::Error> {
    nbt::write_network(&schedule_tag(schedule), PACKET_LIMITS)
}

fn decode(data: &[u8]) -> Option<Schedule> {
    let (tag, consumed) = nbt::read_network(data, PACKET_LIMITS).ok()?;
    if consumed != data.len() {
        return None;
    }
    read_document(tag)
}

fn read_schedule(game: &Game<'_>, stack: &ItemStack) -> Option<Schedule> {
    match game.native_component(stack, COMPONENT).ok()? {
        Some(tag) => read_document(tag.clone()),
        None => Some(Schedule::default()),
    }
}

pub(super) fn use_schedule(game: &mut Game<'_>, stack: &ItemStack, claimed: &mut bool) {
    if *claimed || &*stack.item != SCHEDULE || game.hand != Hand::Main || game.native_sneaking() {
        return;
    }
    if let Some(player) = game.native_acting_player()
        && let Some(schedule) = read_schedule(game, stack)
    {
        let mut view = Tag::compound([
            ("Schedule", schedule_tag(&schedule)),
            ("Stations", Catalog::capture(game, player.position).tag()),
        ]);
        let mut data = nbt::write_network(&view, PACKET_LIMITS);
        if data.is_err() {
            if let Tag::Compound(fields) = &mut view {
                fields.remove(&"Stations".into());
            }
            data = nbt::write_network(&view, PACKET_LIMITS);
        }
        if let Ok(data) = data {
            *claimed = true;
            let _ = game.native_net_send_to_player(player.uuid, CHANNEL, &data);
        }
    }
}

pub(super) fn receive(game: &mut Game<'_>, channel: &str, data: &[u8]) {
    if channel != CHANNEL || game.native_mod_screen() == Some(EDITOR) {
        return;
    }
    let Ok((Tag::Compound(mut view), consumed)) = nbt::read_network(data, PACKET_LIMITS) else {
        return;
    };
    if consumed != data.len() {
        return;
    }
    let stations = view.get(&"Stations".into()).map_or_else(Catalog::default, Catalog::read);
    if let Some(schedule) = view.remove(&"Schedule".into()).and_then(read_document)
        && game.native_mod_screen_open(EDITOR)
    {
        STATE.replace(Some(Editor {
            schedule,
            stations,
            draft: None,
            condition_draft: None,
            condition_fields: ConditionFields::new("10".to_owned(), [None, None]),
            condition_columns: BTreeMap::new(),
            scroll: 0.0,
            previous_scroll: 0.0,
            scroll_target: 0.0,
            closing: false,
        }));
    }
}

pub(super) fn save(game: &mut Game<'_>, player: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 30_000 {
        return;
    }
    let Some(schedule) = decode(data) else {
        return;
    };
    let Some(conn) = game.lan.as_ref().and_then(|host| {
        host.hub
            .guests
            .iter()
            .find(|guest| guest.uuid == player && guest.placed && !guest.released)
            .map(|guest| guest.conn)
    }) else {
        return;
    };
    game.for_player(Target::Guest(conn), |actor| {
        let slot = actor.selected;
        let Some(mut stack) =
            actor.stack_in(slot).cloned().filter(|stack| &*stack.item == SCHEDULE)
        else {
            return;
        };
        if read_schedule(actor, &stack).is_none() {
            return;
        }
        let updated = if schedule.stops.is_empty() && schedule.other_data.is_empty() {
            actor.native_remove_component(&mut stack, COMPONENT)
        } else {
            actor.native_set_component(&mut stack, COMPONENT, schedule_tag(&schedule))
        };
        if updated.is_ok() {
            *actor.stack_in_mut(slot) = Some(stack);
            actor.add_cooldown(Arc::from(SCHEDULE), 5);
        }
    });
}

fn origin([x, y, w, h]: [f32; 4]) -> [f32; 2] {
    [x + ((w - WIDTH) / 2.0).floor(), y + ((h - HEIGHT) / 2.0).floor()]
}

fn contains([x, y, w, h]: [f32; 4], [mx, my]: [f32; 2]) -> bool {
    mx >= x && mx < x + w && my >= y && my < y + h
}

fn button_at([left, top]: [f32; 2], [x, y]: [f32; 2]) -> [f32; 4] {
    [left + x, top + y, 18.0, 18.0]
}

fn sprite(game: &Game<'_>, batch: &mut HudBatch, atlas: &str, source: [f32; 4], at: [f32; 2]) {
    let [_, _, w, h] = source;
    game.native_sprite(batch, atlas, source, [at[0], at[1], w, h]);
}

fn blit(
    game: &Game<'_>,
    batch: &mut HudBatch,
    atlas: &str,
    [left, top]: [f32; 2],
    source: [f32; 4],
    [x, y]: [f32; 2],
) {
    sprite(game, batch, atlas, source, [left + x, top + y]);
}

fn stretch(
    game: &Game<'_>,
    batch: &mut HudBatch,
    [left, top]: [f32; 2],
    source: [f32; 4],
    [x, y, w, h]: [f32; 4],
) {
    game.native_sprite(batch, ATLAS, source, [left + x, top + y, w, h]);
}

fn title(game: &Game<'_>, batch: &mut HudBatch, text: &str, [left, top]: [f32; 2]) {
    game.native_text(
        batch,
        text,
        [left + 124.0 - game.native_text_width(text) / 2.0, top],
        0x505050,
        false,
    );
}

fn button(
    game: &Game<'_>,
    batch: &mut HudBatch,
    mouse: [f32; 2],
    bounds: [f32; 4],
    icon: [f32; 2],
    label: &str,
    enabled: bool,
    green: bool,
) {
    let [x, y, _, _] = bounds;
    let tile = if !enabled {
        90.0
    } else if contains(bounds, mouse) {
        18.0
    } else if green {
        72.0
    } else {
        0.0
    };
    game.native_sprite(batch, WIDGETS, [tile, 0.0, 18.0, 18.0], bounds);
    sprite(game, batch, ICONS, [icon[0], icon[1], 16.0, 16.0], [x + 1.0, y + 1.0]);
    horizon_client::widgets::record(label, bounds, enabled);
}

fn strip(game: &Game<'_>, batch: &mut HudBatch, origin: [f32; 2], end: f32) {
    stretch(game, batch, origin, [5.0, 237.0, 3.0, 1.0], [33.0, 16.0, 3.0, 10.0]);
    blit(game, batch, ATLAS, origin, [34.0, 239.0, 11.0, 16.0], [29.0, end]);
    blit(game, batch, ATLAS, origin, [79.0, 239.0, 16.0, 16.0], [43.0, end]);
}

fn timed_label(game: &Game<'_>, delay: Delay, key: &str, fallback: &str) -> String {
    let amount = format!("{}{}", delay.value, ["t", "s", "min"][delay.unit as usize]);
    game.translate(key, fallback)
        .replace("%1$s", &amount)
        .replace("%s", &amount)
}

fn condition_label(game: &Game<'_>, condition: Option<Condition>) -> String {
    condition.map_or_else(
        || game.translate("create.schedule.condition_type", "Continue if/after:"),
        |value| value.summary(game),
    )
}

fn condition_width(game: &Game<'_>, condition: Option<Condition>, label: &str) -> f32 {
    let icon = if matches!(condition, Some(Condition::TimeOfDay(_) | Condition::PlayerCount(_)
        | Condition::RedstoneLink(_) | Condition::Cargo(CargoThreshold { sampled: true, .. }))) {
        20.0
    } else {
        0.0
    };
    (game.native_text_width(label) + 16.0 + icon).max(32.0)
}

fn condition_group_width(game: &Game<'_>, group: &[Option<Condition>]) -> f32 {
    group.iter().map(|&condition| condition_width(game, condition, &condition_label(game, condition)))
        .fold(32.0, f32::max)
}

fn condition_columns(game: &Game<'_>, stop: &Stop, offset: usize) -> impl Iterator<Item=(f32, f32)> {
    let offset: f32 = stop.conditions.iter().take(offset)
        .map(|group| condition_group_width(game, group) + 10.0).sum();
    stop.conditions.iter().scan(51.0 - offset, move |cursor, group| {
        let width = condition_group_width(game, group);
        let x = *cursor;
        *cursor += width + 10.0;
        Some((x,width))
    })
}

fn overflowing(game: &Game<'_>, stop: &Stop) -> bool {
    condition_columns(game, stop, 0).last().is_some_and(|(x,w)| x + w + 26.0 > 195.0)
}


fn card(game: &Game<'_>, batch: &mut HudBatch, origin: [f32; 2], stop: &Stop) {
    let title = stop.title(game);
    let destination = stop.destination.as_deref().unwrap_or(&title);
    let [left, top] = origin;
    let display = destination
        .char_indices()
        .find(|(end, _)| game.native_text_width(&destination[..*end]) >= 112.0)
        .map_or(destination, |(end, _)| &destination[..end]);
    let text_width = (game.native_text_width(display) + 36.0).clamp(100.0, 150.0);
    let height = stop.height();
    let has_conditions = stop.has_conditions();
    for (tile, area) in [
        (7.0, [25.0, 26.0, 195.0, height - 2.0]),
        (7.0, [26.0, 25.0, 193.0, height]),
        (5.0, [26.0, 26.0, 193.0, height - 2.0]),
        (6.0, [27.0, 27.0, 191.0, height - 4.0]),
        (if has_conditions { 7.0 } else { 6.0 }, [27.0, 27.0, 191.0, 22.0]),
    ] {
        stretch(game, batch, origin, [tile, 233.0, 1.0, 1.0], area);
    }
    stretch(game, batch, origin, [5.0, 237.0, 3.0, 1.0], [33.0, 25.0, 3.0, height + 10.0]);
    let directive = if has_conditions { 12.0 } else { 209.0 };
    for (source, offset) in [
        ([directive, 239.0, 11.0, 16.0], [29.0, 31.0]),
        ([51.0, 243.0, 12.0, 12.0], [206.0, 27.0]),
        ([65.0, 243.0, 12.0, 12.0], [206.0, 11.0 + height]),
    ] {
        blit(game, batch, ATLAS, origin, source, offset);
    }
    if has_conditions {
        blit(game, batch, ATLAS, origin, [1.0, 239.0, 11.0, 16.0], [29.0, 53.0]);
    }
    let [x, y] = [51.0, 30.0];
    stretch(game, batch, origin, [123.0, 239.0, 1.0, 16.0], [x, y, text_width, 16.0]);
    blit(game, batch, ATLAS, origin, [116.0, 239.0, 6.0, 16.0], [x - 3.0, y]);
    blit(game, batch, ATLAS, origin, [144.0, 239.0, 2.0, 16.0], [x + text_width - 2.0, y]);
    let at = if let Some(kind) = stop.kind() {
        blit(game, batch, ATLAS, origin, [125.0, 239.0, 18.0, 16.0], [x + 3.0, y]);
        kind.draw_icon(game, batch, [left + x + 4.0, top + y]);
        x + 28.0
    } else { x + 8.0 };
    game.native_text(batch, display, [left + at, top + y + 4.0], 0xF2F2EE, true);
}

const MOVE_UP: [f32; 4] = [220.0, 8.0, 12.0, 12.0];
const MOVE_DOWN: [f32; 4] = [220.0, 22.0, 12.0, 12.0];
fn duplicate_area(height: f32) -> [f32; 4] {
    [206.0, height - 14.0, 12.0, 12.0]
}

const CONDITION_LEFT: f32 = 43.0;
const CONDITION_RIGHT: f32 = 210.0;
const CONDITION_TOP: f32 = 54.0;

fn add_condition_label(game: &Game<'_>) -> String {
    game.translate("create.gui.schedule.add_condition", "Add Condition")
}

fn alternative_label(game: &Game<'_>) -> String {
    game.translate("create.gui.schedule.alternative_condition", "Alternative Condition")
}

fn condition_buttons(
    game: &Game<'_>,
    batch: &mut HudBatch,
    origin: [f32; 2],
    stop: &Stop,
    column: usize,
    available: bool,
    panel_top: f32,
) {
    if !stop.has_conditions() {
        return;
    }
    let [left, top] = origin;
    let start = batch.vertices.len();
    let within = |x: f32, y: f32, width: f32, height: f32| {
        let min = x.max(CONDITION_LEFT);
        let max = (x + width).min(CONDITION_RIGHT);
        let y = y + top;
        let from = y.max(panel_top + VIEW_TOP);
        let to = (y + height).min(panel_top + VIEW_BOTTOM);
        (available && max > min && to > from).then_some([left + min, from, max - min, to - from])
    };
    let mut alternative = 51.0;
    for (group, (x, width)) in condition_columns(game, stop, column).enumerate() {
        for (term, &condition) in stop.conditions[group].iter().enumerate() {
            let y = CONDITION_TOP + term as f32 * 18.0;
            let label = condition_label(game, condition);
            stretch(game, batch, origin, [123.0, 239.0, 1.0, 16.0], [x, y, width, 16.0]);
            if term == 0 {
                blit(game, batch, ATLAS, origin, [116.0, 239.0, 6.0, 16.0], [x - 3.0, y]);
            } else {
                blit(game, batch, ATLAS, origin, [147.0, 239.0, 2.0, 16.0], [x, y]);
            }
            blit(game, batch, ATLAS, origin, [144.0, 239.0, 2.0, 16.0], [x + width - 2.0, y]);
            let icon = [left + x + 4.0, top + y];
            let text_x = match condition {
                Some(Condition::TimeOfDay(time)) => {
                    blit(game, batch, ATLAS, origin, [125.0, 239.0, 18.0, 16.0], [x + 3.0, y]);
                    time.icon(game, batch, icon);
                    x + 28.0
                }
                Some(Condition::PlayerCount(_)) => {
                    blit(game, batch, ATLAS, origin, [125.0, 239.0, 18.0, 16.0], [x + 3.0, y]);
                    game.native_item(batch, "create:yellow_seat", icon, 16.0);
                    x + 28.0
                }
                Some(Condition::RedstoneLink(_)) => {
                    blit(game, batch, ATLAS, origin, [125.0, 239.0, 18.0, 16.0], [x + 3.0, y]);
                    game.native_item(batch, LINK_ITEM, icon, 16.0);
                    x + 28.0
                }
                Some(value @ Condition::Cargo(CargoThreshold { sampled: true, .. })) => {
                    if let Some(sample) = stop.condition_sample(ConditionSlot::Existing { group, term }, value, 0) {
                        blit(game, batch, ATLAS, origin, [125.0, 239.0, 18.0, 16.0], [x + 3.0, y]);
                        game.native_item_stack(batch, &sample, icon, 16.0);
                    }
                    x + 28.0
                }
                _ => x + 8.0,
            };
            game.native_text(batch, &label, [left + text_x, top + y + 4.0], 0xF2F2EE, true);
            if condition.is_some() && let Some(bounds) = within(x, y, width, 16.0) {
                horizon_client::widgets::record(&label, bounds, true);
            }
        }
        let y = CONDITION_TOP + stop.conditions[group].len() as f32 * 18.0;
        let append = x + width / 2.0 - 5.0;
        blit(game, batch, ATLAS, origin, [150.0, 245.0, 10.0, 10.0], [append, y]);
        if let Some(bounds) = within(append, y, 10.0, 10.0) {
            horizon_client::widgets::record(&add_condition_label(game), bounds, true);
        }
        alternative = x + width + 10.0;
    }
    blit(game, batch, ATLAS, origin, [96.0, 239.0, 19.0, 16.0], [alternative - 3.0, CONDITION_TOP]);
    if let Some(bounds) = within(alternative, CONDITION_TOP, 16.0, 16.0) {
        horizon_client::widgets::record(&alternative_label(game), bounds, true);
    }
    batch.clip_since(start, left + CONDITION_LEFT, top, left + CONDITION_RIGHT, top + 25.0 + stop.height());
    if overflowing(game, stop) {
        let y = ROW_TOP + (stop.height() - 8.0 + 22.0) / 2.0;
        if column > 0 {
            blit(game, batch, ATLAS, origin, [161.0, 247.0, 4.0, 8.0], [39.0, y]);
        }
        if column + 1 < stop.conditions.len() {
            blit(game, batch, ATLAS, origin, [166.0, 247.0, 4.0, 8.0], [203.0, y]);
        }
    }
}

enum ConditionClick {
    Edit(ConditionSlot, Condition),
    Remove { group: usize, term: usize },
    Scroll(usize),
}

fn condition_click(
    game: &Game<'_>,
    stop: &Stop,
    column: usize,
    [x, y]: [f32; 2],
    button: i32,
) -> Option<ConditionClick> {
    if !stop.has_conditions() {
        return None;
    }
    if button == 0 && overflowing(game, stop) {
        let center = ROW_TOP + (stop.height() - 8.0 + 22.0) / 2.0;
        if y >= center - 1.0 && y < center + 8.0 {
            if (37.0..44.0).contains(&x) && column > 0 {
                return Some(ConditionClick::Scroll(column - 1));
            }
            if (202.0..209.0).contains(&x) && column + 1 < stop.conditions.len() {
                return Some(ConditionClick::Scroll(column + 1));
            }
        }
    }
    if !(CONDITION_LEFT..CONDITION_RIGHT).contains(&x) || y < CONDITION_TOP - 1.0 {
        return None;
    }
    let mut alternative = 51.0;
    for (group, (start, width)) in condition_columns(game, stop, column).enumerate() {
        let terms = &stop.conditions[group];
        if (start..start + width).contains(&x) {
            let term = ((y + 1.0 - CONDITION_TOP) / 18.0).floor() as usize;
            if let Some(value) = terms.get(term) {
                if button == 1 && stop.removable(group) {
                    return Some(ConditionClick::Remove { group, term });
                }
                if button == 0 && let Some(value) = value {
                    return Some(ConditionClick::Edit(ConditionSlot::Existing { group, term }, *value));
                }
            }
            let center = start + width / 2.0;
            if button == 0 && contains([center - 5.0, CONDITION_TOP + terms.len() as f32 * 18.0,
                10.0, 10.0], [x,y])
            {
                return Some(ConditionClick::Edit(ConditionSlot::Append { group }, Condition::new(ConditionKind::Delay)));
            }
            return None;
        }
        alternative = start + width + 10.0;
    }
    if button == 0 && contains([alternative, CONDITION_TOP, 16.0, 16.0], [x,y]) {
        return Some(ConditionClick::Edit(ConditionSlot::Alternative, Condition::new(ConditionKind::Delay)));
    }
    None
}

fn modal(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    batch: &mut HudBatch,
    origin: [f32; 2],
    heading: &str,
) {
    let [left, top] = origin;
    let [x, y, w, h] = screen.rect;
    batch.fill_gradient(
        &game.gui.atlas,
        (x, y, w, h),
        rgba(16, 16, 16, 192),
        rgba(16, 16, 16, 208),
    );
    blit(game, batch, INSTRUCTION_ATLAS, origin, [0.0, 0.0, 256.0, 89.0], [-2.0, 40.0]);
    blit(game, batch, INVENTORY_ATLAS, origin, [0.0, 0.0, 176.0, 108.0], [38.0, 122.0]);
    title(
        game,
        batch,
        heading,
        [left, top + 44.0],
    );
    game.native_text(
        batch,
        &game.translate("container.inventory", "Inventory"),
        [left + 46.0, top + 128.0],
        0x505050,
        false,
    );
}

fn instruction(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    batch: &mut HudBatch,
    origin: [f32; 2],
    draft: &Draft,
) {
    let [left, top] = origin;
    modal(game, screen, batch, origin,
        &game.translate("create.schedule.instruction.editor", "Instruction Editor"));
    let [type_x, type_y, type_width, type_height] = ACTION_TYPE_AREA;
    game.native_sprite(batch, FIELD_ATLAS, [3.0, 163.0, 1.0, 18.0], [left + type_x - 3.0, top + type_y - 1.0, type_width + 3.0, type_height + 2.0]);
    game.native_text(batch, &draft.kind.label(game), [left + 59.0, top + 69.0], 0xFFFFFF, true);
    horizon_client::widgets::record(
        &game.translate("create.schedule.instruction_type", "Next Action:"),
        [left + type_x, top + type_y, type_width, type_height], true,
    );
    draft.kind.draw_icon(game, batch, [left + 54.0, top + 88.0]);
    if draft.kind == ActionKind::Throttle {
        let [x, y, w, h] = THROTTLE_AREA;
        game.native_sprite(batch, FIELD_ATLAS, [3.0, 163.0, 1.0, 18.0], [left + x, top + y, w, h]);
        game.native_text(batch, &format!("{}%", draft.throttle), [left + x + 5.0, top + y + 4.0], 0xFFFFFF, true);
        horizon_client::widgets::record(
            &game.translate("create.schedule.instruction.throttle_edit_box", "Throttle"),
            [left + x, top + y, w, h], true,
        );
    }
    if draft.kind.text() {
        instruction_text(game, batch, origin, draft);
    }
    editor_inventory(game, batch, origin);
    button(
        game, batch, screen.mouse, button_at(origin, [224.0, 87.0]),
        [0.0, 16.0], "Confirm Action", true, false,
    );
    if draft.row.is_none() {
        button(game, batch, screen.mouse, button_at(origin, [11.0, 87.0]),
            [16.0, 0.0], "Cancel Action", true, false);
    }
}

fn instruction_text(game: &Game<'_>, batch: &mut HudBatch, origin: [f32; 2], draft: &Draft) {
    let [left, top] = origin;
    game.native_sprite(
        batch,
        FIELD_ATLAS,
        [3.0, 163.0, 1.0, 18.0],
        [left + 77.0, top + 87.0, 121.0, 18.0],
    );
    blit(game, batch, FIELD_ATLAS, origin, [8.0, 163.0, 5.0, 18.0], [74.0, 87.0]);
    blit(game, batch, FIELD_ATLAS, origin, [5.0, 163.0, 2.0, 18.0], [196.0, 87.0]);
    let filter = &draft.filter;
    if draft.selected_all {
        batch.fill(
            &game.gui.atlas,
            left + 82.0,
            top + 92.0,
            game.native_text_width(filter).min(112.0),
            8.0,
            rgba(0, 0, 255, 95),
        );
    }
    let start = filter
        .char_indices()
        .find(|(start, _)| game.native_text_width(&filter[*start..]) <= 110.0)
        .map_or(filter.len(), |(start, _)| start);
    game.native_text(batch, &filter[start..], [left + 82.0, top + 92.0], 0xFFFFFF, false);
    if draft.focused && game.ticks % 12 < 6 {
        let cursor = left + 82.0 + game.native_text_width(&filter[start..]);
        game.native_text(batch, "_", [cursor, top + 92.0], 0xFFFFFF, false);
    }
    let label = match draft.kind {
        ActionKind::Title => game.translate("create.schedule.instruction.name_edit_box", "Schedule Title"),
        ActionKind::Retrieve => game.translate(
            "create.schedule.instruction.address_filter_edit_box", "Retrieve Packages with this Address",
        ),
        _ => game.translate("create.schedule.instruction.filter_edit_box", "Station Name"),
    };
    horizon_client::widgets::record(&label, [left + 77.0, top + 87.0, 121.0, 18.0], true);
}

fn inventory_area([left, top]: [f32; 2], index: usize) -> [f32; 4] {
    let x = left + 46.0 + (index % 9) as f32 * 18.0;
    let y = top + if index < 9 { 198.0 } else { 140.0 + ((index - 9) / 9) as f32 * 18.0 };
    [x, y, 16.0, 16.0]
}

fn editor_inventory(game: &Game<'_>, batch: &mut HudBatch, origin: [f32; 2]) {
    for index in 0..36 {
        if let Some(stack) = game.stack_in(index) {
            let [x, y, _, _] = inventory_area(origin, index);
            game.native_item_stack(batch, stack, [x, y], 16.0);
        }
    }
}

fn frequency_area([left, top]: [f32; 2], index: usize) -> [f32; 4] {
    [left + 54.0 + index as f32 * 20.0, top + 88.0, 16.0, 16.0]
}

fn condition_box(game: &Game<'_>, batch: &mut HudBatch, origin: [f32; 2], area: [f32; 4], speech: bool) {
    let [left, top] = origin;
    let [x, y, width, height] = area;
    game.native_sprite(batch, FIELD_ATLAS, [3.0, 163.0, 1.0, 18.0], [left + x, top + y, width, height]);
    if speech {
        blit(game, batch, FIELD_ATLAS, origin, [8.0, 163.0, 5.0, 18.0], [x - 3.0, y]);
    } else {
        blit(game, batch, FIELD_ATLAS, origin, [0.0, 163.0, 2.0, 18.0], [x, y]);
    }
    blit(game, batch, FIELD_ATLAS, origin, [5.0, 163.0, 2.0, 18.0], [x + width - 2.0, y]);
}

fn condition_field(
    game: &Game<'_>,
    batch: &mut HudBatch,
    origin: [f32; 2],
    area: [f32; 4],
    label: &str,
    value: &str,
    speech: bool,
) {
    condition_box(game, batch, origin, area, speech);
    let [x, y, w, h] = area;
    let [left, top] = origin;
    game.native_text(batch, value, [left + x + 5.0, top + y + 4.0], 0xFFFFFF, true);
    horizon_client::widgets::record(label, [left + x, top + y, w, h], true);
}

fn draw_condition(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    batch: &mut HudBatch,
    origin: [f32; 2],
    value: Condition,
    fields: &ConditionFields,
    allow_delete: bool,
) {
    let [left, top] = origin;
    modal(game, screen, batch, origin,
        &game.translate("create.schedule.condition.editor", "Condition Editor"));
    condition_box(game, batch, origin, [53.0, 64.0, 145.0, 18.0], false);
    game.native_text(batch, &value.kind().label(game), [left + 59.0, top + 69.0], 0xFFFFFF, true);
    let [x, y, width, height] = ACTION_TYPE_AREA;
    horizon_client::widgets::record(&game.translate("create.schedule.condition_type", "Continue if/after:"),
        [left + x, top + y, width, height], true);
    blit(game, batch, INSTRUCTION_ATLAS, origin, [0.0, 91.0, 18.0, 18.0], [53.0, 87.0]);

    match value {
        Condition::Delay(delay) | Condition::Idle(delay) => {
            game.native_item(batch, "minecraft:repeater", [left + 54.0, top + 88.0], 16.0);
            let (key, fallback) = [("ticks", "Ticks"), ("seconds", "Seconds"), ("minutes", "Minutes")]
                [delay.unit as usize];
            let unit = game.translate(&format!("create.generic.unit.{key}"), fallback);
            condition_field(game, batch, origin, DURATION_AREA,
                &game.translate("create.generic.duration", "Duration"), &delay.value.to_string(), true);
            condition_field(game, batch, origin, TIME_UNIT_AREA,
                &game.translate("create.generic.timeUnit", "Time Unit"), &unit, false);
        }
        Condition::Cargo(cargo) => {
            let slot = frequency_area(origin, 0);
            if let Some(item) = &fields.samples[0] {
                game.native_item_stack(batch, item, [slot[0], slot[1]], 16.0);
            }
            horizon_client::widgets::record(
                &game.translate("create.schedule.condition.threshold.place_item", "Reference Item"),
                slot, true,
            );
            let operator = CargoThreshold::OPERATORS[cargo.operator as usize];
            condition_field(game, batch, origin, CARGO_OPERATOR_AREA, "Comparison", operator, true);
            condition_box(game, batch, origin, CARGO_AMOUNT_AREA, false);
            let [x, y, w, h] = CARGO_AMOUNT_AREA;
            let slot = [left + x, top + y, w, h];
            horizon_client::widgets::record("Threshold", slot, true);
            let tail = fields.text.char_indices()
                .find(|(index, _)| game.native_text_width(&fields.text[*index..]) <= w - 10.0)
                .map_or(fields.text.as_str(), |(index, _)| &fields.text[index..]);
            let width = game.native_text_width(tail);
            if fields.selected_all {
                batch.fill(&game.gui.atlas, slot[0] + 5.0, slot[1] + 5.0, width, 8.0, rgba(0, 0, 255, 95));
            }
            game.native_text(batch, tail, [slot[0] + 5.0, slot[1] + 5.0], 0xFFFFFF, false);
            if fields.focused && game.ticks % 12 < 6 {
                game.native_text(batch, "_", [slot[0] + 5.0 + width, slot[1] + 5.0], 0xFFFFFF, false);
            }
            let measure = cargo.measure(game);
            if cargo.kind == ConditionKind::ItemThreshold {
                condition_field(game, batch, origin, CARGO_MEASURE_AREA,
                    &game.translate("create.schedule.condition.threshold.item_measure", "Item Measure"), &measure, false);
            } else {
                condition_box(game, batch, origin, CARGO_MEASURE_AREA, false);
                let [x, y, _, _] = CARGO_MEASURE_AREA;
                game.native_text(batch, &measure, [left + x + 5.0, top + y + 4.0], 0xFFFFFF, true);
            }
        }
        Condition::RedstoneLink(inverted) => {
            blit(game, batch, INSTRUCTION_ATLAS, origin, [0.0, 91.0, 18.0, 18.0], [73.0, 87.0]);
            for (index, (key, fallback)) in [
                ("create.logistics.firstFrequency", "Frequency #1"),
                ("create.logistics.secondFrequency", "Frequency #2"),
            ].into_iter().enumerate() {
                let at = frequency_area(origin, index);
                if let Some(item) = &fields.samples[index] {
                    game.native_item_stack(batch, item, [at[0], at[1]], 16.0);
                }
                horizon_client::widgets::record(&game.translate(key, fallback), at, true);
            }
            let option = if inverted == 1 {
                game.translate("create.schedule.condition.redstone_link.unpowered", "Not powered")
            } else {
                game.translate("create.schedule.condition.redstone_link.powered", "Powered")
            };
            condition_field(game, batch, origin, FREQUENCY_STATE_AREA,
                &game.translate("create.schedule.condition.redstone_link.frequency_state", "Frequency state:"),
                &option, true);
        }
        Condition::PlayerCount(players) => {
            game.native_item(batch, "create:yellow_seat", [left + 54.0, top + 88.0], 16.0);
            condition_field(game, batch, origin, DURATION_AREA,
                &game.translate("create.schedule.condition.player_count.players", "Players"),
                &players.count.to_string(), true);
            condition_field(game, batch, origin, CONDITIONAL_AREA,
                &game.translate("create.schedule.condition.player_count.condition", "Conditional"),
                &players.comparison(game), false);
        }
        Condition::TimeOfDay(time) => {
            time.icon(game, batch, [left + 54.0, top + 88.0]);
            condition_box(game, batch, origin, [77.0, 87.0, 52.0, 18.0], true);
            game.native_text(batch, &time.label(game, true), [left + 82.0, top + 91.0], 0xFFFFFF, true);
            for (area, text) in [
                (HOUR_AREA, game.translate("create.generic.daytime.hour", "Hour")),
                (MINUTE_AREA, game.translate("create.generic.daytime.minute", "Minute")),
            ] {
                let [x,y,w,h] = area;
                horizon_client::widgets::record(&text, [left + x, top + y,w,h], true);
            }
            condition_box(game, batch, origin, [129.0, 87.0, 69.0, 18.0], false);
            game.native_text(batch, &time.rotation_label(game), [left + 134.0, top + 91.0], 0xFFFFFF, true);
            let [x, y, width, height] = ROTATION_AREA;
            horizon_client::widgets::record(
                &game.translate("create.schedule.condition.time_of_day.rotation", "Rotation"),
                [left + x, top + y, width, height], true,
            );
        }
        _ => (),
    }
    editor_inventory(game, batch, origin);
    button(game, batch, screen.mouse, button_at(origin, [224.0, 87.0]), [0.0, 16.0],
        "Confirm Condition", true, false);
    if allow_delete {
        button(game, batch, screen.mouse, button_at(origin, [11.0, 87.0]), [16.0, 0.0],
            "Delete Condition", true, false);
    }
}

pub(super) fn render(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    STATE.with_borrow(|state| {
        let Some(editor) = state else {
            return;
        };
        let [x, y, w, h] = screen.rect;
        game.native_apply_screen_blur();
        batch.fill_gradient(
            &game.gui.atlas,
            (x, y, w, h),
            rgba(16, 16, 16, 192),
            rgba(16, 16, 16, 208),
        );
        let origin = origin(screen.rect);
        let [left, top] = origin;
        blit(game, batch, ATLAS, origin, [0.0, 0.0, WIDTH, HEIGHT], [0.0, 0.0]);
        let scroll =
            editor.previous_scroll + (editor.scroll - editor.previous_scroll) * screen.partial_tick;
        let content = [left, top - scroll];
        stretch(
            game,
            batch,
            origin,
            [5.0, 235.0, 3.0, 1.0],
            [33.0, VIEW_TOP, 3.0, VIEW_BOTTOM - VIEW_TOP],
        );
        let start = batch.vertices.len();
        strip(game, batch, content, editor.content_end());
        if !editor.schedule.stops.is_empty() {
            let row = editor.schedule.progress().min(editor.schedule.stops.len() - 1);
            let expected = editor.rows().nth(row).map_or(ROW_TOP, |(y, _)| y) + 4.0 - scroll;
            let actual = expected.clamp(18.0, 170.0);
            let source = if actual == expected { [185.0, 239.0, 21.0, 16.0] }
                else { [171.0, 239.0, 13.0, 16.0] };
            blit(game, batch, ATLAS, origin, source, [0.0, actual]);
        }
        for (row, (offset, stop)) in editor.rows().enumerate() {
            let destination = stop.title(game);
            let row_y = offset - scroll;
            let height = stop.height();
            if row_y + height + 10.0 <= VIEW_TOP || row_y >= VIEW_BOTTOM {
                continue;
            }
            let row_origin = [left, top + row_y - ROW_TOP];
            card(game, batch, row_origin, stop);
            let column = editor.condition_columns.get(&row).copied().unwrap_or_default();
            condition_buttons(game, batch, row_origin, stop, column, !editor.editing(), top);
            if row + 1 < editor.schedule.stops.len() {
                blit(game, batch, ATLAS, row_origin, [23.0, 239.0, 11.0, 16.0], [29.0, ROW_TOP + height - 3.0]);
            }
            for (available, area, sprite, key, fallback) in [
                (row > 0, MOVE_UP, Some([51.0, 230.0, 12.0, 12.0]), "create.gui.schedule.move_up", "Move up"),
                (row + 1 < editor.schedule.stops.len(), MOVE_DOWN, Some([65.0, 230.0, 12.0, 12.0]), "create.gui.schedule.move_down", "Move down"),
                (true, duplicate_area(height), None, "create.gui.schedule.duplicate", "Duplicate"),
            ] {
                if !available { continue; }
                let [x, y, w, h] = area;
                if let Some(sprite) = sprite {
                    blit(game, batch, ATLAS, row_origin, sprite, [x, ROW_TOP + y]);
                }
                if !editor.editing() && row_y + y >= VIEW_TOP && row_y + y + h <= VIEW_BOTTOM {
                    let label = format!("{} {}", game.translate(key, fallback), row + 1);
                    horizon_client::widgets::record(&label, [left + x, top + row_y + y, w, h], true);
                }
            }
            if !editor.editing() && row_y + 2.0 >= VIEW_TOP && row_y + 21.0 <= VIEW_BOTTOM {
                horizon_client::widgets::record(
                    &destination,
                    [left + 51.0, top + row_y + 5.0, 100.0, 16.0],
                    stop.kind().is_some(),
                );
                horizon_client::widgets::record(
                    &format!(
                        "{} {}",
                        game.translate("create.gui.schedule.remove_entry", "Remove Action"),
                        row + 1
                    ),
                    [left + 206.0, top + row_y + 2.0, 12.0, 12.0],
                    true,
                );
            }
        }
        batch.clip_since(start, left + 16.0, top + VIEW_TOP, left + 236.0, top + VIEW_BOTTOM);
        let dark = rgba(0, 0, 0, 119);
        let clear = rgba(0, 0, 0, 0);
        batch.fill_gradient(&game.gui.atlas, (left + 16.0, top + 16.0, 220.0, 10.0), dark, clear);
        batch.fill_gradient(&game.gui.atlas, (left + 16.0, top + 179.0, 220.0, 10.0), clear, dark);
        title(
            game,
            batch,
            &game.translate("item.create.schedule", "Train Schedule"),
            [left, top + 4.0],
        );
        if let Some(draft) = &editor.draft {
            instruction(game, screen, batch, origin, draft);
            let choices = editor.suggestions(draft);
            if !choices.is_empty() {
                Dropdown::new(game, &choices, draft.suggestion, origin).draw(game, batch);
            }
        } else if let Some((row, slot, condition)) = editor.condition_draft {
            let allow_delete = match slot {
                ConditionSlot::Existing { group, .. } => editor.schedule.stops[row].removable(group),
                _ => true,
            };
            draw_condition(game, screen, batch, origin, condition, &editor.condition_fields, allow_delete);
        }
        game.native_item(batch, SCHEDULE, [left + WIDTH, top + HEIGHT - 56.0], 48.0);
        if editor.editing() {
            return;
        }
        let end = editor.content_end() - scroll;
        if end >= VIEW_TOP && end + 16.0 <= VIEW_BOTTOM {
            horizon_client::widgets::record(
                &game.translate("create.gui.schedule.add_entry", "Add Action"),
                [left + 43.0, top + end, 16.0, 16.0],
                true,
            );
        }
        for (at, icon, label, enabled, green) in [
            (
                [21.0, 196.0],
                [48.0, 16.0],
                game.translate("create.schedule.loop", "Loop Forever"),
                true,
                editor.schedule.cyclic,
            ),
            (
                [45.0, 196.0],
                [112.0, 0.0],
                game.translate("create.schedule.reset", "Reset Progress"),
                !editor.schedule.stops.is_empty() && editor.schedule.progress() > 0,
                false,
            ),
            (
                [63.0, 196.0],
                [80.0, 0.0],
                game.translate("create.schedule.skip", "Skip current Stop"),
                editor.schedule.stops.len() > 1,
                false,
            ),
            ([214.0, 196.0], [0.0, 16.0], game.translate("gui.done", "Done"), true, false),
        ] {
            button(game, batch, screen.mouse, button_at(origin, at), icon, &label, enabled, green);
        }
    });
}

pub(super) fn mouse(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || !matches!(button, 0 | 1) || game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    let origin = origin(screen.rect);
    let [left, top] = origin;
    STATE.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        let picked = if button == 0 {
            editor.draft.as_ref().and_then(|draft| {
                let choices = editor.suggestions(draft);
                Dropdown::new(game, &choices, draft.suggestion, origin).hit(screen.mouse).map(String::from)
            })
        } else {
            None
        };
        if let Some(name) = picked.filter(|name| valid_filter(name))
            && let Some(draft) = editor.draft.as_mut()
        {
            draft.filter = name;
            draft.selected_all = false;
            draft.suggestions_hidden = true;
            *canceled = true;
            return;
        }
        if let Some((row, slot, condition)) = editor.condition_draft {
            let fields = &mut editor.condition_fields;
            fields.focused = matches!(condition, Condition::Cargo(_)) && button == 0 && contains(
                CARGO_AMOUNT_AREA, [screen.mouse[0] - left, screen.mouse[1] - top],
            );
            fields.selected_all = false;
            let slots = condition.ghost_slots();
            if slots > 0 {
                if let Some(index) = (0..slots).find(|&i| contains(frequency_area(origin, i), screen.mouse)) {
                    fields.samples[index] = None;
                    *canceled = true;
                    return;
                }
                if modifiers & 1 != 0
                    && let Some(index) = (0..36).find(|&i| contains(inventory_area(origin, i), screen.mouse))
                    && let Some(stack) = game.stack_in(index)
                    && let Some(available) = fields.samples[..slots].iter_mut().find(|item| item.is_none())
                {
                    let mut sample = stack.clone();
                    sample.count = 1;
                    *available = Some(sample);
                    *canceled = true;
                    return;
                }
            }
            if button == 0 && contains(button_at(origin, [224.0, 87.0]), screen.mouse) {
                editor.schedule.stops[row].set_condition(slot, condition, fields);
                editor.condition_draft = None;
            } else if button == 0 && contains(button_at(origin, [11.0, 87.0]), screen.mouse) {
                if let ConditionSlot::Existing { group, term } = slot {
                    if editor.schedule.stops[row].removable(group) {
                        editor.schedule.stops[row].remove_condition(group, term);
                        editor.condition_draft = None;
                        editor.condition_columns.remove(&row);
                    }
                } else {
                    editor.condition_draft = None;
                }
            }
            *canceled = true;
        } else if button == 1 {
            if editor.draft.is_none()
                && let Some((row, ConditionClick::Remove { group, term })) =
                editor_condition_click(game, editor, screen.mouse, origin, button)
            {
                editor.schedule.stops[row].remove_condition(group, term);
                editor.condition_columns.remove(&row);
                *canceled = true;
            }
        } else if let Some(draft) = &mut editor.draft {
            if contains(button_at(origin, [224.0, 87.0]), screen.mouse) {
                editor.confirm_draft();
            } else if draft.row.is_none() && contains(button_at(origin, [11.0, 87.0]), screen.mouse)
            {
                editor.draft = None;
            } else {
                draft.focused = draft.kind.text()
                    && contains([left + 77.0, top + 87.0, 121.0, 18.0], screen.mouse);
                draft.selected_all = false;
                draft.suggestions_hidden = false;
                draft.suggestion = 0;
            }
            *canceled = true;
        } else if contains(button_at(origin, [21.0, 196.0]), screen.mouse) {
            editor.schedule.cyclic = !editor.schedule.cyclic;
            *canceled = true;
        } else if contains(button_at(origin, [45.0, 196.0]), screen.mouse) {
            if !editor.schedule.stops.is_empty() && editor.schedule.progress() > 0 {
                editor.schedule.set_progress(0);
            }
            *canceled = true;
        } else if contains(button_at(origin, [63.0, 196.0]), screen.mouse) {
            let count = editor.schedule.stops.len();
            if count > 1 {
                editor.schedule.set_progress((editor.schedule.progress() + 1) % count);
            }
            *canceled = true;
        } else if contains(button_at(origin, [214.0, 196.0]), screen.mouse) {
            editor.closing = true;
            *canceled = true;
        } else if contains(
            [left + 16.0, top + VIEW_TOP, 220.0, VIEW_BOTTOM - VIEW_TOP],
            screen.mouse,
        ) {
            let scrolled_top = top - editor.previous_scroll;
            if contains(
                [left + 43.0, scrolled_top + editor.content_end(), 16.0, 16.0],
                screen.mouse,
            ) {
                editor.start_draft(None);
                *canceled = true;
                return;
            }
            let row_y: Vec<_> = editor.rows().map(|(y, _)| scrolled_top + y).collect();
            for (row, row_top) in row_y.into_iter().enumerate() {
                let at = [screen.mouse[0] - left, screen.mouse[1] - row_top];
                let height = editor.schedule.stops[row].height();
                if contains([206.0, 2.0, 12.0, 12.0], at) {
                    editor.remove(row);
                } else if contains(duplicate_area(height), at) {
                    editor.duplicate(row);
                } else if row > 0 && contains(MOVE_UP, at) {
                    editor.move_row(row, row - 1);
                } else if row + 1 < editor.schedule.stops.len() && contains(MOVE_DOWN, at) {
                    editor.move_row(row, row + 1);
                } else if editor.schedule.stops[row].kind().is_some()
                    && contains([left + 50.0, row_top + 5.0, 150.0, 16.0], screen.mouse)
                {
                    editor.start_draft(Some(row));
                } else {
                    continue;
                }
                *canceled = true;
                return;
            }
            if let Some((row, action)) = editor_condition_click(game, editor, screen.mouse, origin, button) {
                match action {
                    ConditionClick::Edit(slot, value) => {
                        let stop = &editor.schedule.stops[row];
                        let text = stop.condition_tag(slot).and_then(|tag| tag.get("Data"))
                            .and_then(|data| match data.get("Threshold") {
                                Some(Tag::String(text)) => text.to_string().ok(),
                                _ => None,
                            }).unwrap_or_else(|| "10".to_owned());
                        let samples = std::array::from_fn(|index| {
                            if index < value.ghost_slots() { stop.condition_sample(slot, value, index) } else { None }
                        });
                        editor.condition_fields = ConditionFields::new(text, samples);
                        editor.condition_draft = Some((row, slot, value));
                    }
                    ConditionClick::Scroll(column) => {
                        editor.condition_columns.insert(row, column);
                    }
                    ConditionClick::Remove { .. } => (),
                }
                *canceled = true;
            }
        }
    });
}

fn editor_condition_click(
    game: &Game<'_>,
    editor: &Editor,
    [mx, my]: [f32; 2],
    [left, top]: [f32; 2],
    button: i32,
) -> Option<(usize, ConditionClick)> {
    if my < top + VIEW_TOP || my >= top + VIEW_BOTTOM {
        return None;
    }
    editor.rows().enumerate().find_map(|(row, (y, stop))| {
        let at = [mx - left, my - top + editor.previous_scroll - y + ROW_TOP];
        if at[1] > ROW_TOP + stop.height() {
            return None;
        }
        let column = editor.condition_columns.get(&row).copied().unwrap_or_default();
        condition_click(game, stop, column, at, button).map(|click| (row, click))
    })
}

pub(super) fn character(game: &Game<'_>, c: char, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    STATE.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        if editor.condition_draft.is_some() && editor.condition_fields.focused {
            let fields = &mut editor.condition_fields;
            let mut text = if fields.selected_all { String::new() } else { fields.text.clone() };
            text.push(c);
            if text.parse::<i32>().is_ok() {
                fields.text = text;
                fields.selected_all = false;
            }
            *canceled = true;
            return;
        }
        let Some(draft) = editor.draft.as_mut().filter(|draft| draft.focused) else {
            return;
        };
        *canceled = true;
        let mut value = if draft.selected_all { String::new() } else { draft.filter.clone() };
        value.push(c);
        if (draft.kind == ActionKind::Title && value.encode_utf16().count() <= 32)
            || (matches!(draft.kind, ActionKind::Destination | ActionKind::Retrieve) && valid_filter(&value))
        {
            draft.filter = value;
            draft.selected_all = false;
            draft.suggestions_hidden = false;
            draft.suggestion = 0;
        }
    });
}

pub(super) fn key(game: &Game<'_>, key: &str, modifiers: u32, canceled: &mut bool) {
    if *canceled || game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    STATE.with_borrow_mut(|state| {
        let Some(editor) = state else {
            return;
        };
        if editor.condition_draft.is_some() && editor.condition_fields.focused {
            let fields = &mut editor.condition_fields;
            match key {
                "key.keyboard.a" if modifiers & 10 != 0 => fields.selected_all = true,
                "key.keyboard.backspace" => {
                    if fields.selected_all {
                        fields.text.clear();
                        fields.selected_all = false;
                    } else {
                        fields.text.pop();
                    }
                }
                "key.keyboard.end" => fields.selected_all = false,
                _ => return,
            }
            *canceled = true;
            return;
        }
        let (count, next) = editor.draft.as_ref().map_or((0, None), |draft| {
            let choices = editor.suggestions(draft);
            (choices.len(), choices.get(draft.suggestion.min(choices.len().saturating_sub(1))).copied().map(String::from))
        });
        let Some(draft) = editor.draft.as_mut().filter(|draft| draft.focused) else {
            return;
        };
        match key {
            "key.keyboard.tab" => {
                let Some(name) = next.filter(|name| valid_filter(name)) else { return; };
                draft.filter = name;
                draft.selected_all = false;
                draft.suggestions_hidden = true;
            }
            "key.keyboard.down" if count > 0 => draft.suggestion = (draft.suggestion + 1) % count,
            "key.keyboard.up" if count > 0 => {
                draft.suggestion = (draft.suggestion + count - 1) % count;
            }
            "key.keyboard.escape" if count > 0 => draft.suggestions_hidden = true,
            "key.keyboard.enter" | "key.keyboard.keypad.enter" => editor.confirm_draft(),
            "key.keyboard.a" if modifiers & 10 != 0 => {
                draft.selected_all = true;
                draft.suggestions_hidden = false;
                draft.suggestion = 0;
            }
            "key.keyboard.backspace" => {
                if draft.selected_all {
                    draft.filter.clear();
                    draft.selected_all = false;
                } else {
                    draft.filter.pop();
                }
                draft.suggestions_hidden = false;
                draft.suggestion = 0;
            }
            _ => return,
        }
        *canceled = true;
    });
}

pub(super) fn scroll(
    game: &mut Game<'_>,
    mouse: [f32; 2],
    dy: f64,
    modifiers: u32,
    canceled: &mut bool,
) {
    if *canceled || dy == 0.0 || game.native_mod_screen() != Some(EDITOR) {
        return;
    }
    let pitch = STATE.with_borrow_mut(|state| {
        let editor = state.as_mut()?;
        if let Some(draft) = &mut editor.draft {
            let [left, top] = origin(game.screen_view_now()?.rect);
            let at = [mouse[0] - left, mouse[1] - top];
            let sign = if dy > 0.0 { 1 } else { -1 };
            if contains(ACTION_TYPE_AREA, at) {
                let prior = draft.kind as i32;
                let step = if modifiers & 1 != 0 { 5 } else { 1 };
                let next = (prior - step * sign).clamp(0, ActionKind::ALL.len() as i32 - 1);
                if next != prior {
                    draft.kind = ActionKind::ALL[next as usize];
                    draft.filter.clear();
                    draft.throttle = 100;
                    draft.focused = false;
                    draft.selected_all = false;
                    draft.suggestion = 0;
                    draft.suggestions_hidden = false;
                }
                *canceled = true;
                return (prior != next).then_some(1.5 + 0.1 * next as f32 / 5.0);
            }
            if draft.kind == ActionKind::Throttle && contains(THROTTLE_AREA, at) {
                let previous = draft.throttle;
                let step = if modifiers & 1 != 0 { 25 } else { 5 };
                let next = (previous + step * sign).clamp(5, 100);
                draft.throttle = next - if modifiers & 1 != 0 { next % 5 } else { 0 };
                *canceled = true;
                return (previous != draft.throttle).then_some(1.5 + 0.1 * (draft.throttle - 5) as f32 / 96.0);
            }
            return None;
        }
        if let Some((_, _, condition)) = &mut editor.condition_draft {
            let [left, top] = origin(game.screen_view_now()?.rect);
            let at = [mouse[0] - left, mouse[1] - top];
            let direction = if dy > 0.0 { 1 } else { -1 };
            let shift = modifiers & 1 != 0;
            if contains(ACTION_TYPE_AREA, at) {
                let previous = condition.kind() as i32;
                let mut next = previous - direction * if shift { 5 } else { 1 };
                if shift {
                    next -= next % 5;
                }
                next = next.clamp(0, ConditionKind::ALL.len() as i32 - 1);
                *canceled = true;
                if previous != next {
                    *condition = Condition::new(ConditionKind::ALL[next as usize]);
                    let samples = core::mem::take(&mut editor.condition_fields.samples);
                    editor.condition_fields = ConditionFields::new("10".to_owned(), samples);
                    return Some(1.5 + 0.1 * next as f32 / ConditionKind::ALL.len() as f32);
                }
                return None;
            }
            let (value, direction, max, shift_step) = match condition {
                Condition::Delay(delay) | Condition::Idle(delay) if contains(DURATION_AREA, at) =>
                    (&mut delay.value, direction, MAX_DURATION, 15),
                Condition::Delay(delay) | Condition::Idle(delay) if contains(TIME_UNIT_AREA, at) =>
                    (&mut delay.unit, -direction, 2, 5),
                Condition::Cargo(cargo) if contains(CARGO_OPERATOR_AREA, at) =>
                    (&mut cargo.operator, -direction, 2, 5),
                Condition::Cargo(cargo) if cargo.kind == ConditionKind::ItemThreshold && contains(CARGO_MEASURE_AREA, at) =>
                    (&mut cargo.measure, -direction, 1, 5),
                Condition::RedstoneLink(inverted) if contains(FREQUENCY_STATE_AREA, at) =>
                    (inverted, -direction, 1, 5),
                Condition::PlayerCount(players) if contains(DURATION_AREA, at) =>
                    (&mut players.count, direction, 20, 5),
                Condition::PlayerCount(players) if contains(CONDITIONAL_AREA, at) =>
                    (&mut players.exact, -direction, 1, 5),
                Condition::TimeOfDay(time) if contains(HOUR_AREA, at) =>
                    (&mut time.hour, direction, 23, 6),
                Condition::TimeOfDay(time) if contains(MINUTE_AREA, at) =>
                    (&mut time.minute, direction, 59, 15),
                Condition::TimeOfDay(time) if contains(ROTATION_AREA, at) =>
                    (&mut time.rotation, -direction, 9, 5),
                _ => return None,
            };
            let previous = *value;
            let mut next = previous + direction * if shift { shift_step } else { 1 };
            if shift {
                next -= next % shift_step;
            }
            *value = next.clamp(0, max);
            *canceled = true;
            return (*value != previous).then_some(1.5 + 0.1 * *value as f32 / (max + 1) as f32);
        }
        if !editor.editing() {
            if modifiers & 1 != 0 {
                let [left, top] = origin(game.screen_view_now()?.rect);
                let row = editor.rows().enumerate().find_map(|(row, (y, stop))| {
                    let rel = mouse[1] - top + editor.previous_scroll - y;
                    (mouse[0] >= left + CONDITION_LEFT && mouse[0] < left + CONDITION_RIGHT
                        && rel >= 28.0 && rel < stop.height() && overflowing(game, stop))
                        .then_some((row, stop.conditions.len()))
                });
                if let Some((row, groups)) = row {
                    let column = editor.condition_columns.entry(row).or_default();
                    *column = if dy < 0.0 { (*column + 1).min(groups.saturating_sub(1)) } else { column.saturating_sub(1) };
                    *canceled = true;
                    return None;
                }
            }
            editor.scroll_target =
                (editor.scroll_target - dy as f32 * 12.0).clamp(0.0, editor.scroll_limit());
            *canceled = true;
        }
        None
    });
    if let Some(pitch) = pitch {
        game.audio.play_on(0, "create:scroll_value", None, 0.25, pitch);
    }
}

pub(super) fn tick(game: &mut Game<'_>) {
    let visible = game.native_mod_screen() == Some(EDITOR);
    let closed = STATE.with_borrow_mut(|state| {
        if !visible || state.as_ref().is_some_and(|editor| editor.closing) {
            state.take().map(|mut editor| {
                editor.schedule.clamp_progress();
                editor
            })
        } else {
            if let Some(editor) = state.as_mut() {
                editor.schedule.clamp_progress();
                let limit = editor.scroll_limit();
                editor.scroll_target = editor.scroll_target.min(limit);
                editor.scroll = editor.scroll.min(limit);
                editor.previous_scroll = editor.scroll;
                editor.scroll += (editor.scroll_target - editor.scroll) * 0.7;
            }
            None
        }
    });
    if let Some(editor) = closed {
        if let Ok(data) = encode(&editor.schedule) {
            let _ = game.native_net_send_to_server(CHANNEL, &data);
        }
        game.native_mod_screen_close(EDITOR);
    }
}

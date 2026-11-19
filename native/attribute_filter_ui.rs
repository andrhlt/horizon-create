use horizon_client::hud::HudBatch;
use horizon_world::nbt::{Compound, Tag};

use crate::items::{ItemStack, Items};

use super::{
    Game, create_item_filters,
    create_machines::{int, string},
};

pub(super) const ITEM: &str = "create:attribute_filter";
pub(super) const SCREEN: &str = "create:attribute_filter_editor";
const MODE: &str = "create:attribute_filter_whitelist_mode";
const SELECTED: &str = "create:attribute_filter_matched_attributes";
const MODES: [&str; 3] = ["whitelist_disj", "whitelist_conj", "blacklist"];
pub(super) const CHOICE: [f32; 4] = [39.0, 26.0, 137.0, 18.0];

#[derive(Clone, Default)]
pub(super) struct Attributes {
    mode: usize,
    saved: Vec<Tag>,
    offered: Vec<Tag>,
    picked: usize,
}

pub(super) fn register(types: &mut Vec<String>) {
    types.extend([MODE, SELECTED].map(str::to_owned));
}

fn list(value: Option<&Tag>) -> Vec<Tag> {
    match value {
        Some(Tag::List(values)) => values.clone(),
        _ => Vec::new(),
    }
}

impl Attributes {
    pub(super) fn read(game: &Game<'_>, holder: &ItemStack) -> Self {
        let mode = game
            .native_component(holder, MODE)
            .ok()
            .flatten()
            .and_then(|tag| {
                let Tag::String(value) = tag else { return None };
                MODES.iter().position(|&mode| value == &mode.into())
            })
            .unwrap_or_default();
        Self {
            mode,
            saved: list(game.native_component(holder, SELECTED).ok().flatten()),
            ..Self::default()
        }
    }

    pub(super) fn tag(&self) -> Tag {
        Tag::compound([
            ("Mode", Tag::Int(self.mode as i32)),
            ("Saved", Tag::List(self.saved.clone())),
            ("Offered", Tag::List(self.offered.clone())),
            ("Pick", Tag::Int(self.picked as i32)),
        ])
    }

    pub(super) fn from_tag(tag: &Tag) -> Option<Self> {
        let Tag::Compound(fields) = tag else {
            return None;
        };
        Some(Self {
            mode: usize::try_from(int(fields, "Mode")?)
                .ok()?
                .min(MODES.len() - 1),
            saved: list(tag.get("Saved")),
            offered: list(tag.get("Offered")),
            picked: usize::try_from(int(fields, "Pick")?).ok()?,
        })
    }

    pub(super) fn write(&self, game: &Game<'_>, holder: &mut ItemStack) -> bool {
        if self.mode == 0 && self.saved.is_empty() {
            return game.native_remove_component(holder, MODE).is_ok()
                && game.native_remove_component(holder, SELECTED).is_ok();
        }
        game.native_set_component(holder, MODE, Tag::String(MODES[self.mode].into()))
            .is_ok()
            && game
                .native_set_component(holder, SELECTED, Tag::List(self.saved.clone()))
                .is_ok()
    }

    pub(super) fn reference(&mut self, items: &Items, stack: Option<&ItemStack>) {
        self.offered = stack.map_or_else(Vec::new, |stack| choices(items, stack));
        self.picked = 0;
    }

    pub(super) fn pick(&mut self, forward: bool) {
        self.picked = if forward {
            (self.picked + 1).min(self.offered.len().saturating_sub(1))
        } else {
            self.picked.saturating_sub(1)
        };
    }

    pub(super) fn add(&mut self, inverted: bool) {
        if let Some(choice) = self.available().cloned() {
            self.saved.push(Tag::compound([
                ("attribute", choice),
                ("inverted", Tag::Byte(i8::from(inverted))),
            ]));
        }
    }

    fn available(&self) -> Option<&Tag> {
        let choice = self.offered.get(self.picked)?;
        self.saved
            .iter()
            .all(|record| record.get("attribute") != Some(choice))
            .then_some(choice)
    }

    pub(super) fn mode(&mut self, mode: usize) {
        if mode < MODES.len() {
            self.mode = mode;
        }
    }

    pub(super) fn clear(&mut self) {
        self.saved.clear();
    }

    pub(super) fn buttons(&self) -> [([f32; 2], [f32; 2], bool, bool); 7] {
        let available = self.available().is_some();
        [
            ([38.0, 61.0], [160.0, 0.0], self.mode == 0, true),
            ([56.0, 61.0], [176.0, 0.0], self.mode == 1, true),
            ([74.0, 61.0], [192.0, 0.0], self.mode == 2, true),
            ([182.0, 26.0], [0.0, 0.0], false, available),
            ([200.0, 26.0], [112.0, 64.0], false, available),
            ([179.0, 61.0], [16.0, 0.0], false, true),
            ([208.0, 61.0], [0.0, 16.0], false, true),
        ]
    }

    pub(super) fn draw_label(&self, game: &Game<'_>, batch: &mut HudBatch, [left, top]: [f32; 2]) {
        let label = self
            .offered
            .get(self.picked)
            .and_then(|choice| {
                let Tag::Compound(attribute) = choice else {
                    return None;
                };
                Some(label(game, attribute))
            })
            .unwrap_or_else(|| {
                game.translate(
                    "create.gui.attribute_filter.add_reference_item",
                    "Add Reference Item",
                )
            });
        let mut display = String::new();
        for character in label.chars() {
            display.push(character);
            if game.native_text_width(&display) > 127.0 {
                display.pop();
                break;
            }
        }
        game.native_text(batch, &display, [left + 43.0, top + 31.0], 0xf3ebde, true);
        game.native_item(batch, "minecraft:name_tag", [left + 16.0, top + 62.0], 16.0);
        game.native_text(
            batch,
            &self.saved.len().to_string(),
            [left + 26.0, top + 71.0],
            0xffffff,
            true,
        );
    }
}

fn label(game: &Game<'_>, attribute: &Compound) -> String {
    let kind = string(attribute, "type").unwrap_or_default();
    let kind = kind.strip_prefix("create:").unwrap_or(&kind);
    let (key, parameter) = match kind {
        "book_copy" => (
            match int(attribute, "value").unwrap_or(-1) {
                0 => "book_copy_original",
                1 => "book_copy_first",
                2 => "book_copy_second",
                _ => "book_copy_tattered",
            },
            String::new(),
        ),
        "shulker_fill_level" => {
            let value = string(attribute, "value").unwrap_or_default();
            let localized = game.translate(
                &format!("create.item_attributes.shulker_level.{value}"),
                &value,
            );
            ("shulker_level", localized)
        }
        "has_color" => {
            let value = string(attribute, "value").unwrap_or_default();
            let color = game.translate(
                &format!("color.minecraft.{value}"),
                &value.replace('_', " "),
            );
            ("color", color)
        }
        "added_by" => {
            let value = string(attribute, "value").unwrap_or_default();
            let display = match value.as_str() {
                "create" => "Create".to_owned(),
                "minecraft" => "Minecraft".to_owned(),
                _ => value,
            };
            (kind, display)
        }
        _ => (kind, string(attribute, "value").unwrap_or_default()),
    };
    game.translate(
        &format!("create.item_attributes.{key}"),
        &kind.replace('_', " "),
    )
    .replace("%1$s", &parameter)
}

fn choices(items: &Items, stack: &ItemStack) -> Vec<Tag> {
    let choice = |name: &str, value| {
        Tag::compound([
            (
                "type",
                Tag::String(format!("create:{name}").as_str().into()),
            ),
            ("value", value),
        ])
    };
    let mut result = Vec::new();
    for kind in [
        "placeable",
        "consumable",
        "fluid_container",
        "enchanted",
        "max_enchanted",
        "renamed",
        "damaged",
        "badly_damaged",
        "not_stackable",
        "equipable",
        "furnace_fuel",
        "compostable",
    ] {
        let attribute = choice(kind, Tag::Compound(Compound::new()));
        if let Tag::Compound(data) = &attribute
            && create_item_filters::applies(items, data, stack) == Some(true)
        {
            result.push(attribute);
        }
    }
    let mut tags: Vec<_> = items
        .item_tags
        .iter()
        .filter_map(|(tag, entries)| entries.contains(stack.item.as_ref()).then_some(tag))
        .collect();
    tags.sort_unstable();
    result.extend(
        tags.into_iter()
            .map(|tag| choice("in_tag", Tag::String(tag.as_str().into()))),
    );
    if let Some((namespace, _)) = stack.item.split_once(':') {
        result.push(choice("added_by", Tag::String(namespace.into())));
    }
    result.extend(
        stack
            .enchantments()
            .iter()
            .chain(stack.stored_enchantments())
            .map(|(id, _)| choice("has_enchant", Tag::String(id.as_ref().into()))),
    );
    if let Some(fill) = create_item_filters::shulker_fill(items, stack) {
        result.push(choice("shulker_fill_level", Tag::String(fill.into())));
    }
    result.extend(
        create_item_filters::colors(items, stack)
            .into_iter()
            .map(|color| choice("has_color", Tag::String(color.into()))),
    );
    if let Some(fluid) = create_item_filters::fluid_content(stack) {
        result.push(choice("has_fluid", Tag::String(fluid.as_str().into())));
    }
    let name = create_item_filters::structured_name(stack);
    if !name.is_empty() {
        result.push(choice("has_name", Tag::String(name.as_str().into())));
    }
    if let Some(book) = stack.data().and_then(|data| data.written.as_ref()) {
        if !book.author.is_empty() {
            result.push(choice(
                "book_author",
                Tag::String(book.author.as_str().into()),
            ));
        }
        result.push(choice("book_copy", Tag::Int(i32::from(book.generation))));
    }
    result
}

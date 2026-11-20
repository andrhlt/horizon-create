use horizon_world::nbt::{Compound, Tag};

use crate::items::{ItemStack, Items};

use super::create_depot::compound;
use super::create_fluids::{Fluid, liquid_from_stack};
use super::create_machines::{int, string};
use super::create_package_address;

pub(super) fn accepts(items: &Items, nbt: &Compound, stack: &ItemStack) -> bool {
    let Some(filter) = compound(nbt, "Filter") else {
        return true;
    };
    matches(items, filter, stack, false)
}

pub(super) fn matches(
    items: &Items,
    filter: &Compound,
    stack: &ItemStack,
    components: bool,
) -> bool {
    let Some(sample) = ItemStack::from_nbt(filter) else {
        return true;
    };
    if sample.item.as_ref() == "create:attribute_filter"
        && let Some(result) = matches_attributes(items, filter, stack)
    {
        return result;
    }
    // Java only wraps List Filters with a component patch. A fresh List Filter
    // is an ordinary item sample, including when placed in another List Filter.
    if sample.item.as_ref() == "create:filter"
        && (compound(filter, "tag").is_some()
            || compound(filter, "components").is_some_and(|patch| !patch.is_empty()))
    {
        return list_matches(filter, |candidate, respect| {
            matches(items, candidate, stack, respect)
        });
    }

    let same_item = sample.item == stack.item
        && (!components || (sample.damage == stack.damage && sample.extra == stack.extra));
    if sample.item.as_ref() == "create:package_filter" && sample.data().is_some() {
        let request = package_address(&sample);
        let same_filter = if components && stack.item == sample.item {
            same_trimmed_filter(&sample, stack)
        } else {
            same_item
        };
        return (create_package_address::is_blank(&request) && same_filter)
            || (is_package(items, stack)
                && create_package_address::matches(&package_address(stack), &request));
    }
    same_item || (!components && is_package(items, &sample) && is_package(items, stack))
}

fn same_trimmed_filter(sample: &ItemStack, candidate: &ItemStack) -> bool {
    // FilterItemStack.of strips these two item prototype components when wrapping a filter.
    let mut normalized = sample.clone();
    let data = normalized.data_mut();
    data.enchantments.clear();
    for (component, removed) in [
        ("minecraft:enchantments", "!minecraft:enchantments"),
        (
            "minecraft:attribute_modifiers",
            "!minecraft:attribute_modifiers",
        ),
    ] {
        data.set_other(component, None);
        data.set_other(removed, Some(Tag::Compound(Compound::new())));
    }
    normalized.damage == candidate.damage && normalized.extra == candidate.extra
}

fn is_package(items: &Items, stack: &ItemStack) -> bool {
    items
        .item_tags
        .get("create:packages")
        .is_some_and(|tag| tag.contains(stack.item.as_ref()))
}

fn package_address(stack: &ItemStack) -> String {
    match stack
        .data()
        .and_then(|data| data.other("create:package_address"))
    {
        Some(Tag::String(text)) => text.to_string().unwrap_or_default(),
        _ => String::new(),
    }
}

pub(super) fn accepts_fluid(nbt: &Compound, fluid: &Fluid) -> bool {
    compound(nbt, "Filter").is_none_or(|filter| matches_fluid(filter, fluid, true))
}

fn matches_fluid(filter: &Compound, fluid: &Fluid, respect: bool) -> bool {
    let Some(sample) = ItemStack::from_nbt(filter) else {
        return true;
    };
    if sample.item.as_ref() == "create:filter" {
        return list_matches(filter, |candidate, respect| {
            matches_fluid(candidate, fluid, respect)
        });
    }
    if sample.item.as_ref() == "minecraft:milk_bucket" && fluid.id == "create:milk" {
        return !respect || fluid.components.is_none();
    }
    liquid_from_stack(&sample, 1).is_some_and(|sample| {
        if respect {
            sample.same_variant(fluid)
        } else {
            sample.id == fluid.id
        }
    })
}

fn list_matches(filter: &Compound, mut accepts: impl FnMut(&Compound, bool) -> bool) -> bool {
    let (entries, blacklist, respect) = if let Some(legacy) = compound(filter, "tag") {
        let items = compound(legacy, "Items").and_then(|items| items.get(&"Items".into()));
        let blacklist = int(legacy, "Blacklist").unwrap_or(0) != 0;
        let respect = int(legacy, "RespectNBT").unwrap_or(0) != 0;
        (items, blacklist, respect)
    } else if let Some(fields) = compound(filter, "components") {
        let items = fields.get(&"create:filter_items".into());
        let blacklist = int(fields, "create:filter_items_blacklist").unwrap_or(0) != 0;
        let respect = int(fields, "create:filter_items_respect_nbt").unwrap_or(0) != 0;
        (items, blacklist, respect)
    } else {
        return false;
    };
    let Some(Tag::List(entries)) = entries else {
        return false;
    };
    let contributes = entries.iter().any(|entry| {
        let Tag::Compound(candidate) = entry else {
            return false;
        };
        accepts(compound(candidate, "item").unwrap_or(candidate), respect)
    });
    contributes != blacklist
}

fn matches_attributes(items: &Items, filter: &Compound, stack: &ItemStack) -> Option<bool> {
    let fields = compound(filter, "components")?;
    let Tag::List(entries) = fields.get(&"create:attribute_filter_matched_attributes".into())?
    else {
        return None;
    };
    let mut tests = entries
        .iter()
        .filter_map(|entry| {
            let Tag::Compound(entry) = entry else {
                return None;
            };
            let attribute = compound(entry, "attribute")?;
            applies(items, attribute, stack)
                .map(|matched| matched != (int(entry, "inverted") == Some(1)))
        })
        .peekable();
    tests.peek()?;
    Some(
        match string(fields, "create:attribute_filter_whitelist_mode").as_deref() {
            Some("blacklist") => !tests.any(|matches| matches),
            Some("whitelist_conj") => tests.all(|matches| matches),
            _ => tests.any(|matches| matches),
        },
    )
}

pub(super) fn applies(items: &Items, attribute: &Compound, stack: &ItemStack) -> Option<bool> {
    let info = items.get(&stack.item);
    Some(match string(attribute, "type")?.as_str() {
        "create:in_tag" => {
            let tag = string(attribute, "value")?;
            items
                .item_tags
                .get(&tag)
                .is_some_and(|items| items.contains(stack.item.as_ref()))
        }
        "create:placeable" => info.is_some_and(|item| item.block.is_some()),
        "create:consumable" => info.is_some_and(|item| item.food.is_some()),
        "create:enchanted" => !stack.enchantments().is_empty(),
        "create:max_enchanted" => stack.enchantments().iter().any(|(id, level)| {
            items
                .enchantments
                .get(id)
                .is_some_and(|enchantment| *level >= enchantment.max_level)
        }),
        "create:renamed" => stack.data().is_some_and(|data| data.custom_name.is_some()),
        "create:badly_damaged" => info.is_some_and(|item| {
            item.max_damage > 0 && stack.damage as f32 / item.max_damage as f32 > 0.75
        }),
        "create:not_stackable" => max_stack(items, stack) <= 1 || stack.damage != 0,
        "create:added_by" => {
            stack.item.split_once(':').map(|(namespace, _)| namespace)
                == Some(string(attribute, "value")?.as_str())
        }
        "create:has_color" => {
            let expected = string(attribute, "value")?;
            colors(items, stack).contains(&expected.as_str())
        }
        "create:has_name" => structured_name(stack) == string(attribute, "value")?,
        "create:has_fluid" => {
            let id = string(attribute, "value")?;
            fluid_content(stack).as_deref() == Some(id.as_str())
        }
        "create:shulker_fill_level" => {
            shulker_fill(items, stack) == Some(string(attribute, "value")?.as_str())
        }
        "create:book_author" => {
            let author = stack
                .data()
                .and_then(|data| data.written.as_ref())
                .map_or("", |book| book.author.as_str());
            author == string(attribute, "value")?
        }
        "create:book_copy" => stack
            .data()
            .and_then(|data| data.written.as_ref())
            .is_some_and(|book| Some(i32::from(book.generation)) == int(attribute, "value")),

        "create:fluid_container" => {
            matches!(
                stack.item.as_ref(),
                "minecraft:bucket"
                    | "minecraft:water_bucket"
                    | "minecraft:lava_bucket"
                    | "minecraft:milk_bucket"
                    | "minecraft:powder_snow_bucket"
            )
        }
        "create:has_enchant" => {
            let id = string(attribute, "value")?;
            stack
                .enchantments()
                .iter()
                .chain(stack.stored_enchantments())
                .any(|(enchantment, level)| enchantment.as_ref() == id && *level > 0)
        }
        "create:damaged" => stack.damage > 0,
        "create:equipable" => info
            .and_then(|item| item.equip_slot.as_deref())
            .is_some_and(|slot| !matches!(slot, "mainhand" | "offhand")),
        "create:furnace_fuel" => info.is_some_and(|item| item.fuel.is_some()),
        "create:compostable" => info.is_some_and(|item| item.compostable.is_some()),
        _ => return None,
    })
}

fn max_stack(items: &Items, stack: &ItemStack) -> u32 {
    match stack
        .data()
        .and_then(|data| data.other("minecraft:max_stack_size"))
    {
        Some(Tag::Int(max)) if *max > 0 => *max as u32,
        _ => items.get(&stack.item).map_or(64, |item| item.max_stack),
    }
}

pub(super) fn structured_name(stack: &ItemStack) -> String {
    let Some(name) = stack.custom_name() else {
        return String::new();
    };
    let name = name.trim_matches(|c: char| c.is_ascii_whitespace());
    if let Ok(component) = serde_json::from_str::<serde_json::Value>(name) {
        return match component {
            serde_json::Value::String(_)
            | serde_json::Value::Object(_)
            | serde_json::Value::Array(_) => {
                horizon_client::scoreboard::comp_text(&component).plain()
            }
            _ => String::new(),
        };
    }
    if let Some(quoted) = name
        .strip_prefix('\'')
        .and_then(|value| value.strip_suffix('\''))
    {
        return single_quoted_name(quoted).unwrap_or_default();
    }
    // Java's component parser accepts an unquoted string token in lenient JSON mode.
    if name.chars().all(|c| {
        !matches!(
            c,
            ' ' | '\t'
                | '\r'
                | '\n'
                | '\u{c}'
                | '/'
                | '\\'
                | ';'
                | '#'
                | '='
                | '{'
                | '}'
                | '['
                | ']'
                | ':'
                | ','
                | '\''
                | '"'
        )
    }) && !["true", "false", "null"]
        .iter()
        .any(|literal| literal.eq_ignore_ascii_case(name))
    {
        name.to_owned()
    } else {
        String::new()
    }
}

fn single_quoted_name(value: &str) -> Option<String> {
    let mut json = String::from("\"");
    let mut chars = value.chars();
    while let Some(c) = chars.next() {
        match c {
            '\'' => return None,
            '\\' => match chars.next()? {
                '\'' => json.push('\''),
                escaped => {
                    json.push('\\');
                    json.push(escaped);
                }
            },
            '"' => json.push_str("\\\""),
            c => json.push(c),
        }
    }
    json.push('"');
    serde_json::from_str(&json).ok()
}

pub(super) fn shulker_fill(items: &Items, stack: &ItemStack) -> Option<&'static str> {
    if !stack.item.ends_with("shulker_box") {
        return None;
    }
    let inside = stack.container();
    if inside.is_empty() {
        return Some("empty");
    }
    if stack
        .data()
        .is_some_and(|data| data.other("minecraft:container_loot").is_some())
    {
        return None;
    }
    let full = inside.len() == 27
        && inside
            .iter()
            .all(|(_, item)| item.count == max_stack(items, item));
    Some(if full { "full" } else { "partial" })
}

pub(super) fn fluid_content(stack: &ItemStack) -> Option<String> {
    if stack.item.as_ref() == "minecraft:bucket" {
        Some("minecraft:empty".to_owned())
    } else {
        liquid_from_stack(stack, 1).map(|fluid| fluid.id)
    }
}

pub(super) fn colors(items: &Items, stack: &ItemStack) -> Vec<&'static str> {
    use horizon_items::firework::DYE_FIREWORK_COLORS;
    let path = stack
        .item
        .split_once(':')
        .map_or(stack.item.as_ref(), |(_, path)| path);
    if let Some((dye, _)) = DYE_FIREWORK_COLORS.iter().find(|(name, _)| {
        items
            .item_tags
            .get(&format!("c:dyes/{name}"))
            .is_some_and(|members| members.contains(stack.item.as_ref()))
    }) {
        return vec![*dye];
    }
    let explosions = if matches!(
        stack.item.as_ref(),
        "minecraft:firework_rocket" | "minecraft:firework_star"
    ) {
        stack
            .data()
            .and_then(|data| data.fireworks.as_ref())
            .map(|(_, explosions)| explosions.as_slice())
    } else {
        None
    };
    DYE_FIREWORK_COLORS
        .iter()
        .filter_map(|&(name, rgb)| {
            let prefix = path
                .strip_prefix(name)
                .is_some_and(|rest| rest.starts_with('_'));
            let pigment = explosions.is_some_and(|explosions| {
                explosions.iter().any(|explosion| {
                    explosion.colors.contains(&rgb) || explosion.fade.contains(&rgb)
                })
            });
            (prefix || pigment).then_some(name)
        })
        .collect()
}

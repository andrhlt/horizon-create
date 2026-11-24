use std::collections::HashSet;

use horizon_client::text::Text;
use horizon_world::{
    level::flags,
    nbt::{Compound, Tag},
};

use super::{
    Game, Hand,
    create_clipboard::{COMPONENT, ITEM, content},
    create_clipboard_block as board, create_clipboard_filter as filter,
    create_depot::compound,
    create_latches as diode,
    create_machines::{int, mod_entity},
    create_redstone_link as link,
    create_speed_controller::CONTROLLER,
    create_speed_controller_controls::{self, Selection, ValueBlock},
};

fn pages(content: &Compound) -> impl Iterator<Item = &Tag> {
    let pages = match content.get(&"pages".into()) {
        Some(Tag::List(pages)) => pages.as_slice(),
        _ => &[],
    };
    pages
        .iter()
        .filter_map(|page| match page {
            Tag::List(entries) => Some(entries.as_slice()),
            _ => None,
        })
        .flatten()
}

fn entry_text(entry: &Compound) -> Option<String> {
    Some(horizon_protocol::text::plain(
        entry.get(&"text".into())?,
        &Default::default(),
    ))
}

fn copy_board(held: &mut Compound, source: &Compound) {
    let existing: HashSet<_> = pages(held)
        .filter_map(|entry| {
            let Tag::Compound(entry) = entry else {
                return None;
            };
            entry_text(entry)
        })
        .collect();
    let to_add: Vec<_> = pages(source)
        .filter_map(|entry| {
            let Tag::Compound(entry) = entry else {
                return None;
            };
            if existing.contains(&entry_text(entry)?) {
                return None;
            }
            Some(Tag::Compound(Compound::from([
                (
                    "checked".into(),
                    Tag::Byte(i8::from(int(entry, "checked") == Some(1))),
                ),
                ("text".into(), entry.get(&"text".into())?.clone()),
                ("icon".into(), Tag::Compound(Compound::new())),
                ("item_amount".into(), Tag::Int(0)),
            ])))
        })
        .collect();
    let Tag::List(pages) = held
        .entry("pages".into())
        .or_insert_with(|| Tag::List(Vec::new()))
    else {
        return;
    };
    let written = !to_add.is_empty();
    for entry in to_add {
        let entries = pages.iter_mut().find_map(|page| match page {
            Tag::List(entries) if entries.len() < 12 => Some(entries),
            _ => None,
        });
        if let Some(entries) = entries {
            entries.push(entry);
        } else {
            pages.push(Tag::List(vec![entry]));
        }
    }
    if written {
        held.insert("type".into(), Tag::String("written".into()));
    }
}

fn diode_values(game: &Game<'_>, [x, y, z]: [i32; 3], block: &str) -> Tag {
    let (row, value) = diode::pulse_selection(mod_entity(game, [x, y, z]), block);
    let state = game.world.block(x, y, z);
    let inverted = game
        .pack
        .assets
        .registry
        .state(state)
        .and_then(|state| state.properties.get("inverted"))
        .is_some_and(|inverted| inverted == "true");
    Tag::Compound(Compound::from([
        (
            "Block".into(),
            Tag::Compound(Compound::from([(
                "Inverted".into(),
                Tag::Byte(i8::from(inverted)),
            )])),
        ),
        (
            "Timings".into(),
            Tag::Compound(Compound::from([
                ("Row".into(), Tag::Int(i32::from(row))),
                ("Value".into(), Tag::Int(value)),
            ])),
        ),
    ]))
}

fn paste_diode(game: &mut Game<'_>, pos: [i32; 3], values: &Compound) -> bool {
    let mut applied = false;
    if let Some(timing) = compound(values, "Timings")
        && let (Some(row), Some(value)) = (int(timing, "Row"), int(timing, "Value"))
    {
        diode::set_pulse_interval(
            game,
            pos,
            match row {
                0 => 0,
                1 => 1,
                _ => 2,
            },
            value,
        );
        applied = true;
    }
    if let Some(block) = compound(values, "Block")
        && let Some(inverted) = int(block, "Inverted")
    {
        game.native_set_block_property_with(
            pos,
            "inverted",
            if inverted != 0 { "true" } else { "false" },
            flags::UPDATE_ALL,
        );
        applied = true;
    }
    applied
}

fn message(game: &mut Game<'_>, key: &str, block: &str) {
    if let Some(player) = game.native_acting_player() {
        let name = block.replace(':', ".");
        let name = Text::translate(&format!("block.{name}"), &[]);
        game.native_action_bar(player.uuid, Text::translate(key, &[name]));
    }
}

pub(super) fn interact(game: &mut Game<'_>, pos: [i32; 3], paste: bool) -> bool {
    if !game.native_authoritative()
        || game.hand != Hand::Main
        || game.native_sneaking()
        || game.spectator()
    {
        return false;
    }
    let Some(mut held) = game
        .held()
        .filter(|stack| stack.item.as_ref() == ITEM)
        .cloned()
    else {
        return false;
    };
    let block = game.native_block(pos);
    let Some(mut target) = content(game, &held) else {
        return false;
    };
    let key = if block == ITEM {
        let Some(source) = board::stack_at(game, pos).and_then(|stack| content(game, &stack))
        else {
            return false;
        };
        copy_board(&mut target, &source);
        "create.clipboard.copied_from_clipboard"
    } else if block == CONTROLLER {
        if paste {
            let Some(settings) =
                compound(&target, "copied_values").and_then(|values| compound(values, "Speed"))
            else {
                return false;
            };
            let (Some(row), Some(value)) = (int(settings, "Row"), int(settings, "Value")) else {
                return true;
            };
            create_speed_controller_controls::apply_clipboard_setting(
                game,
                pos,
                ValueBlock::Controller,
                Selection {
                    row: u8::from(row != 0),
                    value,
                },
            );
            message(game, "create.clipboard.pasted_to", &block);
            return true;
        }
        let selection = ValueBlock::Controller.selection(game, pos);
        target.insert("type".into(), Tag::String("written".into()));
        target.insert(
            "copied_values".into(),
            Tag::Compound(Compound::from([(
                "Speed".into(),
                Tag::Compound(Compound::from([
                    ("Row".into(), Tag::Int(i32::from(selection.row))),
                    ("Value".into(), Tag::Int(selection.value)),
                ])),
            )])),
        );
        "create.clipboard.copied_from"
    } else if diode::is_pulse(&block) {
        if paste {
            let Some(values) = compound(&target, "copied_values") else {
                return false;
            };
            if paste_diode(game, pos, values) {
                message(game, "create.clipboard.pasted_to", &block);
            }
            return true;
        }
        target.insert("type".into(), Tag::String("written".into()));
        target.insert("copied_values".into(), diode_values(game, pos, &block));
        "create.clipboard.copied_from"
    } else if block == link::LINK {
        if paste {
            let Some(values) = compound(&target, "copied_values") else {
                return false;
            };
            if let Some(frequencies) = compound(values, "Frequencies")
                && link::paste_clipboard_frequencies(game, pos, frequencies)
            {
                message(game, "create.clipboard.pasted_to", &block);
            }
            return true;
        }
        let Some(frequencies) = link::clipboard_frequencies(game, pos) else {
            return false;
        };
        target.insert("type".into(), Tag::String("written".into()));
        target.insert(
            "copied_values".into(),
            Tag::Compound(Compound::from([("Frequencies".into(), frequencies)])),
        );
        "create.clipboard.copied_from"
    } else if matches!(
        block.as_str(),
        super::create_machines::CHUTE
            | super::create_funnel::BRASS
            | super::create_belt_funnel::BRASS
    ) {
        if paste {
            let Some(values) = compound(&target, "copied_values") else {
                return false;
            };
            if let Some(filter) = compound(values, "Filtering")
                && filter::paste(game, pos, filter)
            {
                message(game, "create.clipboard.pasted_to", &block);
            }
            return true;
        }
        let Some(filter) = filter::capture(game, pos) else {
            return false;
        };
        target.insert("type".into(), Tag::String("written".into()));
        target.insert(
            "copied_values".into(),
            Tag::Compound(Compound::from([(
                "Filtering".into(),
                Tag::Compound(filter),
            )])),
        );
        "create.clipboard.copied_from"
    } else {
        return false;
    };
    if game
        .native_set_component(&mut held, COMPONENT, Tag::Compound(target))
        .is_ok()
    {
        *game.held_mut() = Some(held);
        game.guest_inventory_resend |= game.lan_acting.is_some();
        message(game, key, &block);
    }
    true
}

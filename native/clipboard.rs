use horizon_client::mod_api::StackView;
use horizon_client::text::Text;
use horizon_world::nbt::{Compound, Tag};

use super::Game;
use super::create_package_address::is_blank;

pub(super) const ITEM: &str = "create:clipboard";
pub(super) const COMPONENT: &str = "create:clipboard_content";

pub(super) fn content(game: &Game<'_>, stack: &crate::items::ItemStack) -> Option<Compound> {
    match game.native_component(stack, COMPONENT) {
        Ok(Some(Tag::Compound(data))) => Some(data.clone()),
        Ok(None) => Some(Compound::from([
            ("pages".into(), Tag::List(Vec::new())),
            ("previously_opened_page".into(), Tag::Int(0)),
            ("read_only".into(), Tag::Byte(0)),
            ("type".into(), Tag::String("empty".into())),
        ])),
        _ => None,
    }
}

fn append_address(content: &mut Compound, address: &str) -> bool {
    if is_blank(address) {
        return false;
    }
    let plain = format!("#{address}");
    let spaced = format!("# {address}");
    let Tag::List(pages) = content
        .entry("pages".into())
        .or_insert_with(|| Tag::List(Vec::new()))
    else {
        return false;
    };
    let already_written = pages.iter().any(|page| {
        let Tag::List(entries) = page else {
            return false;
        };
        entries.iter().any(|entry| {
            let Tag::Compound(entry) = entry else {
                return false;
            };
            entry.get(&"text".into()).is_some_and(|text| {
                let text = horizon_protocol::text::plain(text, &Default::default());
                text == plain || text == spaced
            })
        })
    });
    if already_written {
        return false;
    }

    let available = pages
        .iter()
        .position(|page| matches!(page, Tag::List(entries) if entries.len() < 12));
    let page = available.unwrap_or_else(|| {
        pages.push(Tag::List(Vec::new()));
        pages.len() - 1
    });
    let Tag::List(entries) = &mut pages[page] else {
        return false;
    };
    entries.push(Tag::Compound(Compound::from([
        ("checked".into(), Tag::Byte(0)),
        ("text".into(), Tag::String(plain.as_str().into())),
        ("icon".into(), Tag::Compound(Compound::new())),
        ("item_amount".into(), Tag::Int(0)),
    ])));
    content.insert("type".into(), Tag::String("written".into()));
    true
}

pub(super) fn copy_address(game: &mut Game<'_>, address: &str) {
    let Some(mut stack) = game.held().cloned() else {
        return;
    };
    let mut content = match game.native_component(&stack, COMPONENT) {
        Ok(Some(Tag::Compound(content))) => content.clone(),
        Ok(None) => Compound::from([
            ("read_only".into(), Tag::Byte(0)),
            ("previously_opened_page".into(), Tag::Int(0)),
        ]),
        _ => return,
    };
    if !append_address(&mut content, address)
        || game
            .native_set_component(&mut stack, COMPONENT, Tag::Compound(content))
            .is_err()
    {
        return;
    }
    *game.held_mut() = Some(stack);
    game.guest_inventory_resend |= game.lan_acting.is_some();
    if let Some(player) = game.native_acting_player() {
        game.native_action_bar(
            player.uuid,
            Text::translate("create.clipboard.address_added", &[Text::literal(address)]),
        );
    }
}

pub(super) fn model(property: &str, stack: &StackView) -> Option<bool> {
    if stack.item != ITEM {
        return None;
    }
    let mode = match property {
        "create:clipboard_written" => "written",
        "create:clipboard_editing" => "editing",
        _ => return None,
    };
    let matches = stack
        .patch
        .get(COMPONENT)
        .and_then(Option::as_ref)
        .and_then(|content| content.get("type"))
        .and_then(serde_json::Value::as_str)
        == Some(mode);
    if std::env::var_os("CREATE_CLIPBOARD_MODEL").is_some() {
        println!("CREATE_CLIPBOARD_MODEL {mode},{matches}");
    }
    Some(matches)
}

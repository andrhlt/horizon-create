use crate::{
    containers::{BlockEntity, ModBlockEntity, ModBlockEntityFields},
    items::ItemStack,
};
use horizon_client::hud::HudBatch;
use horizon_world::nbt::Tag;

use super::Game;

pub(super) const BLOCK: &str = "create:schematic_table";
const LOAD: i32 = 0;
const BUTTON: [f32; 4] = [44.0, 56.0, 18.0, 18.0];

pub(super) fn open(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.hand != super::Hand::Main || game.native_sneaking() || game.native_block(pos) != BLOCK {
        return false;
    }
    let key = (pos[0], pos[1], pos[2]);
    game.world.block_entities.get_or_insert_with(key, || {
        BlockEntity::for_block(BLOCK).unwrap_or_else(|| {
            BlockEntity::Mod(Box::new(ModBlockEntity::new(ModBlockEntityFields {
                id: BLOCK.to_owned(),
                ..Default::default()
            })))
        })
    });
    game.open_menu(pos);
    true
}

pub(super) fn layout() -> crate::mod_api::NativeScreen {
    crate::mod_api::NativeScreen {
        width: 214.0,
        height: 194.0,
        slots: vec![Some([21.0, 59.0]), Some([166.0, 59.0])],
        inventory_x: 19.0,
        inventory_y: 89.0,
        own_labels: true,
        own_background: true,
    }
}

pub(super) fn screen_click(at: [f32; 2]) -> Option<i32> {
    let [x, y] = at;
    (BUTTON[0]..BUTTON[0] + BUTTON[2])
        .contains(&x)
        .then_some(())?;
    (BUTTON[1]..BUTTON[1] + BUTTON[3])
        .contains(&y)
        .then_some(())?;
    Some(LOAD)
}

pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch, origin: [f32; 2]) {
    let [x, y] = origin;
    game.native_sprite(
        batch,
        "create:gui/schematics",
        [10.0, 139.0, 214.0, 85.0],
        [x, y, 214.0, 85.0],
    );
    if let Some(title) = game.native_screen_title() {
        game.native_text(batch, &title, [x + 72.0, y + 4.0], 0x505050, false);
    }
    // The loaded template is validated again on the server when the button is
    // clicked; the client-side screen may not have the server's template map.
    let enabled = true;
    let button = [x + BUTTON[0], y + BUTTON[1], BUTTON[2], BUTTON[3]];
    let [cursor_x, cursor_y] = game.native_cursor();
    let hovered = (button[0]..button[0] + button[2]).contains(&cursor_x)
        && (button[1]..button[1] + button[3]).contains(&cursor_y);
    horizon_client::widgets::record("Load Template", button, enabled);
    game.native_sprite(
        batch,
        "create:gui/widgets",
        [if hovered { 18.0 } else { 0.0 }, 0.0, 18.0, 18.0],
        button,
    );
    game.native_sprite(
        batch,
        "create:gui/icons",
        [0.0, 16.0, 16.0, 16.0],
        [button[0] + 1.0, button[1] + 1.0, 16.0, 16.0],
    );
}

pub(super) fn menu_button(
    game: &mut Game<'_>,
    pos: [i32; 3],
    entity: &mut ModBlockEntity,
    button: i32,
) {
    if button != LOAD || entity.id != BLOCK {
        return;
    }
    let Some(Some(input)) = entity.items.first().cloned() else {
        return;
    };
    let valid_template = input
        .custom_data()
        .and_then(|data| data.get(&"Template".into()))
        .and_then(|tag| match tag {
            Tag::String(name) => Some(name.to_string_lossy()),
            _ => None,
        })
        .is_some_and(|name| super::create_schematicannon::valid_template_id(&name));
    if input.item.as_ref() != "create:schematic"
        || !valid_template
        || entity.items.get(1).is_none_or(Option::is_some)
    {
        return;
    }
    entity.items.resize(2, None);
    entity.items[0] = None;
    entity.items[1] = Some(input);
    game.native_block_entity_sync(pos);
}

pub(super) fn accepts(entity: &ModBlockEntity, slot: usize, stack: &ItemStack) -> bool {
    entity.id == BLOCK
        && slot == 0
        && matches!(
            stack.item.as_ref(),
            "create:empty_schematic" | "create:schematic_and_quill" | "create:schematic"
        )
}

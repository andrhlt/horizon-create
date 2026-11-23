//! Creative Motor's server-authoritative board/menu bridge.

use mod_api::{
    BlockEntityPart, BlockPart, InteractionResult, LevelRef, MenuReplace, ServerHost, Text,
    UseWithoutItemEvent,
};

use crate::kinetic_adapter;

const MENU_ID: &str = "create:creative_motor";

pub fn setting_from_button(id: i32) -> i32 {
    (id - 256).clamp(-256, 256)
}

#[derive(Clone, Copy, Default)]
pub struct MotorBoard;

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let kind = registrar.block_entity_type_key("create:motor");
    registrar
        .block_entity_part(&kind, MotorBoard)
        .expect("creative motor board part registration");
}

pub fn open_with_menu(
    host: &mut dyn ServerHost,
    click: &mod_api::BlockClick<'_>,
    menu: mod_api::MenuKey,
) -> Option<InteractionResult> {
    if click.hand != mod_api::client::first_person::Hand::Main {
        return None;
    }
    let player = host.player(click.player)?;
    let opened = player
        .open_mod_menu(
            host,
            menu,
            Text::literal("Creative Motor"),
            Vec::new(),
            Some(click.pos),
            MenuReplace::InPlace,
        )
        .ok()?
        .is_some();
    opened.then_some(InteractionResult::SuccessServer)
}

#[mod_api::horizon_part]
impl BlockPart for MotorBoard {
    fn use_without_item(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseWithoutItemEvent<'_>,
    ) -> Option<InteractionResult> {
        if host.block_key(MENU_ID) != Some(event.state.block()) {
            return None;
        }
        let _ = host;
        let _ = event;
        None
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for MotorBoard {
    fn menu_button(&self, host: &mut dyn ServerHost, event: &mut mod_api::MenuButtonEvent<'_>) {
        let Some(player) = host.player(event.context.player) else {
            return;
        };
        let Some(level): Option<LevelRef> = player.entity().level(host) else {
            return;
        };
        let setting = setting_from_button(event.context.id);
        let _ = kinetic_adapter::set_motor_setting(host, level, event.context.pos, setting);
    }
}

#[cfg(test)]
mod tests {
    use super::setting_from_button;

    #[test]
    fn button_mapping_preserves_signed_detents() {
        assert_eq!(setting_from_button(0), -256);
        assert_eq!(setting_from_button(232), -24);
        assert_eq!(setting_from_button(256), 0);
        assert_eq!(setting_from_button(320), 64);
        assert_eq!(setting_from_button(512), 256);
        assert_eq!(setting_from_button(999), 256);
    }
}

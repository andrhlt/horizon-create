//! Creative Motor's server-authoritative board/menu bridge.
//!
//! The adapter deliberately keeps the player identity and level from the
//! interaction event all the way to the shared kinetic setter.  That makes
//! LAN guests and non-overworld dimensions use the same path as the host.

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

fn menu_key(host: &dyn ServerHost) -> Option<mod_api::MenuKey> {
    let keys = host.menu_keys();
    let found = keys
        .into_iter()
        .find(|key| mod_api::__private::menu_key_id(*key).as_deref() == Some(MENU_ID));
    if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
        eprintln!("CREATE_MOTOR_BOARD_MENU key={}", found.is_some());
    }
    found
}

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let kind = registrar.block_entity_type_key("create:motor");
    registrar
        .block_entity_part(&kind, MotorBoard)
        .expect("creative motor board part registration");
}

/// Open the board with a menu key resolved from the pinned host registry.
pub fn open_with_menu(
    host: &mut dyn ServerHost,
    click: &mod_api::BlockClick<'_>,
    menu: mod_api::MenuKey,
) -> Option<InteractionResult> {
    if click.hand != mod_api::client::first_person::Hand::Main {
        return None;
    }
    let player = host.player(click.player)?;
    let result = match player.open_mod_menu(
        host,
        menu,
        Text::literal("Creative Motor"),
        Vec::new(),
        Some(click.pos),
        MenuReplace::InPlace,
    ) {
        Ok(result) => result,
        Err(error) => {
            if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
                eprintln!("CREATE_MOTOR_BOARD_OPEN error={error:?}");
            }
            return None;
        }
    };
    if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
        eprintln!("CREATE_MOTOR_BOARD_OPEN result={result:?}");
    }
    let opened = result.is_some();
    opened.then_some(InteractionResult::SuccessServer)
}

#[mod_api::horizon_part]
impl BlockPart for MotorBoard {
    fn use_without_item(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseWithoutItemEvent<'_>,
    ) -> Option<InteractionResult> {
        if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
            eprintln!(
                "CREATE_MOTOR_BOARD_USE pos={:?} block={:?} expected={MENU_ID}",
                event.click.pos,
                host.block_key(MENU_ID),
            );
        }
        if host.block_key(MENU_ID) != Some(event.state.block()) {
            return None;
        }
        // Resolve by canonical menu id, keeping the opaque key out of content
        // code and preserving the normal main-hand interaction contract.
        let menu = menu_key(host)?;
        open_with_menu(host, &event.click, menu)
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
        // Button ids are the signed board value shifted into the menu's
        // non-negative protocol range. The shared adapter clamps again.
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

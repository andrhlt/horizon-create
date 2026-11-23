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
        let menu = menu_key(host)?;
        open_with_menu(host, &event.click, menu)
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for MotorBoard {
    fn screen(
        &self,
        _host: &dyn mod_api::Host,
        event: &mut mod_api::ScreenEvent<'_>,
    ) -> Option<mod_api::Screen> {
        (event.block == "create:creative_motor").then(|| mod_api::Screen {
            width: 334.0,
            height: 166.0,
            slots: vec![Some([8.0, 84.0])],
            inventory_y: 80.0,
            inventory_x: 8.0,
            own_labels: true,
            own_background: true,
            ..Default::default()
        })
    }

    fn screen_draw(
        &self,
        _host: &dyn mod_api::ClientHost,
        event: &mut mod_api::ScreenDrawEvent<'_>,
    ) {
        if event.block != "create:creative_motor" {
            return;
        }
        const ROWS: [&str; 2] = ["Counterclockwise RPM", "Clockwise RPM"];
        for (row, label) in ROWS.into_iter().enumerate() {
            let y = event.origin[1] + 19.0 + row as f32 * 11.0;
            let _ = event.draw.widget_button(
                [event.origin[0] + 25.0, y, 294.0, 11.0],
                &mod_api::Text::literal(label),
                true,
                false,
            );
        }
    }

    fn screen_click(
        &self,
        _host: &dyn mod_api::ClientHost,
        event: &mut mod_api::ScreenClickEvent<'_>,
    ) -> Option<i32> {
        if event.block != "create:creative_motor" || event.right {
            return None;
        }
        let [x, y] = event.at;
        let row = (0..2).find(|row| {
            let top = 19.0 + *row as f32 * 11.0;
            (top..top + 11.0).contains(&y) && (25.0..319.0).contains(&x)
        })?;
        let value = (0i32..=256i32)
            .min_by_key(|value| {
                let milestone = (*value).saturating_sub(1) / 32 * 4;
                let marker = 25
                    + milestone
                    + *value
                    + 1
                    + i32::from(*value % 32 == 0) * 2
                    + i32::from(*value > 0) * 4;
                (marker as f32 - x).abs().to_bits()
            })
            .unwrap_or(0);
        Some(if row == 0 { 256 - value } else { 256 + value })
    }

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

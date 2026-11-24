//! Creative Motor's server-authoritative board/menu bridge.
//!
//! The adapter deliberately keeps the player identity and level from the
//! interaction event all the way to the shared kinetic setter.  That makes
//! LAN guests and non-overworld dimensions use the same path as the host.

use std::collections::VecDeque;
use std::sync::atomic::{AtomicU64, Ordering};
use std::sync::{Mutex, OnceLock};

use mod_api::{
    BlockEntityPart, BlockPart, InteractionResult, LevelRef, MenuReplace, ServerHost, Text,
    UseWithoutItemEvent,
};

use super::kinetic_adapter;

const MENU_ID: &str = "create:creative_motor";
const MOTOR_SETTING_TASK_PREFIX: u64 = 0x4352_4541_5400_0000;
static NEXT_MOTOR_SETTING_TASK: AtomicU64 = AtomicU64::new(MOTOR_SETTING_TASK_PREFIX);

struct PendingSetting {
    token: u64,
    dimension: String,
    pos: [i32; 3],
    setting: i32,
}

static PENDING_SETTINGS: OnceLock<Mutex<VecDeque<PendingSetting>>> = OnceLock::new();

fn pending_settings() -> &'static Mutex<VecDeque<PendingSetting>> {
    PENDING_SETTINGS.get_or_init(|| Mutex::new(VecDeque::new()))
}

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
    let block = registrar.block_key(MENU_ID);
    registrar.block_container(
        &block,
        mod_api::ModContainer {
            slots: 1,
            faces: std::array::from_fn(|_| vec![0]),
            inputs: vec![0],
            outputs: vec![0],
            menu: Some(MENU_ID.to_owned()),
        },
    );
    registrar
        .block_entity_part(&kind, MotorBoard)
        .expect("creative motor board part registration");
}

/// Open the board after resolving its content menu key from the host registry.
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
    fn screen(
        &self,
        _host: &dyn mod_api::Host,
        event: &mut mod_api::ScreenEvent<'_>,
    ) -> Option<mod_api::Screen> {
        (event.block == MENU_ID).then(|| mod_api::Screen {
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
        if event.block != MENU_ID {
            return;
        }
        const ROWS: [&str; 2] = ["Counterclockwise RPM", "Clockwise RPM"];
        for (row, label) in ROWS.into_iter().enumerate() {
            let y = event.origin[1] + 19.0 + row as f32 * 11.0;
            let _ = event.draw.widget_button(
                [event.origin[0] + 25.0, y, 294.0, 11.0],
                &Text::literal(label),
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
        if event.block != MENU_ID {
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
        // Button ids are the signed board value shifted into the menu's
        // non-negative protocol range. The shared adapter clamps again.
        let setting = setting_from_button(event.context.id);
        if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
            let _ = host.messages().broadcast(Text::literal(format!(
                "CREATE_MOTOR_BOARD_MENU_BUTTON_QUEUED pos={:?} setting={setting}",
                event.context.pos
            )));
        }
        let Some(dimension) = level.dimension().id(host) else {
            return;
        };
        let token = NEXT_MOTOR_SETTING_TASK.fetch_add(1, Ordering::Relaxed);
        pending_settings()
            .lock()
            .expect("motor setting queue")
            .push_back(PendingSetting {
                token,
                dimension: dimension.to_string(),
                pos: event.context.pos,
                setting,
            });
        let scheduled = host.schedule_task(0, token).is_ok();
        if !scheduled {
            pending_settings()
                .lock()
                .expect("motor setting queue")
                .retain(|item| item.token != token);
        }
        if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
            let _ = host.messages().broadcast(Text::literal(format!(
                "CREATE_MOTOR_BOARD_SETTING_SCHEDULED scheduled={scheduled}"
            )));
        }
    }
}

pub fn scheduled_task(host: &mut dyn ServerHost, event: &mut mod_api::ScheduledTaskEvent<'_>) {
    if event.token & 0xffff_ffff_ffff_0000 != MOTOR_SETTING_TASK_PREFIX {
        return;
    }
    let request = {
        let mut pending = pending_settings().lock().expect("motor setting queue");
        pending
            .iter()
            .position(|item| item.token == event.token)
            .and_then(|index| pending.remove(index))
    };
    let Some(request) = request else {
        return;
    };
    let Some(level) = host.level(&request.dimension) else {
        return;
    };
    let updated = kinetic_adapter::set_motor_setting(host, level, request.pos, request.setting);
    if std::env::var_os("CREATE_MOTOR_BOARD_TRACE").is_some() {
        let _ = host.messages().broadcast(Text::literal(format!(
            "CREATE_MOTOR_BOARD_SETTING_APPLIED pos={:?} setting={} updated={updated}",
            request.pos, request.setting
        )));
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

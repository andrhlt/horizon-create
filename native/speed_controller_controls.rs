use std::cell::RefCell;
use std::sync::OnceLock;

use horizon_client::hud::HudBatch;
use horizon_client::keybinds;
use horizon_client::mod_api::NativeScreenView;
use serde::{Deserialize, Serialize};
use winit::dpi::PhysicalPosition;
use winit::event::MouseButton;
use winit::keyboard::KeyCode;

use super::Game;
use super::create_bearing::{self, WINDMILL};
use super::create_chassis_range;
use super::create_clockwork::{self, CLOCKWORK};
use super::create_ejector::{self, EJECTOR};
use super::create_latches;
use super::create_mechanical_piston;
use super::create_linear_chassis::{self, RADIAL_CHASSIS};
use super::create_machines::{axis_index, mod_entity};
use super::create_speed_controller::{self, CONTROLLER, ValueBoard};
use super::create_valve;
use super::create_windmill_settings::{self, IconBoard};

const SPEED_SCREEN: &str = "create:rotation_speed_controller";
const CHASSIS_SCREEN: &str = "create:chassis_range";
const WINDMILL_SCREEN: &str = "create:windmill_direction";
const CLOCKWORK_SCREEN: &str = "create:clockwork_arrangement";
const PISTON_SCREEN: &str = "create:mechanical_piston_movement_mode";
const VALVE_SCREEN: &str = "create:valve_handle_angle";
const EJECTOR_SCREEN: &str = "create:ejector_stack_size";
const PULSE_SCREEN: &str = "create:brass_diode_interval";
const CHANNEL: &str = "create:speed_controller";
const HOLD_TICKS: u8 = 6;

#[derive(Clone, Copy, Eq, PartialEq, Serialize, Deserialize)]
pub(super) enum ValueBlock {
    Controller,
    Motor,
    LinearChassis,
    RadialChassis,
    Windmill,
    Clockwork,
    Piston,
    Valve,
    Ejector,
    PulseDiode,
}

impl ValueBlock {
    fn at(game: &Game<'_>, pos: [i32; 3]) -> Option<Self> {
        match game.native_block(pos).as_str() {
            CONTROLLER => Some(Self::Controller),
            EJECTOR => Some(Self::Ejector),
            name if create_latches::is_pulse(name) => Some(Self::PulseDiode),
            "create:creative_motor" => Some(Self::Motor),
            name if create_valve::is_handle(name) => Some(Self::Valve),
            WINDMILL => Some(Self::Windmill),
            CLOCKWORK => Some(Self::Clockwork),
            create_mechanical_piston::PISTON | create_mechanical_piston::STICKY => Some(Self::Piston),
            RADIAL_CHASSIS => Some(Self::RadialChassis),
            name if create_linear_chassis::linear(name) => Some(Self::LinearChassis),
            _ => None,
        }
    }

    fn chassis(self) -> bool {
        matches!(self, Self::LinearChassis | Self::RadialChassis)
    }

    fn icon_board(self) -> Option<IconBoard> {
        match self {
            Self::Windmill => Some(IconBoard::Windmill),
            Self::Clockwork => Some(IconBoard::Clockwork),
            Self::Piston => Some(IconBoard::Piston),
            _ => None,
        }
    }

    fn value_board(self) -> ValueBoard {
        match self {
            Self::Valve => ValueBoard::Angle,
            Self::Ejector => ValueBoard::StackSize,
            Self::PulseDiode => ValueBoard::Interval,
            _ => ValueBoard::Speed,
        }
    }

    fn rows(self) -> u8 {
        match self {
            Self::PulseDiode => 3,
            Self::Controller | Self::Motor | Self::Valve => 2,
            _ => 1,
        }
    }

    pub(super) fn speed_entity(self) -> Option<&'static str> {
        match self {
            Self::Controller => Some(CONTROLLER),
            Self::Motor => Some("create:motor"),
            _ => None,
        }
    }

    fn has_short_action(self) -> bool {
        matches!(self, Self::Valve | Self::PulseDiode)
    }

    fn title(self) -> &'static str {
        match self {
            Self::Controller => "Targeted Speed in RPM",
            Self::Motor => "Generated Speed in RPM",
            Self::Valve => create_valve::ANGLE_TITLE,
            Self::Ejector => "Ejected Stack Size",
            Self::PulseDiode => "Redstone Interval",
            Self::Windmill => create_windmill_settings::TITLE,
            Self::Clockwork => "Clock Hand Arrangement",
            Self::Piston => "Movement Mode",
            Self::LinearChassis => "Range of Sticky Sides",
            Self::RadialChassis => "Radius when Sticky",
        }
    }

    fn screen(self) -> &'static str {
        match self {
            Self::Windmill => WINDMILL_SCREEN,
            Self::Valve => VALVE_SCREEN,
            Self::Ejector => EJECTOR_SCREEN,
            Self::PulseDiode => PULSE_SCREEN,
            Self::Clockwork => CLOCKWORK_SCREEN,
            Self::Piston => PISTON_SCREEN,
            Self::LinearChassis | Self::RadialChassis => CHASSIS_SCREEN,
            Self::Controller | Self::Motor => SPEED_SCREEN,
        }
    }

    fn maximum(self) -> i32 {
        match self {
            Self::Windmill => IconBoard::Windmill.maximum(),
            Self::Clockwork => IconBoard::Clockwork.maximum(),
            Self::Piston => IconBoard::Piston.maximum(),
            Self::LinearChassis | Self::RadialChassis => create_chassis_range::MAX - 1,
            Self::Controller | Self::Motor | Self::Valve | Self::Ejector | Self::PulseDiode => {
                self.value_board().maximum()
            }
        }
    }

    fn selection(self, game: &Game<'_>, pos: [i32; 3]) -> Selection {
        if let Some(board) = self.icon_board() {
            let value = mod_entity(game, pos)
                .and_then(|entity| super::create_machines::int(&entity.nbt, "ScrollValue"))
                .unwrap_or(0)
                .clamp(0, board.maximum());
            return Selection { row: 0, value };
        }
        if self.chassis() {
            return Selection {
                row: 0,
                value: create_chassis_range::value(game, pos) - 1,
            };
        }
        let entity = mod_entity(game, pos);
        if self == Self::PulseDiode {
            let (row, value) = create_latches::pulse_selection(entity, &game.native_block(pos));
            return Selection { row, value };
        }
        if self == Self::Ejector {
            return Selection {
                row: 0,
                value: create_ejector::stack_size(entity),
            };
        }
        let current = if self == Self::Valve {
            create_valve::setting(entity)
        } else {
            create_speed_controller::target(entity) as i32
        };
        Selection {
            row: u8::from(current >= 0),
            value: current.abs(),
        }
    }

    fn apply(self, game: &mut Game<'_>, setting: Setting) {
        let at = setting.target.pos;
        if self == Self::Windmill {
            create_bearing::windmill_setting(game, at, setting.selection.value);
        } else if self == Self::Clockwork {
            create_clockwork::set_mode(game, at, setting.selection.value);
        } else if self == Self::Piston {
            create_mechanical_piston::set_mode(game, at, setting.selection.value);
        } else if self == Self::Valve {
            if setting.short {
                create_valve::click(game, at, &mut false);
            } else {
                create_valve::set_angle(game, at, setting.selection);
            }
        } else if self == Self::PulseDiode {
            if setting.short {
                create_latches::pulse_short_action(game, at);
            } else {
                create_latches::set_pulse_interval(
                    game,
                    at,
                    setting.selection.row,
                    setting.selection.value,
                );
            }
        } else if self == Self::Ejector {
            create_ejector::set_stack_size(game, at, setting.selection.value);
        } else if self.chassis() {
            create_chassis_range::set(game, at, setting.selection.value, setting.bulk);
        } else {
            create_speed_controller::set_value(game, at, self, setting.selection);
        }
    }

    fn box_center(self, game: &Game<'_>, pos: [i32; 3], side: [i32; 3]) -> Option<[f64; 3]> {
        match self {
            Self::Controller => {
                let axis = game.native_block_property(pos, "axis")?;
                if side[1] != 0 || side[axis_index(&axis)?] != 0 {
                    return None;
                }
                Some([
                    0.5 + f64::from(side[0]) * 0.46875,
                    0.6875,
                    0.5 + f64::from(side[2]) * 0.46875,
                ])
            }
            Self::Motor => {
                let facing = game.native_block_property(pos, "facing")?;
                let direction = super::machines::dir_from_name(&facing)?.normal();
                let same_axis = direction
                    .iter()
                    .zip(side)
                    .any(|(&facing, side)| facing * side != 0);
                if same_axis || direction[1] == 0 && side[1] < 0 {
                    return None;
                }
                Some(std::array::from_fn(|i| {
                    0.5 + f64::from(side[i]) * 0.28125 - f64::from(direction[i]) / 16.0
                }))
            }
            Self::Valve => create_valve::box_center(game, pos, side),
            Self::Ejector => create_ejector::stack_box(game, pos, side),
            Self::PulseDiode => (side == [0, 1, 0]
                && !game
                    .stack_in(game.selected)
                    .is_some_and(|stack| stack.item.as_ref() == "create:wrench"))
            .then_some([0.5, 2.6 / 16.0, 0.5]),
            Self::Piston => {
                let facing = game.native_block_property(pos, "facing")?;
                let direction = super::machines::dir_from_name(&facing)?.normal();
                let extension = super::create_machines::facing_axis(&facing)?;
                let first = game.native_block_property(pos, "axis_along_first")? == "true";
                let shaft = super::create_machines::gauge_axis(&facing, first)?;
                if side[extension] != 0 || side[shaft] != 0 { return None; }
                Some(std::array::from_fn(|i| 0.5 + f64::from(side[i]) * 0.46875 - f64::from(direction[i]) / 8.0))
            }
            Self::Windmill | Self::Clockwork => {
                let facing = game.native_block_property(pos, "facing")?;
                let direction = super::machines::dir_from_name(&facing)?.normal();
                if direction
                    .iter()
                    .zip(side)
                    .any(|(&axis, side)| axis * side != 0)
                {
                    return None;
                }
                Some(std::array::from_fn(|i| {
                    0.5 + f64::from(side[i]) * 0.46875 - f64::from(direction[i]) / 8.0
                }))
            }
            Self::LinearChassis | Self::RadialChassis => create_chassis_range::has_wrench(game)
                .then(|| side.map(|component| 0.5 + f64::from(component) * 0.46875)),
        }
    }
}

#[derive(Clone, Copy, Eq, PartialEq, Serialize, Deserialize)]
struct Target {
    pos: [i32; 3],
    block: ValueBlock,
}

#[derive(Clone, Copy)]
struct Holding {
    target: Target,
    ticks: u8,
}

#[derive(Clone, Copy, Eq, PartialEq, Serialize, Deserialize)]
pub(super) struct Selection {
    pub(crate) row: u8,
    pub(crate) value: i32,
}

#[derive(Clone, Copy, Serialize, Deserialize)]
struct Setting {
    target: Target,
    selection: Selection,
    #[serde(default)]
    bulk: bool,
    #[serde(default, skip_serializing_if = "std::ops::Not::not")]
    short: bool,
}

struct Board {
    target: Target,
    last: Selection,
    submit: Option<Setting>,
}

#[derive(Default)]
struct Client {
    hold: Option<Holding>,
    board: Option<Board>,
}

thread_local! {
    static CLIENT: RefCell<Client> = RefCell::new(Client::default());
}

fn trace(game: &Game<'_>, event: &str, target: Target) {
    static SPEED_TRACE: OnceLock<bool> = OnceLock::new();
    static CHASSIS_TRACE: OnceLock<bool> = OnceLock::new();
    let prefix = if target.block.chassis() {
        CHASSIS_TRACE
            .get_or_init(|| std::env::var_os("CREATE_CHASSIS_RANGE_INPUT_TRACE").is_some())
            .then_some("CREATE_CHASSIS_RANGE_INPUT")
    } else {
        SPEED_TRACE
            .get_or_init(|| std::env::var_os("CREATE_SPEED_CONTROLLER_INPUT_TRACE").is_some())
            .then_some("CREATE_SPEED_CONTROLLER_INPUT")
    };
    if let Some(prefix) = prefix {
        let [x, y, z] = target.pos;
        eprintln!("{prefix} {} {event} {x},{y},{z}", game.ticks);
    }
}

fn target(game: &Game<'_>) -> Option<Target> {
    if !game.native_playing()
        || !game.may_build()
        || game.native_sneaking()
        || game
            .stack_in(game.selected)
            .is_some_and(|stack| stack.item.as_ref() == "create:clipboard")
    {
        return None;
    }
    let hit = game.pick()?;
    let block = ValueBlock::at(game, hit.pos)?;
    hits_value_box(game, block, hit.pos, hit.face, hit.point).then_some(Target {
        pos: hit.pos,
        block,
    })
}

fn hits_value_box(
    game: &Game<'_>,
    block: ValueBlock,
    pos: [i32; 3],
    face: [i32; 3],
    point: [f64; 3],
) -> bool {
    let Some(center) = block.box_center(game, pos, face) else {
        return false;
    };
    let distance = point
        .into_iter()
        .zip(pos)
        .zip(center)
        .map(|((point, origin), center)| (point - f64::from(origin) - center).powi(2))
        .sum::<f64>();
    let radius_squared = if block == ValueBlock::Valve {
        1.0 / 9.0
    } else {
        0.0625
    };
    distance < radius_squared
}

pub(super) fn claims_value_box(game: &Game<'_>, pos: [i32; 3]) -> bool {
    target(game).is_some_and(|target| target.pos == pos && target.block != ValueBlock::PulseDiode)
}

pub(super) fn claims_diode_hit(
    game: &Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    point: [f64; 3],
) -> bool {
    game.may_build()
        && !game.native_sneaking()
        && ValueBlock::at(game, pos) == Some(ValueBlock::PulseDiode)
        && hits_value_box(game, ValueBlock::PulseDiode, pos, face, point)
}

fn board_visible(game: &Game<'_>) -> bool {
    matches!(
        game.native_mod_screen(),
        Some(
            SPEED_SCREEN
                | CHASSIS_SCREEN
                | WINDMILL_SCREEN
                | CLOCKWORK_SCREEN
                | PISTON_SCREEN
                | VALVE_SCREEN
                | EJECTOR_SCREEN
                | PULSE_SCREEN
        )
    )
}

pub(super) fn diode_mouse_press(game: &Game<'_>, key: &str, pressed: bool) {
    if key != "key.mouse.right" || !pressed || board_visible(game) {
        return;
    }
    let Some(target) = target(game).filter(|target| target.block == ValueBlock::PulseDiode) else {
        return;
    };
    CLIENT.with_borrow_mut(|client| {
        client.hold = Some(Holding { target, ticks: 0 });
    });
}

pub(super) fn tick(game: &mut Game<'_>) {
    if board_visible(game) {
        board_tick(game);
        return;
    }
    let tracking_release = CLIENT.with_borrow(|client| {
        client
            .hold
            .is_some_and(|hold| hold.target.block.has_short_action())
    });
    let aimed = (game.right || tracking_release)
        .then(|| target(game))
        .flatten();
    let Some(target) = aimed.filter(|_| game.right) else {
        let released = CLIENT.with_borrow_mut(|client| std::mem::take(client).hold);
        if let Some(hold) = released
            && hold.target.block.has_short_action()
            && !game.right
            && aimed == Some(hold.target)
        {
            let setting = Setting {
                target: hold.target,
                selection: Selection { row: 0, value: 0 },
                bulk: false,
                short: true,
            };
            if let Ok(data) = serde_json::to_vec(&setting) {
                let _ = game.native_net_send_to_server(CHANNEL, &data);
            }
            trace(game, "short", hold.target);
        }
        return;
    };
    let count = CLIENT.with_borrow_mut(|client| {
        client.board = None;
        let hold = client.hold.get_or_insert(Holding { target, ticks: 0 });
        if hold.target != target {
            *hold = Holding { target, ticks: 0 };
        }
        hold.ticks = hold.ticks.saturating_add(1);
        hold.ticks
    });
    if count == 1 {
        trace(game, "hold", target);
    }
    if count != HOLD_TICKS || !game.native_mod_screen_open(target.block.screen()) {
        return;
    }
    let selection = target.block.selection(game, target.pos);
    CLIENT.with_borrow_mut(|client| {
        client.hold = None;
        client.board = Some(Board {
            target,
            last: selection,
            submit: None,
        });
    });
    warp(game, target.block, selection);
    trace(game, "open", target);
}

fn viewport(game: &Game<'_>) -> Option<([f32; 4], f32)> {
    let renderer = game.renderer.as_ref()?;
    let batch = HudBatch::new([renderer.config.width, renderer.config.height]);
    Some(([0.0, 0.0, batch.width, batch.height], batch.scale))
}

fn warp(game: &mut Game<'_>, block: ValueBlock, selection: Selection) {
    let Some((rect, scale)) = viewport(game) else {
        return;
    };
    let [x, y] = if let Some(board) = block.icon_board() {
        board.coordinate(rect, selection.value)
    } else if block.chassis() {
        create_chassis_range::coordinate(game, rect, selection.value)
    } else {
        let board = block.value_board();
        let [left, top] = board.panel(game, rect);
        let [x, y] = board.coordinate(game, selection);
        [left + x, top + y]
    };
    game.cursor = (x, y);
    if let Some(window) = game.window.as_ref() {
        let _ = window.set_cursor_position(PhysicalPosition::new(
            f64::from(game.cursor.0 * scale),
            f64::from(game.cursor.1 * scale),
        ));
    }
}

fn at(
    game: &Game<'_>,
    block: ValueBlock,
    rect: [f32; 4],
    mouse: [f32; 2],
    shift: bool,
) -> Selection {
    if let Some(board) = block.icon_board() {
        return board.selection_at(rect, mouse);
    }
    if block.chassis() {
        return create_chassis_range::selection_at(game, rect, mouse);
    }
    let board = block.value_board();
    let [x, y] = board.panel(game, rect);
    board.selection_at(game, [mouse[0] - x, mouse[1] - y], shift)
}

fn shifted(game: &Game<'_>) -> bool {
    game.physical_keys.contains(&KeyCode::ShiftLeft)
        || game.physical_keys.contains(&KeyCode::ShiftRight)
}

fn board_tick(game: &mut Game<'_>) {
    let pending = CLIENT.with_borrow_mut(|client| client.board.as_mut()?.submit.take());
    if let Some(pending) = pending {
        if let Ok(data) = serde_json::to_vec(&pending) {
            let _ = game.native_net_send_to_server(CHANNEL, &data);
        }
        trace(game, "submit", pending.target);
        game.native_mod_screen_close(pending.target.block.screen());
        return;
    }
    let Some((rect, _)) = viewport(game) else {
        return;
    };
    let changed = CLIENT.with_borrow_mut(|client| {
        let board = client.board.as_mut()?;
        let block = board.target.block;
        let selection = at(game, block, rect, game.native_cursor(), shifted(game));
        if block.chassis() {
            super::create_chassis_preview::hover(game, board.target.pos, selection.value + 1);
        }
        if selection == board.last {
            return None;
        }
        board.last = selection;
        Some((selection, block.maximum()))
    });
    if let Some((selection, maximum)) = changed {
        let pitch = 1.15 + selection.value as f32 / maximum as f32 * 0.35;
        game.audio
            .play_on(0, "create:scroll_value", None, 0.25, pitch);
    }
}

pub(super) fn render(game: &Game<'_>, screen: &NativeScreenView<'_>, batch: &mut HudBatch) {
    if board_visible(game)
        && let Some(target) =
            CLIENT.with_borrow(|client| client.board.as_ref().map(|board| board.target))
    {
        let block = target.block;
        let selection = at(game, block, screen.rect, screen.mouse, shifted(game));
        if let Some(board) = block.icon_board() {
            board.draw(game, selection, batch, screen.rect);
        } else if block.chassis() {
            create_chassis_range::draw(game, block.title(), selection, batch, screen.rect);
        } else {
            let title = match block {
                ValueBlock::Valve => {
                    game.translate("create.kinetics.valve_handle.rotated_angle", block.title())
                }
                ValueBlock::Ejector => {
                    game.translate("create.weighted_ejector.stack_size", block.title())
                }
                ValueBlock::PulseDiode => {
                    game.translate("create.logistics.redstone_interval", block.title())
                }
                _ => block.title().to_owned(),
            };
            block
                .value_board()
                .draw_screen(game, &title, selection, batch, screen.rect);
        }
    }
}

fn queue_release(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    modifiers: u32,
    canceled: &mut bool,
) {
    if !board_visible(game) {
        return;
    }
    CLIENT.with_borrow_mut(|client| {
        if let Some(board) = client.board.as_mut() {
            let target = board.target;
            let selection = at(
                game,
                target.block,
                screen.rect,
                screen.mouse,
                modifiers & 1 != 0,
            );
            board.submit = Some(Setting {
                target,
                selection,
                bulk: modifiers & 2 != 0,
                short: false,
            });
            trace(game, "release", target);
        }
    });
    *canceled = true;
}

pub(super) fn mouse_released(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    button: i32,
    modifiers: u32,
    canceled: &mut bool,
) {
    let mouse = match button {
        0 => MouseButton::Left,
        1 => MouseButton::Right,
        2 => MouseButton::Middle,
        3 => MouseButton::Back,
        4 => MouseButton::Forward,
        other => MouseButton::Other(other as u16),
    };
    if game.settings.keys.get("key.use") == keybinds::mouse_name(mouse) {
        queue_release(game, screen, modifiers, canceled);
    }
}

pub(super) fn key_released(
    game: &Game<'_>,
    screen: &NativeScreenView<'_>,
    key: &str,
    modifiers: u32,
    canceled: &mut bool,
) {
    if game.settings.keys.get("key.use") == key {
        queue_release(game, screen, modifiers, canceled);
    }
}

pub(super) fn scroll(
    game: &mut Game<'_>,
    mouse: [f32; 2],
    dy: f64,
    modifiers: u32,
    canceled: &mut bool,
) {
    if !board_visible(game) || dy == 0.0 {
        return;
    }
    let Some((rect, _)) = viewport(game) else {
        return;
    };
    let Some(block) =
        CLIENT.with_borrow(|client| client.board.as_ref().map(|board| board.target.block))
    else {
        return;
    };
    let shift = modifiers & 1 != 0;
    let mut selection = at(game, block, rect, mouse, shift);
    let step = if shift && (block.rows() > 1 || block == ValueBlock::Ejector) {
        block.value_board().milestone()
    } else {
        1
    };
    selection.value = (selection.value + dy.signum() as i32 * step).clamp(0, block.maximum());
    warp(game, block, selection);
    *canceled = true;
}

pub(super) fn receive(game: &mut Game<'_>, uuid: u128, channel: &str, data: &[u8]) {
    if channel != CHANNEL || data.len() > 128 {
        return;
    }
    let Ok(setting) = serde_json::from_slice::<Setting>(data) else {
        return;
    };
    if setting.selection.row >= setting.target.block.rows()
        || setting.short && !setting.target.block.has_short_action()
    {
        return;
    }
    let Some(conn) = game.lan.as_ref().and_then(|host| {
        host.hub
            .guests
            .iter()
            .find(|player| player.uuid == uuid && player.placed && !player.released)
            .map(|player| player.conn)
    }) else {
        return;
    };
    let Target { pos, block } = setting.target;
    game.for_player(super::commands::Target::Guest(conn), |actor| {
        if !actor.may_build()
            || ValueBlock::at(actor, pos) != Some(block)
            || block.chassis() && !create_chassis_range::has_wrench(actor)
        {
            return;
        }
        let Some(eye) = actor.eye_position() else {
            return;
        };
        let distance = eye
            .into_iter()
            .zip(pos)
            .map(|(eye, pos)| {
                let min = f64::from(pos);
                let max = min + 1.0;
                (eye - eye.clamp(min, max)).powi(2)
            })
            .sum::<f64>();
        if distance <= (actor.reach() + 20.0).powi(2) {
            block.apply(actor, setting);
        }
    });
}

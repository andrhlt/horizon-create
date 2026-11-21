use super::{
    Game,
    create_machines::mod_entity,
};
use horizon_client::hud::{HudBatch, rgba};
use horizon_world::nbt::{Compound, Tag};
use std::cell::RefCell;
use std::time::{Duration, Instant};

const CHANNEL: &str = "create:train_feedback";
#[derive(Clone, serde::Serialize, serde::Deserialize)]
struct View {
    name: String,
    speed: f64,
    throttle: f64,
    prompt: String,
}
thread_local! { static VIEW: RefCell<Option<(View, Instant)>> = const { RefCell::new(None) }; }

fn name(game: &Game<'_>, data: &Compound) -> String {
    match data.get(&"Name".into()) {
        Some(Tag::String(name)) => name.to_string_lossy(),
        _ => game.translate("create.train.unnamed", "Unnamed Train"),
    }
}
fn station_name(game: &Game<'_>, pos: [i32; 3]) -> String {
    mod_entity(game, pos)
        .and_then(|entity| match entity.nbt.get(&"Name".into()) {
            Some(Tag::String(name)) => Some(name.to_string_lossy()),
            _ => None,
        })
        .unwrap_or_else(|| "Track Station".into())
}
fn number(data: &Compound, key: &str, default: f64) -> f64 {
    match data.get(&key.into()) {
        Some(Tag::Double(bits)) => f64::from_bits(*bits),
        _ => default,
    }
}
pub(super) fn update(
    game: &mut Game<'_>,
    data: &Compound,
    dock: Option<[i32; 3]>,
    drive: i32,
    space: bool,
) {
    let Some(Tag::IntArray(words)) = data.get(&"Driver".into()) else {
        return;
    };
    if words.len() != 4 {
        return;
    }
    let player = words
        .iter()
        .fold(0_u128, |id, word| (id << 32) | (*word as u32) as u128);
    let prompt = if let Some(station) = dock {
        let (key, fallback) = if drive != 0 {
            ("create.train.departing_from", "Departing from %1$s")
        } else if space {
            ("create.train.arrived_at", "Arrived at %1$s")
        } else {
            ("", "")
        };
        game.translate(key, fallback)
            .replace("%1$s", &station_name(game, station))
    } else if let Some(station) = super::create_train::coords(data, "ApproachStation") {
        format!("Approaching {}", station_name(game, station))
    } else {
        String::new()
    };
    let view = View {
        name: name(game, data),
        speed: number(data, "Speed", 0.0),
        throttle: number(data, "Throttle", 1.0),
        prompt,
    };
    if game.player.is_some() && game.acting_player_uuid() == words.as_slice() {
        VIEW.with_borrow_mut(|state| *state = Some((view, Instant::now())));
    } else if let Ok(bytes) = serde_json::to_vec(&view) {
        let _ = game.native_net_send_to_player(player, CHANNEL, &bytes);
    }
}
pub(super) fn receive(channel: &str, data: &[u8]) {
    if channel == CHANNEL
        && let Ok(view) = serde_json::from_slice(data)
    {
        VIEW.with_borrow_mut(|state| *state = Some((view, Instant::now())));
    }
}
pub(super) fn draw(game: &Game<'_>, batch: &mut HudBatch) {
    if game.spectator() {
        return;
    }
    VIEW.with_borrow(|state| {
        let Some((view, at)) = state else {
            return;
        };
        if at.elapsed() > Duration::from_millis(750) {
            return;
        }
        let lines = [
            view.name.clone(),
            format!(
                "{:.1} m/s   Throttle {:.0}%",
                view.speed.abs() * 20.0,
                view.throttle * 100.0
            ),
            view.prompt.clone(),
        ];
        let width = lines
            .iter()
            .map(|line| game.native_text_width(line))
            .fold(180.0_f32, f32::max);
        let x = (batch.width - width) / 2.0;
        let y = batch.height - 110.0;
        batch.fill(
            &game.gui.atlas,
            x - 4.0,
            y - 4.0,
            width + 8.0,
            36.0,
            rgba(16, 16, 16, 190),
        );
        for (index, line) in lines.iter().enumerate() {
            game.native_text(batch, line, [x, y + index as f32 * 11.0], 0xFFFFFF, true);
        }
        if let Ok(path) = std::env::var("CREATE_TRAIN_HUD_TRACE") {
            use std::io::Write;
            if let Ok(mut file) = std::fs::OpenOptions::new()
                .create(true)
                .append(true)
                .open(path)
            {
                let _ = writeln!(file, "{}", serde_json::to_string(view).unwrap_or_default());
            }
        }
    });
}

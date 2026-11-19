use std::cell::RefCell;

use horizon_client::{keybinds, text::Text};
use horizon_core::geometry::Vec3;

use super::create_chain_conveyor_connect::links;
use super::create_chain_conveyor_ride_motion::{Motion, Rider, Wheel};
use super::create_chain_conveyor_ride_packets::{keepalive, stop};
use super::create_chain_conveyor_span::nearest_span;
use super::create_chain_conveyor_target::loop_target;
use super::create_machines::{CONVEYOR, int, mod_entity, saved_speed};
use super::{Game, Hand};

const RIDEABLE: &str = "create:chain_rideable";
const SOUND: &str = "minecraft:block.chain.hit";

thread_local! {
    static RIDE: RefCell<Option<Rider>> = const { RefCell::new(None) };
}

pub(super) fn rideable_hand(game: &Game<'_>) -> Option<Hand> {
    let items = game.items();
    let items = if game.remote.is_some() && !items.item_tags.contains_key(RIDEABLE) {
        // A LAN host can omit custom item tags from its synced tables.
        game.res.items()
    } else {
        items
    };
    Hand::BOTH.into_iter().find(|hand| {
        let stack = match hand {
            Hand::Main => game.stack_in(game.selected),
            Hand::Off => game.offhand.as_ref(),
        };
        stack.is_some_and(|stack| items.item_in_tag(RIDEABLE, &stack.item))
    })
}

pub(super) fn wheel(game: &Game<'_>, at: [i32; 3]) -> Option<Wheel> {
    let entity = mod_entity(game, at).filter(|entity| entity.id == CONVEYOR)?;
    let rpm = saved_speed(&entity.nbt);
    Some(Wheel {
        rpm,
        reversed: if rpm == 0.0 {
            int(&entity.nbt, "Reversed") == Some(1)
        } else {
            rpm < 0.0
        },
        links: links(&entity.nbt).collect(),
    })
}

pub(super) fn board(game: &mut Game<'_>) -> Option<Hand> {
    if !game.may_build() || game.native_sneaking() {
        return None;
    }
    let hand = rideable_hand(game);
    if std::env::var_os("CREATE_CHAIN_RIDE").is_some() {
        let tag = |items: &horizon_client::items::Items| {
            items.item_tags.get(RIDEABLE).map(|tag| tag.len())
        };
        println!(
            "CREATE_CHAIN_RIDE_SELECTION {:?},{:?},{:?}",
            hand,
            tag(game.items()),
            tag(game.res.items())
        );
    }
    let hand = hand?;
    let target = nearest_span(game).or_else(|| loop_target(game))?;
    let rpm = wheel(game, target.conveyor)?.rpm;
    let rider = Rider::embark(target.conveyor, target.edge, target.position, rpm);
    RIDE.with_borrow_mut(|ride| *ride = Some(rider));

    let key = keybinds::display_name(game.settings.keys.get("key.sneak"));
    game.native_client_action_bar(Text::translate("mount.onboard", &[key]), false);
    game.audio.play(SOUND, None, 0.5, 1.0);
    if std::env::var_os("CREATE_CHAIN_RIDE").is_some() {
        println!(
            "CREATE_CHAIN_RIDE_BOARD {:?},{:?},{:.9}",
            target.conveyor, target.edge, target.position
        );
    }
    Some(hand)
}

pub(super) fn local_grip(game: &Game<'_>) -> Option<Hand> {
    RIDE.with_borrow(|ride| ride.as_ref().is_some())
        .then(|| rideable_hand(game))
        .flatten()
}

pub(super) fn clear() {
    RIDE.with_borrow_mut(|ride| *ride = None);
}

pub(super) fn tick(game: &mut Game<'_>) {
    if game.pause || game.title.is_some() {
        return;
    }
    let Some(mut rider) = RIDE.with_borrow_mut(Option::take) else {
        return;
    };
    let look = game.aim().map_or([0.0; 3], |(_, facing)| facing);
    let holding_tool = rideable_hand(game).is_some();
    let sneaking = game.native_sneaking();
    let Some(player) = game.player.as_mut() else {
        return;
    };
    if player.health.dead_or_dying() || player.is_passenger {
        stop(game);
        return;
    }
    let motion = Motion {
        feet: player.position.components(),
        look,
        velocity: player.velocity.components(),
        height: f64::from(player.dimensions.height),
        scale: player.attribute("minecraft:scale").unwrap_or(1.0) as f32,
        holding_tool,
        sneaking,
    };
    let step = rider.step(motion, 1.0, |at| wheel(game, at));
    if std::env::var_os("CREATE_CHAIN_RIDE").is_some() {
        println!(
            "CREATE_CHAIN_RIDE_TICK {},{:?},{:?},{:.9},{},{},{:?},{:?}",
            game.ticks,
            rider.wheel,
            rider.connection,
            rider.position,
            rider.catching_up,
            step.stopped,
            step.target,
            step.velocity
        );
    }
    if step.stopped {
        stop(game);
        game.audio.play(SOUND, None, 0.35, 0.75);
        return;
    }
    if step.target.is_some()
        && let Some(player) = game.player.as_mut()
    {
        let [x, y, z] = step.velocity;
        player.velocity = Vec3::new(x, y, z);
        if game.ticks % 10 == 0 {
            player.fall_distance = 0.0;
            keepalive(game, &rider);
        }
    }
    RIDE.with_borrow_mut(|ride| *ride = Some(rider));
}

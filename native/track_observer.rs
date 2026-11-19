use horizon_world::level::flags;
use horizon_world::nbt::Tag;
use horizon_world::registry::BlockStateId;

use super::create_station::{targeting_position, valid_track};
use super::{Game, GameLevel};
use crate::containers::ModBlockEntity;

pub(super) const OBSERVER: &str = "create:track_observer";

pub(super) fn tick(game: &mut Game<'_>, pos: [i32; 3], entity: &mut ModBlockEntity) {
    let observed = targeting_position(&entity.nbt, pos).and_then(|(track, _)| {
        if valid_track(game, track).is_none() {
            return None;
        }
        let axis = match game.native_block_property(track, "shape").as_deref() {
            Some("xo") => 0,
            Some("zo") => 2,
            _ => return None,
        };
        let side = 2 - axis;
        let middle = f64::from(track[axis]) + 0.5;
        super::create_train::wheel_positions_with_id(game, None).find_map(|(id, wheels)| {
            let mut low = f64::INFINITY;
            let mut high = f64::NEG_INFINITY;
            for wheel in wheels {
                let point = wheel.location().components();
                if (point[side] - (f64::from(track[side]) + 0.5)).abs() < 1e-6
                    && (point[1] - (f64::from(track[1]) + 1.0)).abs() < 1e-6
                {
                    low = low.min(point[axis]);
                    high = high.max(point[axis]);
                }
            }
            (low <= middle && high >= middle).then_some(id)
        })
    });
    let now = game.world.game_time;
    if let Some(id) = observed {
        entity.nbt.insert("ObservedTrain".into(), Tag::Int(id as i32));
        entity
            .nbt
            .insert("ActivatedUntil".into(), Tag::Long(now + 8));
    }
    let active =
        matches!(entity.nbt.get(&"ActivatedUntil".into()), Some(Tag::Long(until)) if *until > now);
    if !active { entity.nbt.remove(&"ObservedTrain".into()); }
    if (game.native_block_property(pos, "powered").as_deref() == Some("true")) != active {
        game.native_set_block_property_with(
            pos,
            "powered",
            if active { "true" } else { "false" },
            flags::UPDATE_ALL,
        );
        super::create_display_link::observed_train_changed(game, pos, active.then(|| observed.or_else(|| {
            match entity.nbt.get(&"ObservedTrain".into()) { Some(Tag::Int(id)) => Some(*id as u32), _ => None }
        })).flatten());
    }
}

pub(super) fn signal(level: &GameLevel<'_>, state: BlockStateId, direct: bool, output: &mut i32) {
    if !direct && let Some(state) = level.registry.state(state).filter(|s| s.name == OBSERVER) {
        *output = if state
            .properties
            .get("powered")
            .is_some_and(|p| p.as_str() == "true")
        {
            15
        } else {
            0
        };
    }
}

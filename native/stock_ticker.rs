use horizon_world::{
    level::PlacementContext,
    nbt::{Compound, Tag},
    registry::BlockStateId,
};

use super::{Game, GameLevel, create_burner, create_elevator_seats, create_machines};
use crate::text::Text;

pub(super) const TICKER: &str = "create:stock_ticker";
const KEEPER_MISSING: &str = "create.stock_ticker.keeper_missing";

pub(super) fn new_tag() -> Compound {
    Compound::from([(
        "Freq".into(),
        Tag::IntArray(crate::save::random_uuid().to_vec()),
    )])
}

pub(super) fn place(
    level: &GameLevel<'_>,
    state: BlockStateId,
    context: &PlacementContext,
) -> Option<BlockStateId> {
    if level.native_state_block(state) != Some(TICKER) {
        return None;
    }
    let facing = (f64::from(context.yaw) / 90.0 + 0.5).floor() as i32;
    let facing = facing + if context.sneaking { 0 } else { 2 };
    level.native_state_with_property(
        state,
        "facing",
        ["south", "west", "north", "east"][facing.rem_euclid(4) as usize],
    )
}

pub(super) fn keeper_present(game: &Game<'_>, [x, y, z]: [i32; 3]) -> bool {
    [(-1, 0), (1, 0), (0, -1), (0, 1)]
        .into_iter()
        .any(|(dx, dz)| {
            let adjacent = [x + dx, y, z + dz];
            let below = [x + dx, y - 1, z + dz];
            create_elevator_seats::occupied_static(game, adjacent)
                || create_elevator_seats::occupied_static(game, below)
                || create_machines::mod_entity(game, adjacent)
                    .is_some_and(|entity| entity.id == create_burner::HEATER)
        })
}

pub(super) fn missing_keeper(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_sneaking() || game.native_block(pos) != TICKER || keeper_present(game, pos) {
        return false;
    }
    if game.native_authoritative() {
        game.send_overlay_message(Text::translate(KEEPER_MISSING, &[]));
    }
    true
}

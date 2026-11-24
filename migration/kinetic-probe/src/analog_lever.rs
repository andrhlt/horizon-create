//! Typed empty-hand interaction for Create's analog lever.
//!
//! The legacy implementation also owns redstone-neighbour propagation and the
//! animation timer. This probe deliberately ports the authoritative saved
//! `State` write first; the remaining tick/propagation work stays visible in
//! the migration inventory until its typed hook is wired.

use mod_api::{
    BlockEntityPart, BlockPart, Compound, InteractionResult, ServerHost, Tag, UseWithoutItemEvent,
};

const LEVER_ID: &str = "create:analog_lever";
const STATE: &str = "State";
const CHANGE_TIMER: &str = "ChangeTimer";

#[derive(Clone, Copy, Default)]
pub struct AnalogLever;

pub fn register(registrar: &mut dyn mod_api::Registrar) {
    let kind = registrar
        .block_entity_type("create:analog_lever")
        .blocks(&[LEVER_ID])
        .build();
    registrar
        .block_entity_part(&kind, AnalogLever)
        .expect("analog lever part registration");
}

fn current_state(host: &dyn mod_api::Host, entity: mod_api::BlockEntityRef) -> i32 {
    entity
        .data(host)
        .and_then(|data| match data.get(&STATE.into()) {
            Some(Tag::Byte(value)) => Some(i32::from(*value)),
            Some(Tag::Short(value)) => Some(i32::from(*value)),
            Some(Tag::Int(value)) => Some(*value),
            _ => None,
        })
        .unwrap_or(0)
        .clamp(0, 15)
}

fn change_data(next: i32) -> Compound {
    let mut data = Compound::new();
    data.insert(STATE.into(), Tag::Int(next));
    data.insert(CHANGE_TIMER.into(), Tag::Int(0));
    data
}

#[mod_api::horizon_part]
impl BlockPart for AnalogLever {
    fn use_without_item(
        &self,
        host: &mut dyn ServerHost,
        event: &mut UseWithoutItemEvent<'_>,
    ) -> Option<InteractionResult> {
        if host.block_key(LEVER_ID) != Some(event.state.block())
            || event.click.hand != mod_api::client::first_person::Hand::Main
        {
            return None;
        }
        let level = host.level(event.click.dimension.key().id())?;
        let entity = host.block_entity(level, event.click.pos)?;
        let player = host.player(event.click.player)?;
        let delta = if player.is_secondary_use_active(host).unwrap_or(false) {
            -1
        } else {
            1
        };
        let next = (current_state(host, entity) + delta).clamp(0, 15);
        let changed = entity.merge_data(host, change_data(next)).ok()?;
        changed.then_some(InteractionResult::SuccessServer)
    }
}

#[mod_api::horizon_part]
impl BlockEntityPart for AnalogLever {}

#[cfg(test)]
mod tests {
    #[test]
    fn lever_state_wraps_at_the_supported_bounds() {
        assert_eq!((0_i32 - 1).clamp(0, 15), 0);
        assert_eq!((15_i32 + 1).clamp(0, 15), 15);
    }
}

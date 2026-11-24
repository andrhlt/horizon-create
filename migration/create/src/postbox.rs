//! Postbox inventory conservation at block-entity removal.
//!
//! The legacy port's player-break hook preserves contents before the engine
//! removes the entity. The typed API exposes the same boundary while the
//! entity and its item slots are still available.

use mod_api::{
    BlockEntityPart, BlockEntityTypeKey, BlockPart, LevelRandomHost,
    PreRemoveSideEffectsEvent, Registrar,
};

const BLOCKS: &[&str] = &[
    "create:white_postbox",
    "create:orange_postbox",
    "create:magenta_postbox",
    "create:light_blue_postbox",
    "create:yellow_postbox",
    "create:lime_postbox",
    "create:pink_postbox",
    "create:gray_postbox",
    "create:light_gray_postbox",
    "create:cyan_postbox",
    "create:purple_postbox",
    "create:blue_postbox",
    "create:brown_postbox",
    "create:green_postbox",
    "create:red_postbox",
    "create:black_postbox",
];

#[derive(Clone, Copy)]
struct PostboxPart;

fn contents_to_drop<T: Clone>(slots: &[Option<T>]) -> Vec<T> {
    slots.iter().flatten().cloned().collect()
}

#[mod_api::horizon_part]
impl BlockPart for PostboxPart {}

#[mod_api::horizon_part]
impl BlockEntityPart for PostboxPart {
    fn pre_remove_side_effects(
        &self,
        _: &mut dyn LevelRandomHost,
        event: &mut PreRemoveSideEffectsEvent<'_>,
    ) {
        event.drops.extend(contents_to_drop(&event.entity.items));
    }
}

pub fn register(registrar: &mut dyn Registrar) {
    let postbox: BlockEntityTypeKey = registrar
        .block_entity_type("create:package_postbox")
        .blocks(BLOCKS)
        .build();
    registrar.block_entity_part(&postbox, PostboxPart).unwrap();
}

#[cfg(test)]
mod tests {
    use super::contents_to_drop;

    #[test]
    fn removal_drops_every_occupied_slot_once_in_order() {
        let slots = [Some("package-a"), None, Some("package-b"), None];
        assert_eq!(contents_to_drop(&slots), ["package-a", "package-b"]);
    }

    #[test]
    fn removal_of_an_empty_postbox_adds_no_drops() {
        let slots: [Option<u8>; 3] = [None, None, None];
        assert!(contents_to_drop(&slots).is_empty());
    }
}

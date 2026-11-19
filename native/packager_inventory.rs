// Item transfer for the original Packager's nine-slot payload.
use horizon_world::nbt::{Compound, Tag};

use crate::items::ItemStack;

use super::{create_depot::encode, create_machines::insert};

const PACKAGE_SLOTS: usize = 9;

pub(super) type Payload = [Option<ItemStack>; PACKAGE_SLOTS];

pub(super) fn collect(
    source: &mut [Option<ItemStack>],
    stack_limit: impl Fn(&ItemStack) -> u32,
) -> [Option<ItemStack>; PACKAGE_SLOTS] {
    let mut payload = std::array::from_fn(|_| None);
    for slot in source {
        let Some(stack) = slot.as_mut() else {
            continue;
        };
        let offered = ItemStack {
            count: stack.count.min(64),
            ..stack.clone()
        };
        let remaining = insert(&mut payload, &offered, stack_limit(&offered));
        stack.count -= offered.count - remaining;
        if stack.count == 0 {
            *slot = None;
        }
    }
    payload
}

pub(super) fn deposit(
    target: &mut [Option<ItemStack>],
    payload: &[Option<ItemStack>; PACKAGE_SLOTS],
    stack_limit: impl Fn(&ItemStack) -> u32,
) -> bool {
    let mut proposed = target.to_vec();
    for stack in payload.iter().flatten() {
        if insert(&mut proposed, stack, stack_limit(stack)) != 0 {
            return false;
        }
    }
    target.clone_from_slice(&proposed);
    true
}

pub(super) fn encode_contents(payload: &[Option<ItemStack>; PACKAGE_SLOTS]) -> Tag {
    let contents = payload
        .iter()
        .enumerate()
        .filter_map(|(slot, stack)| {
            let mut entry = Compound::new();
            entry.insert("slot".into(), Tag::Int(slot as i32));
            entry.insert("item".into(), encode(stack.as_ref()?));
            Some(Tag::Compound(entry))
        })
        .collect();
    Tag::List(contents)
}

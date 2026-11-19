fn save_bearing_items(
    pos: (i32, i32, i32),
    entity: &crate::containers::BlockEntity,
) -> std::ops::ControlFlow<Tag> {
    let crate::containers::BlockEntity::Mod(entity) = entity else {
        return std::ops::ControlFlow::Continue(());
    };
    if entity.id != "create:mechanical_bearing" || entity.items.is_empty() {
        return std::ops::ControlFlow::Continue(());
    }
    let mut nbt = entity.nbt.clone();
    nbt.insert("id".into(), string(&entity.id));
    for (key, value) in [("x", pos.0), ("y", pos.1), ("z", pos.2)] {
        nbt.insert(key.into(), Tag::Int(value));
    }
    // The vanilla Items list uses a byte Slot. A contraption can carry many containers.
    let cargo = entity.items.iter().enumerate().filter_map(|(i, slot)| {
        let Tag::Compound(mut item) = item_to_nbt(slot.as_ref()?) else {
            return None;
        };
        item.insert("Slot".into(), Tag::Int(i as i32));
        Some(Tag::Compound(item))
    });
    nbt.insert("MountedItems".into(), Tag::List(cargo.collect()));
    std::ops::ControlFlow::Break(Tag::Compound(nbt))
}

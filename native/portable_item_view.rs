fn portable_item_view(
    containers: &Containers<'_>,
    pos: Pos,
) -> std::ops::ControlFlow<Option<View>> {
    use crate::game::create_portable_interface::{ITEM, bearing_at};
    if containers.name(containers.world.block(pos.0, pos.1, pos.2)) == "create:mechanical_bearing" {
        return std::ops::ControlFlow::Break(None);
    }
    if let Some(key) = crate::game::create_train_portable_items::cargo_at(containers.world, pos) {
        let slots = containers.world.block_entities[&key].slots().len();
        return std::ops::ControlFlow::Break(Some(View {
            parts: vec![(key, slots), (pos, 0)],
            kind: Kind::Generic,
            container: None,
        }));
    }
    let Some([x, y, z]) = bearing_at(containers.world, [pos.0, pos.1, pos.2], ITEM) else {
        return std::ops::ControlFlow::Continue(());
    };
    let bearing = (x, y, z);
    let slots = containers
        .world
        .block_entities
        .get(&bearing)
        .map_or(0, |entity| entity.slots().len());
    std::ops::ControlFlow::Break(Some(View {
        parts: vec![(bearing, slots), (pos, 0)],
        kind: Kind::Generic,
        container: None,
    }))
}

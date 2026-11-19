fn cart_assembler_rail(
    game: &Game<'_>,
    x: i32,
    y: i32,
    z: i32,
) -> std::ops::ControlFlow<Option<Rail>> {
    use crate::game::create_cart_assembler::ASSEMBLER;
    let pos = [x, y, z];
    if game.native_block(pos) == crate::game::create_controller_rail::RAIL {
        let shape = game.native_block_property(pos, "shape").unwrap_or_default();
        return std::ops::ControlFlow::Break(Some(Rail {
            name: crate::game::create_controller_rail::RAIL.into(),
            shape: Shape::parse(&shape),
            powered: false,
        }));
    }
    if game.native_block(pos) != ASSEMBLER {
        return std::ops::ControlFlow::Continue(());
    }
    let shape = match game.native_block_property(pos, "shape").as_deref() {
        Some("east_west") => Shape::EastWest,
        _ => Shape::NorthSouth,
    };
    std::ops::ControlFlow::Break(Some(Rail {
        name: "minecraft:rail".into(),
        shape,
        powered: false,
    }))
}

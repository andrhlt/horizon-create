use crate::level::StateTable;
use crate::registry::BlockStateId;
use horizon_core::geometry::Direction;
use horizon_core::position::BlockPos;

pub(crate) fn blocks(
    table: &StateTable,
    from: BlockPos,
    flow: Direction,
    state: impl Fn(BlockPos) -> BlockStateId,
) -> bool {
    let axis_name = |direction| match direction {
        Direction::East | Direction::West => "x",
        Direction::Up | Direction::Down => "y",
        Direction::North | Direction::South => "z",
    };
    let fluid_axis = axis_name(flow);
    if fluid_axis == "y" {
        return false;
    }
    let mut below = from.offset(0, -1, 0);
    let mut block = state(below);
    let facing = |block| table.key_of("facing").and_then(|key| table.dir(block, key));
    if table.name(block) == "create:water_wheel" {
        return facing(block).is_some_and(|direction| axis_name(direction) == fluid_axis);
    }
    for _ in 0..2 {
        if table.name(block) != "create:water_wheel_structure" {
            return false;
        }
        let Some(direction) = facing(block) else {
            return false;
        };
        let [dx, dy, dz] = direction.normal();
        below = below.offset(dx, dy, dz);
        block = state(below);
        if table.name(block) == "create:large_water_wheel" {
            let axis = table.key_of("axis").map(|key| table.text(block, key));
            return axis_name(direction) != fluid_axis && axis == Some(fluid_axis);
        }
    }
    false
}

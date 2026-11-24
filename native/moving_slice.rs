//! Bounded moving-payload state shared by the bearing/piston migration.
//!
//! The legacy Create code keeps the assembled blocks and their inventories on
//! the moving carrier.  This small value type keeps that ownership explicit at
//! the new API boundary: movement changes pose only; disassembly returns the
//! exact payload once, and a rider is either carried or safely dismounted.

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Payload {
    pub blocks: Vec<Block>,
    pub inventories: Vec<Inventory>,
    pub rider: Option<Rider>,
    pub offset: i32,
    pub moving: bool,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Block {
    pub id: String,
    pub relative: [i32; 3],
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Inventory {
    pub relative: [i32; 3],
    pub items: Vec<(String, u32)>,
}

#[derive(Clone, Debug, PartialEq, Eq)]
pub struct Rider {
    pub id: [i32; 4],
    pub relative: [i32; 3],
}

#[derive(Clone, Copy, Debug, PartialEq)]
pub struct GlueBox {
    pub low: [f64; 3],
    pub high: [f64; 3],
}

fn inside_glue(area: GlueBox, position: [i32; 3]) -> bool {
    (0..3).all(|axis| {
        let center = f64::from(position[axis]) + 0.5;
        center >= area.low[axis] && center < area.high[axis]
    })
}

/// Expand a seeded payload through the legacy six-sided glue relation.
/// Marker discovery is deliberately separate so an engine adapter can provide
/// the saved `From`/`To` boxes without changing the graph rule.
pub fn expand_glued_payload(
    seeds: &[[i32; 3]],
    solids: &[[i32; 3]],
    glue: &[GlueBox],
) -> Vec<[i32; 3]> {
    let mut result: Vec<_> = seeds
        .iter()
        .copied()
        .filter(|position| solids.contains(position))
        .collect();
    let mut index = 0;
    while index < result.len() {
        let current = result[index];
        for neighbor in [
            [current[0] + 1, current[1], current[2]],
            [current[0] - 1, current[1], current[2]],
            [current[0], current[1] + 1, current[2]],
            [current[0], current[1] - 1, current[2]],
            [current[0], current[1], current[2] + 1],
            [current[0], current[1], current[2] - 1],
        ] {
            if result.contains(&neighbor)
                || !solids.contains(&neighbor)
                || !glue
                    .iter()
                    .any(|area| inside_glue(*area, current) && inside_glue(*area, neighbor))
            {
                continue;
            }
            result.push(neighbor);
        }
        index += 1;
    }
    result
}

impl Payload {
    pub fn assemble(blocks: Vec<Block>, inventories: Vec<Inventory>, rider: Option<Rider>) -> Self {
        assert!(inventories.iter().all(|inventory| {
            blocks
                .iter()
                .any(|block| block.relative == inventory.relative)
        }));
        Self {
            blocks,
            inventories,
            rider,
            offset: 0,
            moving: false,
        }
    }

    pub fn start(&mut self) {
        self.moving = true;
    }

    pub fn advance(&mut self, distance: i32) {
        if self.moving {
            self.offset = self.offset.saturating_add(distance);
        }
    }

    /// Stop movement and return the rider's safe landing position.
    pub fn stop_and_dismount(&mut self) -> Option<[i32; 3]> {
        self.moving = false;
        self.rider.take().map(|rider| {
            [
                rider.relative[0],
                rider.relative[1] + self.offset,
                rider.relative[2],
            ]
        })
    }

    /// Consume the carrier exactly once. The payload's blocks and inventories
    /// are returned together so callers cannot restore one without the other.
    pub fn disassemble(self) -> (Vec<Block>, Vec<Inventory>) {
        (self.blocks, self.inventories)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn payload() -> Payload {
        Payload::assemble(
            vec![Block {
                id: "minecraft:chest".into(),
                relative: [0, 0, 0],
            }],
            vec![Inventory {
                relative: [0, 0, 0],
                items: vec![("minecraft:iron_ingot".into(), 7)],
            }],
            Some(Rider {
                id: [1, 2, 3, 4],
                relative: [0, 1, 0],
            }),
        )
    }

    #[test]
    fn assembled_payload_moves_as_one_and_lands_rider_safely() {
        let mut payload = payload();
        payload.start();
        payload.advance(3);
        assert_eq!(payload.offset, 3);
        assert_eq!(payload.stop_and_dismount(), Some([0, 4, 0]));
        assert!(!payload.moving);
    }

    #[test]
    fn disassembly_conserves_blocks_and_inventory() {
        let mut payload = payload();
        payload.start();
        payload.advance(9);
        let (blocks, inventories) = payload.disassemble();
        assert_eq!(blocks.len(), 1);
        assert_eq!(inventories[0].items, [("minecraft:iron_ingot".into(), 7)]);
    }

    #[test]
    fn stopped_payload_without_rider_has_no_duplicate_carrier() {
        let mut payload = Payload::assemble(vec![], vec![], None);
        payload.start();
        assert_eq!(payload.stop_and_dismount(), None);
        assert_eq!(payload.stop_and_dismount(), None);
    }

    #[test]
    fn glue_bfs_keeps_connected_solid_neighbors() {
        let found = expand_glued_payload(
            &[[1, 101, 0]],
            &[[1, 101, 0], [2, 101, 0], [3, 101, 0], [3, 101, 2]],
            &[GlueBox {
                low: [0.0, 101.0, -1.0],
                high: [4.0, 102.0, 1.0],
            }],
        );
        assert_eq!(found, vec![[1, 101, 0], [2, 101, 0], [3, 101, 0]]);
    }

    #[test]
    fn glue_bfs_does_not_cross_unattached_or_air_cells() {
        let found = expand_glued_payload(
            &[[1, 101, 0]],
            &[[1, 101, 0], [3, 101, 0], [2, 102, 0]],
            &[GlueBox {
                low: [0.0, 101.0, -1.0],
                high: [3.0, 102.0, 1.0],
            }],
        );
        assert_eq!(found, vec![[1, 101, 0]]);
    }

    #[test]
    fn glue_bfs_accepts_reversed_marker_corners() {
        let found = expand_glued_payload(
            &[[2, 101, 0]],
            &[[1, 101, 0], [2, 101, 0]],
            &[GlueBox {
                low: [0.0, 101.0, -1.0],
                high: [3.0, 102.0, 2.0],
            }],
        );
        assert_eq!(found, vec![[2, 101, 0], [1, 101, 0]]);
    }
}

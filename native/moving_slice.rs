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
}

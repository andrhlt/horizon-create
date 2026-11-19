use horizon_core::random::XoroshiroRandom;
use horizon_world::{
    heightmap::HeightmapType,
    nbt::Tag,
    registry::{BlockRegistry, BlockStateId},
    worldgen::{
        anchor::WorldGenerationContext,
        block_feature::FeatureBlockBindings,
        feature::{FeatureBlocks, FeatureWorld},
        feature_graph::FeatureDefinition,
        placement::{PlacementContext, PlacementQueryError},
    },
};
use std::{collections::BTreeMap, convert::Infallible};

const BLOCKS: &[&str] = &[
    "minecraft:air",
    "minecraft:cave_air",
    "minecraft:void_air",
    "minecraft:stone",
    "minecraft:cobblestone",
    "minecraft:end_stone",
    "minecraft:obsidian",
    "minecraft:andesite",
    "minecraft:basalt",
    "minecraft:blackstone",
    "minecraft:calcite",
    "minecraft:deepslate",
    "minecraft:diorite",
    "minecraft:dripstone_block",
    "minecraft:granite",
    "minecraft:magma_block",
    "minecraft:netherrack",
    "minecraft:smooth_basalt",
    "minecraft:soul_sand",
    "minecraft:soul_soil",
    "minecraft:tuff",
    "create:asurine",
    "create:crimsite",
    "create:limestone",
    "create:ochrum",
    "create:scorchia",
    "create:scoria",
    "create:veridium",
];

fn registry() -> BlockRegistry {
    BlockRegistry::from_nbt(&Tag::compound([
        ("DataVersion", Tag::Int(horizon_world::DATA_VERSION)),
        (
            "states",
            Tag::List(
                BLOCKS
                    .iter()
                    .map(|name| Tag::compound([("id", Tag::String((*name).into()))]))
                    .collect(),
            ),
        ),
        (
            "defaults",
            Tag::compound(
                BLOCKS
                    .iter()
                    .enumerate()
                    .map(|(index, name)| (*name, Tag::Int(index as i32))),
            ),
        ),
    ]))
    .unwrap()
}

struct Cube {
    center: [i32; 3],
    upper: BlockStateId,
    lower: BlockStateId,
    air: BlockStateId,
    cells: BTreeMap<[i32; 3], BlockStateId>,
}
impl Cube {
    fn initial(&self, p: [i32; 3]) -> BlockStateId {
        if (0..3).any(|axis| (p[axis] - self.center[axis]).abs() > 16) {
            self.air
        } else if p[1] >= self.center[1] {
            self.upper
        } else {
            self.lower
        }
    }
}
impl FeatureWorld for Cube {
    type Error = Infallible;
    fn block(&mut self, p: [i32; 3]) -> Result<BlockStateId, Self::Error> {
        Ok(*self.cells.get(&p).unwrap_or(&self.initial(p)))
    }
    fn set_block(
        &mut self,
        p: [i32; 3],
        block: BlockStateId,
        _flags: i32,
    ) -> Result<bool, Self::Error> {
        Ok(self.cells.insert(p, block) != Some(block))
    }
}
impl PlacementContext for Cube {
    fn generation(&self) -> WorldGenerationContext {
        WorldGenerationContext::new(-64, 384, 63)
    }
    fn min_y(&mut self) -> Result<i32, PlacementQueryError> {
        Ok(-64)
    }
    fn max_y(&mut self) -> Result<i32, PlacementQueryError> {
        Ok(319)
    }
    fn height(&mut self, _: HeightmapType, _: i32, _: i32) -> Result<i32, PlacementQueryError> {
        Ok(self.center[1] + 17)
    }
    fn block_state(&mut self, p: [i32; 3]) -> Result<BlockStateId, PlacementQueryError> {
        Ok(self.block(p).unwrap())
    }
    fn set_section_block(
        &mut self,
        p: [i32; 3],
        state: BlockStateId,
    ) -> Result<(), PlacementQueryError> {
        self.set_block(p, state, 0).unwrap();
        Ok(())
    }
}

fn main() {
    let [config, mode, seed, x, y, z]: [String; 6] = std::env::args()
        .skip(1)
        .collect::<Vec<_>>()
        .try_into()
        .unwrap();
    let center = [x, y, z].map(|v| v.parse::<i32>().unwrap());
    let registry = registry();
    let tags = [
        (
            "minecraft:stone_ore_replaceables",
            [
                "minecraft:stone",
                "minecraft:andesite",
                "minecraft:diorite",
                "minecraft:granite",
            ]
            .as_slice(),
        ),
        (
            "minecraft:deepslate_ore_replaceables",
            ["minecraft:deepslate", "minecraft:tuff"].as_slice(),
        ),
        (
            "minecraft:base_stone_nether",
            [
                "minecraft:netherrack",
                "minecraft:basalt",
                "minecraft:blackstone",
            ]
            .as_slice(),
        ),
    ]
    .into_iter()
    .map(|(tag, values)| {
        (
            tag.to_string(),
            values.iter().map(|v| v.to_string()).collect(),
        )
    })
    .collect();
    let binding = FeatureBlockBindings::with_tags(&registry, Default::default(), &tags).unwrap();
    let feature = FeatureDefinition::from_json_with_blocks(
        &std::fs::read_to_string(config).unwrap(),
        &binding,
    )
    .unwrap();
    let get = |name| registry.default_state(name).unwrap();
    let (upper, lower) = if mode == "nether" {
        (get("minecraft:netherrack"), get("minecraft:netherrack"))
    } else {
        (get("minecraft:stone"), get("minecraft:deepslate"))
    };
    let mut cube = Cube {
        center,
        upper,
        lower,
        air: get("minecraft:air"),
        cells: BTreeMap::new(),
    };
    let mut random = XoroshiroRandom::new(seed.parse().unwrap());
    assert!(
        feature
            .place(
                &mut cube,
                &mut random,
                center,
                FeatureBlocks::from_registry(&registry).unwrap()
            )
            .unwrap()
    );
    for (&[x, y, z], &block) in &cube.cells {
        if block != cube.initial([x, y, z]) {
            println!(
                "{},{},{},{}",
                x - center[0],
                y - center[1],
                z - center[2],
                registry.state(block).unwrap().name
            );
        }
    }
}

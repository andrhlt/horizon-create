use horizon_core::geometry::{Direction, Vec3};
use horizon_core::position::BlockPos;
use horizon_world::level::{LevelAccess, LevelEvent};
use horizon_world::nbt::{Compound, Tag};
use horizon_world::registry::BlockStateId;

use crate::containers::{BlockEntity, ModBlockEntity};
use crate::items::ItemStack;

use super::create_cogwheel::direction_axis;
use super::create_fluids::name;
use super::create_machines::{COG, LARGE_COG, SHAFT, mod_entity};
use super::native_block_entity_draw::BlockEntityDraw;
use super::{Game, GameLevel};

const WOOD: &str = "create:wooden_bracket";
const METAL: &str = "create:metal_bracket";
const KINETIC: &str = "create:simple_kinetic";
const KEY: &str = "Bracket";
const PIPE: &str = "create:fluid_pipe";
const GLASS_PIPE: &str = "create:glass_fluid_pipe";
const PUMP: &str = "create:mechanical_pump";

#[derive(Clone, Copy, PartialEq)]
struct Bracket {
    block: &'static str,
    kind: &'static str,
    facing: Direction,
    along_first: bool,
}

fn material(block: &str) -> Option<&'static str> {
    match block {
        WOOD => Some(WOOD),
        METAL => Some(METAL),
        _ => None,
    }
}

impl Bracket {
    fn properties(self) -> [(&'static str, &'static str); 3] {
        [
            ("type", self.kind),
            ("facing", name(self.facing)),
            (
                "axis_along_first",
                if self.along_first { "true" } else { "false" },
            ),
        ]
    }

    fn tag(self) -> Tag {
        let properties = self
            .properties()
            .into_iter()
            .map(|(key, value)| (key.into(), Tag::String(value.into())))
            .collect();
        Tag::Compound(Compound::from([
            ("Name".into(), Tag::String(self.block.into())),
            ("Properties".into(), Tag::Compound(properties)),
        ]))
    }

    fn state(self, level: &GameLevel<'_>) -> Option<BlockStateId> {
        let id = level.registry.default_state(self.block)?;
        self.properties()
            .into_iter()
            .try_fold(id, |state, (key, value)| {
                level.native_state_with_property(state, key, value)
            })
    }
}

fn nbt_text(tag: &Compound, name: &str) -> Option<String> {
    if let Some(Tag::String(text)) = tag.get(&name.into()) {
        Some(text.to_string_lossy())
    } else {
        None
    }
}

fn bracket(entity: &ModBlockEntity) -> Option<Bracket> {
    let Some(Tag::Compound(tag)) = entity.nbt.get(&KEY.into()) else {
        return None;
    };
    let (block, Some(Tag::Compound(props))) = (
        material(&nbt_text(tag, "Name")?)?,
        tag.get(&"Properties".into()),
    ) else {
        return None;
    };
    let kind = match nbt_text(props, "type")?.as_str() {
        "shaft" => "shaft",
        "cog" => "cog",
        _ => return None,
    };
    Some(Bracket {
        block,
        kind,
        facing: super::machines::dir_from_name(&nbt_text(props, "facing")?)?,
        along_first: nbt_text(props, "axis_along_first")? == "true",
    })
}

fn target_bracket(
    game: &Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    block: &'static str,
) -> Option<Bracket> {
    let target_block = game.native_block(pos);
    let (kind, axis) = match target_block.as_str() {
        SHAFT => ("shaft", game.native_block_property(pos, "axis")?),
        COG | LARGE_COG => ("cog", game.native_block_property(pos, "axis")?),
        GLASS_PIPE | PUMP => (
            "pipe",
            game.native_block_property(
                pos,
                if target_block == PUMP {
                    "facing"
                } else {
                    "axis"
                },
            )
            .and_then(|property| match property.as_str() {
                "up" | "down" => Some("y".to_owned()),
                "east" | "west" => Some("x".to_owned()),
                "north" | "south" => Some("z".to_owned()),
                "x" | "y" | "z" => Some(property),
                _ => None,
            })?,
        ),
        PIPE => {
            let open = Direction::ALL
                .into_iter()
                .filter(|&direction| {
                    game.native_block_property(pos, name(direction)).as_deref() == Some("true")
                })
                .collect::<Vec<_>>();
            if open.len() != 2 || open[0] != open[1].opposite() {
                return None;
            }
            ("pipe", direction_axis(open[0]).to_owned())
        }
        _ => return None,
    };
    let mut facing = Direction::ALL
        .into_iter()
        .find(|&direction| direction.normal() == face)?;
    if direction_axis(facing) == axis {
        let (_, aim) = game.aim()?;
        facing = Direction::approximate_nearest(Vec3::new(aim[0], aim[1], aim[2])).opposite();
    }
    let side_axis = direction_axis(facing);
    if side_axis == axis {
        return None;
    }
    let along_first = if side_axis != "z" {
        axis != "z"
    } else {
        axis != "y"
    };
    Some(Bracket {
        block,
        kind,
        facing,
        along_first,
    })
}

fn return_bracket(game: &mut Game<'_>, pos: [i32; 3], bracket: Bracket) {
    if !game.creative
        && let Some(leftover) = game.give(ItemStack::new(bracket.block, 1))
    {
        game.pop_resource(pos, leftover);
    }
}

pub(super) fn apply(game: &mut Game<'_>, stack: &ItemStack, pos: [i32; 3], face: [i32; 3]) -> bool {
    let Some(block) = material(&stack.item) else {
        return false;
    };
    if !game.native_authoritative() {
        return false;
    }
    game.guest_inventory_resend |= game.lan_acting.is_some();
    let supported_entity = mod_entity(game, pos)
        .is_some_and(|entity| matches!(entity.id.as_str(), KINETIC | PIPE | GLASS_PIPE | PUMP));
    if !game.may_build() || !supported_entity {
        game.use_failed = true;
        return true;
    }
    let Some(target) = target_bracket(game, pos, face, block) else {
        return true;
    };
    let old = mod_entity(game, pos).and_then(bracket);
    if old == Some(target) {
        return true;
    }
    game.native_with_mod_block_entity(pos, |entity| entity.nbt.insert(KEY.into(), target.tag()));
    game.consume_held();
    if let Some(old) = old {
        return_bracket(game, pos, old);
    }
    let sound = if block == WOOD {
        "minecraft:block.scaffolding.place"
    } else {
        "minecraft:block.netherite_block.place"
    };
    let at = pos.map(|coordinate| f64::from(coordinate) + 0.5);
    game.native_play_sound_in_place(sound, at, 4, 0.75, 1.0);
    game.native_block_entity_sync(pos);
    true
}

pub(super) fn remove(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    let Some(old) = mod_entity(game, pos).and_then(bracket) else {
        return false;
    };
    if game.native_authoritative() {
        game.native_with_mod_block_entity(pos, |entity| entity.nbt.remove(&KEY.into()));
        let at = BlockPos::new(pos[0], pos[1], pos[2]);
        let state = game.with_level(|_, level, _| old.state(level));
        if let Some(state) = state {
            game.level_events.push(LevelEvent::LevelEvent {
                id: 2001,
                pos: at,
                data: state.0 as i32,
            });
            let _ = game.process_level_events();
        }
        return_bracket(game, pos, old);
        game.native_block_entity_sync(pos);
    }
    true
}

pub(super) fn on_remove(level: &mut GameLevel<'_>, pos: BlockPos, side_effects: bool) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    else {
        return;
    };
    let Some(state) = bracket(entity).and_then(|bracket| bracket.state(level)) else {
        return;
    };
    level.emit(LevelEvent::LevelEvent {
        id: 2001,
        pos,
        data: state.0 as i32,
    });
    level.pop_block_item(pos, state);
}

pub(super) fn update_tag(entity: &ModBlockEntity, tag: &mut Option<Compound>) {
    if matches!(entity.id.as_str(), KINETIC | PIPE | GLASS_PIPE | PUMP) {
        // Client update tags merge, so an empty compound clears a removed bracket.
        let value = entity
            .nbt
            .get(&KEY.into())
            .cloned()
            .unwrap_or_else(|| Tag::Compound(Compound::new()));
        tag.get_or_insert_with(Compound::new)
            .insert(KEY.into(), value);
    }
}

pub(super) fn render(game: &Game<'_>, entity: &ModBlockEntity, draw: &mut BlockEntityDraw) {
    if let Some(bracket) = bracket(entity) {
        game.native_draw_block(draw, bracket.block, &bracket.properties());
    }
}

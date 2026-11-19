use super::Game;
use crate::containers::BlockEntity;
use crate::items::ItemStack;
use horizon_core::position::BlockPos;
use horizon_world::{
    level::flags,
    nbt::{Compound, Tag},
};

pub(super) const BLOCK: &str = "create:lectern_controller";
const ITEM: &str = "create:linked_controller";
const CONTROLLER_DATA: &str = "ControllerData";
const FREQUENCIES: &str = "create:linked_controller_items";

fn frequencies(nbt: &Compound) -> Tag {
    if let Some(data @ Tag::List(_)) = nbt.get(&CONTROLLER_DATA.into()) {
        return data.clone();
    }
    // Early Horizon worlds stored the whole controller stack.
    super::create_depot::compound(nbt, "Controller")
        .and_then(|stack| stack.get(&"components".into()))
        .and_then(|components| match components {
            Tag::Compound(components) => components.get(&FREQUENCIES.into()),
            _ => None,
        })
        .cloned()
        .unwrap_or_else(|| Tag::List(Vec::new()))
}

fn controller(data: Tag) -> Option<ItemStack> {
    let mut components = Compound::new();
    components.insert(FREQUENCIES.into(), data);
    let mut stack = Compound::new();
    stack.insert("id".into(), Tag::String(ITEM.into()));
    stack.insert("count".into(), Tag::Int(1));
    stack.insert("components".into(), Tag::Compound(components));
    ItemStack::from_nbt(&stack)
}

fn replace(game: &mut Game<'_>, pos: [i32; 3], block: &str) -> bool {
    let Some(mut state) = game.native_default_state(block) else {
        return false;
    };
    let facing = game.native_block_property(pos, "facing");
    let powered = game.native_block_property(pos, "powered");
    state = game.with_level(|_, level, _| {
        for (key, value) in [("facing", facing), ("powered", powered)] {
            if let Some(value) = value {
                state = level
                    .native_state_with_property(state, key, &value)
                    .unwrap_or(state);
            }
        }
        state
    });
    game.native_set_block(game.native_dimension(), pos, state, flags::UPDATE_ALL)
}

fn sound(game: &mut Game<'_>, pos: [i32; 3], event: &str) {
    let at = pos.map(|coord| f64::from(coord) + 0.5);
    if game.native_play_sound_in_place(event, at, 4, 1.0, 1.0)
        && std::env::var_os("HORIZON_CREATE_LECTERN_TRACE").is_some()
    {
        let [x, y, z] = at;
        eprintln!("CREATE_LECTERN_SOUND {event},4,{x},{y},{z},1,1");
    }
}

pub(super) fn attach(game: &mut Game<'_>, pos: [i32; 3], stack: &ItemStack) -> bool {
    if stack.item.as_ref() != ITEM
        || game.native_sneaking()
        || game.native_block(pos) != "minecraft:lectern"
        || game.native_block_property(pos, "has_book").as_deref() != Some("false")
    {
        return false;
    }
    if !game.native_authoritative() {
        return true;
    }
    let data = game
        .native_component(stack, FREQUENCIES)
        .ok()
        .flatten()
        .cloned()
        .unwrap_or_else(|| Tag::List(Vec::new()));
    if replace(game, pos, BLOCK) {
        game.native_with_mod_block_entity(pos, |entity| {
            entity.nbt.insert(CONTROLLER_DATA.into(), data);
        });
        game.native_block_entity_sync(pos);
        sound(game, pos, "create:controller_put");
        if !game.creative {
            game.consume_held();
        }
    }
    true
}

pub(super) fn detach(game: &mut Game<'_>, pos: [i32; 3]) -> bool {
    if game.native_block(pos) != BLOCK || !game.native_sneaking() {
        return false;
    }
    if !game.native_authoritative() {
        return true;
    }
    if replace(game, pos, "minecraft:lectern") {
        sound(game, pos, "create:controller_take");
    }
    true
}

pub(super) fn remove(
    level: &mut super::GameLevel<'_>,
    pos: BlockPos,
    old: horizon_world::registry::BlockStateId,
    side_effects: bool,
) {
    if !side_effects || !level.native_authoritative {
        return;
    }
    let Some(BlockEntity::Mod(entity)) = level.world.block_entities.get(&(pos.x, pos.y, pos.z))
    else {
        return;
    };
    if entity.id != BLOCK {
        return;
    }
    let Some(stack) = controller(frequencies(&entity.nbt)) else {
        return;
    };
    let facing = level
        .registry
        .state(old)
        .and_then(|state| state.properties.get("facing"));
    let (x, z) = match facing.map(String::as_str) {
        Some("north") => (0.0, -0.25),
        Some("south") => (0.0, 0.25),
        Some("east") => (0.25, 0.0),
        Some("west") => (-0.25, 0.0),
        _ => (0.0, 0.0),
    };
    level.spill.spawns.push(super::spill::Spawn {
        stack,
        pos: [
            f64::from(pos.x) + 0.5 + x,
            f64::from(pos.y) + 1.0,
            f64::from(pos.z) + 0.5 + z,
        ],
        motion: None,
        delay: 10,
    });
}

pub(super) fn render(
    game: &Game<'_>,
    state: horizon_world::registry::BlockStateId,
    draw: &mut super::native_block_entity_draw::BlockEntityDraw,
) {
    let yaw = match game.native_block_state_property(state, "facing") {
        Some("north") => 90.0,
        Some("south") => -90.0,
        Some("east") => 180.0,
        _ => 0.0,
    };
    draw.push();
    draw.translate([0.5, 1.45, 0.5]);
    draw.rotate_about([0.0, 1.0, 0.0], yaw, [0.0; 3]);
    draw.translate([0.28, 0.0, 0.0]);
    draw.rotate_about([0.0, 0.0, 1.0], -22.0, [0.0; 3]);
    draw.translate([-0.5; 3]);
    game.native_draw_model(draw, "create:item/linked_controller/item", 0xffffff);
    draw.pop();
}

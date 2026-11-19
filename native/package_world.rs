use horizon_core::{
    geometry::{Aabb, Vec3},
    random::RandomSource,
};
use horizon_world::nbt::{Compound, Tag};

use crate::{items::ItemStack, save::item_to_nbt};

use super::{
    Game,
    create_package_style::{ENTITY, STYLES, dimensions},
};

pub(super) fn models(models: &mut Vec<String>) {
    models.extend(
        STYLES
            .iter()
            .map(|(name, _, _)| format!("create:item/{name}")),
    );
}

pub(super) fn spawn(
    game: &mut Game<'_>,
    stack: &ItemStack,
    position: [f64; 3],
    velocity: [f64; 3],
    tossed_by: Option<u128>,
) -> Option<u32> {
    dimensions(&stack.item)?;
    let mut nbt = Compound::new();
    nbt.insert("Silent".into(), Tag::Byte(1));
    nbt.insert("Fire".into(), Tag::Short(-1));
    nbt.insert("PersistenceRequired".into(), Tag::Byte(1));
    nbt.insert("Health".into(), Tag::Float(5.0f32.to_bits()));
    nbt.insert(
        "Motion".into(),
        Tag::List(velocity.map(|v| Tag::Double(v.to_bits())).to_vec()),
    );
    nbt.insert(
        "equipment".into(),
        Tag::compound([("mainhand", item_to_nbt(stack))]),
    );
    if let Some(owner) = tossed_by {
        let uuid = horizon_client::lan::playerdata::uuid_ints(owner);
        nbt.insert("CreatePackageTossedBy".into(), Tag::IntArray(uuid.to_vec()));
    }

    let id = game.native_summon(game.native_dimension(), ENTITY, position, nbt)?;
    if let Some(mob) = game.mobs.iter_mut().find(|mob| mob.id == id) {
        let yaw = mob.random.next_float() * 360.0;
        mob.yaw = yaw;
        mob.previous_yaw = yaw;
        mob.body_yaw = yaw;
        mob.previous_body_yaw = yaw;
        mob.head_yaw = yaw;
        mob.previous_head_yaw = yaw;
        if std::env::var_os("HORIZON_CREATE_PACKAGE_TRACE").is_some() {
            let (width, height, _) = mob.dims();
            let [x, y, z] = position;
            eprintln!(
                "CREATE_PACKAGE_SPAWN {id},{},{x:.9},{y:.9},{z:.9},{width:.9},{height:.9}",
                stack.item
            );
        }
    }
    Some(id)
}

fn placement_position(
    game: &Game<'_>,
    stack: &ItemStack,
    face: [i32; 3],
    point: [f64; 3],
) -> Option<[f64; 3]> {
    let (width, height) = dimensions(&stack.item)?;
    let [mut x, mut y, mut z] = point;
    let radius = width / 2.0;
    if face[1] < 0 {
        y -= height + 0.25;
    } else if face[1] == 0 {
        x += f64::from(face[0]) * radius;
        z += f64::from(face[2]) * radius;
    }
    let scan = Aabb::new(
        Vec3::new(x - radius, y, z - radius),
        Vec3::new(x + radius, y + height, z + radius),
    );
    let occupied = game
        .mobs
        .iter()
        .any(|mob| !mob.removed && mob.kind.id == ENTITY && mob.bounds().intersects(scan));
    (!occupied).then_some([x, y, z])
}

pub(super) fn predicts_placement(game: &Game<'_>, stack: &ItemStack, hit: &super::Hit) -> bool {
    placement_position(game, stack, hit.face, hit.point).is_some()
}

pub(super) fn place(game: &mut Game<'_>, stack: &ItemStack, pos: [i32; 3], face: [i32; 3]) -> bool {
    if !game.native_authoritative() || game.native_sneaking() || dimensions(&stack.item).is_none() {
        return false;
    }
    let Some(hit) = game.pick().filter(|hit| hit.pos == pos && hit.face == face) else {
        return false;
    };
    let Some(position) = placement_position(game, stack, face, hit.point) else {
        return false;
    };
    if spawn(game, stack, position, [0.0; 3], None).is_none() {
        return false;
    }
    game.consume_held();
    true
}

fn package_arrow_damage(
    game: &mut Game<'_>,
    arrow: &Projectile,
    target: u32,
) -> std::ops::ControlFlow<Option<bool>> {
    use crate::game::{create_package_damage, create_package_style};
    use std::ops::ControlFlow::{Break, Continue};

    if !game
        .mobs
        .iter()
        .any(|mob| mob.id == target && mob.kind.id == create_package_style::ENTITY)
    {
        return Continue(());
    }
    let saved_player_may_build = arrow.owner_uuid.and_then(|owner| {
        let uuid_ints = horizon_client::lan::playerdata::uuid_ints;
        if game
            .lan_acting_uuid
            .is_some_and(|player| uuid_ints(player) == owner)
        {
            return Some(game.may_build());
        }
        let guest = game.lan.as_ref().and_then(|host| {
            host.hub
                .guests
                .iter()
                .find(|guest| uuid_ints(guest.uuid) == owner)
        });
        guest
            .map(|guest| guest.may_build())
            .or_else(|| (game.level.player_uuid == Some(owner)).then(|| game.may_build()))
    });
    let may_build = saved_player_may_build.unwrap_or_else(|| match (arrow.owner, arrow.guest) {
        (Some(Who::Player), Some(guest)) => game
            .command_guest(guest)
            .is_none_or(|guest| guest.may_build()),
        (Some(Who::Player), None) => game.may_build(),
        _ => true,
    });
    if !may_build || !create_package_damage::can_hurt(game, target) {
        return Break(Some(false));
    }
    let spilled = create_package_damage::spill_now(game, target);
    let pierced = arrow.arrow.as_ref().is_some_and(|flight| flight.pierce > 0);
    Break(Some(spilled && pierced))
}

fn diving_player_damage(
    game: &crate::game::Game<'_>,
    damage_type: &str,
) -> std::ops::ControlFlow<bool> {
    use horizon_world::nbt::Tag;
    use std::ops::ControlFlow::{Break, Continue};

    let armor = &game.armor;
    let full_netherite_suit = armor[0]
        .as_ref()
        .is_some_and(|stack| stack.item.as_ref() == "create:netherite_diving_helmet")
        && armor[1].as_ref().is_some_and(|stack| {
            stack.item.as_ref() == "create:netherite_backtank"
                && matches!(stack.data().and_then(|data| data.other("create:banktank_air")), Some(Tag::Int(air)) if *air > 0)
        })
        && armor[2]
            .as_ref()
            .is_some_and(|stack| stack.item.as_ref() == "minecraft:netherite_leggings")
        && armor[3].as_ref().is_some_and(|stack| {
            matches!(stack.item.as_ref(), "create:netherite_diving_boots" | "minecraft:netherite_boots")
        });
    if !full_netherite_suit {
        return Continue(());
    }

    let Some(id) = game.health_resources.damage.id(damage_type) else {
        return Continue(());
    };
    if game
        .health_resources
        .damage
        .in_tag(id, "minecraft:is_fire")
    {
        Break(false)
    } else {
        Continue(())
    }
}

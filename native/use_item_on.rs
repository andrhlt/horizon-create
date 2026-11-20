fn use_item_on(
    game: &mut crate::game::Game<'_>,
    stack: &crate::items::ItemStack,
    pos: [i32; 3],
    face: [i32; 3],
    claimed: &mut bool,
) {
    if crate::game::create_factory_gauge::reject_untuned(stack) {
        game.guest_inventory_resend |= game.lan_acting.is_some();
        *claimed = true;
        return;
    }
    if crate::game::create_factory_gauge::add_panel(game, pos, stack) {
        *claimed = true;
        return;
    }
    if crate::game::create_factory_gauge::set_filter(game, pos, stack) {
        *claimed = true;
        return;
    }
    if game.native_block(pos) == "create:deployer" {
        if stack.item.as_ref() == "create:wrench"
            && crate::game::create_wrench::apply(game, pos, face)
        {
            *claimed = true;
            return;
        }
        if crate::game::create_machines::deployer_interact(game, pos, face) {
            *claimed = true;
            return;
        }
    }
    if !game.native_sneaking() {
        crate::game::create_clipboard_editor::open(game, stack, claimed);
    }
    crate::game::create_train_schedule::use_schedule(game, stack, claimed);
    if *claimed
        || crate::game::create_tree_fertilizer::use_item(game, pos, stack)
        || crate::game::create_symmetry_wand::activate(game, stack, pos, face)
        || crate::game::create_worldshaper_screen::open(game, stack)
        || crate::game::create_worldshaper::use_tool(game, stack, Some((pos, face)))
        || crate::game::create_shopping_list::discard(game, stack)
        || crate::game::create_package_world::place(game, stack, pos, face)
        || crate::game::create_table_cloth::blocked(game, pos, face, stack)
        || crate::game::create_sail::use_item(game, pos, stack)
        || crate::game::structure_blocks::create_schematic_capture::use_item(game, pos, stack)
        || crate::game::create_schematic_table::open(game, pos)
        || crate::game::create_steam::use_item(game, pos, face, stack)
        || crate::game::create_shaft::encase(game, pos, stack)
        || crate::game::create_encased_fluid_pipe::encase(game, pos, stack)
        || crate::game::create_shaft::insert_into_girder(game, pos, face, stack)
        || crate::game::create_bracket::apply(game, stack, pos, face)
        || crate::game::create_burner::use_item(game, pos, face, stack)
        || crate::game::create_schematicannon::use_item(game, pos, face, stack)
        || crate::game::create_track::use_track(game, pos, face, stack)
        || crate::game::create_display_link::use_item(game, pos, face, stack)
        || crate::game::create_station::use_item(game, pos, face, stack)
        || crate::game::create_station::use_track(game, pos, stack)
        || crate::game::create_belt::use_connector(game, pos, stack)
        || crate::game::create_cart_assembler::use_rail(game, pos, stack)
        || crate::game::create_cart_assembler_pickup::place_portable(game, pos, stack)
        || crate::game::create_mixer::use_item(game, pos, stack)
        || crate::game::create_fluid_tank::use_bucket(game, pos, stack)
        || crate::game::create_roller::set_filter(game, pos, stack)
        || crate::game::create_contraption_controls::filter(game, pos, stack)
        || crate::game::create_funnel::use_item(game, pos, face, stack)
        || crate::game::create_wheel_material::use_planks(game, pos, stack)
    {
        *claimed = true;
    } else if crate::game::create_item_application::apply(game, pos, stack) {
        game.consume_held();
        if game.native_block(pos) == "create:andesite_casing" {
            let player = game.native_acting_id();
            game.native_trigger_criterion(player, "create:andesite_casing_builtin", |_| true);
        }
        *claimed = true;
    }
}

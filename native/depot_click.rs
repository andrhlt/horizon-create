fn depot_click(
    game: &mut crate::game::Game<'_>,
    pos: [i32; 3],
    face: [i32; 3],
    canceled: &mut bool,
) {
    if !*canceled
        && game.native_block(pos) == "create:deployer"
        && game.hand == super::Hand::Main
        && !game
            .held()
            .is_some_and(|stack| stack.item.as_ref() == "create:wrench")
        && crate::game::create_machines::deployer_interact(game, pos, face)
    {
        *canceled = true;
        return;
    }
    if !*canceled
        && (crate::game::create_chain_conveyor_target::click(game, pos)
            || crate::game::create_chain_conveyor_connect::click(game, pos)
            || crate::game::create_clipboard_block::sneak_pickup(game, pos)
            || crate::game::create_wrench::apply(game, pos, face)
            || crate::game::create_clipboard_editor::open_placed(game, pos))
    {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_table_cloth::click(game, pos, face) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_shopping_list::ticker_click(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_placard::click(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_steam_whistle::grow(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_crafter::click(game, pos, face) {
        *canceled = true;
        return;
    }
    crate::game::create_packager::click(game, pos, canceled);
    if !*canceled && crate::game::create_threshold_switch::filter_click(game, pos, face) {
        *canceled = true;
        return;
    }
    if !*canceled
        && (crate::game::create_sequencer_editor::open(game, pos, face)
            || crate::game::create_threshold_switch_editor::open(game, pos))
    {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_speed_controller_controls::claims_value_box(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled
        && (crate::game::create_bearing::windmill_click(game, pos)
            || crate::game::create_clockwork::click(game, pos))
    {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_hand_crank::click(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_redstone_link::click(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_arm::choose_point(game, pos, false) {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_linear_chassis::click(game, pos, face) {
        *canceled = true;
        return;
    }
    if !*canceled
        && game
            .held()
            .cloned()
            .is_some_and(|stack| crate::game::create_glue::use_item(game, pos, &stack))
    {
        *canceled = true;
        return;
    }
    if !*canceled
        && (crate::game::create_station::open(game, pos)
            || crate::game::create_display_link::open(game, pos)
            || crate::game::create_chain_conveyor_packages::open_port(game, pos)
            || crate::game::create_schematic_table::open(game, pos)
            || crate::game::create_brass_tunnel::click(game, pos, face))
    {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_ejector_target::select(game, pos) {
        *canceled = true;
        return;
    }
    if !*canceled
        && game
            .held()
            .cloned()
            .is_some_and(|stack| crate::game::create_toolbox::dye(game, pos, &stack))
    {
        *canceled = true;
        return;
    }
    if !*canceled && crate::game::create_toolbox_menu::open(game, pos) {
        *canceled = true;
        return;
    }
    crate::game::create_saw::click(game, pos, canceled);
    crate::game::create_valve::click(game, pos, canceled);
    crate::game::create_depot::nixie_click(game, pos, canceled);
    crate::game::create_depot::click(game, pos, face, canceled);
    crate::game::create_item_drain::click(game, pos, canceled);
}

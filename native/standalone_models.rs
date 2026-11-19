fn standalone_models(models: &mut Vec<String>) {
    crate::game::create_visuals::register_models(models);
    crate::game::create_encased_pipe_visual::models(models);
    crate::game::create_chain_conveyor_visual::models(models);
    crate::game::create_packager_visual::models(models);
    models.push("create:block/factory_gauge/panel".into());
    crate::game::create_saw::models(models);
    models.push(crate::game::create_drill::HEAD.into());
    crate::game::create_analog_lever::models(models);
    models.extend([
        "create:block/schematicannon/connector".to_owned(),
        "create:block/schematicannon/pipe".to_owned(),
    ]);
    crate::game::create_desk_bell::models(models);
    crate::game::create_package_world::models(models);
    crate::game::create_toolbox_animation::models(models);
}

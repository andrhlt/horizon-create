pub(crate) mod create_kinetic_slice;
pub(crate) mod kinetic_adapter;
pub(crate) mod kinetic_controls;
pub(crate) mod postbox;

#[derive(Default)]
struct Create;

#[mod_api::horizon_mod]
impl mod_api::Hooks for Create {
    fn register(
        &self,
        registrar: &mut dyn mod_api::Registrar,
        _: &mod_api::RegistrationContext,
    ) {
        for recipe_type in [
            "create:compacting",
            "create:cutting",
            "create:crushing",
            "create:deploying",
            "create:emptying",
            "create:filling",
            "create:haunting",
            "create:item_application",
            "create:item_copying",
            "create:mechanical_crafting",
            "create:milling",
            "create:mixing",
            "create:pressing",
            "create:sandpaper_polishing",
            "create:sequenced_assembly",
            "create:splashing",
            "create:toolbox_dyeing",
        ] {
            registrar.register_recipe_type(recipe_type);
            registrar.register_raw_recipe_serializer(recipe_type, recipe_type);
        }
        kinetic_adapter::register(registrar);
        kinetic_controls::register(registrar);
        postbox::register(registrar);
    }
}

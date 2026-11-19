pub(crate) const ENTITY: &str = "create:package";

pub(crate) const STYLES: [(&str, f64, f64); 14] = [
    ("cardboard_package_12x12", 12.0, 12.0),
    ("cardboard_package_10x12", 10.0, 12.0),
    ("cardboard_package_10x8", 10.0, 8.0),
    ("cardboard_package_12x10", 12.0, 10.0),
    ("rare_creeper_package", 12.0, 10.0),
    ("rare_darcy_package", 12.0, 10.0),
    ("rare_evan_package", 12.0, 10.0),
    ("rare_jinx_package", 12.0, 10.0),
    ("rare_kryppers_package", 12.0, 10.0),
    ("rare_simi_package", 12.0, 10.0),
    ("rare_starlotte_package", 12.0, 10.0),
    ("rare_thunder_package", 12.0, 10.0),
    ("rare_up_package", 12.0, 10.0),
    ("rare_vector_package", 12.0, 10.0),
];

pub(crate) fn dimensions(item: &str) -> Option<(f64, f64)> {
    let name = item.strip_prefix("create:")?;
    STYLES
        .iter()
        .find(|(style, _, _)| *style == name)
        .map(|(_, width, height)| (width / 16.0, height / 16.0))
}

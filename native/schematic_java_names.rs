fn schematic_java_names(
    template: Option<Tag>,
) -> Option<Tag> {
    use horizon_world::nbt::Tag;

    let mut template = template?;
    // Create 6.0.10 uses the 1.21.1 JSON component string representation.
    if template.get("DataVersion") != Some(&Tag::Int(3955)) {
        return Some(template);
    }
    if let Some(Tag::List(blocks)) = template.get_mut("blocks") {
        for block in blocks {
            let Some(name) = block
                .get_mut("nbt")
                .and_then(|nbt| nbt.get_mut("CustomName"))
            else {
                continue;
            };
            let Tag::String(encoded) = name else {
                continue;
            };
            let Ok(decoded) = serde_json::from_str::<serde_json::Value>(&encoded.to_string_lossy())
            else {
                continue;
            };
            let plain = match &decoded {
                serde_json::Value::String(text) => Some(text.as_str()),
                serde_json::Value::Object(fields) if fields.len() == 1 => {
                    fields.get("text").and_then(serde_json::Value::as_str)
                }
                _ => None,
            };
            if let Some(plain) = plain {
                *name = Tag::String(plain.into());
            }
        }
    }
    Some(template)
}

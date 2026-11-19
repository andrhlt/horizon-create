#[path = "../native/frogport_anticipation.rs"]
mod frogport_anticipation;

#[test]
fn repeated_requests_and_head_pitch_match_java() {
    let mut motion = frogport_anticipation::Anticipation::default();
    let mut prior = -1;
    let mut count = 0;
    for row in include_str!("../fixtures/frogport-anticipation-pose-java.csv")
        .lines()
        .skip(1)
    {
        let fields: Vec<_> = row.split(',').collect();
        let tick = fields[0].parse::<i32>().unwrap();
        if tick != prior {
            prior = tick;
            let request = fields[1].parse::<i64>().unwrap();
            motion.tick((request >= 0).then_some(request));
            if fields[2] == "true" {
                motion.reset();
            }
        }
        let phase = motion.value(fields[3].parse().unwrap());
        for (actual, expected) in [phase, frogport_anticipation::head_factor(phase)]
            .into_iter()
            .zip(&fields[4..])
        {
            assert!(
                (actual - expected.parse::<f32>().unwrap()).abs() < 1e-6,
                "{row}: {actual}"
            );
        }
        count += 1;
    }
    assert_eq!(count, 76);
}

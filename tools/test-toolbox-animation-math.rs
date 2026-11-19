#[path = "../native/toolbox_animation_math.rs"]
mod animation;

use animation::{Cue, Motion};

#[test]
fn lids_and_drawers_match_original_toolbox_ticks() {
    let mut motion = Motion::default();
    let mut cues = Vec::new();
    let mut ticks = 0;
    for row in include_str!("../fixtures/toolbox-animation-java.csv")
        .lines()
        .skip(1)
    {
        let mut fields = row.split(',');
        let tick = fields.next().unwrap().parse::<usize>().unwrap();
        assert_eq!(ticks, tick);
        let viewers_before = fields.next().unwrap().parse::<u32>().unwrap();
        let viewers = fields.next().unwrap().parse::<u32>().unwrap();
        assert_eq!(viewers_before, viewers);
        if let Some(cue) = motion.tick(viewers > 0) {
            cues.push((tick, cue));
        }
        let expected: Vec<f32> = fields.map(|field| field.parse().unwrap()).collect();
        for (phase, partial) in [0.0, 0.5, 1.0].into_iter().enumerate() {
            let [lid, drawers] = motion.at(partial);
            assert!(
                (lid - expected[phase]).abs() < 5.1e-10,
                "lid {partial}: {row}"
            );
            assert!(
                (drawers - expected[phase + 3]).abs() < 5.1e-10,
                "drawers {partial}: {row}"
            );
        }
        ticks += 1;
    }
    assert_eq!(ticks, 19);
    assert_eq!(
        cues,
        [(1, Cue::Open), (8, Cue::ChestClose), (15, Cue::IronClose)]
    );
    for _ in 0..100 {
        assert_eq!(motion.tick(false), None);
    }
    assert!(motion.closed());
}

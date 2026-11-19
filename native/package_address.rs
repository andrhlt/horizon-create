#[derive(Debug)]
enum Atom {
    Literal(char),
    Any,
    Star,
    Class {
        inverted: bool,
        ranges: Vec<(char, char)>,
    },
    Choice(Vec<Vec<Atom>>),
    NotAhead(Vec<Vec<Atom>>),
    NotBehind(Vec<Vec<Atom>>),
}

type Input<'a> = std::iter::Peekable<std::str::Chars<'a>>;

pub(super) fn is_blank(address: &str) -> bool {
    address.chars().all(|c| {
        matches!(c,
            '\u{9}'..='\u{d}' | '\u{1c}'..=' ' | '\u{1680}' | '\u{2000}'..='\u{2006}'
            | '\u{2008}'..='\u{200a}' | '\u{2028}' | '\u{2029}' | '\u{205f}' | '\u{3000}'
        )
    })
}

pub(super) fn matches(box_address: &str, requested: &str) -> bool {
    if is_blank(requested) {
        return is_blank(box_address);
    }
    requested == "*"
        || box_address == "*"
        || requested == box_address
        || glob_matches(box_address, requested)
        || glob_matches(requested, box_address)
}

fn glob_matches(pattern: &str, value: &str) -> bool {
    if !pattern.contains(['*', '?', '[', '{', '\\']) {
        return false;
    }
    let Some(pattern) = parse(pattern) else {
        return value.is_empty();
    };
    let value: Vec<char> = value.chars().collect();
    advance(&pattern, &value, 0).contains(&value.len())
}

fn parse(pattern: &str) -> Option<Vec<Atom>> {
    let mut input = pattern.chars().peekable();
    let mut atoms = Vec::new();
    let mut anchored = true;
    while let Some(c) = input.next() {
        if c == '{' {
            let inverted = input.next_if_eq(&'!').is_some();
            let group = alternatives(&mut input)?;
            if !inverted {
                atoms.push(Atom::Choice(group));
            } else if anchored {
                atoms.push(Atom::NotAhead(group));
                atoms.push(Atom::Star);
                anchored = false;
            } else {
                atoms.push(Atom::NotBehind(group));
            }
        } else {
            anchored = c != '*';
            atoms.push(atom(c, &mut input)?);
        }
    }
    Some(atoms)
}

fn alternatives(input: &mut Input<'_>) -> Option<Vec<Vec<Atom>>> {
    let mut alternatives = Vec::new();
    let mut branch = Vec::new();
    loop {
        match input.next()? {
            '}' => {
                alternatives.push(branch);
                return Some(alternatives);
            }
            ',' => alternatives.push(std::mem::take(&mut branch)),
            '{' => return None,
            c => branch.push(atom(c, input)?),
        }
    }
}

fn atom(c: char, input: &mut Input<'_>) -> Option<Atom> {
    Some(match c {
        '*' => Atom::Star,
        '?' => Atom::Any,
        '[' => class(input)?,
        '\\' => Atom::Literal(input.next()?),
        c => Atom::Literal(c),
    })
}

fn class(input: &mut Input<'_>) -> Option<Atom> {
    let inverted = input.next_if_eq(&'!').is_some();
    let mut ranges = Vec::new();
    loop {
        let start = match input.next()? {
            ']' => break,
            '\\' => input.next()?,
            c => c,
        };
        let end = if input.next_if_eq(&'-').is_some() {
            match input.next()? {
                ']' => {
                    ranges.extend([(start, start), ('-', '-')]);
                    break;
                }
                end if end >= start => end,
                _ => return None,
            }
        } else {
            start
        };
        ranges.push((start, end));
    }
    (!ranges.is_empty()).then_some(Atom::Class { inverted, ranges })
}

fn dot(c: char) -> bool {
    !matches!(c, '\n' | '\r' | '\u{85}' | '\u{2028}' | '\u{2029}')
}

fn advance(atoms: &[Atom], value: &[char], start: usize) -> Vec<usize> {
    let mut positions = vec![start];
    for atom in atoms {
        let mut next = Vec::new();
        for pos in positions {
            match atom {
                Atom::Literal(c) => {
                    if value.get(pos) == Some(c) {
                        next.push(pos + 1);
                    }
                }
                Atom::Any => {
                    if value.get(pos).is_some_and(|&c| dot(c)) {
                        next.push(pos + 1);
                    }
                }
                Atom::Star => {
                    let length = value[pos..].iter().take_while(|&&c| dot(c)).count();
                    next.extend(pos..=pos + length);
                }
                Atom::Class { inverted, ranges } => {
                    if value.get(pos).is_some_and(|c| {
                        ranges.iter().any(|(min, max)| min <= c && c <= max) != *inverted
                    }) {
                        next.push(pos + 1);
                    }
                }
                Atom::Choice(branches) => {
                    for branch in branches {
                        next.extend(advance(branch, value, pos));
                    }
                }
                Atom::NotAhead(branches) => {
                    if branches
                        .iter()
                        .all(|branch| advance(branch, value, pos).is_empty())
                    {
                        next.push(pos);
                    }
                }
                Atom::NotBehind(branches) => {
                    if branches.iter().all(|branch| {
                        (0..=pos).all(|start| !advance(branch, &value[..pos], start).contains(&pos))
                    }) {
                        next.push(pos);
                    }
                }
            }
        }
        if next.is_empty() {
            return next;
        }
        next.sort_unstable();
        next.dedup();
        positions = next;
    }
    positions
}

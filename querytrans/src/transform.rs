use std::collections::HashSet;

use opencc_rust::{OpenCC, DefaultConfig};
use lazy_static::lazy_static;

use crate::parser::*;

lazy_static! {
  static ref OPENCC: Vec<OpenCC> = {
    vec![
      OpenCC::new(DefaultConfig::S2TW).unwrap(),
      OpenCC::new(DefaultConfig::TW2S).unwrap(),
      OpenCC::new(DefaultConfig::S2TWP).unwrap(),
      OpenCC::new(DefaultConfig::TW2SP).unwrap(),
    ]
  };
}

pub fn transform(input: &str) -> eyre::Result<String> {
  let q = match query(input) {
    Ok(("", q)) => q,
    Ok((i, _)) => return Err(eyre::eyre!("unparsed input remains: {}", i)),
    Err(e) => return Err(eyre::eyre!("parse error: {:?}", e)),
  };

  let new = q.0.into_iter().flat_map(|a| transform_simple(a, false)).collect();
  Ok(format!("{}", Query(new)))
}

fn transform_simple(simp: Simple, neg: bool) -> Vec<Simple> {
  match simp {
    Simple::Group(a) => transform_group(a, neg),
    Simple::Negative(a) => transform_negative(a, neg),
    Simple::Term(a) => transform_term(a, neg),
  }
}

fn transform_term(a: Term, neg: bool) -> Vec<Simple> {
  let s = &a.0;
  let mut ss: HashSet<String> = OPENCC.iter().map(|cc| cc.convert(s)).collect();
  ss.insert(s.into());
  let inner = if ss.len() == 1 {
    Simple::Term(a)
  } else if neg {
    Simple::Group(Group(
      ss.into_iter()
        .map(|s| Simple::Term(Term(s))).collect()
    ))
  } else {
    Simple::Group(Group(
      ss.into_iter()
        .intersperse(String::from("OR"))
        .map(|s| Simple::Term(Term(s))).collect()
    ))
  };
  vec![inner]
}

fn transform_group(a: Group, neg: bool) -> Vec<Simple> {
  let inner = a.0.into_iter().flat_map(|a| transform_simple(a, neg)).collect();
  vec![Simple::Group(Group(inner))]
}

fn transform_negative(n: Negative, neg: bool) -> Vec<Simple> {
  let inner = match n {
    Negative::Group(a) => {
      let sg = transform_group(a, !neg).pop().unwrap();
      match sg {
        Simple::Group(a) => Negative::Group(a),
        _ => unreachable!("group must be transformed into a single group"),
      }
    }
    Negative::Term(a) => {
      match transform_term(a, !neg) {
        mut b if b.len() == 1 =>
          match b.pop().unwrap() {
            Simple::Group(a) => Negative::Group(a),
            Simple::Negative(_) => unreachable!("can't transform to negative!"),
            Simple::Term(a) => Negative::Term(a),
          }
        v => Negative::Group(Group(v)),
      }
    },
  };
  vec![Simple::Negative(inner)]
}

#[cfg(test)]
mod test {
  use super::*;

  #[test]
  fn simple_test() {
    assert_eq!(transform("你好").unwrap(), String::from("你好"));
    assert_eq!(transform("你好 ").unwrap(), String::from("你好"));
  }

  #[test]
  fn simple_group() {
    assert_eq!(transform("你好 (A B)").unwrap(), String::from("你好 (A B)"));
  }

  #[test]
  fn simple_negative() {
    assert_eq!(transform("A - B").unwrap(), String::from("A -B"));
  }

  #[test]
  fn group_negative() {
    assert_eq!(transform("A -(B C)").unwrap(), String::from("A -B -C"));
  }

  #[test]
  fn simple_convert() {
    let r = transform("简体中文").unwrap();
    assert!(
      vec![
        String::from("(简体中文 OR 簡體中文)"),
        String::from("(簡體中文 OR 简体中文)"),
      ].contains(&r),
      "{}", r,
    );
  }

  #[test]
  fn negative_convert() {
    let r = transform("你好 - 简体中文").unwrap();
    assert!(
      vec![
        String::from("你好 -简体中文 -簡體中文"),
        String::from("你好 -簡體中文 -简体中文"),
      ].contains(&r),
      "{}", r,
    );
  }

  #[test]
  fn group_convert() {
    let r = transform("依云 百合").unwrap();
    assert!(
      vec![
        String::from("(依云 OR 依雲) 百合"),
        String::from("(依雲 OR 依云) 百合"),
      ].contains(&r),
      "{}", r,
    );
  }

}

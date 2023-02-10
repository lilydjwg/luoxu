use nom::{
  IResult,
  Parser,
  sequence::{delimited, preceded, terminated},
  multi::{many0, many1},
  character::complete::char,
  bytes::complete::{is_a, is_not, tag},
};

#[derive(Debug, PartialEq)]
pub struct Term(pub String);

#[derive(Debug, PartialEq)]
pub enum Negative {
  Group(Group),
  Term(Term),
}

#[derive(Debug, PartialEq)]
pub enum Simple {
  Group(Group),
  Negative(Negative),
  Term(Term),
}

#[derive(Debug, PartialEq)]
pub struct Group(pub Vec<Simple>);

#[derive(Debug, PartialEq)]
pub struct Query(pub Vec<Simple>);

fn space(input: &str) -> IResult<&str, ()> {
  many0(is_a("\t "))
    .map(|_| ())
    .parse(input)
}

fn term(input: &str) -> IResult<&str, Term> {
  terminated(is_not("\t ()"), space)
    .map(|a| Term(String::from(a)))
    .parse(input)
}

fn negative(input: &str) -> IResult<&str, Negative> {
  preceded(
    terminated(tag("-"), space),
    group.map(Negative::Group)
    .or(term.map(Negative::Term))
  ).parse(input)
}

fn simple(input: &str) -> IResult<&str, Simple> {
  negative.map(Simple::Negative)
    .or(group.map(Simple::Group))
    .or(term.map(Simple::Term))
    .parse(input)
}

fn group(input: &str) -> IResult<&str, Group> {
  delimited(
    terminated(char('('), space),
    terminated(many1(simple), space),
    terminated(char(')'), space),
  ).map(Group)
    .parse(input)
}

pub fn query(input: &str) -> IResult<&str, Query> {
  many1(terminated(simple, space))
    .map(Query)
    .parse(input)
}

#[cfg(test)]
mod test {
  use super::*;

  fn fully_parsed_as<T: std::fmt::Debug + PartialEq>(r: IResult<&str, T>, expected: T) {
    if let Ok(("", a)) = r {
      assert_eq!(a, expected);
    } else {
      panic!("parse error or input remain");
    }
  }

  #[test]
  fn term_test() {
    fully_parsed_as(term("你好 "), Term(String::from("你好")));
  }

  #[test]
  fn combine_test() {
    fully_parsed_as(query("A B"), Query(vec![
        Simple::Term(Term(String::from("A"))),
        Simple::Term(Term(String::from("B"))),
    ]));
  }

  #[test]
  fn negative_test() {
    fully_parsed_as(query("A-B"), Query(vec![
        Simple::Term(Term(String::from("A-B"))),
    ]));
    fully_parsed_as(query("A -B"), Query(vec![
        Simple::Term(Term(String::from("A"))),
        Simple::Negative(Negative::Term(Term(String::from("B")))),
    ]));
    fully_parsed_as(query("A - B"), Query(vec![
        Simple::Term(Term(String::from("A"))),
        Simple::Negative(Negative::Term(Term(String::from("B")))),
    ]));
  }

  #[test]
  fn group_test() {
    fully_parsed_as(query("A (B C)"), Query(vec![
        Simple::Term(Term(String::from("A"))),
        Simple::Group(
          Group(vec![
            Simple::Term(Term(String::from("B"))),
            Simple::Term(Term(String::from("C"))),
          ])
        ),
    ]));
  }

  #[test]
  fn group_neg_test() {
    fully_parsed_as(query("A (B - C)"), Query(vec![
        Simple::Term(Term(String::from("A"))),
        Simple::Group(
          Group(vec![
            Simple::Term(Term(String::from("B"))),
            Simple::Negative(Negative::Term(Term(String::from("C")))),
          ])
        ),
    ]));
  }

}

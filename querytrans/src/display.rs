use std::fmt::{Display, Formatter, Result};
use super::parser::*;

impl Display for Query {
  fn fmt(&self, f: &mut Formatter<'_>) -> Result {
    if self.0.is_empty() {
      return Ok(());
    }
    let mut it = self.0.iter();
    write!(f, "{}", it.next().unwrap())?;
    for simp in it {
      write!(f, " {simp}")?;
    }
    Ok(())
  }
}

impl Display for Simple {
  fn fmt(&self, f: &mut Formatter<'_>) -> Result {
    match self {
      Simple::Group(a) => write!(f, "{a}"),
      Simple::Negative(a) => write!(f, "{a}"),
      Simple::Term(a) => write!(f, "{a}"),
    }
  }
}

impl Display for Group {
  fn fmt(&self, f: &mut Formatter<'_>) -> Result {
    if self.0.is_empty() {
      write!(f, "()")?;
      return Ok(());
    }
    write!(f, "(")?;
    let mut it = self.0.iter();
    write!(f, "{}", it.next().unwrap())?;
    for simp in it {
      write!(f, " {simp}")?;
    }
    write!(f, ")")?;
    Ok(())
  }
}

impl Display for Negative {
  fn fmt(&self, f: &mut Formatter<'_>) -> Result {
    match self {
      Negative::Group(a) => {
        let mut it = a.0.iter();
        write!(f, "-{}", it.next().unwrap())?;
        for b in it {
          write!(f, " -{b}")?;
        }
        Ok(())
      },
      Negative::Term(a) => write!(f, "-{a}"),
    }
  }
}

impl Display for Term {
  fn fmt(&self, f: &mut Formatter<'_>) -> Result {
    write!(f, "{}", self.0)
  }
}

#[cfg(test)]
mod test {
  use super::*;

  #[test]
  fn group_display() {
    let a = Group(vec![
      Simple::Term(Term(String::from("A"))),
      Simple::Term(Term(String::from("B"))),
    ]);
    assert_eq!(format!("{a}"), "(A B)");
  }

  #[test]
  fn negative_group_display() {
    let a = Negative::Group(Group(vec![
      Simple::Term(Term(String::from("A"))),
      Simple::Term(Term(String::from("B"))),
    ]));
    assert_eq!(format!("{a}"), "-A -B");
  }

}

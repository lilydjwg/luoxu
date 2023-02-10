#![feature(iter_intersperse)]

mod parser;
mod display;
mod transform;

use pyo3::prelude::*;

#[pyfunction]
#[pyo3(name = "transform")]
fn transform_py(s: &str) -> PyResult<String> {
  let r = transform::transform(s)?;
  Ok(r)
}

#[pymodule]
fn querytrans(_py: Python<'_>, m: &PyModule) -> PyResult<()> {
  m.add_function(wrap_pyfunction!(transform_py, m)?)?;
  Ok(())
}

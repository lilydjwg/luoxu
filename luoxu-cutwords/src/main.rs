use std::fs::File;
use std::io::{BufReader, BufRead, Write};
use std::collections::{HashSet, HashMap};

use eyre::{Result, eyre};
use tracing::{info, warn};
use tracing_subscriber::EnvFilter;
use jieba_rs::Jieba;
use postgres::{Client, NoTls};
use structopt::StructOpt;

mod db;

#[derive(Debug, StructOpt)]
#[structopt(name = "luoxu-cutwords", about = "load messages and analyze")]
struct Opt {
  dbstring: String,
  group_id: i64,
  endtime: u64,
  user_id: i64,
}

fn main() -> Result<()> {
  if std::env::var("RUST_LOG").is_err() {
    std::env::set_var("RUST_LOG", "warn")
  }
  if std::env::var("RUST_SPANTRACE").is_err() {
    std::env::set_var("RUST_SPANTRACE", "0");
  }
  color_eyre::install()?;
  tracing_subscriber::fmt::fmt()
    .with_writer(std::io::stderr)
    .with_env_filter(EnvFilter::from_default_env())
    .init();

  let opt = Opt::from_args();
  info!("connecting to database");
  let client = Client::connect(&opt.dbstring, NoTls)?;
  let msg_iter = db::MessageIter::new(
    client, opt.group_id, opt.endtime,
    if opt.user_id == 0 { None } else { Some(opt.user_id) },
  )?;

  info!("loading jieba");
  let mut jieba = Jieba::new();
  if let Err(e) = load_dict(&mut jieba) {
    warn!("failed to load userdict.txt: {:#}", e);
  }
  let stop_words = match load_stopwords() {
    Ok(s) => s,
    Err(e) => {
      warn!("failed to load StopWords-simple.txt: {:#}", e);
      HashSet::new()
    },
  };

  info!("Processing messages");
  let mut count = 0;
  let mut result = HashMap::new();
  'nextmsg: for msg in msg_iter {
    let msg = msg?;
    count += 1;
    if msg.is_empty() {
      continue;
    }
    if msg.starts_with("/luoxucloud") {
      continue;
    }
    if msg.starts_with("落絮词云为您生成消息词云") {
      continue;
    }
    for line in msg.split('\n') {
      for pat in ["[webpage]", "[poll]", "[file]", "[audio]"] {
        if line.starts_with(pat) {
          continue 'nextmsg;
        }
      }
      for tag in jieba.tag(line, true) {
        if STOP_FLAGS.contains(&tag.tag) || tag.word.len() > 21 {
          continue;
        }
        let word = tag.word.to_lowercase();
        if stop_words.contains(&word) {
          continue;
        }
        let c = result.entry(word).or_insert(0);
        *c += 1;
      }
    }
  }

  let stdout = std::io::stdout();
  let mut stdout = stdout.lock();
  writeln!(stdout, "{}", count)?;
  for (k, v) in result {
    writeln!(stdout, "{} {}", k, v)?;
  }

  Ok(())
}

fn load_dict(jieba: &mut Jieba) -> Result<()> {
  let mut f = BufReader::new(File::open("userdict.txt")?);
  let mut buf = String::new();
  while f.read_line(&mut buf)? > 0 {
    let mut it = buf.trim().split_whitespace();
    let word = it.next().ok_or_else(|| eyre!("bad dict line: {}", buf))?;
    let tag = Some(it.next().ok_or_else(|| eyre!("bad dict line: {}", buf))?);
    jieba.add_word(word, None, tag);
    buf.clear();
  }
  Ok(())
}

fn load_stopwords() -> Result<HashSet<String>> {
  let f = BufReader::new(File::open("StopWords-simple.txt")?);
  let mut set = HashSet::new();
  for line in f.lines() {
    let line = line?;
    set.insert(line);
  }
  Ok(set)
}

const STOP_FLAGS: &[&str] = &[
  "d",  // 副词
  "f",  // 方位名词
  "x",  // 标点符号（文档说是 w 但是实际测试是 x
  "p",  // 介词
  "t",  // 时间
  "q",  // 量词
  "m",  // 数量词
  "nr", // 人名，你我他
  "r",  // 代词
  "c",  // 连词
  "e",  // 文档没说，看着像语气词
  "xc", // 其他虚词
  "zg", // 文档没说，给出的词也没找到规律，但都不是想要的
  "y",  // 文档没说，看着像语气词
  // u 开头的都是助词，具体细分的分类文档没说
  "uj",
  "ug",
  "ul",
  "ud",
];


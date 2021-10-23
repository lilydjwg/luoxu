use std::mem::swap;
use std::time;

use eyre::Result;
use tracing::info;
use postgres::{Client, Statement};

struct Message {
  msgid: i64,
  text: String,
}

pub struct MessageIter {
  client: Client,
  statement: Statement,
  errored: bool,
  done: bool,

  rows: Vec<Message>,
  last_idx: usize,
  last_msgid: i64,

  group_id: i64,
  endtime: time::SystemTime,
  user_id: Option<i64>,
}

impl MessageIter {
  pub fn new(
    mut client: Client,
    group_id: i64, endtime: u64, user_id: Option<i64>,
  ) -> Result<Self> {
    let statement = client.prepare(
      match user_id {
        Some(_) => r"
          SELECT msgid, text FROM messages
          WHERE msgid < $1
            and group_id = $2
            and created_at > $3
            and from_user = $4
          ORDER BY msgid DESC LIMIT 1000
        ",
        None => r"
          SELECT msgid, text FROM messages
          WHERE msgid < $1
            and group_id = $2
            and created_at > $3
          ORDER BY msgid DESC LIMIT 1000
        ",
      }
    )?;
    Ok(MessageIter {
      client,
      statement,
      errored: false,
      done: false,

      rows: Vec::new(),
      last_idx: 0,
      last_msgid: i64::MAX,

      group_id,
      endtime: time::SystemTime::UNIX_EPOCH + time::Duration::from_secs(endtime),
      user_id,
    })
  }
}

impl Iterator for MessageIter {
  type Item = Result<String>;

  fn next(&mut self) -> Option<Self::Item> {
    if self.errored {
      return None;
    }

    if self.last_idx == self.rows.len() {
      if self.done {
        return None;
      }

      info!("query database for messages");
      let rows = match self.user_id {
        Some(uid) => self.client.query(
          &self.statement,
          &[
            &self.last_msgid,
            &self.group_id,
            &self.endtime,
            &uid,
          ],
        ),
        None => self.client.query(
          &self.statement,
          &[
            &self.last_msgid,
            &self.group_id,
            &self.endtime,
          ],
        ),
      };

      if let Err(e) = rows {
        self.errored = true;
        return Some(Err(e.into()));
      }
      let rows = rows.unwrap();

      let messages: Vec<Message> = rows.iter().map(|row| Message {
        msgid: row.get(0),
        text: row.get(1),
      }).collect();
      if messages.len() < 1000 {
        self.done = true;
      }
      self.last_idx = 0;
      self.rows = messages;
      if self.rows.is_empty() {
        return None;
      } else {
        self.last_msgid = self.rows[self.rows.len()-1].msgid;
      }
    }

    let mut ret = String::new();
    swap(&mut self.rows[self.last_idx].text, &mut ret);
    self.last_idx += 1;
    Some(Ok(ret))
  }
}

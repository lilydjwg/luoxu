from contextvars import ContextVar

msg_source = ContextVar('msg_source', default=None)
group_title = ContextVar('group_title', default=None)

from contextvars import ContextVar

msg_source = ContextVar('msg_source', default=None)

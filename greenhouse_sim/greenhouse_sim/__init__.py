"""The simulator. Its modules log through loggers named after them, under
this package's; as a library it leaves where they go to the application,
and prints nothing until one configures logging (AUDIT.14)."""

import logging

logging.getLogger(__name__).addHandler(logging.NullHandler())

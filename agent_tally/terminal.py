"""Terminal output that also works with legacy redirected Windows encodings."""
import sys

import click


def echo(message="", *, file=None, nl=True):
    stream = file if file is not None else sys.stdout
    encoding = getattr(stream, "encoding", None) or "utf-8"
    text = str(message).encode(encoding, errors="replace").decode(encoding)
    click.echo(text, file=stream, nl=nl)

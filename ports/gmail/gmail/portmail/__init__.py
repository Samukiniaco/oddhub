"""PortMail: cliente de email IMAP/SMTP para PortMaster.

Port da colecao OddHub. O id dele no registro da colecao e "gmail", mas o
nome do port e PortMail: o cliente fala IMAP e SMTP com qualquer provedor,
Gmail incluido, e nao tem nada da marca de um servico de email.
"""

from .config import APP_ID, APP_NAME, APP_VERSION  # noqa: F401

__all__ = ["APP_ID", "APP_NAME", "APP_VERSION"]

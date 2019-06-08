
class EsiTokenRejected(Exception):
    """Raised when ESI token was deleted by CCP"""
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

    def __str__(self):
        return "ESI Token/application deleted by user."


class EsiDuplicateCharacterExists(Exception):
    """Raised when a user tries to add a character that's associated with another account."""
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

    def __str__(self):
        return "User tried to add a character that's associated with another account."


class EsiTimeout(Exception):
    """Raised when ESI or Oauth2 endpoints time out."""
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

    def __str__(self):
        return "ESI endpoint timed out"

class EsiDuplicateXMLCharacterExists(Exception):
    """Raised when ESI or Oauth2 endpoints time out."""
    def __init__(self,*args,**kwargs):
        Exception.__init__(self,*args,**kwargs)

    def __str__(self):
        return "User tried to add an ESI character that the XML api believes belongs to another auth account"
"""
Standard definitions that don't change.
"""

ESI_KEY_DELETED_BY_EVEOAUTH = 0
ESI_KEY_REPLACED_BY_OWNER = 1
ESI_KEY_DELETED_BY_SYSADMIN = 2

ESI_KEY_REMOVAL_REASON = (
    (ESI_KEY_DELETED_BY_EVEOAUTH, "The Test Auth app was deleted by the user on the eve website."),
    (ESI_KEY_REPLACED_BY_OWNER,"The character's owner replaced this key with a newer key."),
    (ESI_KEY_DELETED_BY_SYSADMIN,"This key was deleted by a sysadmin, for whatever reason."),
)


ESI_SCOPE_DEFAULT = 0
ESI_SCOPE_ALLIED = 1

ESI_SCOPE_CHOICES = (
    (ESI_SCOPE_DEFAULT, "Default Scopes"),
    (ESI_SCOPE_ALLIED, "Allied Scopes"),
)

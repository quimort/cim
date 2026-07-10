"""Domain exceptions raised by the service layer.

Services know nothing about HTTP. They raise these; ``main.py`` registers the
handlers that turn each one into a status code. That keeps the routers as thin
translators rather than a wall of ``try/except HTTPException``.
"""


class DomainError(Exception):
    """Base for every error the service layer raises deliberately."""


class NotFoundError(DomainError):
    """A row does not exist, or belongs to another owner.

    Deliberately the same error in both cases: answering 403 for a row owned by
    somebody else would confirm that the row exists.
    """


class ConflictError(DomainError):
    """The request collides with the current state (duplicate name, already voided)."""


class DomainRuleError(DomainError):
    """The request is well-formed but breaks a rule the schema could not check.

    Typically because the rule depends on stored state: an inactive account, or
    loan fields on an instrument whose persisted ``asset_class`` is not ``loan``.
    """

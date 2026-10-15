"""Custom exceptions so callers can tell *why* something failed."""


class DroneRouteError(Exception):
    """Base class for every error raised by this project."""


class InvalidInputError(DroneRouteError, ValueError):
    """The user supplied data that cannot be used (bad number, duplicate name, ...)."""


class ProblemTooLargeError(DroneRouteError):
    """An exact algorithm was asked to solve more delivery stops than it supports."""

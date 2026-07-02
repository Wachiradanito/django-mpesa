from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("django-mpesa")
except PackageNotFoundError:  # pragma: no cover
    # Running from source without being installed
    __version__ = "0.0.0-dev"

__all__ = ["__version__"]

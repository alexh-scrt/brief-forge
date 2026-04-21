"""Brief Forge package initializer.

Exposes the Flask application factory function ``create_app`` so that
the package can be imported and the app instantiated with a single call.
Also sets the package-level ``__version__`` string.

Example usage::

    from brief_forge import create_app

    app = create_app()
    app.run()
"""

from __future__ import annotations

__version__ = "0.1.0"
__author__ = "Brief Forge Contributors"
__all__ = ["create_app"]


def create_app() -> "Flask":  # type: ignore[name-defined]  # noqa: F821
    """Application factory — import and delegate to ``brief_forge.app``.

    Keeping this thin wrapper here means callers only need to import from
    the top-level package rather than the ``app`` sub-module.  The real
    factory logic lives in :mod:`brief_forge.app`.

    Returns
    -------
    Flask
        A fully configured Flask application instance.
    """
    # Deferred import so that the package can be imported cheaply without
    # pulling in Flask and all its transitive dependencies at import time.
    from brief_forge.app import create_app as _create_app  # noqa: PLC0415

    return _create_app()

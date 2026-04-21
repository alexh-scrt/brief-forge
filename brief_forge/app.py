"""Flask application factory and route definitions for Brief Forge.

This module implements the Flask web application that powers the Brief Forge
UI.  It exposes a single public factory function :func:`create_app` that
configures and returns a ready-to-use :class:`flask.Flask` instance.

Routes
------
``GET /``
    Renders the main single-page UI (``index.html``).

``POST /generate``
    Accepts a JSON body ``{"description": "..."}`` (or a form field with the
    same name), calls :func:`~brief_forge.generator.generate_brief`, formats
    the result in all three output formats, and returns a JSON response
    containing the structured brief data plus the rendered format strings.

``POST /format``
    Accepts a JSON body ``{"brief": {...}, "format": "markdown"|"text"|"json"}``
    and returns the brief rendered in the requested format.  Useful for
    client-side format switching without re-generating the brief.

Error handling
--------------
All routes return structured JSON error responses with an ``error`` key and
an appropriate HTTP status code so the frontend can display meaningful
messages to the user.

Configuration
-------------
The factory reads all configuration from environment variables (loaded via
``python-dotenv``) — no hardcoded secrets.  See ``.env.example`` for the
full list of supported variables.

Example usage (development)::

    from brief_forge.app import create_app

    app = create_app()
    app.run(debug=True)

Or via the installed entry point::

    briefforge
"""

from __future__ import annotations

import logging
import os
import secrets
from typing import Any

from dotenv import load_dotenv
from flask import Flask, Response, jsonify, render_template, request
from openai import APIConnectionError, APIError, APITimeoutError, RateLimitError
from pydantic import ValidationError

from brief_forge.formatter import format_brief, format_json, format_markdown, format_plain_text
from brief_forge.generator import generate_brief
from brief_forge.models import DesignBrief

# Load .env file as early as possible so all os.environ reads pick up values.
load_dotenv()

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Application factory
# ---------------------------------------------------------------------------


def create_app() -> Flask:
    """Create and configure the Flask application.

    Reads configuration from environment variables (populated via
    ``python-dotenv`` / ``.env`` file).  The factory pattern allows the app
    to be instantiated multiple times with different configurations, which is
    especially useful for testing.

    Returns
    -------
    Flask
        A fully configured, ready-to-run Flask application instance.

    Raises
    ------
    RuntimeError
        If ``FLASK_SECRET_KEY`` is not set in the environment (in production).
    """
    app = Flask(
        __name__,
        template_folder="templates",
        static_folder="static",
    )

    _configure_app(app)
    _configure_logging(app)
    _register_routes(app)
    _register_error_handlers(app)

    logger.info(
        "Brief Forge application created (env=%s).",
        app.config.get("ENV", "production"),
    )
    return app


# ---------------------------------------------------------------------------
# Configuration helpers
# ---------------------------------------------------------------------------


def _configure_app(app: Flask) -> None:
    """Apply configuration values to the Flask app instance.

    Reads from environment variables with sensible defaults.  A
    ``FLASK_SECRET_KEY`` is required in production; in development a
    random key is generated automatically with a warning.

    Parameters
    ----------
    app:
        The :class:`flask.Flask` instance to configure.
    """
    # Secret key — required for session signing.
    secret_key = os.environ.get("FLASK_SECRET_KEY", "").strip()
    if not secret_key:
        flask_env = os.environ.get("FLASK_ENV", "production").strip().lower()
        if flask_env == "production":
            raise RuntimeError(
                "FLASK_SECRET_KEY environment variable must be set in production. "
                "Generate one with: python -c \"import secrets; print(secrets.token_hex(32))\""
            )
        # Development: generate a random key with a warning.
        secret_key = secrets.token_hex(32)
        logger.warning(
            "FLASK_SECRET_KEY not set — using a randomly generated key. "
            "Sessions will be invalidated on every restart. "
            "Set FLASK_SECRET_KEY in your .env file."
        )

    app.config["SECRET_KEY"] = secret_key

    # Environment / debug mode.
    flask_env = os.environ.get("FLASK_ENV", "production").strip().lower()
    app.config["ENV"] = flask_env
    app.config["DEBUG"] = flask_env == "development"

    # JSON settings — keep key order and pretty-print in debug.
    app.config["JSON_SORT_KEYS"] = False

    # Maximum content length for incoming requests (16 MB).
    app.config["MAX_CONTENT_LENGTH"] = 16 * 1024 * 1024


def _configure_logging(app: Flask) -> None:
    """Configure application-level logging.

    In development mode, sets the log level to DEBUG for the ``brief_forge``
    logger hierarchy.  In production, INFO is used.

    Parameters
    ----------
    app:
        The configured :class:`flask.Flask` instance.
    """
    log_level = logging.DEBUG if app.config.get("DEBUG") else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )
    logging.getLogger("brief_forge").setLevel(log_level)
    logging.getLogger("openai").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def _register_routes(app: Flask) -> None:
    """Attach all URL routes to the Flask application.

    Parameters
    ----------
    app:
        The :class:`flask.Flask` instance to register routes on.
    """

    # ------------------------------------------------------------------ #
    #  GET /  — Main UI                                                    #
    # ------------------------------------------------------------------ #

    @app.route("/", methods=["GET"])
    def index() -> str:
        """Render the main single-page UI.

        Returns
        -------
        str
            Rendered HTML of the index template.
        """
        return render_template("index.html")

    # ------------------------------------------------------------------ #
    #  POST /generate  — Brief generation endpoint                         #
    # ------------------------------------------------------------------ #

    @app.route("/generate", methods=["POST"])
    def generate() -> Response:
        """Generate a design brief from a plain-language description.

        Accepts either:

        - ``application/json`` body with a ``"description"`` key, or
        - ``application/x-www-form-urlencoded`` / ``multipart/form-data``
          with a ``description`` field.

        Returns
        -------
        flask.Response
            JSON response containing:

            ``success`` (bool)
                Whether generation succeeded.
            ``brief`` (dict)
                The structured brief data (present on success).
            ``formats`` (dict)
                Pre-rendered output strings keyed by format name
                (``"markdown"``, ``"text"``, ``"json"``).  Present on success.
            ``error`` (str)
                Human-readable error description (present on failure).
            ``error_type`` (str)
                Machine-readable error category (present on failure).

        HTTP status codes
        -----------------
        200 OK
            Brief generated successfully.
        400 Bad Request
            ``description`` field missing or empty.
        429 Too Many Requests
            OpenAI rate limit exceeded.
        500 Internal Server Error
            Any other error (misconfiguration, parse failure, etc.).
        502 Bad Gateway
            OpenAI API connection or timeout error.
        """
        description = _extract_description_from_request()

        if description is None:
            return _error_response(
                error="The 'description' field is required.",
                error_type="missing_field",
                status=400,
            )

        if not description.strip():
            return _error_response(
                error="The 'description' field must not be empty.",
                error_type="empty_field",
                status=400,
            )

        if len(description) > 4000:
            return _error_response(
                error=(
                    f"Description is too long ({len(description)} characters). "
                    "Please keep it under 4000 characters."
                ),
                error_type="input_too_long",
                status=400,
            )

        logger.info(
            "Generating brief for description (length=%d).",
            len(description),
        )

        try:
            brief = generate_brief(description)
        except ValueError as exc:
            logger.warning("Brief generation failed (ValueError): %s", exc)
            return _error_response(
                error=str(exc),
                error_type="generation_error",
                status=500,
            )
        except RuntimeError as exc:
            logger.error("Brief generation failed (RuntimeError): %s", exc)
            return _error_response(
                error=str(exc),
                error_type="configuration_error",
                status=500,
            )
        except RateLimitError as exc:
            logger.warning("OpenAI rate limit exceeded: %s", exc)
            return _error_response(
                error=(
                    "The OpenAI API rate limit has been exceeded. "
                    "Please wait a moment and try again."
                ),
                error_type="rate_limit",
                status=429,
            )
        except (APIConnectionError, APITimeoutError) as exc:
            logger.error("OpenAI API connection/timeout error: %s", exc)
            return _error_response(
                error=(
                    "Could not reach the OpenAI API. "
                    "Please check your internet connection and try again."
                ),
                error_type="api_connection_error",
                status=502,
            )
        except APIError as exc:
            logger.error("OpenAI API error: %s", exc)
            return _error_response(
                error=f"OpenAI API error: {exc.message if hasattr(exc, 'message') else str(exc)}",
                error_type="api_error",
                status=500,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during brief generation: %s", exc)
            return _error_response(
                error="An unexpected error occurred. Please try again.",
                error_type="unexpected_error",
                status=500,
            )

        # Render the brief in all three output formats.
        try:
            rendered_formats = _render_all_formats(brief)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Error rendering brief formats: %s", exc)
            return _error_response(
                error="Brief was generated but could not be formatted. Please try again.",
                error_type="format_error",
                status=500,
            )

        brief_dict = brief.to_dict()

        logger.info("Brief generated successfully: %r", brief.title)

        return jsonify(
            {
                "success": True,
                "brief": brief_dict,
                "formats": rendered_formats,
            }
        )

    # ------------------------------------------------------------------ #
    #  POST /format  — Re-format an existing brief                         #
    # ------------------------------------------------------------------ #

    @app.route("/format", methods=["POST"])
    def reformat() -> Response:
        """Re-render an existing brief dict in a requested output format.

        Accepts a JSON body with:

        ``brief`` (dict)
            A previously generated brief dict matching the
            :class:`~brief_forge.models.DesignBrief` schema.
        ``format`` (str)
            One of ``"markdown"``, ``"text"``, or ``"json"``.

        Returns
        -------
        flask.Response
            JSON response containing:

            ``success`` (bool)
                Whether formatting succeeded.
            ``output`` (str)
                The rendered brief string (present on success).
            ``format`` (str)
                The format that was applied (present on success).
            ``error`` (str)
                Human-readable error description (present on failure).
            ``error_type`` (str)
                Machine-readable error category (present on failure).

        HTTP status codes
        -----------------
        200 OK
            Brief formatted successfully.
        400 Bad Request
            Missing fields, invalid format name, or invalid brief data.
        500 Internal Server Error
            Unexpected formatting error.
        """
        data = _get_json_body()
        if data is None:
            return _error_response(
                error="Request body must be valid JSON.",
                error_type="invalid_json",
                status=400,
            )

        brief_data = data.get("brief")
        output_format = data.get("format", "").strip()

        if not brief_data:
            return _error_response(
                error="The 'brief' field is required and must not be empty.",
                error_type="missing_field",
                status=400,
            )

        if not output_format:
            return _error_response(
                error="The 'format' field is required (one of: markdown, text, json).",
                error_type="missing_field",
                status=400,
            )

        # Reconstruct the DesignBrief from the supplied dict.
        try:
            brief = DesignBrief.from_dict(brief_data)
        except (ValidationError, ValueError) as exc:
            logger.warning("Invalid brief data supplied to /format: %s", exc)
            return _error_response(
                error=f"Invalid brief data: {exc}",
                error_type="invalid_brief",
                status=400,
            )

        # Render in the requested format.
        try:
            output = format_brief(brief, output_format)
        except ValueError as exc:
            return _error_response(
                error=str(exc),
                error_type="unsupported_format",
                status=400,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Unexpected error during /format: %s", exc)
            return _error_response(
                error="An unexpected error occurred while formatting the brief.",
                error_type="format_error",
                status=500,
            )

        return jsonify(
            {
                "success": True,
                "output": output,
                "format": output_format.strip().lower(),
            }
        )

    # ------------------------------------------------------------------ #
    #  GET /health  — Health check                                         #
    # ------------------------------------------------------------------ #

    @app.route("/health", methods=["GET"])
    def health() -> Response:
        """Simple health-check endpoint.

        Returns
        -------
        flask.Response
            JSON ``{"status": "ok"}`` with HTTP 200.
        """
        return jsonify({"status": "ok", "version": "0.1.0"})


# ---------------------------------------------------------------------------
# Error handlers
# ---------------------------------------------------------------------------


def _register_error_handlers(app: Flask) -> None:
    """Register global HTTP error handlers on the Flask application.

    These handlers ensure that even unhandled Flask errors (404, 405, 413,
    500) return JSON responses rather than HTML pages, which is more
    consistent for a JSON API.

    Parameters
    ----------
    app:
        The :class:`flask.Flask` instance to register error handlers on.
    """

    @app.errorhandler(400)
    def bad_request(exc: Exception) -> Response:
        """Handle 400 Bad Request errors."""
        return _error_response(
            error=str(exc),
            error_type="bad_request",
            status=400,
        )

    @app.errorhandler(404)
    def not_found(exc: Exception) -> Response:
        """Handle 404 Not Found errors."""
        return _error_response(
            error="The requested resource was not found.",
            error_type="not_found",
            status=404,
        )

    @app.errorhandler(405)
    def method_not_allowed(exc: Exception) -> Response:
        """Handle 405 Method Not Allowed errors."""
        return _error_response(
            error="HTTP method not allowed for this endpoint.",
            error_type="method_not_allowed",
            status=405,
        )

    @app.errorhandler(413)
    def request_entity_too_large(exc: Exception) -> Response:
        """Handle 413 Request Entity Too Large errors."""
        return _error_response(
            error="Request body is too large. Please reduce the size of your input.",
            error_type="request_too_large",
            status=413,
        )

    @app.errorhandler(500)
    def internal_server_error(exc: Exception) -> Response:
        """Handle 500 Internal Server Error errors."""
        logger.exception("Unhandled 500 error: %s", exc)
        return _error_response(
            error="An internal server error occurred. Please try again.",
            error_type="internal_server_error",
            status=500,
        )


# ---------------------------------------------------------------------------
# Internal utilities
# ---------------------------------------------------------------------------


def _extract_description_from_request() -> str | None:
    """Extract the design description from the current Flask request.

    Supports both JSON bodies (``{"description": "..."}``)
    and form-encoded data (``description=...``).

    Returns
    -------
    str or None
        The raw description string, or ``None`` if the field is absent.
    """
    # Try JSON body first.
    if request.is_json:
        body = request.get_json(silent=True) or {}
        if "description" in body:
            return str(body["description"]) if body["description"] is not None else None

    # Fall back to form data.
    if request.form:
        value = request.form.get("description")
        if value is not None:
            return value

    # Try JSON even if Content-Type header is missing.
    body = request.get_json(force=True, silent=True)
    if body and isinstance(body, dict) and "description" in body:
        return str(body["description"]) if body["description"] is not None else None

    return None


def _get_json_body() -> dict[str, Any] | None:
    """Parse and return the JSON request body as a dictionary.

    Returns
    -------
    dict[str, Any] or None
        Parsed body dict, or ``None`` if the body is absent or not valid JSON.
    """
    body = request.get_json(silent=True, force=True)
    if isinstance(body, dict):
        return body
    return None


def _render_all_formats(brief: DesignBrief) -> dict[str, str]:
    """Render a :class:`~brief_forge.models.DesignBrief` in all supported formats.

    Parameters
    ----------
    brief:
        The design brief to render.

    Returns
    -------
    dict[str, str]
        Dictionary with keys ``"markdown"``, ``"text"``, and ``"json"``,
        each mapping to the corresponding rendered string.
    """
    return {
        "markdown": format_markdown(brief),
        "text": format_plain_text(brief),
        "json": format_json(brief),
    }


def _error_response(
    error: str,
    error_type: str,
    status: int,
) -> Response:
    """Build a structured JSON error response.

    Parameters
    ----------
    error:
        Human-readable error description shown to the user.
    error_type:
        Machine-readable error category for client-side handling.
    status:
        HTTP status code.

    Returns
    -------
    flask.Response
        A JSON response with ``success: false``, ``error``, and
        ``error_type`` fields, plus the given HTTP status code.
    """
    response = jsonify(
        {
            "success": False,
            "error": error,
            "error_type": error_type,
        }
    )
    response.status_code = status
    return response


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """Run the Brief Forge development server.

    This function is registered as the ``briefforge`` console-script entry
    point in ``pyproject.toml``.  It reads ``FLASK_HOST`` and ``FLASK_PORT``
    from the environment and starts Flask's built-in development server.

    .. warning::
        This server is **not** suitable for production use.  Deploy behind
        a WSGI server such as Gunicorn or uWSGI for production workloads.
    """
    load_dotenv()  # Ensure env is loaded even when called as a script.

    host = os.environ.get("FLASK_HOST", "127.0.0.1").strip()
    port_str = os.environ.get("FLASK_PORT", "5000").strip()
    try:
        port = int(port_str)
    except ValueError:
        logger.warning(
            "Invalid FLASK_PORT value %r — defaulting to 5000.", port_str
        )
        port = 5000

    flask_env = os.environ.get("FLASK_ENV", "production").strip().lower()
    debug = flask_env == "development"

    app = create_app()

    logger.info(
        "Starting Brief Forge on http://%s:%d (debug=%s)", host, port, debug
    )
    app.run(host=host, port=port, debug=debug)


if __name__ == "__main__":
    main()

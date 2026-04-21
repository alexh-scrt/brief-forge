"""Unit and integration tests for the Brief Forge Flask application (brief_forge/app.py).

Covers:
- Application factory :func:`~brief_forge.app.create_app` configuration.
- ``GET /`` — index route rendering.
- ``POST /generate`` — brief generation endpoint (happy path and error paths).
- ``POST /format`` — brief re-formatting endpoint.
- ``GET /health`` — health check.
- Global HTTP error handlers (404, 405, 413, 500).
- Internal utilities :func:`~brief_forge.app._extract_description_from_request`,
  :func:`~brief_forge.app._render_all_formats`, :func:`~brief_forge.app._error_response`.

All tests use the Flask test client and mock external dependencies so that:
- No real OpenAI API calls are made.
- No ``OPENAI_API_KEY`` is required in the test environment.
- Tests run quickly and deterministically.
"""

from __future__ import annotations

import json
import os
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from flask import Flask
from flask.testing import FlaskClient

from brief_forge.app import create_app, _render_all_formats
from brief_forge.models import (
    ColorPalette,
    ColorSwatch,
    DesignBrief,
    Layout,
    TypographyPairing,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    """Create a Flask test application with a pre-set secret key."""
    monkeypatch.setenv("FLASK_SECRET_KEY", "test-secret-key-for-testing")
    monkeypatch.setenv("FLASK_ENV", "development")
    monkeypatch.setenv("OPENAI_API_KEY", "sk-test-key")
    return create_app()


@pytest.fixture()
def client(app: Flask) -> FlaskClient:
    """Return a Flask test client for the application."""
    app.config["TESTING"] = True
    return app.test_client()


@pytest.fixture()
def sample_brief() -> DesignBrief:
    """Return a complete, valid DesignBrief for use in tests."""
    return DesignBrief(
        title="Eco Coffee Landing Page",
        project_overview=(
            "A conversion-focused landing page for a sustainable coffee "
            "subscription brand targeting millennials."
        ),
        mood_descriptors=["earthy", "premium", "warm", "approachable"],
        color_palette=ColorPalette(
            swatches=[
                ColorSwatch(role="Primary", name="Espresso Brown", hex_code="#3B2314", usage="Headlines"),
                ColorSwatch(role="Secondary", name="Sage Green", hex_code="#7D9B76", usage="Accents"),
                ColorSwatch(role="Background", name="Oat Cream", hex_code="#F5EFE6", usage="Page BG"),
                ColorSwatch(role="Surface", name="Warm Sand", hex_code="#E8D9C5", usage="Cards"),
                ColorSwatch(role="Text", name="Dark Roast", hex_code="#1A1008", usage="Body copy"),
            ]
        ),
        typography=TypographyPairing(
            display_font="Playfair Display",
            body_font="Inter",
            accent_font="Playfair Display Italic",
            display_weight="700",
            body_weight="400",
            notes="Use 1.6 line-height.",
        ),
        layout=Layout(
            description="Single-column hero with full-bleed background.",
            grid="12-column, 24px gutter",
            sections=["Hero", "Social proof", "Product showcase", "Email capture", "Footer"],
            spacing_notes="80px section padding.",
        ),
        copy_hierarchy=[
            "H1: Good coffee. Good planet.",
            "H2: Ethically sourced.",
            "CTA: Start My Subscription",
        ],
        additional_notes="Keep tone warm but authoritative.",
    )


@pytest.fixture()
def sample_brief_dict(sample_brief: DesignBrief) -> dict[str, Any]:
    """Return the sample brief as a plain dictionary."""
    return sample_brief.to_dict()


# ---------------------------------------------------------------------------
# create_app / configuration
# ---------------------------------------------------------------------------


class TestCreateApp:
    """Tests for the create_app factory function."""

    def test_returns_flask_instance(self, app: Flask) -> None:
        assert isinstance(app, Flask)

    def test_secret_key_set(self, app: Flask) -> None:
        assert app.config["SECRET_KEY"] == "test-secret-key-for-testing"

    def test_debug_mode_in_development(self, app: Flask) -> None:
        assert app.config["DEBUG"] is True

    def test_production_raises_without_secret_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        with pytest.raises(RuntimeError, match="FLASK_SECRET_KEY"):
            create_app()

    def test_development_auto_generates_secret_key(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FLASK_ENV", "development")
        monkeypatch.delenv("FLASK_SECRET_KEY", raising=False)
        app = create_app()
        assert app.config["SECRET_KEY"]  # non-empty
        assert isinstance(app.config["SECRET_KEY"], str)

    def test_debug_false_in_production(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("FLASK_ENV", "production")
        monkeypatch.setenv("FLASK_SECRET_KEY", "prod-secret-key")
        app = create_app()
        assert app.config["DEBUG"] is False

    def test_template_folder_configured(self, app: Flask) -> None:
        assert app.template_folder == "templates"

    def test_static_folder_configured(self, app: Flask) -> None:
        assert app.static_folder is not None


# ---------------------------------------------------------------------------
# GET /
# ---------------------------------------------------------------------------


class TestIndexRoute:
    """Tests for the GET / route."""

    def test_index_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert response.status_code == 200

    def test_index_content_type_html(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert "text/html" in response.content_type

    def test_index_response_not_empty(self, client: FlaskClient) -> None:
        response = client.get("/")
        assert len(response.data) > 0


# ---------------------------------------------------------------------------
# GET /health
# ---------------------------------------------------------------------------


class TestHealthRoute:
    """Tests for the GET /health route."""

    def test_health_returns_200(self, client: FlaskClient) -> None:
        response = client.get("/health")
        assert response.status_code == 200

    def test_health_returns_json(self, client: FlaskClient) -> None:
        response = client.get("/health")
        data = response.get_json()
        assert data is not None

    def test_health_status_ok(self, client: FlaskClient) -> None:
        response = client.get("/health")
        data = response.get_json()
        assert data["status"] == "ok"

    def test_health_contains_version(self, client: FlaskClient) -> None:
        response = client.get("/health")
        data = response.get_json()
        assert "version" in data


# ---------------------------------------------------------------------------
# POST /generate — happy path
# ---------------------------------------------------------------------------


class TestGenerateRouteHappyPath:
    """Tests for the POST /generate route — successful generation."""

    def test_returns_200_on_success(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand landing page."},
            )
        assert response.status_code == 200

    def test_response_success_true(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert data["success"] is True

    def test_response_contains_brief(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert "brief" in data
        assert isinstance(data["brief"], dict)

    def test_response_brief_has_title(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert data["brief"]["title"] == "Eco Coffee Landing Page"

    def test_response_contains_formats(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert "formats" in data
        assert "markdown" in data["formats"]
        assert "text" in data["formats"]
        assert "json" in data["formats"]

    def test_markdown_format_is_string(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert isinstance(data["formats"]["markdown"], str)
        assert len(data["formats"]["markdown"]) > 0

    def test_text_format_is_string(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert isinstance(data["formats"]["text"], str)
        assert len(data["formats"]["text"]) > 0

    def test_json_format_is_string(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        data = response.get_json()
        assert isinstance(data["formats"]["json"], str)
        # The JSON format string should itself be valid JSON.
        parsed = json.loads(data["formats"]["json"])
        assert isinstance(parsed, dict)

    def test_generate_brief_called_with_description(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief) as mock_gen:
            client.post(
                "/generate",
                json={"description": "A coffee brand landing page."},
            )
        mock_gen.assert_called_once_with("A coffee brand landing page.")

    def test_accepts_form_encoded_description(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                data={"description": "A coffee brand."},
            )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True

    def test_response_content_type_json(
        self,
        client: FlaskClient,
        sample_brief: DesignBrief,
    ) -> None:
        with patch("brief_forge.app.generate_brief", return_value=sample_brief):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert "application/json" in response.content_type


# ---------------------------------------------------------------------------
# POST /generate — error paths
# ---------------------------------------------------------------------------


class TestGenerateRouteErrors:
    """Tests for POST /generate error handling."""

    def test_missing_description_returns_400(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={})
        assert response.status_code == 400

    def test_missing_description_error_message(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={})
        data = response.get_json()
        assert data["success"] is False
        assert "description" in data["error"].lower()

    def test_empty_description_returns_400(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={"description": ""})
        assert response.status_code == 400

    def test_whitespace_description_returns_400(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={"description": "   "})
        assert response.status_code == 400

    def test_description_too_long_returns_400(
        self, client: FlaskClient
    ) -> None:
        long_description = "x" * 4001
        response = client.post("/generate", json={"description": long_description})
        assert response.status_code == 400

    def test_description_too_long_error_type(
        self, client: FlaskClient
    ) -> None:
        long_description = "x" * 4001
        response = client.post("/generate", json={"description": long_description})
        data = response.get_json()
        assert data["error_type"] == "input_too_long"

    def test_value_error_from_generator_returns_500(
        self, client: FlaskClient
    ) -> None:
        with patch(
            "brief_forge.app.generate_brief",
            side_effect=ValueError("Could not parse response"),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 500
        data = response.get_json()
        assert data["success"] is False
        assert data["error_type"] == "generation_error"

    def test_runtime_error_from_generator_returns_500(
        self, client: FlaskClient
    ) -> None:
        with patch(
            "brief_forge.app.generate_brief",
            side_effect=RuntimeError("OPENAI_API_KEY not set"),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 500
        data = response.get_json()
        assert data["error_type"] == "configuration_error"

    def test_rate_limit_error_returns_429(
        self, client: FlaskClient
    ) -> None:
        from openai import RateLimitError

        mock_response = MagicMock()
        mock_response.status_code = 429
        with patch(
            "brief_forge.app.generate_brief",
            side_effect=RateLimitError(
                message="Rate limit exceeded",
                response=mock_response,
                body={},
            ),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 429
        data = response.get_json()
        assert data["error_type"] == "rate_limit"

    def test_api_connection_error_returns_502(
        self, client: FlaskClient
    ) -> None:
        from openai import APIConnectionError

        with patch(
            "brief_forge.app.generate_brief",
            side_effect=APIConnectionError(request=MagicMock()),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 502
        data = response.get_json()
        assert data["error_type"] == "api_connection_error"

    def test_api_timeout_error_returns_502(
        self, client: FlaskClient
    ) -> None:
        from openai import APITimeoutError

        with patch(
            "brief_forge.app.generate_brief",
            side_effect=APITimeoutError(request=MagicMock()),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 502
        data = response.get_json()
        assert data["error_type"] == "api_connection_error"

    def test_generic_api_error_returns_500(
        self, client: FlaskClient
    ) -> None:
        from openai import APIStatusError

        mock_response = MagicMock()
        mock_response.status_code = 500
        with patch(
            "brief_forge.app.generate_brief",
            side_effect=APIStatusError(
                message="Internal server error",
                response=mock_response,
                body={},
            ),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 500
        data = response.get_json()
        assert data["error_type"] == "api_error"

    def test_unexpected_exception_returns_500(
        self, client: FlaskClient
    ) -> None:
        with patch(
            "brief_forge.app.generate_brief",
            side_effect=Exception("Something weird happened"),
        ):
            response = client.post(
                "/generate",
                json={"description": "A coffee brand."},
            )
        assert response.status_code == 500
        data = response.get_json()
        assert data["error_type"] == "unexpected_error"

    def test_error_response_has_success_false(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={})
        data = response.get_json()
        assert "success" in data
        assert data["success"] is False

    def test_error_response_has_error_key(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={})
        data = response.get_json()
        assert "error" in data
        assert isinstance(data["error"], str)

    def test_error_response_has_error_type_key(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/generate", json={})
        data = response.get_json()
        assert "error_type" in data


# ---------------------------------------------------------------------------
# POST /format — happy path
# ---------------------------------------------------------------------------


class TestFormatRouteHappyPath:
    """Tests for the POST /format route — successful formatting."""

    def test_markdown_format_returns_200(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "markdown"},
        )
        assert response.status_code == 200

    def test_markdown_format_success_true(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "markdown"},
        )
        data = response.get_json()
        assert data["success"] is True

    def test_markdown_output_contains_heading(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "markdown"},
        )
        data = response.get_json()
        assert "# Design Brief" in data["output"]

    def test_text_format_returns_200(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "text"},
        )
        assert response.status_code == 200

    def test_text_output_contains_section_header(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "text"},
        )
        data = response.get_json()
        assert "PROJECT OVERVIEW" in data["output"]

    def test_json_format_returns_200(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "json"},
        )
        assert response.status_code == 200

    def test_json_output_is_valid_json(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "json"},
        )
        data = response.get_json()
        parsed = json.loads(data["output"])
        assert isinstance(parsed, dict)

    def test_response_contains_format_field(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "markdown"},
        )
        data = response.get_json()
        assert "format" in data
        assert data["format"] == "markdown"

    def test_case_insensitive_format_name(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "MARKDOWN"},
        )
        assert response.status_code == 200
        data = response.get_json()
        assert data["success"] is True


# ---------------------------------------------------------------------------
# POST /format — error paths
# ---------------------------------------------------------------------------


class TestFormatRouteErrors:
    """Tests for POST /format error handling."""

    def test_missing_brief_returns_400(
        self, client: FlaskClient
    ) -> None:
        response = client.post(
            "/format",
            json={"format": "markdown"},
        )
        assert response.status_code == 400

    def test_missing_format_returns_400(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict},
        )
        assert response.status_code == 400

    def test_unsupported_format_returns_400(
        self,
        client: FlaskClient,
        sample_brief_dict: dict[str, Any],
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": sample_brief_dict, "format": "html"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "unsupported_format"

    def test_invalid_brief_data_returns_400(
        self, client: FlaskClient
    ) -> None:
        response = client.post(
            "/format",
            json={"brief": {"only": "garbage"}, "format": "markdown"},
        )
        assert response.status_code == 400
        data = response.get_json()
        assert data["error_type"] == "invalid_brief"

    def test_non_json_body_returns_400(
        self, client: FlaskClient
    ) -> None:
        response = client.post(
            "/format",
            data="not json",
            content_type="text/plain",
        )
        assert response.status_code == 400

    def test_missing_brief_error_message(
        self, client: FlaskClient
    ) -> None:
        response = client.post("/format", json={"format": "markdown"})
        data = response.get_json()
        assert data["success"] is False
        assert "brief" in data["error"].lower()


# ---------------------------------------------------------------------------
# Global error handlers
# ---------------------------------------------------------------------------


class TestErrorHandlers:
    """Tests for the global HTTP error handlers."""

    def test_404_returns_json(self, client: FlaskClient) -> None:
        response = client.get("/nonexistent-route")
        assert response.status_code == 404
        data = response.get_json()
        assert data is not None
        assert data["success"] is False
        assert data["error_type"] == "not_found"

    def test_405_returns_json(self, client: FlaskClient) -> None:
        # GET /generate should return 405 (only POST is allowed).
        response = client.get("/generate")
        assert response.status_code == 405
        data = response.get_json()
        assert data is not None
        assert data["error_type"] == "method_not_allowed"

    def test_404_has_error_key(self, client: FlaskClient) -> None:
        response = client.get("/nonexistent")
        data = response.get_json()
        assert "error" in data


# ---------------------------------------------------------------------------
# _render_all_formats utility
# ---------------------------------------------------------------------------


class TestRenderAllFormats:
    """Tests for the _render_all_formats utility function."""

    def test_returns_dict_with_all_keys(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        assert set(result.keys()) == {"markdown", "text", "json"}

    def test_markdown_value_is_string(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        assert isinstance(result["markdown"], str)

    def test_text_value_is_string(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        assert isinstance(result["text"], str)

    def test_json_value_is_string(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        assert isinstance(result["json"], str)

    def test_markdown_contains_title(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        assert sample_brief.title in result["markdown"]

    def test_text_contains_title(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        assert sample_brief.title.upper() in result["text"]

    def test_json_is_valid_json(self, sample_brief: DesignBrief) -> None:
        result = _render_all_formats(sample_brief)
        parsed = json.loads(result["json"])
        assert isinstance(parsed, dict)
        assert parsed["title"] == sample_brief.title


# ---------------------------------------------------------------------------
# Route method restrictions
# ---------------------------------------------------------------------------


class TestRouteMethods:
    """Verify that routes only accept their declared HTTP methods."""

    def test_generate_rejects_get(self, client: FlaskClient) -> None:
        response = client.get("/generate")
        assert response.status_code == 405

    def test_format_rejects_get(self, client: FlaskClient) -> None:
        response = client.get("/format")
        assert response.status_code == 405

    def test_index_rejects_post(self, client: FlaskClient) -> None:
        response = client.post("/")
        assert response.status_code == 405

    def test_health_rejects_post(self, client: FlaskClient) -> None:
        response = client.post("/health")
        assert response.status_code == 405

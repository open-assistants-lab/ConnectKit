"""Tests that shipped connector YAMLs parse correctly."""

from pathlib import Path

from connectkit.spec import ConnectorSpec


CONNECTORS_DIR = Path(__file__).parent.parent / "connectors"


def test_firecrawl_parses():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "firecrawl.yaml")
    assert spec.name == "firecrawl"
    assert spec.auth.type.value == "api_key"
    assert spec.tool_source.type == "cli"
    assert spec.auth.api_key.env_var == "FIRECRAWL_API_KEY"
    assert len(spec.tool_descriptions) > 0


def test_google_workspace_parses():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "google-workspace.yaml")
    assert spec.name == "google-workspace"
    assert spec.auth.type.value == "oauth2"
    assert spec.auth.oauth2.scopes
    assert spec.auth.oauth2.extra_params["access_type"] == "offline"
    assert spec.tool_source.type == "cli"
    assert spec.tool_source.command == "gws"
    assert len(spec.tool_descriptions) > 0


def test_github_parses():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "github.yaml")
    assert spec.name == "github"
    assert spec.auth.type.value == "oauth2"
    assert "repo" in spec.auth.oauth2.scopes
    assert spec.tool_source.type == "cli"
    assert spec.tool_source.command == "gh"
    assert len(spec.tool_descriptions) > 0


def test_microsoft_365_parses():
    spec = ConnectorSpec.from_yaml(CONNECTORS_DIR / "microsoft-365.yaml")
    assert spec.name == "microsoft-365"
    assert spec.auth.type.value == "oauth2"
    assert spec.auth.oauth2.scopes
    assert "offline_access" in spec.auth.oauth2.scopes
    assert spec.tool_source.type == "cli"
    assert spec.tool_source.command == "m365"
    assert len(spec.tool_descriptions) > 0
    assert len(spec.auth.required_fields) == 2
    assert spec.auth.required_fields[0].name == "client_id"

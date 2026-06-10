# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

import pytest

from ansible_collections.stevefulme1.haproxy.plugins.module_utils.haproxy_config_parser import (
    HAProxyConfigParser,
    HAProxyConfigError,
)


class TestHAProxyConfigParser:
    def test_parse_sections(self, tmp_path):
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
            "\n"
            "defaults\n"
            "    mode http\n"
            "\n"
            "frontend web_front\n"
            "    bind *:80\n"
            "\n"
            "backend web_back\n"
            "    server web1 127.0.0.1:8080\n"
        )

        parser = HAProxyConfigParser(str(config))
        sections = parser.read()

        section_types = [s["type"] for s in sections]
        assert "global" in section_types
        assert "defaults" in section_types
        assert "frontend" in section_types
        assert "backend" in section_types

    def test_get_section(self, tmp_path):
        config = tmp_path / "haproxy.cfg"
        config.write_text(
            "global\n"
            "    maxconn 4096\n"
            "\n"
            "backend web_back\n"
            "    server web1 127.0.0.1:8080\n"
        )

        parser = HAProxyConfigParser(str(config))
        parser.read()

        section = parser.get_section("backend", "web_back")
        assert section is not None
        assert section["name"] == "web_back"

    def test_get_section_not_found(self, tmp_path):
        config = tmp_path / "haproxy.cfg"
        config.write_text("global\n    maxconn 4096\n")

        parser = HAProxyConfigParser(str(config))
        parser.read()

        assert parser.get_section("backend", "nonexistent") is None

    def test_file_not_found(self):
        parser = HAProxyConfigParser("/nonexistent/path")
        with pytest.raises(HAProxyConfigError, match="Config file not found"):
            parser.read()

    def test_write(self, tmp_path):
        config = tmp_path / "haproxy.cfg"
        config.write_text("global\n    maxconn 4096\n")

        parser = HAProxyConfigParser(str(config))
        parser.read()

        output = tmp_path / "output.cfg"
        parser.write(str(output))

        assert output.exists()
        assert "maxconn 4096" in output.read_text()

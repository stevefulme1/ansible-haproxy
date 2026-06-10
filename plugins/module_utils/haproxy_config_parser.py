# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

import re
from pathlib import Path


class HAProxyConfigError(Exception):
    """Raised when HAProxy config parsing or writing fails."""


class HAProxyConfigParser:
    """Parse and modify HAProxy configuration files."""

    SECTION_TYPES = ("global", "defaults", "frontend", "backend", "listen", "resolvers", "peers")

    def __init__(self, config_path="/etc/haproxy/haproxy.cfg"):
        self.config_path = config_path
        self.sections = []
        self._raw = ""

    def read(self):
        path = Path(self.config_path)
        if not path.exists():
            raise HAProxyConfigError(f"Config file not found: {self.config_path}")
        self._raw = path.read_text()
        self.sections = self._parse(self._raw)
        return self.sections

    def _parse(self, content):
        sections = []
        current = None

        for line in content.split("\n"):
            stripped = line.strip()

            match = re.match(r"^(" + "|".join(self.SECTION_TYPES) + r")\s*(.*)?$", stripped)
            if match:
                if current:
                    sections.append(current)
                current = {
                    "type": match.group(1),
                    "name": match.group(2).strip() if match.group(2) else "",
                    "lines": [line],
                }
            elif current:
                current["lines"].append(line)
            else:
                if not sections and current is None:
                    current = {"type": "_preamble", "name": "", "lines": [line]}

        if current:
            sections.append(current)

        return sections

    def get_section(self, section_type, name=None):
        for section in self.sections:
            if section["type"] == section_type:
                if name is None or section["name"] == name:
                    return section
        return None

    def write(self, dest=None):
        output = "\n".join(
            "\n".join(section["lines"]) for section in self.sections
        )
        path = Path(dest or self.config_path)
        path.write_text(output)
        return str(path)

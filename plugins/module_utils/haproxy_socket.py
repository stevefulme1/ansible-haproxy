# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, annotations, division, print_function

import csv
import io
import socket as socket_module


class HAProxySocketError(Exception):
    """Raised when HAProxy socket communication fails."""


class HAProxySocket:
    """Client for the HAProxy Runtime API via Unix or TCP socket."""

    def __init__(self, socket_path, timeout=10):
        self.socket_path = socket_path
        self.timeout = timeout

    def _connect(self):
        if self.socket_path.startswith("tcp://"):
            host_port = self.socket_path[6:]
            host, port = host_port.rsplit(":", 1)
            sock = socket_module.socket(socket_module.AF_INET, socket_module.SOCK_STREAM)
            address = (host, int(port))
        else:
            sock = socket_module.socket(socket_module.AF_UNIX, socket_module.SOCK_STREAM)
            address = self.socket_path

        sock.settimeout(self.timeout)

        try:
            sock.connect(address)
        except (ConnectionRefusedError, FileNotFoundError, socket_module.timeout) as e:
            sock.close()
            raise HAProxySocketError(str(e)) from e

        return sock

    def execute(self, command):
        sock = self._connect()
        try:
            sock.sendall(f"{command}\n".encode())
            response = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
            return response.decode()
        except socket_module.timeout as e:
            raise HAProxySocketError(str(e)) from e
        finally:
            sock.close()

    def get_stats(self):
        raw = self.execute("show stat")
        lines = [line for line in raw.strip().split("\n") if line and not line.startswith("# ")]
        header_line = [line for line in raw.strip().split("\n") if line.startswith("#")]

        if not header_line:
            return []

        headers = header_line[0].lstrip("# ").split(",")
        reader = csv.DictReader(io.StringIO("\n".join(lines)), fieldnames=headers)
        return [dict(row) for row in reader]

    def get_info(self):
        raw = self.execute("show info")
        info = {}
        for line in raw.strip().split("\n"):
            if ": " in line:
                key, value = line.split(": ", 1)
                info[key] = value
        return info

"""
network_tools.py — Blacksun homelab network visibility tools

Provides ping, port check, traceroute, DNS, WHOIS, device inventory,
Wake-on-LAN, interface stats, and speedtest via subprocess/socket/psutil.
No external API keys required. Windows and Linux compatible.
Author: ropeadope62 - Dave C
GitHub: https://github.com/ropeadope62/
"""

import json
import logging
import os
import re
import socket
import subprocess
import sys
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("workstation-agent.network")

_IS_WINDOWS = sys.platform == "win32"
_DEVICES_CONFIG = Path(__file__).parent.parent / "config" / "devices.json"


# ── Helpers ──────────────────────────────────────────────────────────

def _run(cmd: list, timeout: int = 30) -> tuple:
    """Run a subprocess command safely (no shell=True)."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", "Command timed out"
    except FileNotFoundError:
        return -1, "", f"Command not found: {cmd[0]}"
    except Exception as e:
        return -1, "", str(e)


def _load_devices() -> dict:
    """Load device inventory from config/devices.json."""
    if not _DEVICES_CONFIG.exists():
        return {}
    try:
        with open(_DEVICES_CONFIG, encoding="utf-8") as f:
            data = json.load(f)
        # Strip comment keys
        return {k: v for k, v in data.items() if not k.startswith("_")}
    except Exception as e:
        logger.warning(f"Failed to load devices config: {e}")
        return {}


# ── Core implementations ──────────────────────────────────────────────

def _ping(host: str, count: int = 4) -> dict:
    """Ping a host and return latency/packet loss stats."""
    if _IS_WINDOWS:
        cmd = ["ping", "-n", str(count), host]
    else:
        cmd = ["ping", "-c", str(count), "-W", "3", host]

    rc, stdout, stderr = _run(cmd, timeout=count * 5 + 5)
    output = stdout + stderr

    if rc == -1:
        return {"host": host, "reachable": False, "error": stderr}

    loss_match = re.search(r"(\d+)%\s+(?:packet\s+)?loss", output, re.IGNORECASE)
    loss = int(loss_match.group(1)) if loss_match else None
    reachable = rc == 0 and (loss is None or loss < 100)

    result: dict = {
        "host": host,
        "reachable": reachable,
        "packets_sent": count,
        "packet_loss_pct": loss,
    }

    if _IS_WINDOWS:
        for label, key in [
            ("Minimum", "rtt_min_ms"),
            ("Maximum", "rtt_max_ms"),
            ("Average", "rtt_avg_ms"),
        ]:
            m = re.search(rf"{label}\s*=\s*(\d+)ms", output, re.IGNORECASE)
            if m:
                result[key] = int(m.group(1))
    else:
        rtt_match = re.search(
            r"rtt .+ = ([\d.]+)/([\d.]+)/([\d.]+)/([\d.]+) ms", output
        )
        if rtt_match:
            result["rtt_min_ms"] = float(rtt_match.group(1))
            result["rtt_avg_ms"] = float(rtt_match.group(2))
            result["rtt_max_ms"] = float(rtt_match.group(3))

    return result


def _scan_network(subnet: str = "192.168.1.0/24") -> dict:
    """Scan a subnet for live hosts using nmap, or fall back to ARP cache."""
    hosts = []
    method = None

    # Validate subnet looks sane (basic check to avoid command injection)
    if not re.match(r"^[\d./]+$", subnet):
        return {"error": f"Invalid subnet format: {subnet}"}

    # Try nmap ping scan first (no port scan, fast)
    rc, stdout, _ = _run(["nmap", "-sn", subnet], timeout=60)
    if rc == 0:
        method = "nmap"
        for line in stdout.splitlines():
            m = re.search(r"Nmap scan report for (.+?)\s*(?:\((.+?)\))?$", line)
            if m:
                name_or_ip = m.group(1).strip()
                ip = m.group(2).strip() if m.group(2) else name_or_ip
                hostname = name_or_ip if m.group(2) else None
                hosts.append({"ip": ip, "hostname": hostname})
    else:
        # Fallback: arp cache (shows only recently seen hosts — not a full sweep)
        arp_cmd = ["arp", "-a"] if _IS_WINDOWS else ["arp", "-n"]
        rc, stdout, _ = _run(arp_cmd, timeout=10)
        if rc == 0:
            method = "arp_cache"
            prefix = ".".join(subnet.split("/")[0].split(".")[:3])
            for line in stdout.splitlines():
                m = re.search(r"((?:\d{1,3}\.){3}\d{1,3})", line)
                if m:
                    ip = m.group(1)
                    if ip.startswith(prefix):
                        hosts.append({"ip": ip})
        else:
            return {"error": "Neither nmap nor arp is available on this system"}

    return {
        "subnet": subnet,
        "method": method,
        "hosts_found": len(hosts),
        "hosts": hosts,
    }


def _check_port(host: str, port: int, timeout: float = 3.0) -> dict:
    """Check if a TCP port is open on a host."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return {"host": host, "port": port, "open": True}
    except (socket.timeout, TimeoutError):
        return {"host": host, "port": port, "open": False, "reason": "timeout"}
    except ConnectionRefusedError:
        return {"host": host, "port": port, "open": False, "reason": "connection refused"}
    except OSError as e:
        return {"host": host, "port": port, "open": False, "reason": str(e)}


def _traceroute(host: str, max_hops: int = 30) -> dict:
    """Trace the network path to a host."""
    # Validate max_hops to prevent misuse
    max_hops = max(1, min(max_hops, 64))

    if _IS_WINDOWS:
        cmd = ["tracert", "-h", str(max_hops), host]
    else:
        cmd = ["traceroute", "-m", str(max_hops), host]

    rc, stdout, stderr = _run(cmd, timeout=120)

    if rc == -1:
        return {"host": host, "error": stderr}

    hops = []
    for line in stdout.splitlines():
        if _IS_WINDOWS:
            # "  1    <1 ms    <1 ms    <1 ms  192.168.1.1"
            m = re.match(r"\s*(\d+)\s+(.*?)\s+([\w.\-]+)\s*$", line)
            if m:
                timing_str = m.group(2)
                ms_vals = re.findall(r"(?:<\s*)?(\d+)\s*ms", timing_str)
                hops.append({
                    "hop": int(m.group(1)),
                    "address": m.group(3),
                    "rtts_ms": [int(v) for v in ms_vals],
                })
        else:
            m = re.match(r"\s*(\d+)\s+(.+)", line)
            if m:
                rest = m.group(2)
                addr_m = re.search(r"(?:\(?([\d.]+)\)?|(\S+))", rest)
                addr = addr_m.group(1) or addr_m.group(2) if addr_m else rest
                times = [float(t) for t in re.findall(r"([\d.]+)\s*ms", rest)]
                hops.append({
                    "hop": int(m.group(1)),
                    "address": addr,
                    "rtts_ms": times,
                })

    return {"host": host, "hops": hops, "raw": stdout.strip()}


def _dns_lookup(target: str, reverse: bool = False) -> dict:
    """Perform DNS forward or reverse lookup."""
    try:
        if reverse:
            hostname, aliases, _ = socket.gethostbyaddr(target)
            return {
                "target": target,
                "type": "reverse",
                "hostname": hostname,
                "aliases": aliases,
            }
        else:
            infos = socket.getaddrinfo(target, None)
            addresses = list({info[4][0] for info in infos})
            return {"target": target, "type": "forward", "addresses": addresses}
    except socket.herror as e:
        return {"target": target, "error": f"DNS error: {e}"}
    except socket.gaierror as e:
        return {"target": target, "error": f"Name resolution failed: {e}"}


def _whois_lookup(target: str) -> dict:
    """WHOIS lookup for an IP or domain."""
    rc, stdout, stderr = _run(["whois", target], timeout=20)
    if rc == 0 and stdout.strip():
        fields: dict = {}
        for line in stdout.splitlines():
            stripped = line.strip()
            if not stripped or stripped.startswith(("%", "#", ">")):
                continue
            if ":" in stripped:
                key, _, val = stripped.partition(":")
                key = key.strip()
                val = val.strip()
                if val and key not in fields:
                    fields[key] = val
        return {"target": target, "summary": fields, "raw": stdout}
    return {
        "target": target,
        "error": stderr.strip() or "whois command not available or returned no output",
    }


def _device_status(device_names: Optional[list] = None) -> dict:
    """Check reachability of named homelab devices from config/devices.json."""
    devices = _load_devices()
    if not devices:
        return {
            "error": (
                f"No devices configured. Create {_DEVICES_CONFIG} with "
                "name → ip mappings. See config/devices.json.example for format."
            )
        }

    if device_names:
        targets = {k: v for k, v in devices.items() if k in device_names}
        if not targets:
            return {
                "error": "No matching devices found",
                "available": list(devices.keys()),
            }
    else:
        targets = devices

    results = {}
    for name, info in targets.items():
        ip = info.get("ip") if isinstance(info, dict) else str(info)
        ping_result = _ping(ip, count=2)
        entry: dict = {
            "ip": ip,
            "up": ping_result["reachable"],
            "rtt_avg_ms": ping_result.get("rtt_avg_ms"),
        }
        if isinstance(info, dict):
            if "mac" in info:
                entry["mac"] = info["mac"]
            if "description" in info:
                entry["description"] = info["description"]
        results[name] = entry

    up_count = sum(1 for r in results.values() if r["up"])
    return {
        "devices": results,
        "summary": {
            "total": len(results),
            "up": up_count,
            "down": len(results) - up_count,
        },
    }


def _wake_on_lan(
    mac_address: str,
    broadcast: str = "255.255.255.255",
    port: int = 9,
) -> dict:
    """Send a Wake-on-LAN magic packet to a MAC address."""
    mac_clean = re.sub(r"[:\-.]", "", mac_address).upper()
    if len(mac_clean) != 12 or not re.fullmatch(r"[0-9A-F]{12}", mac_clean):
        return {"success": False, "error": f"Invalid MAC address: {mac_address}"}

    mac_bytes = bytes.fromhex(mac_clean)
    magic_packet = b"\xff" * 6 + mac_bytes * 16

    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
            sock.sendto(magic_packet, (broadcast, port))
        return {
            "success": True,
            "mac": mac_address,
            "broadcast": broadcast,
            "port": port,
        }
    except OSError as e:
        return {"success": False, "error": str(e)}


def _interface_stats() -> dict:
    """Get network interface statistics via psutil."""
    try:
        import psutil
    except ImportError:
        return {"error": "psutil not installed. Run: pip install psutil"}

    io = psutil.net_io_counters(pernic=True)
    stats = psutil.net_if_stats()
    addrs = psutil.net_if_addrs()

    interfaces = {}
    for name, counters in io.items():
        iface_stats = stats.get(name)
        iface_addrs = addrs.get(name, [])
        ipv4 = next(
            (a.address for a in iface_addrs if a.family == socket.AF_INET), None
        )
        interfaces[name] = {
            "up": iface_stats.isup if iface_stats else None,
            "speed_mbps": iface_stats.speed if iface_stats else None,
            "ipv4": ipv4,
            "bytes_sent": counters.bytes_sent,
            "bytes_recv": counters.bytes_recv,
            "packets_sent": counters.packets_sent,
            "packets_recv": counters.packets_recv,
            "errin": counters.errin,
            "errout": counters.errout,
            "dropin": counters.dropin,
            "dropout": counters.dropout,
        }

    return {"interfaces": interfaces}


def _speedtest() -> dict:
    """Run a network speed test via speedtest-cli."""
    rc, stdout, stderr = _run(
        [sys.executable, "-m", "speedtest", "--json"],
        timeout=120,
    )
    if rc == 0:
        try:
            data = json.loads(stdout)
            return {
                "download_mbps": round(data["download"] / 1_000_000, 2),
                "upload_mbps": round(data["upload"] / 1_000_000, 2),
                "ping_ms": data["ping"],
                "server": data.get("server", {}).get("sponsor"),
                "isp": data.get("client", {}).get("isp"),
            }
        except (json.JSONDecodeError, KeyError) as e:
            return {"error": f"Failed to parse speedtest output: {e}", "raw": stdout}
    return {
        "error": stderr.strip() or "speedtest-cli not installed. Run: pip install speedtest-cli"
    }


# ── Registration ──────────────────────────────────────────────────────

def register_network_tools(mcp: FastMCP):

    @mcp.tool()
    def ping_host(host: str, count: int = 4) -> str:
        """Ping a host and return reachability, packet loss, and round-trip time.

        Args:
            host: Hostname or IP address to ping.
            count: Number of ping packets to send (default 4).
        """
        return json.dumps(_ping(host, count), indent=2)

    @mcp.tool()
    def scan_network(subnet: str = "192.168.1.0/24") -> str:
        """Scan a subnet for live hosts. Uses nmap if installed, otherwise falls back to ARP cache.

        Args:
            subnet: Network to scan in CIDR notation (e.g. '192.168.1.0/24').
        """
        return json.dumps(_scan_network(subnet), indent=2)

    @mcp.tool()
    def check_port(host: str, port: int, timeout: float = 3.0) -> str:
        """Check if a TCP port is open on a given host.

        Args:
            host: Hostname or IP address.
            port: TCP port number to test.
            timeout: Connection timeout in seconds (default 3).
        """
        return json.dumps(_check_port(host, port, timeout), indent=2)

    @mcp.tool()
    def traceroute(host: str, max_hops: int = 30) -> str:
        """Trace the network path to a host, showing each hop and latency.

        Args:
            host: Hostname or IP address to trace.
            max_hops: Maximum number of hops (default 30, capped at 64).
        """
        return json.dumps(_traceroute(host, max_hops), indent=2)

    @mcp.tool()
    def dns_lookup(target: str, reverse: bool = False) -> str:
        """Perform a DNS lookup for a hostname or IP address.

        Args:
            target: Hostname (e.g. 'nas.local') or IP address.
            reverse: Set True to perform a reverse DNS lookup (IP → hostname).
        """
        return json.dumps(_dns_lookup(target, reverse), indent=2)

    @mcp.tool()
    def whois_lookup(target: str) -> str:
        """Look up WHOIS registration information for a domain or IP address.

        Args:
            target: Domain name (e.g. 'example.com') or IP address.
        """
        return json.dumps(_whois_lookup(target), indent=2)

    @mcp.tool()
    def device_status(device_names: str = "") -> str:
        """Check the reachability (ping) of named homelab devices from config/devices.json.

        Args:
            device_names: Comma-separated list of device names to check.
                          Leave empty to check all configured devices.
        """
        names = [n.strip() for n in device_names.split(",") if n.strip()] or None
        return json.dumps(_device_status(names), indent=2)

    @mcp.tool()
    def wake_on_lan(
        mac_address: str,
        broadcast: str = "255.255.255.255",
        port: int = 9,
    ) -> str:
        """Send a Wake-on-LAN magic packet to power on a sleeping device.

        Args:
            mac_address: MAC address of the target device (e.g. 'AA:BB:CC:DD:EE:FF').
            broadcast: Broadcast address to send the packet to (default '255.255.255.255').
            port: UDP port for the WOL packet (default 9).
        """
        return json.dumps(_wake_on_lan(mac_address, broadcast, port), indent=2)

    @mcp.tool()
    def get_interface_stats() -> str:
        """Get local network interface statistics: bytes in/out, errors, packet counts, IP addresses.
        Requires psutil (pip install psutil).
        """
        return json.dumps(_interface_stats(), indent=2)

    @mcp.tool()
    def speedtest() -> str:
        """Run a network speed test and return download/upload speeds and ping latency.
        Requires speedtest-cli (pip install speedtest-cli).
        """
        return json.dumps(_speedtest(), indent=2)

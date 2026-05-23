"""Tests for the iptables firewall command."""

import importlib
import os
import sys

try:
    kernel_mod = importlib.import_module("pureos.core.kernel")
except Exception:
    sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))
    kernel_mod = importlib.import_module("pureos.core.kernel")

Kernel = kernel_mod.Kernel


class TestIptables:
    def _make_kernel(self, tmp_path):
        backing = tmp_path / "store.json"
        k = Kernel(config={"fs_backing": str(backing)})
        k.initialize()
        return k

    def test_list_empty_rules(self, tmp_path):
        k = self._make_kernel(tmp_path)
        out = k.shell.registry.execute(["iptables", "-L"], capture_output=True)
        assert "Chain" in out
        assert "INPUT" in out
        assert "OUTPUT" in out
        assert "FORWARD" in out
        k.shutdown()

    def test_append_rule(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
        )
        assert result is True
        out = k.shell.registry.execute(["iptables", "-L"], capture_output=True)
        assert "10.0.0.1" in out
        assert "DROP" in out
        k.shutdown()

    def test_delete_rule(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
        )
        result = k.shell.registry.execute(
            ["iptables", "-D", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
        )
        assert result is True
        out = k.shell.registry.execute(["iptables", "-L"], capture_output=True)
        assert "10.0.0.1" not in out
        k.shutdown()

    def test_delete_nonexistent_rule(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["iptables", "-D", "INPUT", "-s", "99.99.99.99", "-j", "DROP"],
        )
        assert result is False
        k.shutdown()

    def test_flush_all_rules(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
        )
        k.shell.registry.execute(
            ["iptables", "-A", "OUTPUT", "-d", "10.0.0.2", "-j", "ACCEPT"],
        )
        result = k.shell.registry.execute(["iptables", "-F"])
        assert result is True
        out = k.shell.registry.execute(["iptables", "-L"], capture_output=True)
        assert "10.0.0.1" not in out
        assert "10.0.0.2" not in out
        k.shutdown()

    def test_flush_specific_chain(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
        )
        k.shell.registry.execute(
            ["iptables", "-A", "OUTPUT", "-d", "10.0.0.2", "-j", "ACCEPT"],
        )
        result = k.shell.registry.execute(
            ["iptables", "-F", "INPUT"],
        )
        assert result is True
        out = k.shell.registry.execute(["iptables", "-L"], capture_output=True)
        assert "10.0.0.1" not in out
        assert "10.0.0.2" in out
        k.shutdown()

    def test_list_specific_chain(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
            capture_output=True,
        )
        k.shell.registry.execute(
            ["iptables", "-A", "OUTPUT", "-d", "10.0.0.2", "-j", "ACCEPT"],
            capture_output=True,
        )
        out = k.shell.registry.execute(["iptables", "-L", "INPUT"], capture_output=True)
        assert "10.0.0.1" in out
        assert "10.0.0.2" not in out
        k.shutdown()

    def test_invalid_chain_rejected(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["iptables", "-A", "INVALID", "-s", "10.0.0.1", "-j", "DROP"],
        )
        assert result is False
        k.shutdown()

    def test_no_action_shows_usage(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(["iptables"])
        assert result is False
        k.shutdown()

    def test_rules_persist_to_vfs(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
            capture_output=True,
        )
        assert k.fs.exists("/etc/iptables/rules")
        content = k.fs.read("/etc/iptables/rules")
        assert "10.0.0.1" in content
        assert "DROP" in content
        k.shutdown()

    def test_rules_load_from_vfs(self, tmp_path):
        k = self._make_kernel(tmp_path)
        # Write rules directly to VFS
        k.fs.mkdir("/etc/iptables", parents=True)
        rules = (
            "*filter\n:INPUT ACCEPT [0:0]\n:OUTPUT ACCEPT [0:0]\n"
            ":FORWARD ACCEPT [0:0]\n-A INPUT -s 192.168.1.1 -j ACCEPT\nCOMMIT\n"
        )
        k.fs.write("/etc/iptables/rules", rules)
        out = k.shell.registry.execute(["iptables", "-L"], capture_output=True)
        assert "192.168.1.1" in out
        assert "ACCEPT" in out
        k.shutdown()

    def test_multiple_rules_same_chain(self, tmp_path):
        k = self._make_kernel(tmp_path)
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
            capture_output=True,
        )
        k.shell.registry.execute(
            ["iptables", "-A", "INPUT", "-s", "10.0.0.2", "-j", "ACCEPT"],
            capture_output=True,
        )
        out = k.shell.registry.execute(["iptables", "-L", "INPUT"], capture_output=True)
        assert "10.0.0.1" in out
        assert "10.0.0.2" in out
        k.shutdown()

    def test_table_flag(self, tmp_path):
        k = self._make_kernel(tmp_path)
        result = k.shell.registry.execute(
            ["iptables", "-t", "filter", "-A", "INPUT", "-s", "10.0.0.1", "-j", "DROP"],
        )
        assert result is True
        out = k.shell.registry.execute(
            ["iptables", "-t", "filter", "-L"], capture_output=True
        )
        assert "10.0.0.1" in out
        k.shutdown()

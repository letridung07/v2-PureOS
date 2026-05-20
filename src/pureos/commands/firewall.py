"""Simulated iptables firewall command for v2-PureOS."""

from typing import List

from .base import Command

_RULES_PATH = "/etc/iptables/rules"
_DEFAULT_TABLE = "filter"
_CHAINS = ("INPUT", "OUTPUT", "FORWARD")


class IptablesCommand(Command):
    name = "iptables"
    usage = "iptables [-t table] [-L|-A|-D|-F] [chain] [rule]"
    description = (
        "Simulate firewall rule management. Rules are stored in /etc/iptables/rules."
    )

    def _load_rules(self) -> dict:
        """Load rules from VFS, returning a dict of table -> chain -> [rules]."""
        tables: dict = {}
        if self.kernel.fs.exists(_RULES_PATH):
            content = self.kernel.fs.read(_RULES_PATH) or ""
            current_table = _DEFAULT_TABLE
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("*"):
                    current_table = line[1:]
                    tables.setdefault(current_table, {c: [] for c in _CHAINS})
                elif line.startswith(":"):
                    chain = line[1:].split()[0]
                    tables.setdefault(current_table, {}).setdefault(chain, [])
                elif line.startswith("-A "):
                    parts = line[3:].split(None, 1)
                    chain = parts[0]
                    rule = parts[1] if len(parts) > 1 else ""
                    tables.setdefault(current_table, {}).setdefault(chain, []).append(
                        rule
                    )
        if not tables:
            tables[_DEFAULT_TABLE] = {c: [] for c in _CHAINS}
        return tables

    def _save_rules(self, tables: dict):
        """Persist rules to VFS."""
        lines = []
        for table, chains in tables.items():
            lines.append(f"*{table}")
            for chain in _CHAINS:
                lines.append(f":{chain} ACCEPT [0:0]")
            for chain, rules in chains.items():
                for rule in rules:
                    lines.append(f"-A {chain} {rule}")
            lines.append("COMMIT")
        self.kernel.fs.mkdir("/etc/iptables", parents=True)
        self.kernel.fs.write(_RULES_PATH, "\n".join(lines) + "\n")

    def execute(
        self,
        parts: List[str],
        input_data=None,
        capture_output=False,
        raw_line=None,
    ):
        # Parse flags
        table = _DEFAULT_TABLE
        args = parts[1:]
        i = 0
        action = None
        chain = None
        rule_parts: List[str] = []

        while i < len(args):
            token = args[i]
            if token in ("-t", "--table") and i + 1 < len(args):
                table = args[i + 1]
                i += 2
            elif token in ("-L", "--list"):
                action = "list"
                if i + 1 < len(args) and not args[i + 1].startswith("-"):
                    chain = args[i + 1]
                    i += 2
                else:
                    i += 1
            elif token in ("-A", "--append") and i + 1 < len(args):
                action = "append"
                chain = args[i + 1]
                rule_parts = args[i + 2 :]
                break
            elif token in ("-D", "--delete") and i + 1 < len(args):
                action = "delete"
                chain = args[i + 1]
                rule_parts = args[i + 2 :]
                break
            elif token in ("-F", "--flush"):
                action = "flush"
                if i + 1 < len(args) and not args[i + 1].startswith("-"):
                    chain = args[i + 1]
                    i += 2
                else:
                    i += 1
            else:
                i += 1

        if action is None:
            print("Usage: iptables [-t table] [-L|-A|-D|-F] [chain] [rule]")
            return False

        tables = self._load_rules()
        tables.setdefault(table, {c: [] for c in _CHAINS})

        if action == "list":
            out_lines = [f"Chain policy for table '{table}':"]
            chains_to_show = [chain] if chain else list(tables[table].keys())
            for ch in chains_to_show:
                rules = tables[table].get(ch, [])
                out_lines.append(f"\nChain {ch} (policy ACCEPT)")
                out_lines.append("target     prot opt source               destination")
                for rule in rules:
                    out_lines.append(f"  {rule}")
            out = "\n".join(out_lines)
            if capture_output:
                return out
            print(out)
            return True

        elif action == "append":
            if chain not in _CHAINS:
                print(f"iptables: invalid chain '{chain}'")
                return False
            rule = " ".join(rule_parts)
            tables[table].setdefault(chain, []).append(rule)
            self._save_rules(tables)
            return True

        elif action == "delete":
            if chain not in _CHAINS:
                print(f"iptables: invalid chain '{chain}'")
                return False
            rule = " ".join(rule_parts)
            rules = tables[table].get(chain, [])
            if rule in rules:
                rules.remove(rule)
                self._save_rules(tables)
                return True
            print(f"iptables: rule not found in chain {chain}")
            return False

        elif action == "flush":
            if chain:
                tables[table][chain] = []
            else:
                for ch in _CHAINS:
                    tables[table][ch] = []
            self._save_rules(tables)
            return True

        return False


def register_firewall_commands(registry):
    registry.register(IptablesCommand(registry.kernel))

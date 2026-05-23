import os
import re

mapping = [
    (r'pureos\.kernel\b', 'pureos.core.kernel'),
    (r'pureos\.boot\b', 'pureos.core.boot'),
    (r'pureos\.config\b', 'pureos.core.config'),
    (r'pureos\.utils\b', 'pureos.core.utils'),
    # Submodules of drivers need to be replaced before pureos.drivers itself
    (r'pureos\.syslog\b', 'pureos.drivers.syslog'),
    (r'pureos\.audit\b', 'pureos.drivers.audit'),
    (r'pureos\.memory\b', 'pureos.drivers.memory'),
    (r'pureos\.network\b', 'pureos.drivers.network'),
    (r'pureos\.drivers\b', 'pureos.drivers.base'),
    (r'pureos\.processes\b', 'pureos.subsystems.processes'),
    (r'pureos\.ipc\b', 'pureos.subsystems.ipc'),
    (r'pureos\.users\b', 'pureos.subsystems.users'),
    (r'pureos\.pkg\b', 'pureos.subsystems.pkg'),
    (r'pureos\.services\b', 'pureos.subsystems.services'),
    (r'pureos\.builtin_services\b', 'pureos.subsystems.builtin_services'),
    # Shell related
    (r'pureos\.parser\b', 'pureos.shell.parser'),
    (r'pureos\.cli\b', 'pureos.shell.cli'),
    (r'pureos\.desktop\b', 'pureos.shell.desktop'),
    (r'pureos\.shell\b', 'pureos.shell.shell'),
]

# We need to be careful with the order of shell and its submodules.
# If we replace pureos.shell with pureos.shell.shell first, then pureos.shell.parser becomes pureos.shell.shell.parser if it matches again.
# BUT we are using r'pureos\.shell\b'. 
# pureos.shell.parser does NOT match pureos.shell\b because of the dot after shell.
# Wait, \b matches the boundary between a word character and a non-word character. Dot is a non-word character.
# So \b DOES match before a dot.
# I should use a more specific regex to avoid double replacement.

ordered_mapping = [
    (r'pureos\.kernel', 'pureos.core.kernel'),
    (r'pureos\.boot', 'pureos.core.boot'),
    (r'pureos\.config', 'pureos.core.config'),
    (r'pureos\.utils', 'pureos.core.utils'),
    (r'pureos\.syslog', 'pureos.drivers.syslog'),
    (r'pureos\.audit', 'pureos.drivers.audit'),
    (r'pureos\.memory', 'pureos.drivers.memory'),
    (r'pureos\.network', 'pureos.drivers.network'),
    (r'pureos\.processes', 'pureos.subsystems.processes'),
    (r'pureos\.ipc', 'pureos.subsystems.ipc'),
    (r'pureos\.users', 'pureos.subsystems.users'),
    (r'pureos\.pkg', 'pureos.subsystems.pkg'),
    (r'pureos\.services', 'pureos.subsystems.services'),
    (r'pureos\.builtin_services', 'pureos.subsystems.builtin_services'),
    (r'pureos\.parser', 'pureos.shell.parser'),
    (r'pureos\.cli', 'pureos.shell.cli'),
    (r'pureos\.desktop', 'pureos.shell.desktop'),
    # Drivers and Shell should be last and use negative lookahead if possible, or just be very specific.
    # In Python regex we can use negative lookahead.
    (r'pureos\.drivers(?!\.(syslog|audit|memory|network|base))', 'pureos.drivers.base'),
    (r'pureos\.shell(?!\.(parser|cli|desktop|shell))', 'pureos.shell.shell'),
]

def update_file(path):
    with open(path, 'r') as f:
        content = f.read()
    
    new_content = content
    for pattern, replacement in ordered_mapping:
        new_content = re.sub(pattern, replacement, new_content)
    
    if new_content != content:
        with open(path, 'w') as f:
            f.write(new_content)
        return True
    return False

test_dir = 'tests'
updated_files = []
for root, dirs, files in os.walk(test_dir):
    for file in files:
        if file.endswith('.py'):
            path = os.path.join(root, file)
            if update_file(path):
                updated_files.append(path)

print(f"Updated {len(updated_files)} files.")
for f in updated_files:
    print(f"  {f}")

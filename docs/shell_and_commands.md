# Shell and Commands

The interactive shell in v2-PureOS simulates standard bash-like behavior, including command chaining, piping, redirection, and environment variables.

## Execution Lifecycle

When a user enters a command line in the shell (`pureos.shell.Shell`), the following steps occur:

1. **Command Sequence Splitting (`parser.py`)**: 
   The input line is split into logical execution units using `&&` (AND), `||` (OR), and `;` (sequential). Background jobs (`&`) are also separated here.
2. **Environment Variable Substitution**:
   Variables prefixed with `$` or enclosed in `${}` are substituted with their values from the shell's environment map.
3. **Pipeline Splitting**:
   Each command sequence is further split by the pipe operator `|`. Output from the left command becomes the input to the right command.
4. **Redirection Processing**:
   The parser scans for `>` (overwrite), `>>` (append), and `<` (input redirection). Redirect targets are handled within the VirtualFS.
5. **Tokenization & Aliasing**:
   The command string is split into tokens (words), respecting quotes (`"` and `'`) and escaped characters (`\`). The first token is checked against defined aliases; if a match is found, the alias is expanded recursively (up to 10 levels deep to prevent infinite loops).
6. **Execution (`commands.registry.CommandRegistry`)**:
   The `CommandRegistry` looks up the command class based on the first token and calls its `execute` method, passing the parsed tokens, pipeline input data (if any), and whether the output should be captured or directly printed.

## Command Registry

Commands are dynamically registered on startup by scanning the `pureos.commands` package. 

- **Automatic Registration**: Any class inheriting from `Command` that has a `name` attribute is automatically registered.
- **Manual Registration**: Modules can optionally provide a `register_<module>_commands(registry)` function for custom registration logic.

## Creating New Commands

To create a new shell command, create a subclass of `Command` (`pureos.commands.base.Command`).

```python
from pureos.commands.base import Command

class MyCommand(Command):
    name = "mycmd"
    description = "A custom command"
    usage = "mycmd [args]"
    aliases = ["mc"]

    def execute(self, parts, input_data=None, capture_output=False, raw_line=None):
        # parts[0] is 'mycmd'
        # parts[1:] are the arguments
        
        output = "Hello from mycmd!"
        
        # If capture_output is True, return the string.
        if capture_output:
            return output
            
        # Otherwise, print it and return True indicating success.
        print(output)
        return True
```

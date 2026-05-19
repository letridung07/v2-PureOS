# Cron Daemon in v2-PureOS

v2-PureOS features a built-in background `cron` service that runs periodically to execute scheduled tasks. Tasks are defined in the virtual crontab configuration file: `/etc/crontab`.

## How It Works

The `cron` service is registered as an auto-started background daemon thread. Once initialized, it checks the `/etc/crontab` file. If the current system time matches the time schedule specified in any crontab entry, the associated command is executed in a background process using the virtual OS scheduler.

## Crontab Configuration Format

The crontab file `/etc/crontab` follows standard 5-field cron syntax:

```text
.---------------- minute (0 - 59)
|  .------------- hour (0 - 23)
|  |  .---------- day of month (1 - 31)
|  |  |  .------- month (1 - 12 or jan-dec)
|  |  |  |  .---- day of week (0 - 6 or sun-sat; Sunday is 0)
|  |  |  |  |
*  *  *  *  *  command to run
```

### Supported Syntax
- Wildcards (`*`): matches any value in the field.
- Exact values (e.g. `15`): matches a specific value.
- Ranges (e.g. `10-15`): matches values within the specified range.
- Steps (e.g. `*/5` or `1-10/2`): matches step values.
- Lists (e.g. `1,3,5`): matches any of the comma-separated options.
- Textual names: Month (`jan`, `feb`, etc.) and Day of Week (`sun`, `mon`, etc.) values are normalized and supported.

*Note: Environment variables (such as `PATH=...`) are not supported in the crontab entries and will be skipped.*

## The `crontab` Command

Manage your cron configurations using the user-facing `crontab` utility.

### Usage
- `crontab <file>`: Install the contents of `<file>` as the active crontab `/etc/crontab`.
- `crontab -l`: List the active crontab configuration.
- `crontab -r`: Remove the active crontab configuration.

### Examples

1. **Write a crontab entry**:
   ```text
   * * * * * date >> /tmp/cron.log
   ```
   *This appends the current date to `/tmp/cron.log` every minute.*

2. **Save to a file and install**:
   ```text
   v2-pureos> write /tmp/mycron "* * * * * date >> /tmp/cron.log"
   v2-pureos> crontab /tmp/mycron
   ```

3. **Check current configurations**:
   ```text
   v2-pureos> crontab -l
   * * * * * date >> /tmp/cron.log
   ```

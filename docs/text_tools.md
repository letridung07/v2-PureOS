# Text Pipeline Tools

v2-PureOS ships eight composable text-processing commands that follow the Unix pipeline convention: each command reads from a **file argument** or from **standard input** (the previous pipe stage), and writes its output to standard output so it can be piped further.

---

## Pipeline Mechanics

Commands are chained with `|`. The shell captures the output of each stage and passes it as `input_data` to the next:

```text
v2-pureos> cat /etc/motd | grep Welcome | wc -w
```

All text commands respect the `capture_output` flag used internally by the shell's pipeline executor so intermediate results are never leaked to the terminal.

---

## `wc` — Word / Line / Byte Count

```
wc [-l] [-w] [-c] [file]
```

Without flags, prints **lines words bytes**. Flags select individual counts:

| Flag | Output |
|------|--------|
| `-l` | Line count |
| `-w` | Word count |
| `-c` | Byte count (UTF-8) |

### Examples

```text
v2-pureos> write /tmp/hi "hello world\nfoo bar\n"
v2-pureos> wc /tmp/hi
  2  4  20
v2-pureos> wc -l /tmp/hi
  2
v2-pureos> cat /tmp/hi | wc -w
  4
```

---

## `grep` — Pattern Filtering

```
grep [-i] [-v] [-n] [-c] [-E] <pattern> [file]
```

Prints every line that matches `<pattern>`. The pattern is treated as a regular expression when it contains special regex characters; otherwise as a literal string. Use `-E` to force extended regex mode.

| Flag | Meaning |
|------|---------|
| `-i` | Case-insensitive matching |
| `-v` | Invert — print lines that do **not** match |
| `-n` | Prefix each line with its line number |
| `-c` | Print match count only |
| `-E` | Extended regex (pattern always compiled as regex) |

### Examples

```text
v2-pureos> write /tmp/fruits "apple\nbanana\nApricot\ncherry\n"
v2-pureos> grep apple /tmp/fruits
apple
v2-pureos> grep -i apple /tmp/fruits
apple
Apricot
v2-pureos> grep -v a /tmp/fruits
cherry
v2-pureos> grep -c a /tmp/fruits
3
v2-pureos> grep -n a /tmp/fruits
1:apple
2:banana
3:Apricot
v2-pureos> grep -E ^[aA] /tmp/fruits
apple
Apricot
```

---

## `sort` — Sort Lines

```
sort [-r] [-n] [-u] [file]
```

| Flag | Meaning |
|------|---------|
| `-r` | Reverse order |
| `-n` | Numeric sort (compares leading numbers) |
| `-u` | Unique — remove duplicate lines after sorting |

### Examples

```text
v2-pureos> echo "banana\napple\ncherry" | sort
apple
banana
cherry
v2-pureos> echo "10\n2\n30" | sort -n
2
10
30
v2-pureos> echo "b\na\nb\na" | sort -u
a
b
```

---

## `uniq` — Deduplicate Adjacent Lines

```
uniq [-c] [-d] [-u] [file]
```

> [!NOTE]
> `uniq` only removes **adjacent** duplicates. Pipe through `sort` first to collapse all duplicates.

| Flag | Meaning |
|------|---------|
| `-c` | Prefix each output line with its occurrence count |
| `-d` | Print only lines that appear more than once |
| `-u` | Print only lines that appear exactly once |

### Examples

```text
v2-pureos> echo "a\na\nb\nc\nc" | uniq
a
b
c
v2-pureos> echo "a\na\nb\nc\nc" | uniq -c
      2 a
      1 b
      2 c
v2-pureos> echo "a\na\nb" | sort | uniq -d
a
```

---

## `cut` — Extract Fields or Characters

```
cut -f <fields> [-d <delim>] [file]
cut -c <range> [file]
```

**Field mode** (`-f`): splits each line on `<delim>` (default `\t`) and extracts the specified field(s).  
**Character mode** (`-c`): extracts character positions.

Field / character specs follow CSV-like notation: `1`, `1,3`, `2-4`, `1-3,6`.

### Examples

```text
v2-pureos> write /tmp/csv "name,age,city\nAlice,30,NYC\nBob,25,LA\n"
v2-pureos> cut -f 1 -d , /tmp/csv
name
Alice
Bob
v2-pureos> cut -f 1,3 -d , /tmp/csv
name,city
Alice,NYC
Bob,LA
v2-pureos> echo "hello world" | cut -c 1-5
hello
```

---

## `tr` — Translate or Delete Characters

```
tr [-d] [-s] <set1> [set2]
```

Reads from stdin only (always used in a pipeline or with redirection).

| Flag | Meaning |
|------|---------|
| `-d` | Delete characters in `set1`; `set2` not used |
| `-s` | Squeeze repeated characters in output |

Set specifications support `a-z` style ranges.

### Examples

```text
v2-pureos> echo "hello" | tr a-z A-Z
HELLO
v2-pureos> echo "hello world" | tr -d aeiou
hll wrld
v2-pureos> echo "aabbcc" | tr -s a-c
abc
v2-pureos> echo "hello" | tr l r
herro
```

---

## `xargs` — Execute Command with Stdin Arguments

```
xargs [-n <max_args>] <command> [initial_args...]
```

Reads whitespace-separated words from stdin and appends them as arguments to `<command>`. With `-n`, limits the number of stdin words per invocation (running the command multiple times if needed).

### Examples

```text
v2-pureos> echo "a b c" | xargs echo prefix
prefix a b c
v2-pureos> echo "a b c" | xargs -n 1 echo
a
b
c
v2-pureos> cat /tmp/dirs | xargs mkdir
```

---

## `base64` — Base64 Encode/Decode

```
base64 [-d] [file]
```

Encodes or decodes text using Base64. By default, it encodes. Use `-d` to decode.

| Flag | Meaning |
|------|---------|
| `-d` | Decode Base64 input into plain text |

### Examples

```text
v2-pureos> echo "hello" | base64
aGVsbG8=
v2-pureos> echo "aGVsbG8=" | base64 -d
hello
v2-pureos> write /tmp/plain "pureos"
v2-pureos> base64 /tmp/plain
cHVyZW9z
```

---

## Composing Pipelines

The power of these tools comes from chaining them:

```text
# Count unique words in a file
v2-pureos> cat /tmp/story | tr A-Z a-z | tr -d .,!? | tr ' ' '\n' | sort | uniq -c | sort -rn

# Extract and sort the second CSV column
v2-pureos> cat /tmp/data.csv | cut -f 2 -d , | sort -n

# Find lines with "error", number them, count results
v2-pureos> grep -n error /var/log/syslog | wc -l

# Delete all empty lines from a file and save
v2-pureos> cat /tmp/notes | grep -v "^$" > /tmp/notes_clean
```

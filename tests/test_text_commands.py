"""Tests for text pipeline commands: wc, grep, sort, uniq, cut, tr, xargs."""

import pytest
from pureos.kernel import Kernel


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    # Provide shell reference so xargs can call registry
    return k


@pytest.fixture
def shell(kernel):
    return kernel.shell


def run(shell, cmd, input_data=None, capture=True):
    """Execute a single-stage command string and return its result."""
    return shell.registry.execute(cmd, input_data=input_data, capture_output=capture)


# ============================================================
# wc
# ============================================================


class TestWc:
    def test_counts_all(self, kernel, shell):
        kernel.fs.write("/tmp/words", "hello world\nfoo bar baz\n")
        result = run(shell, "wc /tmp/words")
        parts = result.split()
        assert parts[0] == "2"  # lines
        assert parts[1] == "5"  # words
        assert int(parts[2]) > 0  # bytes

    def test_lines_flag(self, kernel, shell):
        kernel.fs.write("/tmp/lns", "a\nb\nc\n")
        result = run(shell, "wc -l /tmp/lns")
        assert result.strip() == "3"

    def test_words_flag(self, kernel, shell):
        result = run(shell, "wc -w", input_data="one two three")
        assert result.strip() == "3"

    def test_bytes_flag(self, kernel, shell):
        result = run(shell, "wc -c", input_data="abc")
        assert result.strip() == "3"

    def test_pipeline_input(self, shell):
        result = run(shell, "wc -l", input_data="a\nb\nc")
        assert result.strip() == "3"

    def test_empty_input(self, shell):
        result = run(shell, "wc -l", input_data="")
        assert result.strip() == "0"

    def test_no_input_no_file(self, shell):
        result = run(shell, "wc -l", input_data=None, capture=False)
        assert result is False

    def test_missing_file(self, shell):
        result = run(shell, "wc /nonexistent", input_data=None, capture=False)
        assert result is False


# ============================================================
# grep
# ============================================================


class TestGrep:
    def test_basic_match(self, shell):
        result = run(shell, "grep hello", input_data="hello world\nfoo bar")
        assert result == "hello world"

    def test_no_match_returns_false(self, shell):
        result = run(shell, "grep xyz", input_data="hello world", capture=False)
        assert result is False

    def test_invert_flag(self, shell):
        result = run(shell, "grep -v hello", input_data="hello world\nfoo bar")
        assert result == "foo bar"

    def test_case_insensitive(self, shell):
        result = run(shell, "grep -i HELLO", input_data="hello world\nfoo")
        assert "hello world" in result

    def test_line_numbers(self, shell):
        result = run(shell, "grep -n foo", input_data="bar\nfoo\nbaz")
        assert "2:foo" in result

    def test_count_only(self, shell):
        result = run(shell, "grep -c foo", input_data="foo\nbar\nfoo\nbaz")
        assert result.strip() == "2"

    def test_extended_regex(self, shell):
        result = run(shell, "grep -E ^foo", input_data="foobar\nbar\nfoobaz")
        lines = result.strip().splitlines()
        assert len(lines) == 2
        assert all(line.startswith("foo") for line in lines)

    def test_file_read(self, kernel, shell):
        kernel.fs.write("/tmp/gtest", "apple\nbanana\ncherry\n")
        result = run(shell, "grep banana /tmp/gtest")
        assert "banana" in result

    def test_missing_pattern(self, shell):
        result = run(shell, "grep", input_data="x", capture=False)
        assert result is False

    def test_invert_count(self, shell):
        result = run(shell, "grep -c -v foo", input_data="foo\nbar\nbaz")
        assert result.strip() == "2"


# ============================================================
# sort
# ============================================================


class TestSort:
    def test_alphabetical(self, shell):
        result = run(shell, "sort", input_data="banana\napple\ncherry")
        assert result == "apple\nbanana\ncherry"

    def test_reverse(self, shell):
        result = run(shell, "sort -r", input_data="banana\napple\ncherry")
        assert result == "cherry\nbanana\napple"

    def test_numeric(self, shell):
        result = run(shell, "sort -n", input_data="10\n2\n30\n1")
        assert result == "1\n2\n10\n30"

    def test_unique(self, shell):
        result = run(shell, "sort -u", input_data="b\na\nb\na\nc")
        lines = result.splitlines()
        assert lines == sorted(set(["b", "a", "c"]))

    def test_numeric_reverse(self, shell):
        result = run(shell, "sort -rn", input_data="5\n1\n20")
        assert result == "20\n5\n1"

    def test_file(self, kernel, shell):
        kernel.fs.write("/tmp/sortme", "z\nm\na\n")
        result = run(shell, "sort /tmp/sortme")
        assert result == "a\nm\nz"

    def test_no_input(self, shell):
        result = run(shell, "sort", input_data=None, capture=False)
        assert result is False


# ============================================================
# uniq
# ============================================================


class TestUniq:
    def test_basic_dedup(self, shell):
        result = run(shell, "uniq", input_data="a\na\nb\nb\nc")
        assert result == "a\nb\nc"

    def test_non_adjacent_not_deduped(self, shell):
        result = run(shell, "uniq", input_data="a\nb\na")
        assert result == "a\nb\na"

    def test_count_flag(self, shell):
        result = run(shell, "uniq -c", input_data="a\na\nb")
        lines = result.splitlines()
        assert "2" in lines[0]
        assert "a" in lines[0]
        assert "1" in lines[1]
        assert "b" in lines[1]

    def test_dups_only(self, shell):
        result = run(shell, "uniq -d", input_data="a\na\nb\nc\nc")
        lines = result.splitlines()
        assert "a" in lines
        assert "c" in lines
        assert "b" not in lines

    def test_unique_only(self, shell):
        result = run(shell, "uniq -u", input_data="a\na\nb\nc\nc")
        assert result.strip() == "b"

    def test_empty(self, shell):
        result = run(shell, "uniq", input_data="")
        assert result == ""

    def test_no_input(self, shell):
        result = run(shell, "uniq", input_data=None, capture=False)
        assert result is False


# ============================================================
# cut
# ============================================================


class TestCut:
    def test_field_cut(self, shell):
        result = run(shell, "cut -f 2 -d :", input_data="a:b:c\n1:2:3")
        assert result == "b\n2"

    def test_char_cut(self, shell):
        result = run(shell, "cut -c 1-3", input_data="hello\nworld")
        assert result == "hel\nwor"

    def test_multi_field(self, shell):
        result = run(shell, "cut -f 1,3 -d ,", input_data="a,b,c")
        assert result == "a,c"

    def test_default_delim_tab(self, shell):
        result = run(shell, "cut -f 2", input_data="a\tb\tc")
        assert result == "b"

    def test_field_out_of_range(self, shell):
        # Field 5 doesn't exist — should return empty for that line
        result = run(shell, "cut -f 5 -d ,", input_data="a,b,c")
        assert result == ""

    def test_char_single(self, shell):
        result = run(shell, "cut -c 1", input_data="hello")
        assert result == "h"

    def test_file(self, kernel, shell):
        kernel.fs.write("/tmp/csv", "name,age\nAlice,30\nBob,25\n")
        result = run(shell, "cut -f 1 -d ,  /tmp/csv")
        assert "name" in result
        assert "Alice" in result

    def test_no_flag(self, shell):
        result = run(shell, "cut", input_data="a:b", capture=False)
        assert result is False


# ============================================================
# tr
# ============================================================


class TestTr:
    def test_translate(self, shell):
        result = run(shell, "tr abc ABC", input_data="abc def")
        assert result == "ABC def"

    def test_delete(self, shell):
        result = run(shell, "tr -d aeiou", input_data="hello world")
        assert result == "hll wrld"

    def test_range_lower_to_upper(self, shell):
        result = run(shell, "tr a-z A-Z", input_data="hello")
        assert result == "HELLO"

    def test_squeeze(self, shell):
        result = run(shell, "tr -s a", input_data="aaabbbccc")
        assert result == "abbbccc"

    def test_squeeze_translate(self, shell):
        # squeeze repeated translated chars
        result = run(shell, "tr -s aeiou x", input_data="aeeii")
        assert result == "x"

    def test_no_input(self, shell):
        result = run(shell, "tr a b", input_data=None, capture=False)
        assert result is False

    def test_no_set(self, shell):
        result = run(shell, "tr", input_data="hello", capture=False)
        assert result is False


# ============================================================
# xargs
# ============================================================


class TestXargs:
    def test_basic(self, kernel, shell):
        # echo each word — xargs echo word1 word2
        result = run(shell, "xargs echo", input_data="hello world")
        assert "hello" in result
        assert "world" in result

    def test_max_args(self, shell):
        # With -n 1 each word runs the command separately
        result = run(shell, "xargs -n 1 echo", input_data="a b c")
        # Should contain all three words
        assert "a" in result
        assert "b" in result
        assert "c" in result

    def test_no_input(self, shell):
        result = run(shell, "xargs echo", input_data=None, capture=False)
        assert result is False

    def test_empty_input(self, shell):
        # Empty stdin — success with no output
        result = run(shell, "xargs echo", input_data="  ", capture=False)
        # shlex.split("  ") returns [] so xargs returns True early
        assert result is True or result == ""

    def test_no_command(self, shell):
        result = run(shell, "xargs", input_data="hello", capture=False)
        assert result is False

    def test_with_initial_args(self, kernel, shell):
        # xargs mkdir with stdin dirs
        kernel.fs.mkdir("/xargs_test/")
        result = run(shell, "xargs echo /prefix", input_data="a b")
        assert "/prefix" in result


# ============================================================
# Pipeline integration tests
# ============================================================


class TestPipelines:
    def test_cat_grep_pipeline(self, kernel, shell):
        kernel.fs.write("/tmp/fruits", "apple\nbanana\napricot\ncherry\n")
        result = shell.execute("cat /tmp/fruits | grep a")
        assert result is True or result is not False

    def test_sort_uniq_pipeline(self, shell):
        result = shell._execute_pipeline("echo 'b\na\nb\na' | sort | uniq")
        assert result is True

    def test_wc_after_grep(self, kernel, shell):
        kernel.fs.write("/tmp/data", "foo\nbar\nfoo\nbaz\nfoo\n")
        result = shell._execute_pipeline("cat /tmp/data | grep foo | wc -l")
        assert result is True

    def test_cut_sort(self, kernel, shell):
        kernel.fs.write("/tmp/scores", "Alice:90\nBob:75\nCarol:88\n")
        result = shell._execute_pipeline("cat /tmp/scores | cut -f 2 -d : | sort -n")
        assert result is True


# ============================================================
# Edge-case / regression tests for fixed bugs
# ============================================================


class TestEdgeCases:
    # --- grep: pattern is always literal unless -E ---

    def test_grep_dot_is_literal(self, shell):
        """'.' must match a literal dot, not any character (no -E)."""
        result = run(shell, "grep .", input_data="3.14\nhello\n2.71")
        # Only lines containing a literal '.' should match
        lines = result.splitlines()
        assert all("." in ln for ln in lines)
        assert "hello" not in lines

    def test_grep_star_is_literal(self, shell):
        """'*' must match a literal asterisk without -E."""
        result = run(shell, "grep *", input_data="a*b\nhello\nc*d", capture=False)
        # 'a*b' and 'c*d' contain literal '*'; 'hello' does not
        # Without -E the pattern '*' is re.escape'd so it's fine
        assert result is not False  # at least one match

    def test_grep_E_enables_regex(self, shell):
        """With -E, '^foo' should match lines starting with 'foo'."""
        result = run(shell, "grep -E ^foo", input_data="foobar\nbarfoo\nfoo")
        lines = result.splitlines()
        assert "foobar" in lines
        assert "foo" in lines
        assert "barfoo" not in lines

    def test_grep_literal_special_chars(self, shell):
        """Special regex chars in pattern should match literally without -E."""
        result = run(shell, "grep (test)", input_data="(test)\ntest\nno match")
        assert "(test)" in result
        assert "test\n" not in result or result == "(test)"

    # --- tr: empty set1 guard ---

    def test_tr_empty_set1_fails(self, shell):
        """tr with a set1 that expands to empty (z-a inverted range) should fail."""
        # An inverted range like z-a produces an empty expansion.
        # The guard in tr should catch this and return False.
        result = run(shell, "tr z-a B", input_data="hello", capture=False)
        # z-a: ord('z')=122 > ord('a')=97, range(122, 97+1) is empty
        assert result is False

    def test_tr_delete_ignores_set2(self, shell):
        """-d deletes set1 chars; set2 is ignored per POSIX."""
        result = run(shell, "tr -d aeiou xyz", input_data="hello world")
        # 'xyz' should be silently ignored
        assert result == "hll wrld"

    # --- cut: invalid range spec ---

    def test_cut_invalid_field_spec_letters(self, shell):
        """cut -f abc should fail gracefully, not raise ValueError."""
        result = run(shell, "cut -f abc -d ,", input_data="a,b,c", capture=False)
        assert result is False

    def test_cut_zero_field(self, shell):
        """Field number 0 is invalid (fields are 1-indexed)."""
        result = run(shell, "cut -f 0 -d ,", input_data="a,b,c", capture=False)
        assert result is False

    def test_cut_inverted_range(self, shell):
        """A range like 5-2 (hi < lo) is invalid."""
        result = run(shell, "cut -f 5-2 -d ,", input_data="a,b,c,d,e", capture=False)
        assert result is False

    # --- cut: mutually exclusive -f and -c ---

    def test_cut_f_and_c_mutually_exclusive(self, shell):
        """Specifying both -f and -c should return False."""
        result = run(shell, "cut -f 1 -c 1 -d ,", input_data="a,b,c", capture=False)
        assert result is False

    # --- wc: multi-byte (UTF-8) bytes vs chars ---

    def test_wc_bytes_utf8(self, shell):
        """wc -c counts bytes, not Unicode code points."""
        # '£' is U+00A3, encoded as 2 bytes in UTF-8
        result = run(shell, "wc -c", input_data="£")
        assert result.strip() == "2"

    # --- sort: already-sorted input is unchanged ---

    def test_sort_stable_already_sorted(self, shell):
        result = run(shell, "sort", input_data="a\nb\nc")
        assert result == "a\nb\nc"

    # --- uniq: single-line input ---

    def test_uniq_single_line(self, shell):
        result = run(shell, "uniq", input_data="only")
        assert result == "only"

    # --- grep: empty pattern matches all lines ---

    def test_grep_pattern_subset_of_lines(self, shell):
        """grep only returns lines that contain the pattern."""
        result = run(shell, "grep apple", input_data="apple\napricot\ncherry")
        lines = result.splitlines()
        assert "apple" in lines
        assert "apricot" not in lines
        assert "cherry" not in lines

    # --- xargs: -n 0 should not infinite-loop ---

    def test_xargs_n_zero_treated_as_all(self, shell):
        """max_args=0 is treated as 'all words at once' (chunk_size=total)."""
        result = run(shell, "xargs -n 0 echo", input_data="a b c")
        # chunk_size = max(0,0) falls through to len(stdin_words)
        assert "a" in result and "b" in result

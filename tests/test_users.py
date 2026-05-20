"""Tests for user accounts, group memberships, file ownerships, and permissions."""

import pytest
from unittest.mock import patch
from pureos.kernel import Kernel
from pureos.users import User


@pytest.fixture
def kernel():
    k = Kernel({"format_on_boot": True, "auto_start_services": False})
    k.initialize()
    return k


@pytest.fixture
def shell(kernel):
    return kernel.shell


def run(shell, cmd, input_data=None, capture=True):
    # Ensure variables like $? are expanded
    expanded = shell._substitute_env_vars(cmd)
    return shell.registry.execute(
        expanded, input_data=input_data, capture_output=capture
    )


class TestUserModels:
    def test_user_creation_and_hashing(self):
        user = User("testuser", uid=1001, gid=1001)
        assert user.username == "testuser"
        assert user.uid == 1001
        assert user.gid == 1001
        assert user.gids == [1001]
        assert user.password_hash == ""

        # Test setting and checking password
        user.set_password("mypassword")
        assert user.password_hash != ""
        assert user.check_password("mypassword") is True
        assert user.check_password("wrong") is False

    def test_userdb_defaults(self, kernel):
        users = kernel.users
        assert "root" in users.users
        assert "guest" in users.users
        assert users.current_user.username == "root"
        assert kernel.fs.exists("/etc/passwd")
        assert kernel.fs.exists("/etc/group")


class TestUserCommands:
    def test_whoami(self, shell):
        res = run(shell, "whoami")
        assert res.strip() == "root"

    def test_useradd_and_userdel_permissions(self, kernel, shell):
        # Create non-root user
        kernel.users.add_user("alice")

        # Switch to alice
        success = kernel.users.su("alice")
        assert success is True
        assert kernel.users.current_user.username == "alice"

        # alice trying to add user bob should fail (Permission denied)
        res = run(shell, "useradd bob", capture=False)
        assert res is False
        assert "bob" not in kernel.users.users

        # Switch back to root (bypassed as root has no password hash)
        success = kernel.users.su("root")
        assert success is True

        # root adding user bob should succeed
        res = run(shell, "useradd bob", capture=False)
        assert res is True
        assert "bob" in kernel.users.users

        # alice trying to delete bob should fail
        kernel.users.su("alice")
        res = run(shell, "userdel bob", capture=False)
        assert res is False
        assert "bob" in kernel.users.users

        # root deleting bob should succeed
        kernel.users.su("root")
        res = run(shell, "userdel bob", capture=False)
        assert res is True
        assert "bob" not in kernel.users.users

    def test_passwd_and_su_with_auth(self, kernel, shell):
        # Create user with password
        kernel.users.add_user("charlie")

        # Switch to root (bypasses check)
        kernel.users.su("root")

        # Change charlie's password via passwd command (mock inputs)
        with patch("builtins.input", side_effect=["pwd123", "pwd123"]):
            res = run(shell, "passwd charlie", capture=False)
            assert res is True

        assert kernel.users.users["charlie"].check_password("pwd123") is True

        # Switch user to charlie. Since we are root, su doesn't prompt for password
        success = kernel.users.su("charlie")
        assert success is True

        # Switch from charlie to root (bypassed as root has no password hash)
        success = kernel.users.su("root")
        assert success is True

        # Set password for root
        with patch("builtins.input", side_effect=["rootpwd", "rootpwd"]):
            run(shell, "passwd root", capture=False)

        # Switch to charlie
        kernel.users.su("charlie")

        # Now su to root from charlie. It should prompt for password.
        # Wrong password
        with patch("builtins.input", return_value="wrongpwd"):
            res = run(shell, "su root", capture=False)
            assert res is False
            assert kernel.users.current_user.username == "charlie"

        # Correct password
        with patch("builtins.input", return_value="rootpwd"):
            res = run(shell, "su root", capture=False)
            assert res is True
            assert kernel.users.current_user.username == "root"

    def test_groups_command(self, kernel, shell):
        kernel.users.add_user("david")
        res = run(shell, "groups david")
        assert "david" in res


class TestFilePermissions:
    def test_creation_ownership(self, kernel, shell):
        # Create a file as root
        run(shell, "write /tmp/rootfile 'root content'", capture=False)
        assert kernel.fs.state.owners["/tmp/rootfile"] == 0
        assert kernel.fs.state.groups["/tmp/rootfile"] == 0

        # Create user dev and switch to them
        kernel.users.add_user("dev")
        kernel.users.su("dev")
        uid = kernel.users.users["dev"].uid
        gid = kernel.users.users["dev"].gid

        # Create file as dev
        run(shell, "write /tmp/devfile 'dev content'", capture=False)
        assert kernel.fs.state.owners["/tmp/devfile"] == uid
        assert kernel.fs.state.groups["/tmp/devfile"] == gid

    def test_access_controls(self, kernel, shell):
        kernel.users.add_user("user1")
        kernel.users.add_user("user2")

        # Create a private file for user1
        kernel.users.su("user1")
        run(shell, "write /tmp/private 'secret'", capture=False)
        # Check permissions: owner read/write (600)
        run(shell, "chmod 600 /tmp/private", capture=False)

        # user2 should NOT be able to read or write it
        kernel.users.su("user2")
        with pytest.raises(PermissionError):
            kernel.fs.read("/tmp/private")

        # root user should be able to read it anyway (root bypasses)
        kernel.users.su("root")
        content = kernel.fs.read("/tmp/private")
        assert content == "secret"

    def test_group_access(self, kernel, shell):
        # Ensure shared group exists
        kernel.users.groups["shared"] = 5000

        # Add members
        kernel.users.add_user("member")
        kernel.users.add_user("nonmember")

        kernel.users.group_members["shared"] = ["member"]
        kernel.users.users["member"].gids.append(5000)

        # root creates file, sets group to shared and mode to 640
        kernel.users.su("root")
        run(shell, "write /tmp/sharedfile 'hello group'", capture=False)
        run(shell, "chgrp shared /tmp/sharedfile", capture=False)
        run(shell, "chmod 640 /tmp/sharedfile", capture=False)

        # member should be able to read
        kernel.users.su("member")
        assert kernel.fs.read("/tmp/sharedfile") == "hello group"

        # nonmember should NOT be able to read
        kernel.users.su("nonmember")
        with pytest.raises(PermissionError):
            kernel.fs.read("/tmp/sharedfile")

    def test_chown_chgrp_commands(self, kernel, shell):
        # Create a file
        run(shell, "write /tmp/chfile 'test'", capture=False)
        assert kernel.fs.state.owners["/tmp/chfile"] == 0

        # Create user
        kernel.users.add_user("tester")
        tester_uid = kernel.users.users["tester"].uid

        # chown the file
        res = run(shell, "chown tester /tmp/chfile", capture=False)
        assert res is True
        assert kernel.fs.state.owners["/tmp/chfile"] == tester_uid

        # chown to uid directly
        res = run(shell, "chown 0 /tmp/chfile", capture=False)
        assert res is True
        assert kernel.fs.state.owners["/tmp/chfile"] == 0

        # chgrp
        res = run(shell, "chgrp tester /tmp/chfile", capture=False)
        assert res is True
        assert kernel.fs.state.groups["/tmp/chfile"] == kernel.users.groups["tester"]


class TestExitStatusVariable:
    def test_exit_status_evaluation(self, shell):
        # A successful command should set $? to 0
        shell.execute("whoami")
        assert shell.env["?"] == "0"

        # Test echo $? expansion
        # This translates to 'echo 0', runs successfully, and keeps status 0
        shell.execute("echo $?")
        assert shell.env["?"] == "0"

        # An unknown command / failure should set $? to 1
        shell.execute("su non_existent_user")
        assert shell.env["?"] == "1"

        # This translates to 'echo 1', runs successfully, and sets status back to 0
        shell.execute("echo $?")
        assert shell.env["?"] == "0"

        # Set to 1 again
        shell.execute("su non_existent_user")
        assert shell.env["?"] == "1"

        # Test braced form ${?} - translates to 'echo 1' and sets status back to 0
        shell.execute("echo ${?}")
        assert shell.env["?"] == "0"


class TestUserEdgeCases:
    def test_passwd_non_root_permission_elevation(self, kernel, shell):
        # Create non-root user
        kernel.users.add_user("bob")

        # Switch to bob
        success = kernel.users.su("bob")
        assert success is True
        assert kernel.users.current_user.username == "bob"

        # Change password (succeeds via temporary root elevation)
        with patch("builtins.input", side_effect=["bobpwd123", "bobpwd123"]):
            res = run(shell, "passwd bob", capture=False)
            assert res is True

        assert kernel.users.users["bob"].check_password("bobpwd123") is True

    def test_directory_deletion_cleans_up_ownership_mappings(self, kernel, shell):
        # Create a directory
        kernel.fs.mkdir("/tmp/deldir")
        kernel.fs.write("/tmp/deldir/file1", "content")

        assert "/tmp/deldir/" in kernel.fs.state.owners
        assert "/tmp/deldir/file1" in kernel.fs.state.owners

        # Delete directory
        kernel.fs.delete("/tmp/deldir")

        assert "/tmp/deldir/" not in kernel.fs.state.owners
        assert "/tmp/deldir/file1" not in kernel.fs.state.owners
        assert "/tmp/deldir/" not in kernel.fs.state.groups
        assert "/tmp/deldir/file1" not in kernel.fs.state.groups

    def test_rename_preserves_ownership_and_copy_sets_active_ownership(
        self, kernel, shell
    ):
        # Create dev user
        kernel.users.add_user("devuser")

        # Create file as root
        kernel.fs.write("/tmp/rootfile", "data")
        assert kernel.fs.state.owners["/tmp/rootfile"] == 0

        # Switch to devuser
        kernel.users.su("devuser")
        dev_uid = kernel.users.users["devuser"].uid
        dev_gid = kernel.users.users["devuser"].gid

        # Copy file: should take devuser's ownership context
        kernel.fs.copy("/tmp/rootfile", "/tmp/copiedfile")
        assert kernel.fs.state.owners["/tmp/copiedfile"] == dev_uid
        assert kernel.fs.state.groups["/tmp/copiedfile"] == dev_gid

        # Rename file: should preserve original ownership (root)
        kernel.users.su("root")
        kernel.fs.rename("/tmp/rootfile", "/tmp/movedfile")
        assert kernel.fs.state.owners["/tmp/movedfile"] == 0

    def test_chgrp_non_root_group_membership_enforcement(self, kernel, shell):
        # Create non-root user and groups
        kernel.users.groups["groupA"] = 6000
        kernel.users.groups["groupB"] = 6001

        kernel.users.add_user("userA")
        # Add userA to groupA but NOT groupB
        kernel.users.group_members["groupA"] = ["userA"]
        kernel.users.users["userA"].gids.append(6000)

        # userA creates a file
        kernel.users.su("userA")
        run(shell, "write /tmp/userAfile 'content'", capture=False)

        # userA tries to chgrp to groupA (should succeed)
        res = run(shell, "chgrp groupA /tmp/userAfile", capture=False)
        assert res is True
        assert kernel.fs.state.groups["/tmp/userAfile"] == 6000

        # userA tries to chgrp to groupB (should fail - not member)
        res = run(shell, "chgrp groupB /tmp/userAfile", capture=False)
        assert res is False
        assert kernel.fs.state.groups["/tmp/userAfile"] == 6000  # unchanged


class TestSudoCommand:
    def test_sudo_as_root(self, kernel, shell):
        kernel.users.su("root")
        res = run(shell, "sudo whoami")
        assert res.strip() == "root"

    def test_sudo_as_guest_no_password(self, kernel, shell):
        kernel.users.su("guest")
        res = run(shell, "sudo whoami")
        assert res.strip() == "root"
        assert kernel.users.current_user.username == "guest"

    def test_sudo_unauthorized_user(self, kernel, shell):
        kernel.users.add_user("unauth")
        kernel.users.su("unauth")
        res = run(shell, "sudo whoami", capture=False)
        assert res is False
        assert kernel.users.current_user.username == "unauth"

    def test_sudo_with_password(self, kernel, shell):
        kernel.users.add_user("alice")
        kernel.users.groups["sudo"] = 27
        if "sudo" not in kernel.users.group_members:
            kernel.users.group_members["sudo"] = []
        if "alice" not in kernel.users.group_members["sudo"]:
            kernel.users.group_members["sudo"].append("alice")
        if 27 not in kernel.users.users["alice"].gids:
            kernel.users.users["alice"].gids.append(27)

        kernel.users.su("root")
        with patch("builtins.input", side_effect=["alicepwd", "alicepwd"]):
            run(shell, "passwd alice", capture=False)

        kernel.users.su("alice")

        with patch("builtins.input", return_value="wrongpwd"):
            res = run(shell, "sudo whoami", capture=False)
            assert res is False
            assert kernel.users.current_user.username == "alice"

        with patch("builtins.input", return_value="alicepwd"):
            res = run(shell, "sudo whoami")
            assert res.strip() == "root"
            assert kernel.users.current_user.username == "alice"

    def test_sudo_syntax_error(self, kernel, shell):
        kernel.users.su("root")
        res = run(shell, "sudo", capture=False)
        assert res is False

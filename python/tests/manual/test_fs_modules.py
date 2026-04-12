"""Dedicated tests for the ``adk_fluent._fs`` foundation.

Covers the FsBackend protocol, LocalBackend (disk), MemoryBackend
(dict-backed fake), the SandboxedBackend decorator, and the backend-driven
workspace tool factories.
"""

from __future__ import annotations

import os

import pytest

from adk_fluent import (
    FsBackend,
    FsStat,
    H,
    LocalBackend,
    MemoryBackend,
    SandboxedBackend,
    SandboxPolicy,
    SandboxViolation,
    workspace_tools_with_backend,
)

# ======================================================================
# Protocol
# ======================================================================


class TestProtocol:
    def test_local_satisfies_protocol(self):
        assert isinstance(LocalBackend(), FsBackend)

    def test_memory_satisfies_protocol(self):
        assert isinstance(MemoryBackend(), FsBackend)

    def test_sandboxed_satisfies_protocol(self):
        backend = SandboxedBackend(MemoryBackend(), SandboxPolicy())
        assert isinstance(backend, FsBackend)


# ======================================================================
# MemoryBackend
# ======================================================================


class TestMemoryBackend:
    def test_seeded_write_and_read(self):
        mem = MemoryBackend({"/a/b.txt": "hello"})
        assert mem.exists("/a/b.txt")
        assert mem.read_text("/a/b.txt") == "hello"

    def test_read_missing_raises(self):
        mem = MemoryBackend()
        with pytest.raises(FileNotFoundError):
            mem.read_text("/nope")

    def test_write_creates_parent_dirs(self):
        mem = MemoryBackend()
        mem.write_text("/deep/nested/file.txt", "x")
        entries = {e.name for e in mem.list_dir("/deep")}
        assert "nested" in entries

    def test_stat_returns_size(self):
        mem = MemoryBackend({"/a": "hello"})
        st = mem.stat("/a")
        assert isinstance(st, FsStat)
        assert st.size == 5
        assert st.is_file and not st.is_dir

    def test_stat_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            MemoryBackend().stat("/nope")

    def test_list_dir_separates_files_and_dirs(self):
        mem = MemoryBackend(
            {
                "/root/a.txt": "a",
                "/root/b.py": "b",
                "/root/sub/c.txt": "c",
            }
        )
        entries = mem.list_dir("/root")
        names = {e.name for e in entries}
        assert names == {"a.txt", "b.py", "sub"}
        by_name = {e.name: e for e in entries}
        assert by_name["sub"].is_dir
        assert by_name["a.txt"].is_file

    def test_list_dir_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            MemoryBackend().list_dir("/nope")

    def test_glob_double_star(self):
        mem = MemoryBackend(
            {
                "/root/a.py": "",
                "/root/sub/b.py": "",
                "/root/sub/deep/c.py": "",
                "/root/skip.txt": "",
            }
        )
        results = mem.glob("**/*.py", root="/root")
        assert "/root/a.py" in results
        assert "/root/sub/b.py" in results
        assert "/root/sub/deep/c.py" in results
        assert "/root/skip.txt" not in results

    def test_glob_single_component(self):
        mem = MemoryBackend({"/root/a.py": "", "/root/b.txt": ""})
        assert mem.glob("*.py", root="/root") == ["/root/a.py"]

    def test_delete_file(self):
        mem = MemoryBackend({"/a.txt": "x"})
        mem.delete("/a.txt")
        assert not mem.exists("/a.txt")

    def test_delete_missing_raises(self):
        with pytest.raises(FileNotFoundError):
            MemoryBackend().delete("/nope")

    def test_mkdir_exist_ok(self):
        mem = MemoryBackend()
        mem.mkdir("/a/b")
        mem.mkdir("/a/b")  # no raise
        with pytest.raises(FileExistsError):
            mem.mkdir("/a/b", exist_ok=False)

    def test_iter_files_recursive(self):
        mem = MemoryBackend({"/r/a": "", "/r/sub/b": "", "/other": ""})
        files = list(mem.iter_files("/r"))
        assert "/r/a" in files
        assert "/r/sub/b" in files
        assert "/other" not in files


# ======================================================================
# LocalBackend
# ======================================================================


class TestLocalBackend:
    def test_read_write_cycle(self, tmp_path):
        backend = LocalBackend(root=str(tmp_path))
        backend.write_text("a.txt", "hello")
        assert backend.exists("a.txt")
        assert backend.read_text("a.txt") == "hello"

    def test_list_dir(self, tmp_path):
        (tmp_path / "f.txt").write_text("x")
        (tmp_path / "sub").mkdir()
        backend = LocalBackend(root=str(tmp_path))
        names = {e.name for e in backend.list_dir(".")}
        assert {"f.txt", "sub"} <= names

    def test_glob(self, tmp_path):
        (tmp_path / "a.py").write_text("")
        (tmp_path / "b.txt").write_text("")
        backend = LocalBackend(root=str(tmp_path))
        matches = backend.glob("*.py")
        assert any(m.endswith("a.py") for m in matches)

    def test_stat_file(self, tmp_path):
        (tmp_path / "x.txt").write_text("hello")
        backend = LocalBackend(root=str(tmp_path))
        st = backend.stat("x.txt")
        assert st.is_file
        assert st.size == 5

    def test_mkdir_and_delete_empty_dir(self, tmp_path):
        backend = LocalBackend(root=str(tmp_path))
        backend.mkdir("newdir")
        assert backend.exists("newdir")
        backend.delete("newdir")
        assert not backend.exists("newdir")


# ======================================================================
# SandboxedBackend
# ======================================================================


class TestSandboxedBackend:
    def _make(self, tmp_path):
        ws = str(tmp_path)
        backend = SandboxedBackend(
            LocalBackend(),
            SandboxPolicy(workspace=ws),
        )
        return ws, backend

    def test_inside_workspace_allowed(self, tmp_path):
        ws, backend = self._make(tmp_path)
        backend.write_text(os.path.join(ws, "a.txt"), "x")
        assert backend.read_text(os.path.join(ws, "a.txt")) == "x"

    def test_outside_workspace_denied_read(self, tmp_path):
        _, backend = self._make(tmp_path)
        with pytest.raises(SandboxViolation):
            backend.read_text("/etc/passwd")

    def test_outside_workspace_denied_write(self, tmp_path):
        _, backend = self._make(tmp_path)
        with pytest.raises(SandboxViolation):
            backend.write_text("/tmp/evil-outside-ws.txt", "x")

    def test_exists_returns_false_instead_of_raising(self, tmp_path):
        _, backend = self._make(tmp_path)
        assert backend.exists("/etc/passwd") is False

    def test_relative_path_is_resolved_via_workspace(self, tmp_path):
        ws, backend = self._make(tmp_path)
        backend.write_text("rel.txt", "data")
        assert (tmp_path / "rel.txt").read_text() == "data"

    def test_glob_scoped_to_workspace(self, tmp_path):
        ws, backend = self._make(tmp_path)
        (tmp_path / "a.py").write_text("")
        matches = backend.glob("*.py")
        assert any(m.endswith("a.py") for m in matches)

    def test_inner_and_sandbox_properties(self, tmp_path):
        _, backend = self._make(tmp_path)
        assert isinstance(backend.inner, LocalBackend)
        assert isinstance(backend.sandbox, SandboxPolicy)


# ======================================================================
# Backend-driven workspace tools
# ======================================================================


class TestBackendTools:
    def _mem(self):
        return MemoryBackend(
            {
                "/ws/a.txt": "line1\nline2\nline3\n",
                "/ws/b.py": "x = 1\ny = 2\n",
                "/ws/sub/c.txt": "buried\n",
            }
        )

    def test_read_file_tool(self):
        tools = workspace_tools_with_backend(self._mem())
        by_name = {t.__name__: t for t in tools}
        out = by_name["read_file"]("/ws/a.txt")
        assert "1\tline1" in out
        assert "3\tline3" in out

    def test_read_file_missing(self):
        tools = workspace_tools_with_backend(self._mem())
        out = {t.__name__: t for t in tools}["read_file"]("/ws/nope")
        assert "not found" in out

    def test_edit_file_tool(self):
        mem = self._mem()
        tools = {t.__name__: t for t in workspace_tools_with_backend(mem)}
        out = tools["edit_file"]("/ws/a.txt", "line2", "LINE2")
        assert "Successfully" in out
        assert "LINE2" in mem.read_text("/ws/a.txt")

    def test_edit_file_not_unique(self):
        mem = MemoryBackend({"/x.txt": "a\na\n"})
        tools = {t.__name__: t for t in workspace_tools_with_backend(mem)}
        out = tools["edit_file"]("/x.txt", "a", "b")
        assert "unique" in out.lower() or "2 times" in out

    def test_write_file_tool(self):
        mem = MemoryBackend()
        tools = {t.__name__: t for t in workspace_tools_with_backend(mem)}
        tools["write_file"]("/new.txt", "hello")
        assert mem.read_text("/new.txt") == "hello"

    def test_glob_search_tool(self):
        tools = {t.__name__: t for t in workspace_tools_with_backend(self._mem())}
        out = tools["glob_search"]("**/*.txt")
        assert "/ws/a.txt" in out
        assert "/ws/sub/c.txt" in out
        assert "/ws/b.py" not in out

    def test_grep_search_tool(self):
        tools = {t.__name__: t for t in workspace_tools_with_backend(self._mem())}
        out = tools["grep_search"]("line2")
        assert "a.txt" in out and "line2" in out

    def test_list_dir_tool(self):
        tools = {t.__name__: t for t in workspace_tools_with_backend(self._mem())}
        out = tools["list_dir"]("/ws")
        assert "a.txt" in out
        assert "sub" in out

    def test_read_only_omits_edit_write(self):
        tools = workspace_tools_with_backend(self._mem(), read_only=True)
        names = {t.__name__ for t in tools}
        assert "edit_file" not in names
        assert "write_file" not in names
        assert "read_file" in names

    def test_sandbox_violation_surfaces_as_error(self, tmp_path):
        backend = SandboxedBackend(
            LocalBackend(),
            SandboxPolicy(workspace=str(tmp_path)),
        )
        tools = {t.__name__: t for t in workspace_tools_with_backend(backend)}
        out = tools["read_file"]("/etc/passwd")
        assert "outside" in out.lower()


# ======================================================================
# H namespace sugar
# ======================================================================


class TestHNamespace:
    def test_fs_local(self):
        backend = H.fs_local()
        assert isinstance(backend, LocalBackend)

    def test_fs_memory_seeded(self):
        backend = H.fs_memory({"/x": "y"})
        assert isinstance(backend, MemoryBackend)
        assert backend.read_text("/x") == "y"

    def test_fs_sandboxed(self, tmp_path):
        inner = H.fs_local()
        wrapped = H.fs_sandboxed(inner, SandboxPolicy(workspace=str(tmp_path)))
        assert isinstance(wrapped, SandboxedBackend)
        assert wrapped.inner is inner

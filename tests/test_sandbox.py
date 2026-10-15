import os

from tools.python_exec import python_exec


def test_runs_and_writes_in_artifacts(tmp_path):
    r = python_exec("open('a.csv','w').write('x\\n1\\n')\nprint('ok')", tmp_path)
    assert r["returncode"] == 0 and "ok" in r["stdout"] and "a.csv" in r["new_files"]


def test_network_blocked(tmp_path):
    r = python_exec("import socket\nsocket.create_connection(('example.com', 80))", tmp_path)
    assert r["returncode"] != 0 and "network access is disabled" in r["stderr"]


def test_write_outside_artifacts_refused(tmp_path):
    outside = tmp_path.parent / "evil.txt"
    r = python_exec(f"open(r'{outside}', 'w').write('x')", tmp_path)
    assert r["returncode"] != 0 and not outside.exists()


def test_env_is_stripped(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENROUTER_API_KEY", "sk-secret")
    r = python_exec("import os\nprint(os.environ.get('OPENROUTER_API_KEY', 'NONE'))", tmp_path)
    assert "NONE" in r["stdout"] and "sk-secret" not in r["stdout"]


def test_timeout(tmp_path):
    r = python_exec("while True: pass", tmp_path, timeout=2)
    assert r["returncode"] == -1 and "timeout" in r["stderr"]


def test_plot_style_importable_in_sandbox(tmp_path):
    code = ("from tools.plot_style import apply_style\napply_style()\nimport matplotlib.pyplot as plt\n"
            "plt.plot([1,2,3]); plt.savefig('p.svg')\nprint('saved')")
    r = python_exec(code, tmp_path)
    assert r["returncode"] == 0, r["stderr"]
    assert "p.svg" in r["new_files"]

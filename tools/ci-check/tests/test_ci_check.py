"""워크플로 검사기의 검사.

여기서 잡는 것은 전부 **기존 저장소나 이 저장소에서 실제로 일어난 것**이다. 사람이
다시 안 그러기를 바라는 대신 검사가 막는다.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import ci_check

WORKFLOW = """
name: 보기
on: [push]
jobs:
  build:
    runs-on: windows-latest
    steps:
      - uses: actions/checkout@v4
      - name: 무엇
        shell: bash
        run: uv run python tools/assemble/assemble.py
"""


def _write(tmp_path: Path, text: str, name: str = "build.yml") -> Path:
    root = tmp_path / ".github" / "workflows"
    root.mkdir(parents=True)
    (root / name).write_text(text, encoding="utf-8")
    script = tmp_path / "tools" / "assemble" / "assemble.py"
    script.parent.mkdir(parents=True, exist_ok=True)
    script.write_text("", encoding="utf-8")
    return tmp_path


def test_바른_워크플로는_조용하다(tmp_path: Path) -> None:
    assert ci_check.check_tree(_write(tmp_path, WORKFLOW)) == []


def test_shell이_없는_단계를_잡는다(tmp_path: Path) -> None:
    """러너 기본 셸에 기대면 셸이 바뀔 때 조용히 동작이 달라진다. 기존 저장소의
    워크플로 하나가 그래서 3/3 실패하며 에러를 로그에 한 줄도 못 남겼다."""
    text = WORKFLOW.replace("        shell: bash\n", "")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "shell" in found[0]
    assert "무엇" in found[0]


def test_확인_안_된_러너를_잡는다(tmp_path: Path) -> None:
    """도구가 그 OS에서 도는지 확인하기 전에는 못 바꾼다. 기존 저장소는 ctypes.WinDLL을
    부르는 스크립트를 ubuntu 러너에서 돌리고 있었다."""
    text = WORKFLOW.replace("windows-latest", "ubuntu-latest")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "ubuntu-latest" in found[0]


def test_요약_단계에_always가_없으면_잡는다(tmp_path: Path) -> None:
    """요약이 실패에 딸려 사라지면 무엇이 어디까지 갔는지 로그를 뒤져야 한다.
    같은 결함의 세 번째 재발이었다."""
    text = WORKFLOW.replace(
        "        run: uv run python tools/assemble/assemble.py",
        '        run: echo hi >> "$GITHUB_STEP_SUMMARY"',
    )

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "always()" in found[0]


def test_요약_단계에_always가_있으면_통과한다(tmp_path: Path) -> None:
    text = WORKFLOW.replace(
        "      - name: 무엇\n        shell: bash\n"
        "        run: uv run python tools/assemble/assemble.py",
        "      - name: 무엇\n        if: always()\n        shell: bash\n"
        '        run: echo hi >> "$GITHUB_STEP_SUMMARY"',
    )

    assert ci_check.check_tree(_write(tmp_path, text)) == []


def test_없는_스크립트를_부르면_잡는다(tmp_path: Path) -> None:
    """워크플로만 아는 경로는 아무도 안 고친다. 이름이 바뀌면 여기서 빨개진다."""
    text = WORKFLOW.replace("tools/assemble/assemble.py", "tools/assemble/없다.py")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "없다.py" in found[0]


def _with_constant(value: str) -> str:
    return WORKFLOW.replace("windows-latest", f"windows-latest # {value}")


def test_판_상수가_같은_값으로_두_곳에_있으면_잡는다(tmp_path: Path) -> None:
    """기존 저장소는 워크플로 둘에 같은 값을 두 벌로 갖고 있었다."""
    root = _write(tmp_path, _with_constant("dalamud-kr-1.2.3.4"))
    (root / ".github" / "workflows" / "sync.yml").write_text(
        _with_constant("dalamud-kr-1.2.3.4"), encoding="utf-8"
    )

    found = ci_check.check_tree(root)

    assert len(found) == 1
    assert "build.yml" in found[0] and "sync.yml" in found[0]


def test_판_상수가_갈린_채로_두_곳에_있으면_잡는다(tmp_path: Path) -> None:
    """이것이 이 검사가 막으려던 바로 그 경우다. 같은 값이 두 곳에 있는 것보다
    다른 값이 두 곳에 있는 것이 더 나쁘다."""
    root = _write(tmp_path, _with_constant("dalamud-kr-15.0.3.2"))
    (root / ".github" / "workflows" / "sync.yml").write_text(
        _with_constant("dalamud-kr-15.0.3.3"), encoding="utf-8"
    )

    found = ci_check.check_tree(root)

    assert len(found) == 1
    assert "15.0.3.2" in found[0] and "15.0.3.3" in found[0]


def test_한_파일_안의_반복은_통과한다(tmp_path: Path) -> None:
    """복합 액션이 자기 상수를 여러 단계에서 참조하는 것은 정상이다."""
    text = _with_constant("dalamud-kr-1.2.3.4") + "# 또 dalamud-kr-1.2.3.4 를 쓴다\n"

    assert ci_check.check_tree(_write(tmp_path, text)) == []


def test_복합_액션의_단계도_본다(tmp_path: Path) -> None:
    root = _write(tmp_path, WORKFLOW)
    action = root / ".github" / "actions" / "무엇" / "action.yml"
    action.parent.mkdir(parents=True)
    action.write_text(
        "name: 무엇\nruns:\n  using: composite\n  steps:\n"
        "    - name: 셸이 없다\n      run: echo hi\n",
        encoding="utf-8",
    )

    found = ci_check.check_tree(root)

    assert len(found) == 1
    assert "shell" in found[0]


def test_네트워크를_부르는데_제한이_없으면_잡는다(tmp_path: Path) -> None:
    """상대가 멈추면 잡 제한까지 붙잡힌다. 그때는 무엇을 기다리는지도 안 보인다."""
    text = WORKFLOW.replace(
        "        run: uv run python tools/assemble/assemble.py",
        "        run: curl -sSL -o x.zip https://example.invalid/x.zip",
    )

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "시간 제한" in found[0]


def test_제한을_세_가지_모양으로_인정한다(tmp_path: Path) -> None:
    """단계의 timeout-minutes, timeout 명령, curl의 --max-time."""
    limited = [
        "      - name: 무엇\n        timeout-minutes: 5\n        shell: bash\n"
        "        run: gh release download x",
        "      - name: 무엇\n        shell: bash\n        run: timeout 300 gh release download x",
        "      - name: 무엇\n        shell: bash\n"
        "        run: curl --max-time 300 -o x https://example.invalid/x",
    ]
    for i, step in enumerate(limited):
        text = WORKFLOW.replace(
            "      - name: 무엇\n        shell: bash\n"
            "        run: uv run python tools/assemble/assemble.py",
            step,
        )
        root = _write(tmp_path / str(i), text)

        assert ci_check.check_tree(root) == [], step


def test_yaml_확장자도_본다(tmp_path: Path) -> None:
    """GitHub은 .yml과 .yaml을 다 읽는다. 하나만 보면 그 규칙을 통째로 우회할 수 있다."""
    text = WORKFLOW.replace("        shell: bash\n", "")

    found = ci_check.check_tree(_write(tmp_path, text, name="build.yaml"))

    assert len(found) == 1
    assert "shell" in found[0]


TRIGGERED = """
name: 보기
on:
  push:
    branches: [{branch}]
jobs:
  build:
    runs-on: windows-latest
    steps:
      - name: 무엇
        shell: bash
        run: echo hi
"""


def _repo(tmp_path: Path, text: str, branch: str = "master") -> Path:
    """브랜치 하나를 가진 진짜 git 저장소. 브랜치 검사는 로컬 git이 아는 것을 기준으로 잰다."""
    root = _write(tmp_path, text)
    subprocess.run(["git", "init", "-q", "-b", branch, str(root)], check=True)
    subprocess.run(["git", "-C", str(root), "add", "-A"], check=True)
    who = ["-c", "user.name=t", "-c", "user.email=t@t"]
    subprocess.run(["git", "-C", str(root), *who, "commit", "-qm", "첫"], check=True)
    return root


def test_실재하는_브랜치를_가리키면_통과한다(tmp_path: Path) -> None:
    assert ci_check.check_tree(_repo(tmp_path, TRIGGERED.format(branch="master"))) == []


def test_없는_브랜치를_가리키면_잡는다(tmp_path: Path) -> None:
    """문법은 맞고 YAML도 유효하다. 그래서 트리거가 조용히 안 걸린다 - 푸시해도 아무
    일이 안 일어나고, gh run list에 그 워크플로가 아예 없다."""
    found = ci_check.check_tree(_repo(tmp_path, TRIGGERED.format(branch="main")))

    assert len(found) == 1
    assert "main" in found[0]


def test_표현식으로_적은_브랜치는_검사에서_뺀다(tmp_path: Path) -> None:
    """실행 시점에 정해지는 값이라 여기서 잴 수 없다. 저장소가 말하는 값을 받아 쓰는
    쪽이 손으로 적는 것보다 낫다."""
    text = TRIGGERED.replace(
        "        shell: bash\n        run: echo hi",
        "        timeout-minutes: 5\n        shell: bash\n"
        '        run: gh pr create --base "${{ github.event.repository.default_branch }}"'
        " --head x --title t --body b",
    ).format(branch="master")

    assert ci_check.check_tree(_repo(tmp_path, text)) == []


def test_리터럴로_적은_base도_본다(tmp_path: Path) -> None:
    """트리거만 보면 sync.yml의 --base main을 놓친다. 그쪽은 조립과 빌드를 다 하고
    마지막 PR 생성에서만 실패하는 더 나쁜 모양이다."""
    text = TRIGGERED.replace(
        "        shell: bash\n        run: echo hi",
        "        timeout-minutes: 5\n        shell: bash\n"
        "        run: gh pr create --base main --head x --title t --body b",
    ).format(branch="master")

    found = ci_check.check_tree(_repo(tmp_path, text))

    assert len(found) == 1
    assert "main" in found[0]


def test_head는_안_본다(tmp_path: Path) -> None:
    """--head는 워크플로가 방금 만든 브랜치를 가리키는 자리라 아직 없는 것이 정상이다."""
    text = TRIGGERED.replace(
        "        shell: bash\n        run: echo hi",
        "        timeout-minutes: 5\n        shell: bash\n"
        "        run: gh pr create --base master --head 아직-없는-브랜치 --title t --body b",
    ).format(branch="master")

    assert ci_check.check_tree(_repo(tmp_path, text)) == []


def test_git이_아니면_브랜치_검사를_건너뛴다(tmp_path: Path) -> None:
    """기준값을 네트워크로 얻지 않는다. 로컬 git이 아무것도 모르면 잴 수가 없다."""
    root = _write(tmp_path, TRIGGERED.format(branch="없는브랜치"))

    assert ci_check.check_tree(root) == []
    assert ci_check.known_branches(root) is None


def test_없는_로컬_액션을_가리키면_잡는다(tmp_path: Path) -> None:
    """브랜치와 같은 부류다. 이름은 있는데 그 이름이 가리키는 것이 없다."""
    text = WORKFLOW.replace(
        "      - uses: actions/checkout@v4",
        "      - uses: ./.github/actions/없다",
    )

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "없다" in found[0]


def test_있는_로컬_액션은_통과한다(tmp_path: Path) -> None:
    root = _write(tmp_path, WORKFLOW.replace("actions/checkout@v4", "./.github/actions/무엇"))
    action = root / ".github" / "actions" / "무엇" / "action.yml"
    action.parent.mkdir(parents=True)
    action.write_text("name: 무엇\nruns:\n  using: composite\n  steps: []\n", encoding="utf-8")

    assert ci_check.check_tree(root) == []


def test_안_올린_산출물을_내려받으면_잡는다(tmp_path: Path) -> None:
    """이름이 갈리면 내려받는 잡이 실행 중에만 실패한다."""
    text = WORKFLOW.replace(
        "      - uses: actions/checkout@v4",
        "      - uses: actions/download-artifact@v4\n        with:\n          name: 없는-것",
    )

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "없는-것" in found[0]


def test_올린_산출물을_내려받으면_통과한다(tmp_path: Path) -> None:
    text = WORKFLOW.replace(
        "      - uses: actions/checkout@v4",
        "      - uses: actions/upload-artifact@v4\n        with:\n          name: 보고\n"
        "      - uses: actions/download-artifact@v4\n        with:\n          name: 보고",
    )

    assert ci_check.check_tree(_write(tmp_path, text)) == []


OUTPUTS = """
name: 보기
on: [push]
jobs:
  check:
    runs-on: windows-latest
    outputs:
      has-new: ${{ steps.look.outputs.has-new }}
    steps:
      - name: 본다
        id: look
        shell: bash
        run: echo "has-new=true" >> "$GITHUB_OUTPUT"
  port:
    needs: check
    if: needs.check.outputs.has-new == 'true'
    runs-on: windows-latest
    steps:
      - name: 한다
        shell: bash
        run: echo hi
"""


def test_실재하는_출력은_통과한다(tmp_path: Path) -> None:
    assert ci_check.check_tree(_write(tmp_path, OUTPUTS)) == []


def test_잡이_선언_안_한_출력을_가리키면_잡는다(tmp_path: Path) -> None:
    """이름이 갈리면 if가 늘 거짓이 되어 그 잡이 영영 skipped로 남는다. 워크플로는
    초록으로 끝나고, 그것이 정확히 '12일 연속 초록인데 자동화가 죽어 있던' 모양이다."""
    text = OUTPUTS.replace("needs.check.outputs.has-new ==", "needs.check.outputs.hasNew ==")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "hasNew" in found[0]


def test_없는_잡의_출력을_가리키면_잡는다(tmp_path: Path) -> None:
    text = OUTPUTS.replace("needs.check.outputs.has-new", "needs.없는잡.outputs.has-new")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "없는잡" in found[0]


def test_없는_단계_id의_출력을_가리키면_잡는다(tmp_path: Path) -> None:
    text = OUTPUTS.replace("        id: look\n", "        id: 다른이름\n")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "look" in found[0]


PYTHON_CALLER = """
name: 보기
on: [push]
env:
  PYTHONIOENCODING: utf-8
  PYTHONUTF8: "1"
jobs:
  build:
    runs-on: windows-latest
    steps:
      - name: 무엇
        shell: bash
        run: uv run python tools/assemble/assemble.py
"""


def test_파이썬을_부르면서_인코딩을_안_세우면_잡는다(tmp_path: Path) -> None:
    """첫 CI 실행이 여기서 죽었다. 윈도 러너의 stdout이 cp1252라 우리 도구가 한국어를
    내는 순간 charmap 코덱이 못 넘긴다. 문법은 맞아서 다른 규칙에는 안 걸린다."""
    text = PYTHON_CALLER.replace('  PYTHONUTF8: "1"\n', "")

    found = ci_check.check_tree(_write(tmp_path, text))

    assert len(found) == 1
    assert "PYTHONUTF8" in found[0]


def test_둘_다_있으면_통과한다(tmp_path: Path) -> None:
    assert ci_check.check_tree(_write(tmp_path, PYTHON_CALLER)) == []


def test_잡_수준에_세워도_통과한다(tmp_path: Path) -> None:
    """최상위든 잡이든 그 파이썬에 닿기만 하면 된다."""
    text = PYTHON_CALLER.replace(
        'env:\n  PYTHONIOENCODING: utf-8\n  PYTHONUTF8: "1"\n',
        "",
    ).replace(
        "    runs-on: windows-latest\n",
        '    runs-on: windows-latest\n    env:\n      PYTHONIOENCODING: utf-8\n'
        '      PYTHONUTF8: "1"\n',
    )

    assert ci_check.check_tree(_write(tmp_path, text)) == []


def test_파이썬을_안_부르면_안_따진다(tmp_path: Path) -> None:
    assert ci_check.check_tree(_write(tmp_path, WORKFLOW.replace("uv run python tools/assemble/assemble.py", "echo hi"))) == []


def test_워크플로가_하나도_없으면_잡는다(tmp_path: Path) -> None:
    """검사가 조용히 통과하는 가장 쉬운 길을 막는다."""
    found = ci_check.check_tree(tmp_path)

    assert len(found) == 1
    assert "워크플로" in found[0]


def test_이_저장소의_워크플로가_규칙을_지킨다() -> None:
    """실물을 잰다. 위의 것들은 규칙을 검사하고 이것은 우리 파일을 검사한다."""
    root = Path(__file__).resolve().parents[3]

    assert ci_check.check_tree(root) == []

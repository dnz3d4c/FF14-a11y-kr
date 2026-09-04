"""워크플로 검사기의 검사.

여기서 잡는 넷은 전부 **기존 저장소에서 실제로 재발한 것**이다. 사람이 다시 안
그러기를 바라는 대신 검사가 막는다.
"""

from __future__ import annotations

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


def test_워크플로가_하나도_없으면_잡는다(tmp_path: Path) -> None:
    """검사가 조용히 통과하는 가장 쉬운 길을 막는다."""
    found = ci_check.check_tree(tmp_path)

    assert len(found) == 1
    assert "워크플로" in found[0]


def test_이_저장소의_워크플로가_규칙을_지킨다() -> None:
    """실물을 잰다. 위의 것들은 규칙을 검사하고 이것은 우리 파일을 검사한다."""
    root = Path(__file__).resolve().parents[3]

    assert ci_check.check_tree(root) == []

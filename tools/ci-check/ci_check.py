"""워크플로가 지켜야 할 것을 검사한다.

여기서 막는 넷은 전부 **기존 저장소에서 실제로 일어난 것**이다. 사람이 다시 안
그러기를 바라는 대신 검사가 막는다.

1. **모든 `run:`에 `shell:`을 적는다.** 러너 기본 셸에 기대면 셸이 바뀔 때 조용히
   동작이 달라진다. 워크플로 하나가 그래서 3/3 실패하며 에러를 로그에 한 줄도 못
   남겼다.
2. **`$GITHUB_STEP_SUMMARY`에 쓰는 단계는 `always()`를 단다.** 요약이 실패에 딸려
   사라지면 무엇이 어디까지 갔는지 로그를 뒤져야 한다. 같은 결함의 세 번째 재발이었다.
3. **Dalamud 판 상수는 한 파일에만 있다.** 두 벌이면 갈리고, 갈린 것을 막는 장치가
   "테스트가 YAML을 grep한다"뿐이었다.
4. **워크플로가 부르는 스크립트가 실재하고, 러너 OS가 확인된 것이다.** 기존은
   `ctypes.WinDLL`을 부르는 스크립트를 ubuntu 러너에서 돌리고 있었다. 같은 저장소의
   테스트는 skipif로 플랫폼을 가리는데 워크플로만 안 가렸다.
5. **네트워크를 부르는 단계에 시간 제한이 있다.** 상대가 멈추면 잡 제한까지 붙잡히고,
   그동안 무엇을 기다리는지도 안 보인다.

사용법:
    uv run python tools/ci-check/ci_check.py
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

import yaml

#: 도구가 그 위에서 실제로 도는 것을 확인한 러너.
#:
#: 지금 windows-latest 하나뿐인 까닭은 모드가 `net10.0-windows`를 대상으로 하고
#: 윈도 전용 `System.Speech`를 참조하는데 `-warnaserror`로 빌드하기 때문이다. 다른
#: OS에서는 플랫폼 호환 경고가 그대로 실패가 된다. 우리 파이썬 도구는 표준
#: 라이브러리만 써서 러너를 안 가리므로, 제약은 dotnet 쪽 하나다.
#:
#: **여기를 늘리려면 그 OS에서 실제로 돌려 보고 늘린다.** 이 표는 바람이 아니라
#: 확인의 기록이다.
VERIFIED_RUNNERS = {"windows-latest"}

#: Dalamud 참조 릴리스의 태그 모양. 이 값이 두 파일에 있으면 갈린다.
VERSION_CONSTANT = re.compile(r"dalamud-kr-\d+(?:\.\d+)+")

#: 워크플로가 부르는 우리 스크립트.
SCRIPT_CALL = re.compile(r"(?:uv run )?python3? (tools/[\w./-]+\.py)")

#: 바깥을 부르는 명령. 상대가 멈추면 이쪽이 붙잡힌다.
NETWORK = re.compile(r"\b(?:curl|wget|gh)\b")

#: 제한으로 인정하는 것. 복합 액션의 단계는 `timeout-minutes`를 못 갖기 때문에
#: 명령 쪽 제한도 같이 인정한다.
COMMAND_LIMIT = re.compile(r"--max-time\b|(?:^|\s|&&\s*)timeout\s+\d")

SUMMARY = "GITHUB_STEP_SUMMARY"


def _steps(document: dict[str, Any]) -> list[tuple[str, dict[str, Any]]]:
    """(어느 잡, 단계). 워크플로와 복합 액션을 한 모양으로 편다."""
    found: list[tuple[str, dict[str, Any]]] = []
    for name, job in (document.get("jobs") or {}).items():
        found += [(name, step) for step in (job.get("steps") or [])]
    runs = document.get("runs") or {}
    found += [("runs", step) for step in (runs.get("steps") or [])]
    return found


def _label(job: str, step: dict[str, Any]) -> str:
    return f"{job}/{step.get('name') or step.get('uses') or '(이름 없음)'}"


def check_document(path: str, document: dict[str, Any]) -> list[str]:
    """워크플로 하나 또는 복합 액션 하나를 잰다."""
    problems: list[str] = []

    for runner in (job.get("runs-on") for job in (document.get("jobs") or {}).values()):
        if runner is not None and runner not in VERIFIED_RUNNERS:
            problems.append(
                f"{path}: 확인 안 된 러너다 - {runner}. "
                "그 OS에서 도구가 도는 것을 보고 VERIFIED_RUNNERS에 넣는다"
            )

    for job, step in _steps(document):
        script = step.get("run")
        if script is None:
            continue
        if "shell" not in step:
            problems.append(f"{path}: {_label(job, step)}에 shell이 없다")
        if SUMMARY in script and "always()" not in str(step.get("if", "")):
            problems.append(
                f"{path}: {_label(job, step)}가 요약을 쓰는데 always()가 없다 - "
                "앞 단계가 실패하면 요약이 같이 사라진다"
            )
        if NETWORK.search(script) and not _limited(step, script):
            problems.append(
                f"{path}: {_label(job, step)}가 바깥을 부르는데 시간 제한이 없다 - "
                "timeout-minutes나 명령의 --max-time, timeout 중 하나를 단다"
            )
    return problems


def _limited(step: dict[str, Any], script: str) -> bool:
    return "timeout-minutes" in step or bool(COMMAND_LIMIT.search(script))


def _yaml_files(root: Path, pattern: str) -> list[Path]:
    """GitHub은 `.yml`과 `.yaml`을 다 읽는다. 하나만 보면 규칙을 통째로 우회할 수 있다."""
    return sorted({*root.glob(f"{pattern}.yml"), *root.glob(f"{pattern}.yaml")})


def check_tree(root: Path) -> list[str]:
    """저장소의 워크플로와 복합 액션을 전부 잰다. 비면 통과."""
    workflows = _yaml_files(root / ".github" / "workflows", "*")
    if not workflows:
        return [".github/workflows: 워크플로가 하나도 없다"]

    files = workflows + _yaml_files(root / ".github" / "actions", "*/action")
    problems: list[str] = []
    #: 판 상수를 가진 파일 -> 그 파일이 가진 값들.
    holders: dict[str, set[str]] = {}

    for path in files:
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        problems += check_document(name, yaml.safe_load(text) or {})

        found = set(VERSION_CONSTANT.findall(text))
        if found:
            holders[name] = found
        for script in SCRIPT_CALL.findall(text):
            if not (root / script).is_file():
                problems.append(f"{name}: 부르는 스크립트가 없다 - {script}")

    # 세는 것은 파일 수이지 값의 종류가 아니다. 값이 갈린 두 파일은 값이 같은 두
    # 파일보다 더 나쁜데, 값으로 세면 각각 한 곳이라 통과해 버린다.
    # 한 파일 안에서 같은 상수를 여러 번 쓰는 것은 정상이라 여기 안 걸린다.
    if len(holders) > 1:
        where = ", ".join(
            f"{name}({', '.join(sorted(values))})" for name, values in sorted(holders.items())
        )
        problems.append(f"판 상수가 {len(holders)}곳에 있다 - {where}. 한 곳에만 둔다")
    return problems


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="워크플로 검사.")
    parser.add_argument("--root", default=".", help="저장소 루트")
    args = parser.parse_args(argv)

    problems = check_tree(Path(args.root).resolve())
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1

    print("워크플로가 규칙을 지킨다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

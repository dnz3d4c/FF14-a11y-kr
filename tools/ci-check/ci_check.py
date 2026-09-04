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
6. **이름으로 가리키는 것이 실재한다.** 브랜치, 로컬 액션 경로, 내려받는 산출물이
   여기 해당한다. 문법이 맞으면 YAML도 유효하고 위 다섯도 통과하므로, 실재를 안 재면
   아무도 못 잡는다. `build.yml`이 `branches: [main]`인데 이 저장소의 기본 브랜치가
   `master`라서 푸시해도 워크플로가 아예 안 돈 적이 있다. `sync.yml`의 `--base main`은
   더 나쁜 모양이었다 - 조립과 빌드를 다 하고 마지막 PR 생성에서만 실패한다.

7. **파이썬을 부르는 워크플로는 출력 인코딩을 세운다.** 윈도 러너의 파이썬 stdout이
   cp1252라, 우리 도구가 한국어를 내는 순간 `UnicodeEncodeError`로 죽는다. 첫 CI 실행이
   그렇게 죽었고 문법은 멀쩡해서 다른 규칙에는 안 걸렸다.
8. **건너뛸 수 있는 잡의 이름에 표현식을 쓰지 않는다.** 건너뛴 잡은 실행 컨텍스트가
   없어서 이름의 표현식이 평가되지 않고 원문 그대로 뜬다(2026-09-04 실측). 이름으로
   상태를 말하려던 시도가 정확히 그 경우에 못 읽는 문자열을 내놓는다.

## 이 검사가 못 재는 것

**바깥에 있는 것은 안 잰다.** Dalamud 참조 릴리스 태그와 남의 액션 판(`@v4`)이
그렇다. 재려면 네트워크를 불러야 하는데, CI 안에서 도는 검사기가 바깥에 의존하면
네트워크가 흔들릴 때 우리 코드가 아닌 이유로 빨개진다. 그 둘은 실행이 실패로 알려
준다 - 릴리스 태그는 참조 마련 단계에서, 액션 판은 잡 시작에서 바로 걸린다.

사용법:
    uv run python tools/ci-check/ci_check.py
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "common"))

import console  # noqa: E402 - 위에서 경로를 넣어야 찾는다

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

#: 브랜치 이름을 받는 트리거.
BRANCH_EVENTS = ("push", "pull_request", "pull_request_target")

#: 명령에 리터럴로 적힌 브랜치. `gh pr create --base main`이 이 모양이다.
#:
#: `--head`는 안 본다. 그쪽은 **워크플로가 방금 만든 브랜치**를 가리키는 자리라
#: 아직 없는 것이 정상이다. `--base`만 이미 있어야 하는 이름이다.
BRANCH_FLAG = re.compile(r"--base[= ]+([^\s\"'$]+)")

#: 이름에 이것이 들어 있으면 실행 시점에 정해지는 값이라 여기서 못 잰다.
DYNAMIC = ("${{", "$")

#: 브랜치 필터의 글로브. 여러 이름을 가리키는 것이라 하나로 재지 않는다.
GLOB = set("*?[]!")

#: 파이썬을 부르는 명령.
PYTHON_CALL = re.compile(r"\bpython3?\b")

#: 한국어 출력이 러너에서 살아남으려면 있어야 하는 환경 변수.
ENCODING_ENV = ("PYTHONIOENCODING", "PYTHONUTF8")

#: `needs.<잡>.outputs.<이름>`과 `steps.<id>.outputs.<이름>`.
#: 이름이 갈리면 GitHub이 조용히 빈 값을 준다. 오류가 아니라 빈 문자열이다.
#:
#: `${{ }}`를 요구하지 않는다. `if:`는 그것 없이도 표현식으로 읽히고, 실제로 잡을
#: 건너뛰게 만드는 자리가 바로 거기다.
REFERENCE = re.compile(r"\b(needs|steps)\.([\w-]+)\.outputs\.([\w-]+)")


def _dynamic(name: str) -> bool:
    return any(mark in name for mark in DYNAMIC)


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

    problems += _artifacts(path, document)
    problems += _encoding(path, document)
    problems += _job_names(path, document)
    return problems


def _job_names(path: str, document: dict[str, Any]) -> list[str]:
    """건너뛸 수 있는 잡의 이름에 표현식을 쓰지 않는다.

    건너뛴 잡은 실행 컨텍스트가 없어서 이름의 표현식이 평가되지 않는다. 목록에
    `needs.check.outputs.has-new == 'true' && ...`가 그대로 뜬다 - 이름으로 상태를
    말하려던 시도가 **정확히 그 경우에** 못 읽는 문자열을 내놓는다.

    `if`나 `needs`가 있으면 건너뛸 수 있다. 앞 잡이 건너뛰면 뒤 잡도 건너뛰므로
    `needs`만 있어도 같은 자리다. 늘 도는 잡은 컨텍스트가 있으니 안 따진다.
    """
    return [
        f"{path}: {name} 잡이 건너뛸 수 있는데 이름이 표현식이다 - "
        "건너뛰면 평가가 안 되어 원문 그대로 뜬다. 정적 이름에 까닭을 적는다"
        for name, job in (document.get("jobs") or {}).items()
        if "${{" in str(job.get("name", "")) and ("if" in job or "needs" in job)
    ]


def _encoding(path: str, document: dict[str, Any]) -> list[str]:
    """파이썬을 부르는 단계에 인코딩 환경이 닿는가.

    최상위든 잡이든 단계든, 그 파이썬에 닿기만 하면 된다. `PYTHONUTF8`만으로는 이미
    파이프로 잡힌 stdout을 못 돌리는 경우가 있어 둘을 같이 본다.
    """
    top = document.get("env") or {}
    problems: list[str] = []

    for name, job in (document.get("jobs") or {}).items():
        for step in job.get("steps") or []:
            script = step.get("run")
            if script is None or not PYTHON_CALL.search(script):
                continue
            reachable = {**top, **(job.get("env") or {}), **(step.get("env") or {})}
            missing = [key for key in ENCODING_ENV if key not in reachable]
            if missing:
                problems.append(
                    f"{path}: {_label(name, step)}가 파이썬을 부르는데 {missing}가 없다 - "
                    "윈도 러너의 stdout은 cp1252라 한국어를 내는 순간 죽는다"
                )
    return problems


def _artifact_names(document: dict[str, Any], action: str) -> set[str]:
    return {
        (step.get("with") or {}).get("name", "")
        for _, step in _steps(document)
        if action in str(step.get("uses", ""))
    } - {""}


def _artifacts(path: str, document: dict[str, Any]) -> list[str]:
    """내려받는 산출물을 같은 워크플로가 올리는가. 이름이 갈리면 실행 중에만 실패한다."""
    uploaded = _artifact_names(document, "upload-artifact")
    return [
        f"{path}: 안 올린 산출물을 내려받는다 - {name}. 올리는 쪽 이름은 {sorted(uploaded)}다"
        for name in sorted(_artifact_names(document, "download-artifact"))
        if not _dynamic(name) and name not in uploaded
    ]


def _limited(step: dict[str, Any], script: str) -> bool:
    return "timeout-minutes" in step or bool(COMMAND_LIMIT.search(script))


def known_branches(root: Path) -> set[str] | None:
    """로컬 git이 아는 브랜치 이름. 못 알아내면 None.

    **네트워크를 부르지 않는다.** CI 안에서 도는 검사기가 바깥에 의존하면 네트워크가
    흔들릴 때 우리 코드가 아닌 이유로 빨개진다. 로컬 브랜치와 원격 추적 브랜치를
    본다 - 클론한 저장소면 둘 다 있고, 그것으로 이름의 실재는 충분히 재진다.
    """
    names: set[str] = set()
    for namespace, form in (("refs/heads", "short"), ("refs/remotes", "lstrip=3")):
        found = subprocess.run(
            ["git", "-C", str(root), "for-each-ref", f"--format=%(refname:{form})", namespace],
            capture_output=True,
            text=True,
        )
        if found.returncode != 0:
            return None
        names.update(line for line in found.stdout.split() if line and line != "HEAD")
    return names or None


def named_branches(document: dict[str, Any]) -> set[str]:
    """워크플로가 리터럴로 가리키는 브랜치. 표현식과 글로브는 뺀다."""
    found: set[str] = set()

    # YAML 1.1이 `on`을 참으로 읽어서 열쇠가 문자열이 아니라 `True`로 들어온다.
    raw: dict[Any, Any] = document
    triggers = raw.get(True) or raw.get("on") or {}
    if isinstance(triggers, dict):
        for event in BRANCH_EVENTS:
            filters = triggers.get(event)
            if not isinstance(filters, dict):
                continue
            # `branches-ignore`는 안 본다. 빼겠다고 적은 이름이라 없는 것이 정상이고,
            # 없는 브랜치를 빼는 것은 해롭지도 않다.
            found.update(filters.get("branches") or [])

    for _, step in _steps(document):
        found.update(BRANCH_FLAG.findall(step.get("run") or ""))

    return {name for name in found if not _dynamic(name) and not (GLOB & set(name))}


def _local_actions(root: Path, path: str, document: dict[str, Any]) -> list[str]:
    """`uses: ./...`가 가리키는 액션이 실재하는가. 디렉토리 이름이 바뀌면 여기서 빨개진다."""
    problems: list[str] = []
    for _, step in _steps(document):
        uses = str(step.get("uses", ""))
        if not uses.startswith("./") or _dynamic(uses):
            continue
        folder = root / uses[2:]
        if not any((folder / f"action.{suffix}").is_file() for suffix in ("yml", "yaml")):
            problems.append(f"{path}: 부르는 로컬 액션이 없다 - {uses}")
    return problems


def _references(path: str, text: str, document: dict[str, Any]) -> list[str]:
    """이름으로 가리키는 출력이 실재하는가.

    갈린 이름은 오류가 아니라 **빈 문자열**이 된다. `if: needs.check.outputs.has-new`가
    갈리면 그 조건이 늘 거짓이라 잡이 영영 skipped로 남고, 워크플로는 초록으로 끝난다.
    그것이 정확히 "12일 연속 초록인데 자동화가 죽어 있던" 모양이다.

    단계 id는 원래 잡 안에서만 통하는데 여기서는 문서 전체로 모아 본다. 잡을 넘나드는
    참조는 GitHub이 따로 막고, 우리가 잡으려는 것은 "이름이 갈려 아무 데도 안 맞는
    경우"라 이것으로 충분하다.
    """
    jobs: dict[str, Any] = document.get("jobs") or {}
    ids = {step["id"] for _, step in _steps(document) if "id" in step}

    problems: list[str] = []
    for kind, holder, name in REFERENCE.findall(text):
        if kind == "steps":
            if holder not in ids:
                problems.append(f"{path}: 없는 단계 id의 출력을 가리킨다 - steps.{holder}.{name}")
            continue
        if holder not in jobs:
            problems.append(f"{path}: 없는 잡의 출력을 가리킨다 - needs.{holder}.{name}")
        elif name not in (jobs[holder].get("outputs") or {}):
            problems.append(
                f"{path}: {holder} 잡이 선언 안 한 출력을 가리킨다 - {name}. "
                f"그 잡이 내는 것은 {sorted(jobs[holder].get('outputs') or {})}다"
            )
    return problems


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
    branches = known_branches(root)

    for path in files:
        name = path.relative_to(root).as_posix()
        text = path.read_text(encoding="utf-8")
        document = yaml.safe_load(text) or {}
        problems += check_document(name, document)

        found = set(VERSION_CONSTANT.findall(text))
        if found:
            holders[name] = found
        for script in SCRIPT_CALL.findall(text):
            if not (root / script).is_file():
                problems.append(f"{name}: 부르는 스크립트가 없다 - {script}")
        problems += _local_actions(root, name, document)
        problems += _references(name, text, document)

        # 로컬 git이 아무것도 모르면 잴 수가 없다. 그때는 건너뛰고, main이 그것을 말한다.
        if branches is not None:
            for branch in sorted(named_branches(document)):
                if branch not in branches:
                    problems.append(
                        f"{name}: 없는 브랜치를 가리킨다 - {branch}. "
                        f"이 저장소가 아는 것은 {sorted(branches)}다"
                    )

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
    console.setup()
    parser = argparse.ArgumentParser(description="워크플로 검사.")
    parser.add_argument("--root", default=".", help="저장소 루트")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    problems = check_tree(root)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 1

    # 건너뛴 것을 말한다. 조용히 통과하면 그 규칙이 있으나 마나다.
    if known_branches(root) is None:
        print("브랜치 검사는 건너뛰었다 - 로컬 git이 아는 브랜치가 없다.", file=sys.stderr)

    print("워크플로가 규칙을 지킨다.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

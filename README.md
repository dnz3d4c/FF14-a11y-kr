# FF14-a11y-kr

[derbruedi/ff14-accessibility](https://github.com/derbruedi/ff14-accessibility)의 한국어판이다. 원본은 독일어와 영어 두 언어를 지원하고, 여기에 한국어와 한국 클라이언트 대응을 더한다.

## 이 저장소에 원본 파일은 없다

원본은 `upstream/` 서브모듈이 가리키는 커밋 하나로만 담긴다. 파일 내용은 커밋되지 않고 `git submodule update`가 원본에서 받아 온다. 그래서 이 저장소에 있는 파일은 전부 우리가 쓴 것이다.

한국어는 커밋으로 얹지 않고 **빌드할 때 조립한다**. 원본 위에 우리 커밋을 쌓지 않으므로 새 판을 받을 때 충돌이 나지 않는다.

| 디렉토리 | 담는 것 |
|----------|---------|
| `upstream/` | 원본 서브모듈. 태그 그대로이고 우리 커밋이 없다 |
| `korean/` | 한국어 문장 대장과 게임 용어 |
| `kr/` | 원본에 없는 신규 파일 (한국 클라이언트 대응 등) |
| `graft/` | 원본 파일 안에 덧대는 규칙 |
| `upstream-reports/` | 원본에 보고할 결함과 우리가 버린 개선분 |
| `tools/assemble/` | 조립 도구 |
| `build/` | 조립 산출물. 커밋하지 않는다 |

## 받아 오기

    git clone --recurse-submodules https://github.com/dnz3d4c/FF14-a11y-kr.git

이미 클론했다면 다음으로 서브모듈을 채운다.

    git submodule update --init

## 라이선스

원본의 라이선스를 따른다. `upstream/LICENSE`를 참고한다.

# 장소 유형이 언제나 독일어로 발화된다

**상태**: 초안
**대상**: `FF14Accessibility/Services/NavigationService.cs:1754`, `Services/PlacesService.cs:236-257`
**심각도**: 중간. 독일어를 모르는 사용자가 안내의 한 낱말을 못 알아듣는다

## 증상

장소 안내가 `{이름}, {유형}, ...` 꼴로 조립되는데 `{유형}` 자리에 독일어가 그대로 나간다. 영어로 놓고 써도 `Ort`·`Ätheryt`·`Übergang`·`Markierung`이 들린다. 갈림길이 아예 없어서 언어 설정과 무관하다.

`PlacesService`가 값을 그렇게 짓는다.

```csharp
type = "Ätheryt";     // 236행 부근
type = "Aethernet";   // 249행 부근
type = "Ort";         // 256행
```

`Aethernet`만 영어에서도 같은 글자라 티가 안 난다.

## 원본도 알고 있다

주석 둘이 이 상태를 적어 두고 있다.

```csharp
// NavigationService.cs:1749
// NOTE: place.TypeLabel is still German here - it is coupled to PlacesService

// AccessibilityStrings.cs:2013
//    TypeLabel (der bleibt als Identität deutsch, siehe PlacesService).
```

즉 **독일어로 두는 것 자체는 의도다.** `TypeLabel`이 발화용이 아니라 식별용이라서다. `NavigationService.cs:2101`과 `3031`, `PlacesService.cs:461`이 그 값을 글자로 비교해 에테라이트인지 판정한다.

문제는 그 식별용 값을 **발화 문장에 그대로 넣는다**는 것이다.

```csharp
// NavigationService.cs:1754
var text = $"{place.Name}, {place.TypeLabel}, " + ...
```

식별을 위해 독일어로 둔 값이 안내로 새어 나간다. 두 쓰임이 한 필드에 붙어 있어서 한쪽을 고치면 다른 쪽이 깨지는 구조다.

## 고칠 방향

식별용 값은 그대로 두고, **발화할 때만 거치는 사상 하나를 둔다.** `AccessibilityStrings`에 `PlaceTypeSpoken(string typeLabel)`을 두고 `NavigationService.cs:1754`가 그것을 거치게 하면, 판정은 독일어 값을 계속 쓰고 발화만 언어를 따른다.

[place-type-spoken-twice.md](place-type-spoken-twice.md)가 같은 자리에 같은 해법을 제안한다. 그쪽은 이름에 유형이 이미 들어 있을 때 유형을 두 번 말하는 문제이고, 사상 함수가 빈 문자열을 돌려주면 풀린다. **두 사안이 한 변경으로 같이 닫힌다.**

## 우리 쪽 사정

우리 조립 도구가 이 자리를 못 잡는다. 갈림길이 없으니 삼항이 아니고, 문장 대장의 키는 `(독일어, 영어)` 쌍이라 짝이 성립하지 않는다.

**대장의 고아 3행 중 둘이 이 결함의 자국이다.** `Aethernet`과 `Place`가 대장에 있는데 소스에서 못 만난다. 기존 저장소가 원본 파일을 직접 고쳐 갈림길을 만들어 두고 그 쌍을 담았던 것인데, 재포팅하면서 그 변경을 버려서 짝이 사라졌다.

그래서 한국어판도 지금 이 낱말들을 독일어로 발화한다. 원본이 사상 함수를 받아들이면 그 자리가 평범한 문장이 되어 대장으로 옮겨 갈 수 있다. 받아들이지 않으면 `replace/`나 `graft/`로 우리 쪽에서 따로 다뤄야 하고, 그때는 판정에 쓰는 값을 건드리지 않는 것이 조건이다.

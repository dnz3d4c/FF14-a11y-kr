// v1을 보고 컴파일된다. 여기서 만들어진 MemberReference들이 검사 대상이다.
// 실행되지 않는다 — 필요한 건 IL의 참조 테이블뿐이다.
using Stub;

public static class Use
{
    public static unsafe int Run()
    {
        Foo.Bar(1);             // ARITY MISMATCH 유발
        Gone.Poof();            // MISSING TYPE 유발
        Nest.Inner.Deep();      // 중첩 타입 -> 조용해야 함
        var f = new Foo();
        f.Keep("x");            // SIGNATURE DIFF 유발
        Item it = default;
        f.Ptr(&it);             // 포인터 인자 -> 조용해야 함
        return Foo.Baz;         // MISSING MEMBER 유발 (필드 참조)
    }
}

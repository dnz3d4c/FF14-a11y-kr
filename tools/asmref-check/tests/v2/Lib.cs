// 음성 대조군의 "신판". v1으로 컴파일된 client를 이것에 대고 검사한다.
// 기대: MISSING TYPE / MISSING MEMBER / ARITY MISMATCH / SIGNATURE DIFF 각 1건, 종료 코드 1.
namespace Stub;

public struct Item
{
    public int Id;
}

public class Foo
{
    // Baz 삭제 -> MISSING MEMBER
    public static void Bar(int a, int b) { }   // 인자 1 -> 2, ARITY MISMATCH
    public void Keep(object s) { }             // string -> object, SIGNATURE DIFF
    public unsafe void Ptr(Item* p) { }        // 그대로 -> 조용해야 함
}

// Gone 클래스 삭제 -> MISSING TYPE

public class Nest
{
    public class Inner
    {
        public static void Deep() { }          // 그대로 -> 조용해야 함
    }
}

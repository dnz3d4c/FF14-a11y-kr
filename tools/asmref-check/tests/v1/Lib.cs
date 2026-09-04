// 음성 대조군의 "구판". client가 이걸 보고 컴파일된다.
// v2에서 여기 멤버를 하나씩 없애거나 바꿔서 asmrefcheck가 4종을 다 잡는지 본다.
namespace Stub;

public struct Item
{
    public int Id;
}

public class Foo
{
    public static int Baz;                      // v2에서 삭제
    public static void Bar(int a) { }           // v2에서 인자 1 -> 2
    public void Keep(string s) { }              // v2에서 string -> object
    public unsafe void Ptr(Item* p) { }         // v2에서 그대로 (조용해야 함)
}

public class Gone                               // v2에서 타입째 삭제
{
    public static void Poof() { }
}

public class Nest
{
    public class Inner
    {
        public static void Deep() { }           // v2에서 그대로 (중첩 타입 해석 확인)
    }
}

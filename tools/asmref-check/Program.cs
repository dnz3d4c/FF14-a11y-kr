using System.Collections.Immutable;
using System.Reflection;
using System.Reflection.Metadata;
using System.Reflection.PortableExecutable;

// args: <plugin dll> <reference assembly dir> [--only <asm,...>]
//   플러그인 DLL이 참조하는 멤버가 참조 디렉토리의 어셈블리에 실제로 있는지 대조한다.
//   게임을 띄우지 않고 MissingMethodException 후보를 미리 잡는 게 목적이라
//   MetadataLoadContext가 아니라 SRM으로 참조 테이블을 직접 읽는다.
//   (MetadataLoadContext에는 TypeRef/MemberRef 테이블을 보는 API가 없다.)
if (args.Length < 2)
{
    Console.Error.WriteLine("usage: asmrefcheck <plugin.dll> <refdir> [--only <asm,...>]");
    return 2;
}

var pluginPath = Path.GetFullPath(args[0]);
var refDir = Path.GetFullPath(args[1]);
HashSet<string> only = null;
for (var i = 2; i < args.Length; i++)
    if (args[i] == "--only" && i + 1 < args.Length)
        only = args[++i].Split(',', StringSplitOptions.RemoveEmptyEntries | StringSplitOptions.TrimEntries)
                        .ToHashSet(StringComparer.OrdinalIgnoreCase);

var refDlls = Directory.GetFiles(refDir, "*.dll")
                       .ToDictionary(Path.GetFileNameWithoutExtension, p => p, StringComparer.OrdinalIgnoreCase);

// 참조 디렉토리에 같은 이름이 있어도 플러그인이 자기 사본을 들고 오면 런타임엔 그 사본이 쓰인다
// (Dalamud 플러그인 로더는 플러그인 디렉토리를 먼저 본다). 그런 어셈블리를 대조하면 헛경보가 난다.
// 단 플러그인이 참조 디렉토리 안에 있으면(자기 정합성 검사) 사본이란 개념이 없으므로 배제하지 않는다.
var pluginDir = Path.GetDirectoryName(pluginPath)!;
var bundled = new HashSet<string>(StringComparer.OrdinalIgnoreCase);
if (!string.Equals(pluginDir.TrimEnd('\\'), refDir.TrimEnd('\\'), StringComparison.OrdinalIgnoreCase))
{
    bundled.UnionWith(Directory.GetFiles(pluginDir, "*.dll").Select(Path.GetFileNameWithoutExtension));
    bundled.Remove(Path.GetFileNameWithoutExtension(pluginPath));
}

bool IsTarget(string asm) =>
    refDlls.ContainsKey(asm) && (only?.Contains(asm) ?? !bundled.Contains(asm));

using var pe = new PEReader(File.OpenRead(pluginPath));
var mr = pe.GetMetadataReader();

// --- TypeReference 해석: ResolutionScope를 타고 AssemblyReference까지 올라간다 -------------

var typeRefCache = new Dictionary<TypeReferenceHandle, TypeRefInfo>();

TypeRefInfo ResolveTypeRef(TypeReferenceHandle h)
{
    if (typeRefCache.TryGetValue(h, out var cached)) return cached;
    var tr = mr.GetTypeReference(h);
    var name = mr.GetString(tr.Name);
    TypeRefInfo info = null;
    switch (tr.ResolutionScope.Kind)
    {
        case HandleKind.AssemblyReference:
        {
            var ar = mr.GetAssemblyReference((AssemblyReferenceHandle)tr.ResolutionScope);
            var ns = tr.Namespace.IsNil ? "" : mr.GetString(tr.Namespace);
            var full = ns.Length > 0 ? ns + "." + name : name;
            info = new TypeRefInfo(mr.GetString(ar.Name), ar.Version, full, full);
            break;
        }
        case HandleKind.TypeReference:
        {
            // 중첩 타입: 바깥 타입의 이름에 이어 붙인다. 리플렉션 조회는 '+', 출력은 '/'.
            var outer = ResolveTypeRef((TypeReferenceHandle)tr.ResolutionScope);
            if (outer is not null)
                info = outer with
                {
                    ReflName = outer.ReflName + "+" + name,
                    Display = outer.Display + "/" + name,
                };
            break;
        }
        // ModuleDefinition/ModuleReference 스코프는 플러그인 자기 모듈이라 대조 대상이 아니다.
    }
    typeRefCache[h] = info;
    return info;
}

// TypeSpecification(제네릭 인스턴스 등)이 부모인 MemberReference는 근본 TypeRef까지 벗겨낸다.
// List<Vector3>.Add 같은 참조를 제네릭 정의 List<T>에서 찾기 위한 것.
TypeRefInfo ResolveTypeSpec(TypeSpecificationHandle h)
{
    var blob = mr.GetBlobReader(mr.GetTypeSpecification(h).Signature);
    var root = RootTypeHandle(ref blob);
    return root is { Kind: HandleKind.TypeReference } r ? ResolveTypeRef((TypeReferenceHandle)r) : null;
}

static EntityHandle? RootTypeHandle(ref BlobReader br)
{
    while (true)
    {
        switch (br.ReadSignatureTypeCode())
        {
            case SignatureTypeCode.OptionalModifier:
            case SignatureTypeCode.RequiredModifier:
                br.ReadTypeHandle();
                continue;
            case SignatureTypeCode.GenericTypeInstance:
                br.ReadSignatureTypeCode(); // ELEMENT_TYPE_CLASS / VALUETYPE 표식
                return br.ReadTypeHandle();
            case SignatureTypeCode.TypeHandle:
                return br.ReadTypeHandle();
            default:
                // 배열·포인터 등은 멤버 소유자가 될 수 없으므로 대조하지 않는다.
                return null;
        }
    }
}

// --- 참조 어셈블리 로드 ---------------------------------------------------------------

var resolver = new PathAssemblyResolver(
    Directory.GetFiles(refDir, "*.dll").Concat(
        Directory.GetFiles(Path.GetDirectoryName(typeof(object).Assembly.Location)!, "*.dll")));
using var mlc = new MetadataLoadContext(resolver);

var loadedAsms = new Dictionary<string, Assembly>(StringComparer.OrdinalIgnoreCase);

Assembly LoadTarget(string name)
{
    if (loadedAsms.TryGetValue(name, out var a)) return a;
    try { a = mlc.LoadFromAssemblyPath(refDlls[name]); }
    catch { a = null; }
    loadedAsms[name] = a;
    return a;
}

var typeCache = new Dictionary<string, Type>(StringComparer.Ordinal);

Type FindType(TypeRefInfo info)
{
    var key = info.Asm + "|" + info.ReflName;
    if (typeCache.TryGetValue(key, out var t)) return t;
    var asm = LoadTarget(info.Asm);
    try { t = asm?.GetType(info.ReflName, throwOnError: false); }
    catch { t = null; }
    typeCache[key] = t;
    return t;
}

static IEnumerable<Type> Hierarchy(Type t)
{
    for (var c = t; c is not null;)
    {
        yield return c;
        Type next;
        try { next = c.BaseType; } catch { next = null; }
        c = next;
    }
    Type[] ifaces;
    try { ifaces = t.GetInterfaces(); } catch { ifaces = []; }
    foreach (var i in ifaces) yield return i;
}

// 상속 사슬과 인터페이스를 직접 훑는다. FlattenHierarchy는 정적 멤버만 끌어올리고
// 베이스의 private/internal 인스턴스 멤버는 빼먹어서 없는 멤버로 오판하기 때문.
static IEnumerable<MemberInfo> MembersNamed(Type t, string name)
{
    MemberInfo[] top;
    try { top = t.GetMember(name, Bf.Flat); } catch { top = []; }
    foreach (var m in top) yield return m;

    foreach (var level in Hierarchy(t))
    {
        MemberInfo[] here;
        try { here = level.GetMember(name, Bf.Declared); } catch { continue; }
        foreach (var m in here) yield return m;
    }
}

// --- 시그니처 문자열화 (양쪽을 같은 규칙으로) ------------------------------------------

var provider = new ShortNameSignatureProvider();

static string FormatType(Type t)
{
    try
    {
        if (t.IsByRef) return FormatType(t.GetElementType()) + "&";
        if (t.IsPointer) return FormatType(t.GetElementType()) + "*";
        if (t.IsArray)
        {
            var rank = t.GetArrayRank();
            return FormatType(t.GetElementType()) + (rank == 1 ? "[]" : "[" + new string(',', rank - 1) + "]");
        }
        if (t.IsGenericParameter)
            return (t.DeclaringMethod is not null ? "!!" : "!") + t.GenericParameterPosition;
        // 함수 포인터는 Name이 비어 있어서 그냥 두면 전부 시그니처 불일치로 잡힌다.
        // ClientStructs의 VirtualTable/MemberFunctionPointers가 전부 이 형태다.
        if (IsFnPtr(t))
            return "fnptr(" + string.Join(",", t.GetFunctionPointerParameterTypes().Select(FormatType))
                   + ")->" + FormatType(t.GetFunctionPointerReturnType());
        var name = ShortNameSignatureProvider.Strip(t.Name);
        if (t.IsGenericType)
            return name + "<" + string.Join(",", t.GetGenericArguments().Select(FormatType)) + ">";
        return name;
    }
    catch { return "?"; }
}

static bool IsFnPtr(Type t)
{
    try { return t.IsFunctionPointer; } catch { return false; }
}

static string Key(string ret, int genArity, IEnumerable<string> ps) =>
    ret + "|" + genArity + "|" + string.Join(",", ps);

static string Show(string ret, string name, int genArity, IEnumerable<string> ps) =>
    ret + " " + name + (genArity > 0 ? "<" + genArity + ">" : "") + "(" + string.Join(", ", ps) + ")";

// --- 대조 ------------------------------------------------------------------------------

var findings = new Dictionary<string, List<Finding>>(StringComparer.OrdinalIgnoreCase);
var refVersions = new Dictionary<string, Version>(StringComparer.OrdinalIgnoreCase);
// 없는 타입은 참조가 수십 개씩 달리므로 타입 단위로 묶는다.
var missingTypes = new Dictionary<(string Asm, string Display), SortedSet<string>>();

void Add(string asm, Sev sev, string text)
{
    if (!findings.TryGetValue(asm, out var list)) findings[asm] = list = [];
    list.Add(new Finding(sev, text));
}

foreach (var h in mr.TypeReferences)
{
    var info = ResolveTypeRef(h);
    if (info is null || !IsTarget(info.Asm)) continue;
    refVersions[info.Asm] = info.RefVer;
    if (FindType(info) is null)
        missingTypes.TryAdd((info.Asm, info.Display), []);
}

var checkedRefs = 0;
var missingMember = 0;
var arity = 0;
var sigDiff = 0;

foreach (var h in mr.MemberReferences)
{
    var m = mr.GetMemberReference(h);
    var info = m.Parent.Kind switch
    {
        HandleKind.TypeReference => ResolveTypeRef((TypeReferenceHandle)m.Parent),
        HandleKind.TypeSpecification => ResolveTypeSpec((TypeSpecificationHandle)m.Parent),
        _ => null, // TypeDefinition(자기 모듈), MethodDefinition(vararg 콜사이트), ModuleReference
    };
    if (info is null || !IsTarget(info.Asm)) continue;

    refVersions[info.Asm] = info.RefVer;
    checkedRefs++;

    var name = mr.GetString(m.Name);
    var type = FindType(info);
    if (type is null)
    {
        if (missingTypes.TryGetValue((info.Asm, info.Display), out var names)) names.Add(name);
        continue;
    }

    if (m.GetKind() == MemberReferenceKind.Field)
    {
        var want = m.DecodeFieldSignature(provider, null);
        var cands = MembersNamed(type, name).ToList();
        if (cands.Count == 0)
        {
            missingMember++;
            Add(info.Asm, Sev.MissingMember, $"MISSING MEMBER  {info.Display}.{name}    want field {want}");
            continue;
        }
        var got = cands.Select(c => c switch
        {
            FieldInfo f => FormatType(f.FieldType),
            PropertyInfo p => FormatType(p.PropertyType),
            _ => null,
        }).Where(s => s is not null).Distinct().ToList();
        if (got.Count == 0 || got.Contains(want)) continue;
        sigDiff++;
        Add(info.Asm, Sev.SigDiff,
            $"SIGNATURE DIFF  {info.Display}.{name}    ref: {want}    actual: {string.Join(" | ", got)}");
        continue;
    }

    var sig = m.DecodeMethodSignature(provider, null);
    var wantCount = sig.Header.CallingConvention == SignatureCallingConvention.VarArgs
        ? sig.RequiredParameterCount
        : sig.ParameterTypes.Length;
    var wantKey = Key(sig.ReturnType, sig.GenericParameterCount, sig.ParameterTypes);
    var wantShow = Show(sig.ReturnType, name, sig.GenericParameterCount, sig.ParameterTypes);

    // .ctor은 GetMember로 안 나온다(생성자는 이름 조회 대상이 아니고 상속되지도 않는다).
    List<MethodBase> methods;
    if (name is ".ctor" or ".cctor")
    {
        try { methods = type.GetConstructors(Bf.Declared).Cast<MethodBase>().ToList(); }
        catch { methods = []; }
    }
    else
    {
        methods = MembersNamed(type, name).OfType<MethodBase>().ToList();
    }

    if (methods.Count == 0)
    {
        missingMember++;
        Add(info.Asm, Sev.MissingMember, $"MISSING MEMBER  {info.Display}.{name}    want {wantShow}");
        continue;
    }

    var byArity = methods.Where(x => { try { return x.GetParameters().Length == wantCount; } catch { return false; } }).ToList();
    if (byArity.Count == 0)
    {
        arity++;
        var actual = methods.Select(x => { try { return x.GetParameters().Length; } catch { return -1; } })
                            .Distinct().OrderBy(x => x);
        Add(info.Asm, Sev.Arity,
            $"ARITY MISMATCH  {info.Display}.{name}    want {wantCount} params [{wantShow}]    actual [{string.Join(", ", actual)}]");
        continue;
    }

    var gotShow = new List<string>();
    var match = false;
    foreach (var c in byArity)
    {
        var ret = c is MethodInfo mi ? FormatType(mi.ReturnType) : "Void";
        var gen = c.IsGenericMethodDefinition ? c.GetGenericArguments().Length : 0;
        var ps = c.GetParameters().Select(p => FormatType(p.ParameterType)).ToList();
        if (Key(ret, gen, ps) == wantKey) { match = true; break; }
        gotShow.Add(Show(ret, c.Name, gen, ps));
    }
    if (match) continue;
    sigDiff++;
    Add(info.Asm, Sev.SigDiff,
        $"SIGNATURE DIFF  {info.Display}.{name}    ref: {wantShow}    actual: {string.Join(" | ", gotShow.Distinct())}");
}

foreach (var ((asm, display), names) in missingTypes)
    Add(asm, Sev.MissingType,
        $"MISSING TYPE    {display}" + (names.Count > 0 ? $"    members: {string.Join(", ", names)}" : ""));

// --- 출력 ------------------------------------------------------------------------------

Console.WriteLine($"# plugin: {Path.GetFileName(pluginPath)}");
Console.WriteLine($"# refdir: {refDir}");
Console.WriteLine();

foreach (var asm in refVersions.Keys.OrderBy(x => x, StringComparer.OrdinalIgnoreCase))
{
    var actual = LoadTarget(asm)?.GetName().Version;
    Console.WriteLine($"# {asm} ref={refVersions[asm]} actual={actual?.ToString() ?? "<load failed>"}");
    if (!findings.TryGetValue(asm, out var list) || list.Count == 0)
    {
        Console.WriteLine("  (no issues)");
        continue;
    }
    foreach (var f in list.OrderBy(f => f.Sev).ThenBy(f => f.Text, StringComparer.Ordinal))
        Console.WriteLine("  " + f.Text);
}

Console.WriteLine();
Console.WriteLine($"SUMMARY: {checkedRefs} checked, {missingTypes.Count} missing-type, "
                  + $"{missingMember} missing-member, {arity} arity, {sigDiff} sig-diff");

// SIGNATURE DIFF는 경고. 바인딩이 깨지는 건 타입/멤버 부재와 인자 개수 불일치다.
return missingTypes.Count + missingMember + arity > 0 ? 1 : 0;

enum Sev { MissingType, MissingMember, Arity, SigDiff }

static class Bf
{
    public const BindingFlags Flat = BindingFlags.Public | BindingFlags.NonPublic
                                     | BindingFlags.Instance | BindingFlags.Static
                                     | BindingFlags.FlattenHierarchy;
    public const BindingFlags Declared = BindingFlags.Public | BindingFlags.NonPublic
                                         | BindingFlags.Instance | BindingFlags.Static
                                         | BindingFlags.DeclaredOnly;
}

record Finding(Sev Sev, string Text);

record TypeRefInfo(string Asm, Version RefVer, string ReflName, string Display);

/// 참조 쪽과 실제 쪽을 같은 문자열로 만들기 위한 짧은 이름 규칙.
/// 포인터 *, byref &, 배열 [], 제네릭 <,>. 네임스페이스와 제네릭 arity 표기(`1)는 버린다.
class ShortNameSignatureProvider : ISignatureTypeProvider<string, object>
{
    public static string Strip(string name)
    {
        var i = name.IndexOf('`');
        return i >= 0 ? name[..i] : name;
    }

    public string GetPrimitiveType(PrimitiveTypeCode code) => code switch
    {
        PrimitiveTypeCode.Void => "Void",
        PrimitiveTypeCode.Boolean => "Boolean",
        PrimitiveTypeCode.Char => "Char",
        PrimitiveTypeCode.SByte => "SByte",
        PrimitiveTypeCode.Byte => "Byte",
        PrimitiveTypeCode.Int16 => "Int16",
        PrimitiveTypeCode.UInt16 => "UInt16",
        PrimitiveTypeCode.Int32 => "Int32",
        PrimitiveTypeCode.UInt32 => "UInt32",
        PrimitiveTypeCode.Int64 => "Int64",
        PrimitiveTypeCode.UInt64 => "UInt64",
        PrimitiveTypeCode.Single => "Single",
        PrimitiveTypeCode.Double => "Double",
        PrimitiveTypeCode.String => "String",
        PrimitiveTypeCode.TypedReference => "TypedReference",
        PrimitiveTypeCode.IntPtr => "IntPtr",
        PrimitiveTypeCode.UIntPtr => "UIntPtr",
        PrimitiveTypeCode.Object => "Object",
        _ => code.ToString(),
    };

    public string GetTypeFromDefinition(MetadataReader reader, TypeDefinitionHandle handle, byte rawTypeKind) =>
        Strip(reader.GetString(reader.GetTypeDefinition(handle).Name));

    public string GetTypeFromReference(MetadataReader reader, TypeReferenceHandle handle, byte rawTypeKind) =>
        Strip(reader.GetString(reader.GetTypeReference(handle).Name));

    public string GetTypeFromSpecification(MetadataReader reader, object genericContext,
                                           TypeSpecificationHandle handle, byte rawTypeKind) =>
        reader.GetTypeSpecification(handle).DecodeSignature(this, genericContext);

    public string GetSZArrayType(string elementType) => elementType + "[]";

    public string GetArrayType(string elementType, ArrayShape shape) =>
        elementType + "[" + new string(',', Math.Max(shape.Rank - 1, 0)) + "]";

    public string GetByReferenceType(string elementType) => elementType + "&";

    public string GetPointerType(string elementType) => elementType + "*";

    public string GetPinnedType(string elementType) => elementType;

    public string GetGenericInstantiation(string genericType, ImmutableArray<string> typeArguments) =>
        genericType + "<" + string.Join(",", typeArguments) + ">";

    public string GetGenericMethodParameter(object genericContext, int index) => "!!" + index;

    public string GetGenericTypeParameter(object genericContext, int index) => "!" + index;

    // modreq/modopt는 바인딩 판정에 무의미하므로 벗겨낸다(IsVolatile 등).
    public string GetModifiedType(string modifier, string unmodifiedType, bool isRequired) => unmodifiedType;

    public string GetFunctionPointerType(MethodSignature<string> signature) =>
        "fnptr(" + string.Join(",", signature.ParameterTypes) + ")->" + signature.ReturnType;
}

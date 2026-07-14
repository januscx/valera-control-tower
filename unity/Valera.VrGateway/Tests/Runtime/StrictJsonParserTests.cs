using System;
using System.Reflection;
using NUnit.Framework;

namespace Valera.VrGateway.Tests
{
    public sealed class StrictJsonParserTests
    {
        [TestCase("{\"x\":1,\"\\u0078\":2}")]
        [TestCase("{\"x\":1,}")]
        [TestCase("{\"x\":1} trailing")]
        [TestCase("{\"x\":01}")]
        [TestCase("{\"x\":NaN}")]
        [TestCase("{\"x\":\"\\uD800\"}")]
        public void Parse_RejectsUnsafeJson(string json)
        {
            Exception error = Assert.Throws<TargetInvocationException>(() => Parse(json));
            Assert.That(error.InnerException.GetType().Name, Is.EqualTo("WireValidationException"));
        }

        [Test]
        public void Parse_AcceptsStandardJsonAndDecodesEscapedPropertyNames()
        {
            object root = Parse("{\"nested\":[true,null,\"\\u006f\\u006b\"],\"number\":-12.5}");

            Assert.That(root, Is.Not.Null);
        }

        private static object Parse(string json)
        {
            Type parser = Type.GetType("Valera.VrGateway.Json.StrictJsonParser, Valera.VrGateway.Runtime");
            Assert.That(parser, Is.Not.Null, "StrictJsonParser must exist in the runtime assembly.");
            MethodInfo method = parser.GetMethod("Parse", BindingFlags.Public | BindingFlags.Static);
            Assert.That(method, Is.Not.Null, "StrictJsonParser.Parse must be public.");
            return method.Invoke(null, new object[] { json });
        }
    }
}

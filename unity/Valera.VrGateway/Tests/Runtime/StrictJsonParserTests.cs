using System;
using System.Reflection;
using NUnit.Framework;
using Valera.VrGateway.Json;

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
            Exception error = Assert.Throws<TargetInvocationException>(() => ParseViaReflection(json));
            Assert.That(error.InnerException.GetType().Name, Is.EqualTo("WireValidationException"));
        }

        [Test]
        public void Parse_AcceptsStandardJsonAndDecodesEscapedPropertyNames()
        {
            object root = ParseViaReflection("{\"nested\":[true,null,\"\\u006f\\u006b\"],\"number\":-12.5}");

            Assert.That(root, Is.Not.Null);
        }

        [Test]
        public void Parse_AcceptsRawSurrogatePair()
        {
            // U+1F916 Robot emoji as raw UTF-16 surrogate pair D83E DD16.
            JsonValue root = StrictJsonParser.Parse("{\"emoji\":\"\ud83e\udd16\"}");
            Assert.That(root, Is.Not.Null);
            Assert.That(root.members["emoji"].text, Is.EqualTo("\ud83e\udd16"));
        }

        [Test]
        public void Parse_AcceptsEscapedSurrogatePair()
        {
            JsonValue root = StrictJsonParser.Parse("{\"emoji\":\"\\uD83E\\uDD16\"}");
            Assert.That(root.members["emoji"].text, Is.EqualTo("\ud83e\udd16"));
        }

        [TestCaseSource(nameof(MalformedRawSurrogateCases))]
        public void Parse_RejectsMalformedRawSurrogates(string json)
        {
            Assert.Throws<WireValidationException>(() => StrictJsonParser.Parse(json));
        }

        private static object[] MalformedRawSurrogateCases()
        {
            return new object[]
            {
                "{\"x\":\"" + new string(new[] { (char)0xD83E }) + "\"}",
                "{\"x\":\"" + new string(new[] { (char)0xDD16 }) + "\"}",
                "{\"x\":\"" + new string(new[] { (char)0xD83E, (char)0xD83E }) + "\"}",
                "{\"x\":\"" + new string(new[] { (char)0xDD16, (char)0xDD16 }) + "\"}",
            };
        }

        private static object ParseViaReflection(string json)
        {
            Type parser = Type.GetType("Valera.VrGateway.Json.StrictJsonParser, Valera.VrGateway.Runtime");
            Assert.That(parser, Is.Not.Null, "StrictJsonParser must exist in the runtime assembly.");
            MethodInfo method = parser.GetMethod("Parse", BindingFlags.Public | BindingFlags.Static);
            Assert.That(method, Is.Not.Null, "StrictJsonParser.Parse must be public.");
            return method.Invoke(null, new object[] { json });
        }
    }
}

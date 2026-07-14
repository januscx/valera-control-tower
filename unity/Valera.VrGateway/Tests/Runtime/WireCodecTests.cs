using System;
using System.Reflection;
using NUnit.Framework;

namespace Valera.VrGateway.Tests
{
    public sealed class WireCodecTests
    {
        private const string SessionStart = "{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}";

        [Test]
        public void DecodeCommand_SelectsExactSessionStartDto()
        {
            object dto = Decode("DecodeCommand", SessionStart);
            Assert.That(dto.GetType().FullName, Is.EqualTo("Valera.VrGateway.Contracts.SessionStartCommandDto"));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1.0,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.2\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"unknown\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\"}}")]
        [TestCase("{\"schema_version\":\"0.1\",\"command\":\"session.start\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"requested_mode\":\"head\",\"extra\":true}}")]
        public void DecodeCommand_FailsClosed(string json)
        {
            Exception error = Assert.Throws<TargetInvocationException>(() => Decode("DecodeCommand", json));
            Assert.That(error.InnerException.GetType().Name, Is.EqualTo("WireValidationException"));
        }

        [TestCase("")]
        [TestCase("   ")]
        [TestCase("aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")]
        public void DecodeCommand_RejectsUnsafeModeStrings(string mode)
        {
            string json = "{\"schema_version\":\"0.1\",\"command\":\"mode.set\",\"session_id\":\"s-1\",\"sequence\":1,\"timestamp_ms\":0,\"payload\":{\"mode\":\"" + mode + "\"}}";
            Exception error = Assert.Throws<TargetInvocationException>(() => Decode("DecodeCommand", json));
            Assert.That(error.InnerException.GetType().Name, Is.EqualTo("WireValidationException"));
        }

        private static object Decode(string methodName, string json)
        {
            Type codec = Type.GetType("Valera.VrGateway.Json.WireCodec, Valera.VrGateway.Runtime");
            Assert.That(codec, Is.Not.Null, "WireCodec must exist in the runtime assembly.");
            MethodInfo method = codec.GetMethod(methodName, BindingFlags.Public | BindingFlags.Static);
            Assert.That(method, Is.Not.Null, methodName + " must be public.");
            return method.Invoke(null, new object[] { json });
        }
    }
}

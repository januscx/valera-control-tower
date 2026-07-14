using System;
using System.Reflection;
using NUnit.Framework;

namespace Valera.VrGateway.Tests
{
    public sealed class WireEventCodecTests
    {
        [Test]
        public void DecodeEvent_SelectsExactNeckTargetDto()
        {
            object dto = Decode("{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":\"s-1\",\"sequence\":1,\"pan_degrees\":1.0,\"tilt_degrees\":-2.0,\"hold\":false}");
            Assert.That(dto.GetType().FullName, Is.EqualTo("Valera.VrGateway.Contracts.NeckTargetEventDto"));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":null,\"sequence\":1,\"pan_degrees\":1.0,\"tilt_degrees\":-2.0,\"hold\":false}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"unknown\",\"gateway_monotonic_ns\":1}")]
        public void DecodeEvent_FailsClosed(string json)
        {
            Assert.Throws<TargetInvocationException>(() => Decode(json));
        }

        private static object Decode(string json)
        {
            Type type = Type.GetType("Valera.VrGateway.Json.WireCodec, Valera.VrGateway.Runtime");
            Assert.That(type, Is.Not.Null);
            return type.GetMethod("DecodeEvent", BindingFlags.Public | BindingFlags.Static).Invoke(null, new object[] { json });
        }
    }
}

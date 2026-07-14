using System;
using System.Reflection;
using NUnit.Framework;
using Valera.VrGateway.Contracts;

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

        [Test]
        public void DecodeEvent_AcceptsNullCorrelationForGatewayState()
        {
            object dto = Decode("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"IDLE\",\"session_id\":null,\"sequence\":null}");
            var state = (GatewayStateEventDto)dto;
            Assert.That(state.correlation.IsAvailable, Is.False);
        }

        [Test]
        public void DecodeEvent_AcceptsCorrelatedGatewayState()
        {
            object dto = Decode("{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"HEAD_ACTIVE\",\"session_id\":\"s-1\",\"sequence\":2}");
            var state = (GatewayStateEventDto)dto;
            Assert.That(state.correlation.IsAvailable, Is.True);
            Assert.That(state.correlation.SessionId, Is.EqualTo("s-1"));
            Assert.That(state.correlation.Sequence, Is.EqualTo(2L));
        }

        [Test]
        public void DecodeEvent_RejectsPartialCorrelation()
        {
            string json = "{\"schema_version\":\"0.1\",\"event_type\":\"gateway.state\",\"gateway_monotonic_ns\":1,\"state\":\"IDLE\",\"session_id\":\"s-1\",\"sequence\":null}";
            Assert.Throws<TargetInvocationException>(() => Decode(json));
        }

        [Test]
        public void DecodeEvent_RejectsNullCorrelationForNeckTarget()
        {
            string json = "{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":null,\"sequence\":null,\"pan_degrees\":1.0,\"tilt_degrees\":-2.0,\"hold\":false}";
            Assert.Throws<TargetInvocationException>(() => Decode(json));
        }

        [Test]
        public void EncodeEvent_EmitsNullCorrelationForUnavailable()
        {
            var evt = new GatewayStateEventDto { schema_version = "0.1", event_type = "gateway.state", gateway_monotonic_ns = 1, state = "IDLE", correlation = Correlation.Unavailable };
            string json = Encode(evt);
            Assert.That(json, Does.Contain("\"session_id\":null"));
            Assert.That(json, Does.Contain("\"sequence\":null"));
        }

        [Test]
        public void EncodeEvent_EmitsCorrelationValuesWhenAvailable()
        {
            var evt = new CommandRejectedEventDto { schema_version = "0.1", event_type = "command.rejected", gateway_monotonic_ns = 1, code = "UNKNOWN_MODE", message = "Requested mode is not recognized.", correlation = new Correlation("s-1", 2) };
            string json = Encode(evt);
            Assert.That(json, Does.Contain("\"session_id\":\"s-1\""));
            Assert.That(json, Does.Contain("\"sequence\":2"));
        }

        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"unknown\",\"gateway_monotonic_ns\":1}")]
        [TestCase("{\"schema_version\":\"0.1\",\"event_type\":\"neck.target\",\"gateway_monotonic_ns\":1,\"session_id\":null,\"sequence\":1,\"pan_degrees\":1.0,\"tilt_degrees\":-2.0,\"hold\":false}")]
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

        private static string Encode(object dto)
        {
            return Valera.VrGateway.Json.WireCodec.EncodeEvent(dto);
        }
    }
}

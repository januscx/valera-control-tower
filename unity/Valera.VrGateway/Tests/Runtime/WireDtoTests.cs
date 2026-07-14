using System;
using System.Reflection;
using NUnit.Framework;

namespace Valera.VrGateway.Tests
{
    public sealed class WireDtoTests
    {
        [Test]
        public void CommandEnvelope_UsesSnakeCasePublicFields()
        {
            Type type = RequireType("Valera.VrGateway.Contracts.CommandEnvelopeDto");

            Assert.That(type.GetCustomAttribute<SerializableAttribute>(), Is.Not.Null);
            Assert.That(type.GetField("schema_version"), Is.Not.Null);
            Assert.That(type.GetField("command"), Is.Not.Null);
            Assert.That(type.GetField("session_id"), Is.Not.Null);
            Assert.That(type.GetField("sequence").FieldType, Is.EqualTo(typeof(long)));
            Assert.That(type.GetField("timestamp_ms").FieldType, Is.EqualTo(typeof(long)));
            Assert.That(type.GetField("payload"), Is.Not.Null);
        }

        [Test]
        public void WireValues_ExposeExactSchemaStrings()
        {
            Type type = RequireType("Valera.VrGateway.Contracts.WireValues");

            Assert.That((string)type.GetField("SchemaVersion").GetValue(null), Is.EqualTo("0.1"));
            Assert.That((string)type.GetField("SessionStart").GetValue(null), Is.EqualTo("session.start"));
            Assert.That((string)type.GetField("EmergencyStop").GetValue(null), Is.EqualTo("emergency_stop"));
            Assert.That((string)type.GetField("GatewayState").GetValue(null), Is.EqualTo("gateway.state"));
            Assert.That((string)type.GetField("CommandRejected").GetValue(null), Is.EqualTo("command.rejected"));
        }

        private static Type RequireType(string name)
        {
            Type type = Type.GetType(name + ", Valera.VrGateway.Runtime");
            Assert.That(type, Is.Not.Null, name + " must exist in the runtime assembly.");
            return type;
        }
    }
}

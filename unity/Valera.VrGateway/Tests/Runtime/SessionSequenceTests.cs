using System;
using System.Reflection;
using NUnit.Framework;

namespace Valera.VrGateway.Tests
{
    public sealed class SessionSequenceTests
    {
        [Test]
        public void Next_StartsAtOneAndIncrements()
        {
            object sequence = Create(0L);
            Assert.That(Next(sequence), Is.EqualTo(1L));
            Assert.That(Next(sequence), Is.EqualTo(2L));
        }

        [Test]
        public void Next_FailsAtInt64MaximumWithoutWrapping()
        {
            object sequence = Create(long.MaxValue);
            Assert.Throws<TargetInvocationException>(() => Next(sequence));
        }

        private static object Create(long value)
        {
            Type type = Type.GetType("Valera.VrGateway.Session.SessionSequence, Valera.VrGateway.Runtime");
            Assert.That(type, Is.Not.Null, "SessionSequence must exist.");
            return Activator.CreateInstance(type, value);
        }

        private static long Next(object sequence)
        {
            return (long)sequence.GetType().GetMethod("Next", BindingFlags.Public | BindingFlags.Instance).Invoke(sequence, null);
        }
    }
}

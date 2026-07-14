using System;
using System.Reflection;
using NUnit.Framework;
using UnityEngine;

namespace Valera.VrGateway.Tests
{
    public sealed class QuestLocalPoseConverterTests
    {
        [Test]
        public void Convert_MapsUnityForwardToCanonicalForward()
        {
            Quaternion converted = Convert(Quaternion.identity);
            AssertVector(converted * new Vector3(0f, 0f, -1f), new Vector3(0f, 0f, -1f));
        }

        [Test]
        public void Convert_TreatsQuaternionSignsAsEquivalentRotations()
        {
            Quaternion source = Quaternion.AngleAxis(30f, Vector3.up);
            Quaternion positive = Convert(source);
            Quaternion negative = Convert(new Quaternion(-source.x, -source.y, -source.z, -source.w));
            AssertVector(positive * Vector3.forward, negative * Vector3.forward);
            AssertVector(positive * Vector3.up, negative * Vector3.up);
        }

        [Test]
        public void Convert_RejectsZeroQuaternion()
        {
            Assert.Throws<TargetInvocationException>(() => Convert(new Quaternion(0f, 0f, 0f, 0f)));
        }

        private static Quaternion Convert(Quaternion source)
        {
            Type type = Type.GetType("Valera.VrGateway.OpenXr.QuestLocalPoseConverter, Valera.VrGateway.Runtime");
            Assert.That(type, Is.Not.Null, "QuestLocalPoseConverter must exist.");
            MethodInfo method = type.GetMethod("Convert", BindingFlags.Public | BindingFlags.Static);
            Assert.That(method, Is.Not.Null);
            return (Quaternion)method.Invoke(null, new object[] { source });
        }

        private static void AssertVector(Vector3 actual, Vector3 expected)
        {
            Assert.That(Vector3.Distance(actual, expected), Is.LessThan(0.0001f));
        }
    }
}

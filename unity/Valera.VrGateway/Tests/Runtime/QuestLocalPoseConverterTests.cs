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

        [TestCase(30f, 0f, 0f)]
        [TestCase(-30f, 0f, 0f)]
        [TestCase(0f, 20f, 0f)]
        [TestCase(0f, -20f, 0f)]
        [TestCase(0f, 0f, 45f)]
        [TestCase(0f, 0f, -45f)]
        [TestCase(15f, 10f, 5f)]
        [TestCase(-15f, -10f, -5f)]
        public void Convert_ReflectsYawPitchAndRollBasis(float yaw, float pitch, float roll)
        {
            Quaternion unity = Quaternion.AngleAxis(yaw, Vector3.up)
                * Quaternion.AngleAxis(pitch, Vector3.right)
                * Quaternion.AngleAxis(roll, Vector3.forward);
            Quaternion openXr = Convert(unity);

            AssertVector(openXr * new Vector3(0f, 0f, -1f), Reflect(unity * Vector3.forward));
            AssertVector(openXr * Vector3.up, Reflect(unity * Vector3.up));
            AssertVector(openXr * Vector3.right, Reflect(unity * Vector3.right));
        }

        [Test]
        public void Convert_PreservesRecenterRelativeOrientation()
        {
            Quaternion reference = Quaternion.AngleAxis(25f, Vector3.up);
            Quaternion pose = Quaternion.AngleAxis(50f, Vector3.up) * Quaternion.AngleAxis(10f, Vector3.right);
            Quaternion unityRelative = Quaternion.Inverse(reference) * pose;
            Quaternion canonicalRelative = Quaternion.Inverse(Convert(reference)) * Convert(pose);

            AssertVector(canonicalRelative * new Vector3(0f, 0f, -1f), Reflect(unityRelative * Vector3.forward));
            AssertVector(canonicalRelative * Vector3.up, Reflect(unityRelative * Vector3.up));
        }

        [Test]
        public void Convert_RejectsZeroQuaternion()
        {
            Assert.Throws<TargetInvocationException>(() => Convert(new Quaternion(0f, 0f, 0f, 0f)));
        }

        [Test]
        public void Convert_RejectsNonFiniteQuaternion()
        {
            Assert.Throws<TargetInvocationException>(() => Convert(new Quaternion(float.NaN, 0f, 0f, 1f)));
            Assert.Throws<TargetInvocationException>(() => Convert(new Quaternion(0f, 0f, 0f, float.PositiveInfinity)));
        }

        [Test]
        public void Convert_NormalizesNonUnitQuaternion()
        {
            Quaternion source = new Quaternion(2f, 0f, 0f, 2f);
            Quaternion converted = Convert(source);
            Assert.That(Mathf.Abs(converted.x * converted.x + converted.y * converted.y + converted.z * converted.z + converted.w * converted.w - 1f), Is.LessThan(0.0001f));
        }

        [Test]
        public void Convert_ZeroRelativeOrientationAfterRecenter()
        {
            Quaternion reference = Quaternion.AngleAxis(25f, Vector3.up);
            Quaternion canonicalReference = Convert(reference);
            Quaternion canonicalRelative = Quaternion.Inverse(canonicalReference) * Convert(reference);

            AssertVector(canonicalRelative * new Vector3(0f, 0f, -1f), new Vector3(0f, 0f, -1f));
            AssertVector(canonicalRelative * Vector3.up, Vector3.up);
        }

        [Test]
        public void Convert_SignedRecenterRelativeYawAndPitch()
        {
            Quaternion reference = Quaternion.identity;
            Quaternion pose = Quaternion.AngleAxis(20f, Vector3.up) * Quaternion.AngleAxis(-15f, Vector3.right);
            Quaternion canonicalRelative = Quaternion.Inverse(Convert(reference)) * Convert(pose);

            Vector3 forward = canonicalRelative * new Vector3(0f, 0f, -1f);
            Assert.That(Vector3.Angle(forward, new Vector3(0f, 0f, -1f)), Is.GreaterThan(10f));
            Assert.That(forward.y, Is.LessThan(-0.1f).Or.GreaterThan(0.1f));
        }

        [Test]
        public void Convert_TransformsRightUpForwardBasisVectors()
        {
            Quaternion unity = Quaternion.AngleAxis(90f, Vector3.up);
            Quaternion openXr = Convert(unity);

            AssertVector(openXr * Vector3.right, Reflect(unity * Vector3.right));
            AssertVector(openXr * Vector3.up, Reflect(unity * Vector3.up));
            AssertVector(openXr * new Vector3(0f, 0f, -1f), Reflect(unity * Vector3.forward));
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

        private static Vector3 Reflect(Vector3 value)
        {
            return new Vector3(value.x, value.y, -value.z);
        }
    }
}

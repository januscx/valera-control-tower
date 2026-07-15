using UnityEngine;
using UnityEngine.XR;

namespace Valera.QuestHeadClient.Input
{
    public sealed class QuestControllerInput : MonoBehaviour
    {
        private InputDevice _leftHand;
        private InputDevice _rightHand;

        public Vector2 LeftStick { get; private set; }
        public Vector2 RightStick { get; private set; }
        public float LeftGrip { get; private set; }
        public float RightGrip { get; private set; }
        public float RightTrigger { get; private set; }
        public bool ButtonA { get; private set; }

        private void Update()
        {
            UpdateDevice(ref _leftHand, XRNode.LeftHand);
            UpdateDevice(ref _rightHand, XRNode.RightHand);

            if (_leftHand.isValid)
            {
                _leftHand.TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 leftStick);
                _leftHand.TryGetFeatureValue(CommonUsages.grip, out float leftGrip);
                LeftStick = leftStick;
                LeftGrip = leftGrip;
            }

            if (_rightHand.isValid)
            {
                _rightHand.TryGetFeatureValue(CommonUsages.primary2DAxis, out Vector2 rightStick);
                _rightHand.TryGetFeatureValue(CommonUsages.grip, out float rightGrip);
                _rightHand.TryGetFeatureValue(CommonUsages.trigger, out float rightTrigger);
                _rightHand.TryGetFeatureValue(CommonUsages.primaryButton, out bool buttonA);
                RightStick = rightStick;
                RightGrip = rightGrip;
                RightTrigger = rightTrigger;
                ButtonA = buttonA;
            }
        }

        private static void UpdateDevice(ref InputDevice device, XRNode node)
        {
            if (!device.isValid)
                device = InputDevices.GetDeviceAtXRNode(node);
        }
    }
}

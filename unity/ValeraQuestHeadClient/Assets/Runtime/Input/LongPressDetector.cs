using System;

namespace Valera.QuestHeadClient.Input
{
    public sealed class LongPressDetector
    {
        public event Action OnLongPress;
        public float HoldDuration = 1.0f;

        private float _holdTime;

        public void Update(bool buttonPressed, float deltaTime)
        {
            if (buttonPressed)
            {
                _holdTime += deltaTime;
            }
            else
            {
                _holdTime = 0f;
            }

            if (_holdTime >= HoldDuration)
            {
                _holdTime = 0f;
                OnLongPress?.Invoke();
            }
        }

        public void Reset()
        {
            _holdTime = 0f;
        }
    }
}

using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Net.WebSockets;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.Json;
using Valera.QuestHeadClient.Session;
using Valera.QuestHeadClient.State;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient
{
    public sealed class QuestHeadClientBehaviour : MonoBehaviour
    {
        [SerializeField] private string pi5Address = "127.0.0.1";
        [SerializeField] private int pi5Port = 9091;
        [SerializeField] private QuestHeadPoseSource poseSource;
        [SerializeField] private QuestHeadDebugPanel debugPanel;
        [SerializeField] private GatewayStateStore _stateStore;

        private readonly ConcurrentQueue<Action> mainThreadActions = new ConcurrentQueue<Action>();
        private QuestHeadSession session;
        private VrGatewayWebSocket gatewayWebSocket;
        private int mainThreadId;
        private bool stopping;
        private bool destroyed;
        private bool connecting;
        private readonly TransportCleanupGate cleanupGate = new TransportCleanupGate();
        private bool poseLoopEnabled;
        private int txCount;
        private int rxCount;

        private void Awake()
        {
            mainThreadId = Thread.CurrentThread.ManagedThreadId;
            poseSource = poseSource ?? GetComponent<QuestHeadPoseSource>();
            debugPanel = debugPanel ?? GetComponent<QuestHeadDebugPanel>();
            session = new QuestHeadSession();
            debugPanel?.SetHandlers(Connect, Disconnect, Recenter);
        }

        private void Update()
        {
            DrainMainThreadActions();
            if (!poseLoopEnabled || !session.CanSendPose || poseSource == null || !poseSource.TryGetUnityOrientation(out Quaternion orientation)) return;
            long nowMs = MonotonicMilliseconds();
            if (!session.TryConsumePoseSlot(nowMs)) return;
            SendCommand(session.BuildPose(orientation, nowMs));
        }

        public void Connect()
        {
            if (destroyed || connecting || session.State != QuestHeadClientState.Disconnected || stopping || !cleanupGate.IsAvailable) return;
            connecting = true;
            stopping = false;
            _ = ConnectRoutine();
        }

        public void Recenter()
        {
            if (!session.CanRecenter || poseSource == null || !poseSource.TryGetUnityOrientation(out Quaternion orientation)) return;
            SendCommand(session.BuildRecenter(orientation));
        }

        public void Disconnect()
        {
            BeginCleanup(true, null);
        }

        private async Task ConnectRoutine()
        {
            if (stopping || destroyed)
            {
                connecting = false;
                return;
            }
            session = new QuestHeadSession();
            string startCommand = session.StartSession();
            try
            {
                debugPanel?.SetSocketState("Connecting");
                gatewayWebSocket?.Dispose();
                gatewayWebSocket = new VrGatewayWebSocket();
                gatewayWebSocket.OnEventReceived += OnGatewayEventReceived;
                gatewayWebSocket.OnDisconnected += OnGatewayDisconnected;
                await gatewayWebSocket.Connect($"ws://{pi5Address}:{pi5Port}");
                await gatewayWebSocket.SendCommand(startCommand);
                debugPanel?.SetSocketState("Open");
                debugPanel?.SetSession(session.SessionId);
            }
            catch (Exception exception)
            {
                QueueMainThread(() => HandleTransportError(exception));
            }
            finally
            {
                connecting = false;
            }
        }

        private void OnGatewayEventReceived(string innerJson)
        {
            QueueMainThread(() => HandleInbound(innerJson));
        }

        private void OnGatewayDisconnected()
        {
            QueueMainThread(() => BeginCleanup(false, new WebSocketException("Remote WebSocket close frame received.")));
        }

        private void HandleInbound(string inner)
        {
            rxCount++;
            debugPanel?.SetCounters(txCount, rxCount);
            try
            {
                bool accepted = session.HandleEvent(inner);
                object decoded = WireCodec.DecodeEvent(inner);

                if (_stateStore != null)
                {
                    var envelope = JsonUtility.FromJson<EventEnvelopeDto>(inner);
                    if (envelope != null)
                        _stateStore.UpdateFromEvent(envelope.event_type, inner);
                }

                if (decoded is NeckTargetEventDto target)
                {
                    debugPanel?.SetNeckTarget(target.pan_degrees, target.tilt_degrees, target.correlation.Sequence);
                }
                if (decoded is GatewayStateEventDto state) debugPanel?.SetGatewayState(state.state);
                if (decoded is CommandRejectedEventDto rejection) debugPanel?.SetError($"{rejection.code}: {rejection.message}");
                poseLoopEnabled = accepted && session.CanSendPose;
                if (!accepted || !session.CanSendPose) debugPanel?.SetError(session.LastError);
            }
            catch (Exception exception)
            {
                HandleTransportError(exception);
            }
        }

        private void SendCommand(string innerJson)
        {
            if (string.IsNullOrEmpty(innerJson) || gatewayWebSocket == null || !gatewayWebSocket.IsConnected) return;
            _ = SendCommandSafely(innerJson);
        }

        private async Task SendCommandSafely(string innerJson)
        {
            try
            {
                await gatewayWebSocket.SendCommand(innerJson);
                QueueMainThread(() => { txCount++; debugPanel?.SetCounters(txCount, rxCount); });
            }
            catch (Exception exception)
            {
                QueueMainThread(() => HandleTransportError(exception));
            }
        }

        private void BeginCleanup(bool sendSessionStop, Exception reason)
        {
            if (!cleanupGate.TryClaim()) return;
            stopping = true;
            poseLoopEnabled = false;
            _ = CleanupRoutine(sendSessionStop, reason);
        }

        private async Task CleanupRoutine(bool sendSessionStop, Exception reason)
        {
            try
            {
                if (sendSessionStop && gatewayWebSocket != null && gatewayWebSocket.IsConnected && session.SessionConfirmed)
                {
                    string stop = session.BuildBestEffortStop();
                    if (stop != null) await gatewayWebSocket.SendCommand(stop);
                }
            }
            catch (Exception exception) { reason = reason ?? exception; }
            finally
            {
                try { if (gatewayWebSocket != null) await gatewayWebSocket.Disconnect(); } catch { }
                gatewayWebSocket?.Dispose();
                gatewayWebSocket = null;
                session.Close();
                QueueMainThread(() =>
                {
                    debugPanel?.SetSocketState("Disconnected");
                    if (reason != null) debugPanel?.SetError(reason.Message);
                });
                if (!destroyed)
                {
                    stopping = false;
                }
                cleanupGate.Release();
            }
        }

        private void HandleTransportError(Exception exception)
        {
            BeginCleanup(false, exception);
        }

        private void DrainMainThreadActions()
        {
            while (mainThreadActions.TryDequeue(out Action action)) action();
        }

        private void QueueMainThread(Action action) { mainThreadActions.Enqueue(action); }
        private static long MonotonicMilliseconds() => (long)(Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency);
        private void OnApplicationPause(bool pause) { if (pause) Disconnect(); }
        private void OnApplicationFocus(bool focus) { if (!focus) Disconnect(); }
        private void OnDestroy() { destroyed = true; BeginCleanup(true, null); }

        [Serializable]
        private sealed class EventEnvelopeDto
        {
            public string event_type;
        }
    }
}

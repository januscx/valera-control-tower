using System;
using System.Collections.Concurrent;
using System.Diagnostics;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using Valera.VrGateway.Contracts;
using Valera.VrGateway.Json;
using Valera.QuestHeadClient.Session;
using Valera.QuestHeadClient.Transport;

namespace Valera.QuestHeadClient
{
    public sealed class QuestHeadClientBehaviour : MonoBehaviour
    {
        [SerializeField] private string pi5Address = "127.0.0.1";
        [SerializeField] private int pi5Port = 9091;
        [SerializeField] private QuestHeadPoseSource poseSource;
        [SerializeField] private QuestHeadDebugPanel debugPanel;

        private readonly ConcurrentQueue<Action> mainThreadActions = new ConcurrentQueue<Action>();
        private QuestHeadSession session;
        private IQuestTransport transport;
        private CancellationTokenSource receiveCancellation;
        private Task receiveTask;
        private int mainThreadId;
        private bool stopping;
        private bool poseLoopEnabled;
        private int txCount;
        private int rxCount;

        private void Awake()
        {
            mainThreadId = Thread.CurrentThread.ManagedThreadId;
            poseSource = poseSource ?? GetComponent<QuestHeadPoseSource>();
            debugPanel = debugPanel ?? GetComponent<QuestHeadDebugPanel>();
            session = new QuestHeadSession();
            transport = new ClientWebSocketQuestTransport();
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
            if (session.State != QuestHeadClientState.Disconnected || stopping) return;
            _ = ConnectRoutine();
        }

        public void Recenter()
        {
            if (!session.CanRecenter || poseSource == null || !poseSource.TryGetUnityOrientation(out Quaternion orientation)) return;
            SendCommand(session.BuildRecenter(orientation));
        }

        public void Disconnect()
        {
            _ = DisconnectRoutine();
        }

        private async Task ConnectRoutine()
        {
            stopping = false;
            string startCommand = session.StartSession();
            try
            {
                debugPanel?.SetSocketState("Connecting");
                receiveCancellation = new CancellationTokenSource();
                await transport.ConnectAsync(new Uri($"ws://{pi5Address}:{pi5Port}"), receiveCancellation.Token);
                await SendRawAsync(RosbridgeEnvelopeCodec.EncodeAdvertise("/valera/vr_gateway/command", "std_msgs/msg/String"), receiveCancellation.Token);
                await SendRawAsync(RosbridgeEnvelopeCodec.EncodeSubscribe("/valera/vr_gateway/event"), receiveCancellation.Token);
                receiveTask = ReceiveLoop(receiveCancellation.Token);
                SendCommand(startCommand);
                debugPanel?.SetSocketState("Open");
                debugPanel?.SetSession(session.SessionId);
            }
            catch (Exception exception)
            {
                QueueMainThread(() => HandleTransportError(exception));
            }
        }

        private async Task ReceiveLoop(CancellationToken cancellationToken)
        {
            try
            {
                while (!cancellationToken.IsCancellationRequested)
                {
                    string envelope = await transport.ReceiveAsync(cancellationToken);
                    QueueMainThread(() => HandleInbound(envelope));
                }
            }
            catch (OperationCanceledException) { }
            catch (Exception exception)
            {
                QueueMainThread(() => HandleTransportError(exception));
            }
        }

        private void HandleInbound(string envelope)
        {
            rxCount++;
            debugPanel?.SetCounters(txCount, rxCount);
            try
            {
                string inner = RosbridgeEnvelopeCodec.DecodeMessageData(envelope);
                bool accepted = session.HandleEvent(inner);
                object decoded = WireCodec.DecodeEvent(inner);
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
            if (string.IsNullOrEmpty(innerJson) || transport == null || !transport.IsOpen) return;
            _ = SendRawAsync(RosbridgeEnvelopeCodec.EncodePublish("/valera/vr_gateway/command", innerJson), CancellationToken.None);
        }

        private async Task SendRawAsync(string text, CancellationToken cancellationToken)
        {
            await transport.SendAsync(text, cancellationToken);
            QueueMainThread(() => { txCount++; debugPanel?.SetCounters(txCount, rxCount); });
        }

        private async Task DisconnectRoutine()
        {
            if (stopping) return;
            stopping = true;
            poseLoopEnabled = false;
            try
            {
                if (transport != null && transport.IsOpen && session.SessionConfirmed)
                {
                    string stop = session.BuildBestEffortStop();
                    if (stop != null) await SendRawAsync(RosbridgeEnvelopeCodec.EncodePublish("/valera/vr_gateway/command", stop), CancellationToken.None);
                }
            }
            catch (Exception exception) { debugPanel?.SetError(exception.Message); }
            finally
            {
                receiveCancellation?.Cancel();
                try { if (receiveTask != null) await receiveTask; } catch { }
                try { if (transport != null) await transport.CloseAsync(CancellationToken.None); } catch { }
                transport?.Dispose();
                session.Close();
                debugPanel?.SetSocketState("Disconnected");
            }
        }

        private void HandleTransportError(Exception exception)
        {
            poseLoopEnabled = false;
            debugPanel?.SetSocketState("Disconnected");
            debugPanel?.SetError(exception.Message);
            session.Close();
        }

        private void DrainMainThreadActions()
        {
            while (mainThreadActions.TryDequeue(out Action action)) action();
        }

        private void QueueMainThread(Action action) { mainThreadActions.Enqueue(action); }
        private static long MonotonicMilliseconds() => (long)(Stopwatch.GetTimestamp() * 1000.0 / Stopwatch.Frequency);
        private void OnApplicationPause(bool pause) { if (pause) Disconnect(); }
        private void OnApplicationFocus(bool focus) { if (!focus) Disconnect(); }
        private void OnDestroy() { Disconnect(); }
    }
}

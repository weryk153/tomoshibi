/* eslint-disable global-require */
/* eslint-disable @typescript-eslint/no-var-requires */
/* eslint-disable no-use-before-define */
import { Subject } from 'rxjs';
import { ModelInfo } from '@/context/live2d-config-context';
import { HistoryInfo } from '@/context/websocket-context';
import {
  reconnectDelayMs, shouldAutoReconnect, isHeartbeatStale,
  HEARTBEAT_INTERVAL_MS, HEARTBEAT_MISSED_ALLOWED,
} from '@/services/ws-reconnect';
import { ConfigFile } from '@/context/character-config-context';
import { toaster } from '@/components/ui/tw/toaster';
import { MotionRequest } from '@/hooks/canvas/use-live2d-motion';
import { StageEffectOptions } from '@/effects/stage-effect';
import type { StagePerformanceTrigger } from '@/effects/stage-performance';

export interface DisplayText {
  text: string;
  name: string;
  avatar: string;
}

interface BackgroundFile {
  name: string;
  url: string;
}

export interface AudioPayload {
  type: 'audio';
  audio?: string;
  volumes?: number[];
  slice_length?: number;
  display_text?: DisplayText;
  subtitle_text?: string;
  actions?: Actions;
}

export interface Message {
  id: string;
  content: string;
  role: "ai" | "human";
  timestamp: string;
  name?: string;
  avatar?: string;

  // Fields for different message types (make optional)
  type?: 'text' | 'tool_call_status' | 'image'; // Add possible types, default to 'text' if omitted
  tool_id?: string; // Specific to tool calls
  tool_name?: string; // Specific to tool calls
  status?: 'running' | 'completed' | 'error'; // Specific to tool calls
  // 生成圖片的 URL 路徑，例如 /generated-images/20260817_210311_ab12cd34.png
  image?: string;
}

export interface Actions {
  expressions?: string[] | number [];
  motions?: MotionRequest[];
  pictures?: string[];
  sounds?: string[];
  stage_performance?: string;
}

export interface MessageEvent {
  tool_id: any;
  tool_name: any;
  name: any;
  status: any;
  content: string;
  timestamp: string;
  type: string;
  audio?: string;
  volumes?: number[];
  slice_length?: number;
  files?: BackgroundFile[];
  actions?: Actions;
  text?: string;
  // full-text 的可翻譯代號。後端只會送英文字面值到 text，前端拿 text_key
  // 去翻；沒有這個欄位（舊後端）就用 text。
  text_key?: string;
  model_info?: ModelInfo;
  conf_name?: string;
  conf_uid?: string;
  persona_id?: string | null;
  persona_name?: string | null;
  uids?: string[];
  messages?: Message[];
  history_uid?: string;
  // history-data 上的旗標：true 代表這是連線時後端自動還原的上一段對話，
  // 不是使用者從側邊欄點的，通知就不該跳。
  restored?: boolean;
  success?: boolean;
  histories?: HistoryInfo[];
  configs?: ConfigFile[];
  // 'error' / 'group-operation-result' 帶的純文字說明（toaster 標題用）。
  message?: string;
  members?: string[];
  is_owner?: boolean;
  client_uid?: string;
  forwarded?: boolean;
  display_text?: DisplayText;
  subtitle_text?: string;
  live2d_model?: string;
  browser_view?: {
    debuggerFullscreenUrl: string;
    debuggerUrl: string;
    pages: {
      id: string;
      url: string;
      faviconUrl: string;
      title: string;
      debuggerUrl: string;
      debuggerFullscreenUrl: string;
    }[];
    wsUrl: string;
    sessionId?: string;
  };
  effect?: string;
  effect_options?: StageEffectOptions;
  candidate_count?: number;
  performance_trigger?: StagePerformanceTrigger;
}

// Get translation function for error messages
const getTranslation = () => {
  try {
    const i18next = require('i18next').default;
    return i18next.t.bind(i18next);
  } catch (e) {
    // Fallback if i18next is not available
    return (key: string) => key;
  }
};

class WebSocketService {
  private static instance: WebSocketService;

  private ws: WebSocket | null = null;

  private messageSubject = new Subject<MessageEvent>();

  private stateSubject = new Subject<'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED'>();

  private currentState: 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED' = 'CLOSED';

  // 自動重連。在這之前 onclose 只標記狀態，手機切到別的 App 讓瀏覽器凍結背景
  // 分頁、連線被斷之後，切回來永遠是斷的——畫面看起來正常，只是再也收不到訊息。
  private lastUrl: string | null = null;

  // 使用者／程式主動關閉時不要自己連回去，不然設定頁的「斷線」按鈕會失效。
  private intentionalClose = false;

  private reconnectAttempt = 0;

  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;

  private visibilityBound = false;

  // 心跳。後端 websocket_handler 早就有 heartbeat 處理器會回 heartbeat-ack，
  // 但前端從來沒送過，等於這個機制一直是半成品。它防的是兩件事：閒置的
  // WebSocket 被中間層（例如 Tailscale Serve 這種反向代理）當成沒在用而砍掉，
  // 以及連線「卡住但沒關閉」——那種情況 onclose 永遠不會來，畫面看起來是連著
  // 的，只是再也收不到任何訊息。
  private heartbeatTimer: ReturnType<typeof setInterval> | null = null;

  private lastAckAt: number | null = null;

  static getInstance() {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  private initializeConnection() {
    this.sendMessage({
      type: 'fetch-backgrounds',
    });
    this.sendMessage({
      type: 'fetch-configs',
    });
    this.sendMessage({
      type: 'fetch-history-list',
    });
    // 這裡以前無條件送 create-new-history，於是重新整理＝開一段新對話：
    // 畫面上的訊息被清空，連 AI 的記憶都一起重置。要開哪一段對話現在由後端
    // 決定——它會還原上次那段，沒有可還原的才開新的（見 websocket_handler.py
    // 的 _restore_or_create_history），所以連線時不該再從這裡插手。
  }

  connect(url: string) {
    // 先記位址再關舊連線：disconnect() 會把 intentionalClose 設成 true，
    // 順序反了的話新連線一開始就被當成「使用者要求斷線」，之後斷了不會重連。
    this.lastUrl = url;
    this.cancelPendingReconnect();

    if (this.ws?.readyState === WebSocket.CONNECTING ||
        this.ws?.readyState === WebSocket.OPEN) {
      this.disconnect();
    }
    this.intentionalClose = false;
    this.bindVisibilityReconnect();

    try {
      this.ws = new WebSocket(url);
      this.currentState = 'CONNECTING';
      this.stateSubject.next('CONNECTING');

      this.ws.onopen = () => {
        this.currentState = 'OPEN';
        this.stateSubject.next('OPEN');
        // 連上了就把退避歸零，否則下一次短暫斷線會直接從上次的長間隔起跳。
        this.reconnectAttempt = 0;
        this.startHeartbeat();
        this.initializeConnection();
      };

      this.ws.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          if (message?.type === 'heartbeat-ack') {
            // 純傳輸層的事，不往上送——否則 websocket-handler 的 switch 會
            // 每 25 秒印一次 Unknown message type。
            this.lastAckAt = Date.now();
            return;
          }
          // 任何訊息都證明連線還活著，不是只有 ack。
          this.lastAckAt = Date.now();
          this.messageSubject.next(message);
        } catch (error) {
          console.error('Failed to parse WebSocket message:', error);
          toaster.create({
            title: `${getTranslation()('error.failedParseWebSocket')}: ${error}`,
            type: "error",
            duration: 2000,
          });
        }
      };

      this.ws.onclose = () => {
        this.currentState = 'CLOSED';
        this.stateSubject.next('CLOSED');
        this.stopHeartbeat();
        this.scheduleReconnect();
      };

      this.ws.onerror = () => {
        this.currentState = 'CLOSED';
        this.stateSubject.next('CLOSED');
        this.scheduleReconnect();
      };
    } catch (error) {
      console.error('Failed to connect to WebSocket:', error);
      this.currentState = 'CLOSED';
      this.stateSubject.next('CLOSED');
      this.scheduleReconnect();
    }
  }

  sendMessage(message: object) {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('WebSocket is not open. Unable to send message:', message);
      toaster.create({
        title: getTranslation()('error.websocketNotOpen'),
        type: 'error',
        duration: 2000,
      });
    }
  }

  onMessage(callback: (message: MessageEvent) => void) {
    return this.messageSubject.subscribe(callback);
  }

  onStateChange(callback: (state: 'CONNECTING' | 'OPEN' | 'CLOSING' | 'CLOSED') => void) {
    return this.stateSubject.subscribe(callback);
  }

  disconnect() {
    this.intentionalClose = true;
    this.stopHeartbeat();
    this.cancelPendingReconnect();
    this.ws?.close();
    this.ws = null;
  }

  private startHeartbeat() {
    this.stopHeartbeat();
    this.lastAckAt = Date.now();
    this.heartbeatTimer = setInterval(() => {
      // 分頁在背景時不送：JS 隨時可能被凍結，送了也收不到回覆，反而會在切回來
      // 的瞬間被誤判成卡住。回到前景由 visibilitychange 那條路處理。
      if (typeof document !== 'undefined' && document.visibilityState !== 'visible') return;
      if (this.ws?.readyState !== WebSocket.OPEN) return;

      if (isHeartbeatStale(this.lastAckAt, Date.now(), HEARTBEAT_INTERVAL_MS, HEARTBEAT_MISSED_ALLOWED)) {
        // 主動關掉，讓既有的 onclose -> scheduleReconnect 那條路接手，
        // 而不是在這裡另外寫一份重連邏輯。
        console.warn('[ws] heartbeat 逾時，主動斷線重連');
        this.ws.close();
        return;
      }
      this.ws.send(JSON.stringify({ type: 'heartbeat' }));
    }, HEARTBEAT_INTERVAL_MS);
  }

  private stopHeartbeat() {
    if (this.heartbeatTimer !== null) {
      clearInterval(this.heartbeatTimer);
      this.heartbeatTimer = null;
    }
    this.lastAckAt = null;
  }

  private cancelPendingReconnect() {
    if (this.reconnectTimer !== null) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
  }

  private scheduleReconnect() {
    if (!shouldAutoReconnect({ intentional: this.intentionalClose, url: this.lastUrl })) return;
    // 已經排了就不要再排一個——onerror 後面通常還會跟一個 onclose，兩個都排的話
    // 重連次數會加倍成長，而且會同時開兩條連線。
    if (this.reconnectTimer !== null) return;

    const delay = reconnectDelayMs(this.reconnectAttempt);
    this.reconnectAttempt += 1;
    this.reconnectTimer = setTimeout(() => {
      this.reconnectTimer = null;
      if (this.lastUrl && !this.intentionalClose) this.connect(this.lastUrl);
    }, delay);
  }

  /** 回到前景時如果是斷的就立刻重連，不要等退避那一輪。 */
  private bindVisibilityReconnect() {
    if (this.visibilityBound || typeof document === 'undefined') return;
    this.visibilityBound = true;
    document.addEventListener('visibilitychange', () => {
      if (document.visibilityState !== 'visible') return;
      if (this.currentState === 'OPEN' || this.currentState === 'CONNECTING') return;
      if (!shouldAutoReconnect({ intentional: this.intentionalClose, url: this.lastUrl })) return;
      // 使用者正看著畫面，這時候等 8 秒或 30 秒都太久了。
      this.cancelPendingReconnect();
      this.reconnectAttempt = 0;
      if (this.lastUrl) this.connect(this.lastUrl);
    });
  }

  getCurrentState() {
    return this.currentState;
  }
}

export const wsService = WebSocketService.getInstance();

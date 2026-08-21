/* eslint-disable no-promise-executor-return */
/* eslint-disable arrow-parens */

// 音訊播放佇列。一次只播一段，播完才播下一段。
//
// 這個類別有兩個不變條件，兩個都是踩過才補上的（見 task-queue.test.ts）：
//
// 1. 全程只有一條抽取迴圈。原本 clearQueue() 會把 running 直接設成 false，
//    但那時候可能還有一個 task 在飛——於是下一個 addTask() 會立刻再起一條
//    迴圈，兩條同時讀寫 running，結果是疊音，或是兩條都以為對方會繼續而一起
//    停住。現在 clearQueue() 只清待播清單，不碰 running：在飛的那個 task
//    仍然是 running 旗標的唯一擁有者，它結束時自然會接手後面新排進來的工作。
//
// 2. 單一個 task 卡住不能拖垮整條佇列。播放 task 的 promise 由 audio 事件
//    收尾，而事件不是每種情況都保證會來。一個永不 resolve 的 task 會讓
//    hasTask() 永遠為真，waitForCompletion() 永不 resolve，前端就再也不會送
//    frontend-playback-complete，後端在 finalize_conversation_turn 無限等待，
//    conversation-chain-end 永遠不送，aiState 卡在 thinking-speaking，連帶
//    「主動發言」的閒置計時器永遠不啟動。看門狗把這條連鎖切斷在第一節。
//
// 看門狗只是最後一道防線，不是正常流程的一部分：真正的收尾修在
// audio-manager.ts（停止播放時確實地結束等待中的 task）。所以逾時值取得寬鬆，
// 只要能擋住「永遠」就夠，不該有機會截斷正常長度的語音。
const DEFAULT_TASK_TIMEOUT_MS = 120_000;

export class TaskQueue {
  private queue: (() => Promise<void>)[] = [];

  private running = false;

  private taskInterval: number;

  private taskTimeout: number;

  private activeTasks = new Set<Promise<void>>();

  constructor(taskIntervalMs = 3000, taskTimeoutMs = DEFAULT_TASK_TIMEOUT_MS) {
    this.taskInterval = taskIntervalMs;
    this.taskTimeout = taskTimeoutMs;
  }

  addTask(task: () => Promise<void>) {
    this.queue.push(task);
    this.runNextTask();
  }

  // 打斷時呼叫：捨棄還沒開始的段落。已經在飛的那個 task 不在這裡處理——
  // 停止播放是 audioManager 的事，它會讓那個 task 收尾，收尾後這條迴圈自己
  // 會繼續。刻意不動 running 與 activeTasks，否則就會回到上面說的雙迴圈。
  clearQueue() {
    this.queue = [];
  }

  private async runNextTask() {
    if (this.running || this.queue.length === 0) return;

    this.running = true;
    const task = this.queue.shift();
    if (!task) {
      this.running = false;
      return;
    }

    const taskPromise = task();
    this.activeTasks.add(taskPromise);

    try {
      await this.withWatchdog(taskPromise);
      await new Promise(resolve => setTimeout(resolve, this.taskInterval));
    } catch (error) {
      console.error('Task Queue Error', error);
    } finally {
      this.activeTasks.delete(taskPromise);
      this.running = false;
      this.runNextTask();
    }
  }

  // 逾時的 task 會被放生（沒有取消機制可用），但佇列不再等它。這裡一定要出聲：
  // 靜靜跳過會讓「有一段沒播出來」變成查不到的怪事。
  private withWatchdog(taskPromise: Promise<void>): Promise<void> {
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        console.warn(`Task Queue: task exceeded ${this.taskTimeout}ms, moving on`);
        resolve();
      }, this.taskTimeout);

      taskPromise.then(
        () => { clearTimeout(timer); resolve(); },
        (error) => { clearTimeout(timer); reject(error); },
      );
    });
  }

  public hasTask(): boolean {
    return this.queue.length > 0 || this.activeTasks.size > 0 || this.running;
  }

  public waitForCompletion(): Promise<void> {
    return new Promise((resolve) => {
      const check = () => {
        if (!this.hasTask()) {
          resolve();
        } else {
          setTimeout(check, 100);
        }
      };
      check();
    });
  }
}

export const audioTaskQueue = new TaskQueue(20);

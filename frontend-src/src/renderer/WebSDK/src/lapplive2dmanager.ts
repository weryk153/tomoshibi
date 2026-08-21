// @ts-nocheck
/**
 * Copyright(c) Live2D Inc. All rights reserved.
 *
 * Use of this source code is governed by the Live2D Open Software license
 * that can be found at https://www.live2d.com/eula/live2d-open-software-license-agreement_en.html.
 */

import { CubismMatrix44 } from '@framework/math/cubismmatrix44';
import { ACubismMotion } from '@framework/motion/acubismmotion';
import { csmVector } from '@framework/type/csmvector';

import * as LAppDefine from './lappdefine';
import { canvas } from './lappglmanager';
import { LAppModel } from './lappmodel';
import { LAppPal } from './lapppal';

export let s_instance: LAppLive2DManager | null | undefined = null;

export interface BackgroundLive2DTransform {
  scale: number;
  x: number;
  y: number;
  opacity: number;
  parallax: number;
  transitionMs: number;
}

/**
 * サンプルアプリケーションにおいてCubismModelを管理するクラス
 * モデル生成と破棄、タップイベントの処理、モデル切り替えを行う。
 * 
 * 在示例应用程序中管理CubismModel的类
 * 执行模型生成和销毁、触摸事件处理、模型切换。
 */
export class LAppLive2DManager {
  /**
   * クラスのインスタンス（シングルトン）を返す。
   * インスタンスが生成されていない場合は内部でインスタンスを生成する。
   * 
   * 返回类的实例（单例）。
   * 如果尚未创建实例，则在内部创建实例。
   *
   * @return クラスのインスタンス
   */
  public static getInstance(): LAppLive2DManager {
    if (s_instance == null) {
      s_instance = new LAppLive2DManager();
    }

    return s_instance;
  }

  /**
   * クラスのインスタンス（シングルトン）を解放する。
   * 
   * 释放类的实例（单例）。
   */
  public static releaseInstance(): void {
    if (s_instance != null) {
      s_instance = void 0;
    }

    s_instance = null;
  }

  /**
   * 現在のシーンで保持しているモデルを返す。
   *
   * @param no モデルリストのインデックス値
   * @return モデルのインスタンスを返す。インデックス値が範囲外の場合はNULLを返す。
   */
  public getModel(no: number): LAppModel | null {
    if (no < this._models.getSize()) {
      return this._models.at(no);
    }

    return null;
  }

  /**
   * 現在のシーンで保持しているすべてのモデルを解放する
   */
  public releaseAllModel(): void {
    for (let i = 0; i < this._models.getSize(); i++) {
      this._models.at(i).release();
      this._models.set(i, null);
    }

    this._models.clear();
  }

  /**
   * Load a separate Cubism model for the animated scene layer.
   * Character integrations continue to address model index 0.
   */
  public setBackgroundScene(
    modelUrl: string,
    transform: Partial<BackgroundLive2DTransform> = {}
  ): void {
    const source = String(modelUrl || '').trim();
    this._backgroundSceneTransform = {
      ...this._backgroundSceneTransform,
      ...transform
    };
    if (!source || !source.toLowerCase().includes('.model3.json')) {
      this.clearBackgroundScene();
      return;
    }
    if (source === this._backgroundSceneSource && this._backgroundSceneModel) {
      return;
    }

    this.retireBackgroundSceneModel();
    const cleanUrl = source.split(/[?#]/, 1)[0];
    const slash = cleanUrl.lastIndexOf('/');
    if (slash < 0) return;
    const modelPath = source.slice(0, source.lastIndexOf('/') + 1);
    const modelJsonName = cleanUrl.slice(slash + 1);
    const model = new LAppModel();
    this._backgroundSceneModel = model;
    this._backgroundSceneSource = source;
    this._backgroundSceneReady = false;
    this._backgroundSceneFadeStartedAt = 0;
    model.loadAssets(modelPath, modelJsonName, 1);
  }

  public updateBackgroundSceneTransform(
    transform: Partial<BackgroundLive2DTransform>
  ): void {
    this._backgroundSceneTransform = {
      ...this._backgroundSceneTransform,
      ...transform
    };
  }

  public clearBackgroundScene(): void {
    this.retireBackgroundSceneModel();
    this._backgroundSceneSource = '';
  }

  private retireBackgroundSceneModel(): void {
    if (this._backgroundSceneModel) {
      this._retiredBackgroundSceneModels.push(this._backgroundSceneModel);
      this._backgroundSceneModel = null;
    }
    this._backgroundSceneReady = false;
  }

  private releaseRetiredBackgroundSceneModels(): void {
    this._retiredBackgroundSceneModels =
      this._retiredBackgroundSceneModels.filter((model) => {
        if (!model.isLoadComplete() && !model.hasLoadFailed()) return true;
        model.release();
        return false;
      });
  }

  /**
   * 画面をドラッグした時の処理
   * 
   * 当拖动屏幕时的处理
   *
   * @param x 画面のX座標
   * @param y 画面のY座標
   */
  public onDrag(x: number, y: number): void {
    for (let i = 0; i < this._models.getSize(); i++) {
      const model: LAppModel = this.getModel(i)!;

      if (model) {
        model.setDragging(x, y);
      }
    }
    if (this._backgroundSceneModel) {
      const parallax = this._backgroundSceneTransform.parallax;
      this._backgroundSceneModel.setDragging(x * parallax, y * parallax);
    }
  }

  /**
   * 画面をタップした時の処理
   *
   * @param x 画面のX座標
   * @param y 画面のY座標
   */
  public onTap(x: number, y: number): void {
    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(
        `[APP]tap point: {x: ${x.toFixed(2)} y: ${y.toFixed(2)}}`
      );
    }

    for (let i = 0; i < this._models.getSize(); i++) {
      if (this._models.at(i).hitTest(LAppDefine.HitAreaNameHead, x, y)) {
        if (LAppDefine.DebugLogEnable) {
          LAppPal.printMessage(
            `[APP]hit area: [${LAppDefine.HitAreaNameHead}]`
          );
        }
        this._models.at(i).setRandomExpression();
      } else if (this._models.at(i).hitTest(LAppDefine.HitAreaNameBody, x, y)) {
        if (LAppDefine.DebugLogEnable) {
          LAppPal.printMessage(
            `[APP]hit area: [${LAppDefine.HitAreaNameBody}]`
          );
        }
        this._models
          .at(i)
          .startRandomMotion(
            LAppDefine.MotionGroupTapBody,
            LAppDefine.PriorityNormal,
            this._finishedMotion
          );
      }
    }
  }

  /**
   * 画面を更新するときの処理
   * モデルの更新処理及び描画処理を行う
   */
  public onUpdate(): void {
    const { width, height } = canvas;

    const modelCount: number = this._models.getSize();

    this.releaseRetiredBackgroundSceneModels();

    const backgroundModel = this._backgroundSceneModel;
    if (backgroundModel) {
      if (backgroundModel.hasLoadFailed()) {
        backgroundModel.release();
        this._backgroundSceneModel = null;
        this._backgroundSceneSource = '';
        this._backgroundSceneReady = false;
      } else {
        const projection: CubismMatrix44 = new CubismMatrix44();
        if (
          backgroundModel.getModel() &&
          backgroundModel.getModel().getCanvasWidth() > 1.0 &&
          width < height
        ) {
          backgroundModel.getModelMatrix().setWidth(2.0);
          projection.scale(1.0, width / height);
        } else {
          projection.scale(height / width, 1.0);
        }
        projection.scaleRelative(
          this._backgroundSceneTransform.scale,
          this._backgroundSceneTransform.scale
        );
        projection.translateRelative(
          this._backgroundSceneTransform.x,
          this._backgroundSceneTransform.y
        );

        const isReady = backgroundModel.isLoadComplete();
        if (isReady && !this._backgroundSceneReady) {
          this._backgroundSceneReady = true;
          this._backgroundSceneFadeStartedAt = performance.now();
        }
        const fadeDuration = Math.max(
          0,
          this._backgroundSceneTransform.transitionMs
        );
        const fadeProgress =
          fadeDuration > 0
            ? Math.min(
                1,
                (performance.now() - this._backgroundSceneFadeStartedAt) /
                  fadeDuration
              )
            : 1;
        const opacity =
          this._backgroundSceneTransform.opacity * fadeProgress;
        backgroundModel.setOpacity(opacity);
        if (isReady) {
          const renderer = backgroundModel.getRenderer();
          const color = renderer.getModelColor();
          renderer.setModelColor(color.r, color.g, color.b, opacity);
        }
        backgroundModel.update();
        backgroundModel.draw(projection);
      }
    }

    for (let i = 0; i < modelCount; ++i) {
      const projection: CubismMatrix44 = new CubismMatrix44();
      const model: LAppModel = this.getModel(i);

      if (model.getModel()) {
        if (model.getModel().getCanvasWidth() > 1.0 && width < height) {
          // 横に長いモデルを縦長ウィンドウに表示する際モデルの横サイズでscaleを算出する
          model.getModelMatrix().setWidth(2.0);
          projection.scale(1.0, width / height);
        } else {
          projection.scale(height / width, 1.0);
        }

        // 必要があればここで乗算
        if (this._viewMatrix != null) {
          projection.multiplyByMatrix(this._viewMatrix);
        }
      }

      model.update();
      model.draw(projection); // 参照渡しなのでprojectionは変質する。
    }
  }

  /**
   * 次のシーンに切りかえる
   * サンプルアプリケーションではモデルセットの切り替えを行う。
   */
  public nextScene(): void {
    const no: number = (this._sceneIndex + 1) % LAppDefine.ModelDirSize;
    this.changeScene(no);
  }

  /**
   * シーンを切り替える
   * サンプルアプリケーションではモデルセットの切り替えを行う。
   */
  public changeScene(index: number): void {
    this._sceneIndex = index;
    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(`[APP]model index: ${this._sceneIndex}`);
    }

    // Use the directory name and file name from our configuration
    const model: string = LAppDefine.ModelDir[index];
    const modelPath: string = LAppDefine.ResourcesPath + model + '/';
    
    // Use ModelFileNames if available, otherwise fall back to ModelDir
    let modelJsonName: string = LAppDefine.ModelFileNames && 
                                LAppDefine.ModelFileNames[index] ? 
                                LAppDefine.ModelFileNames[index] : 
                                LAppDefine.ModelDir[index];
                                
    modelJsonName += '.model3.json';

    if (LAppDefine.DebugLogEnable) {
      LAppPal.printMessage(`[APP]model path: ${modelPath}${modelJsonName}`);
    }

    this.releaseAllModel();
    this._models.pushBack(new LAppModel());
    this._models.at(0).loadAssets(modelPath, modelJsonName);
  }

  public setViewMatrix(m: CubismMatrix44) {
    for (let i = 0; i < 16; i++) {
      this._viewMatrix.getArray()[i] = m.getArray()[i];
    }
  }

  /**
   * コンストラクタ
   */
  constructor() {
    this._viewMatrix = new CubismMatrix44();
    this._models = new csmVector<LAppModel>();
    this._sceneIndex = 0;
    this._backgroundSceneModel = null;
    this._backgroundSceneSource = '';
    this._retiredBackgroundSceneModels = [];
    this._backgroundSceneTransform = {
      scale: 1,
      x: 0,
      y: 0,
      opacity: 1,
      parallax: 0.12,
      transitionMs: 500
    };
    this._backgroundSceneFadeStartedAt = 0;
    this._backgroundSceneReady = false;
    this.changeScene(this._sceneIndex);
  }

  _viewMatrix: CubismMatrix44; // モデル描画に用いるview行列
  _models: csmVector<LAppModel>; // モデルインスタンスのコンテナ
  _sceneIndex: number; // 表示するシーンのインデックス値
  _backgroundSceneModel: LAppModel | null;
  _backgroundSceneSource: string;
  _retiredBackgroundSceneModels: LAppModel[];
  _backgroundSceneTransform: BackgroundLive2DTransform;
  _backgroundSceneFadeStartedAt: number;
  _backgroundSceneReady: boolean;
  // モーション再生終了のコールバック関数
  _finishedMotion = (self: ACubismMotion): void => {
    LAppPal.printMessage('Motion Finished:');
    console.log(self);
  };
}

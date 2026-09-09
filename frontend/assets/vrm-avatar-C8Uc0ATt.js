var ir=Object.defineProperty;var rr=(t,e,n)=>e in t?ir(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n;var U=(t,e,n)=>rr(t,typeof e!="symbol"?e+"":e,n);import{i as Zn,u as or,a as sr,r as Pe,t as Yt,j as ar,b as lr}from"./main-BOjYUPF-.js";import{M as ur,B as dr,V as g,Q as T,E as ce,a as I,G as pe,b as Qt,D as $t,c as Zt,L as We,d as _t,I as hr,S as cr,T as pr,U as fr,e as me,f as X,C as F,g as Y,O as he,h as D,i as mr,j as J,k as _r,l as gr,m as Jt,n as gt,A as vr,R as Ve,o as we,p as Jn,q as Kn,N as Mr,r as xr,s as yr,t as wr,u as ei,v as Rr,w as Tr,W as Sr,x as Ar,P as Er,H as Pr,y as Lr,z as br}from"./GLTFLoader-DsdVE1tb.js";/*!
 * @pixiv/three-vrm v3.5.5
 * VRM file loader for three.js.
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */var Le=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),E=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),Kt=class extends he{constructor(t){super(),this.weight=0,this.isBinary=!1,this.overrideBlink="none",this.overrideLookAt="none",this.overrideMouth="none",this._binds=[],this.name=`VRMExpression_${t}`,this.expressionName=t,this.type="VRMExpression",this.visible=!1}get binds(){return this._binds}get overrideBlinkAmount(){return this.overrideBlink==="block"?0<this.outputWeight?1:0:this.overrideBlink==="blend"?this.outputWeight:0}get overrideLookAtAmount(){return this.overrideLookAt==="block"?0<this.outputWeight?1:0:this.overrideLookAt==="blend"?this.outputWeight:0}get overrideMouthAmount(){return this.overrideMouth==="block"?0<this.outputWeight?1:0:this.overrideMouth==="blend"?this.outputWeight:0}get outputWeight(){return this.isBinary?this.weight>.5?1:0:this.weight}addBind(t){this._binds.push(t)}deleteBind(t){const e=this._binds.indexOf(t);e>=0&&this._binds.splice(e,1)}applyWeight(t){var e;let n=this.outputWeight;n*=(e=t==null?void 0:t.multiplier)!=null?e:1,this.isBinary&&n<1&&(n=0),this._binds.forEach(i=>i.applyWeight(n))}clearAppliedWeight(){this._binds.forEach(t=>t.clearAppliedWeight())}};function ti(t,e,n){var i,r;const o=t.parser.json,s=(i=o.nodes)==null?void 0:i[e];if(s==null)return console.warn(`extractPrimitivesInternal: Attempt to use nodes[${e}] of glTF but the node doesn't exist`),null;const l=s.mesh;if(l==null)return null;const a=(r=o.meshes)==null?void 0:r[l];if(a==null)return console.warn(`extractPrimitivesInternal: Attempt to use meshes[${l}] of glTF but the mesh doesn't exist`),null;const u=a.primitives.length,h=[];return n.traverse(d=>{h.length<u&&d.isMesh&&h.push(d)}),h}function en(t,e){return E(this,null,function*(){const n=yield t.parser.getDependency("node",e);return ti(t,e,n)})}function tn(t){return E(this,null,function*(){const e=yield t.parser.getDependencies("node"),n=new Map;return e.forEach((i,r)=>{const o=ti(t,r,i);o!=null&&n.set(r,o)}),n})}var dt={Aa:"aa",Ih:"ih",Ou:"ou",Ee:"ee",Oh:"oh",Blink:"blink",Happy:"happy",Angry:"angry",Sad:"sad",Relaxed:"relaxed",LookUp:"lookUp",Surprised:"surprised",LookDown:"lookDown",LookLeft:"lookLeft",LookRight:"lookRight",BlinkLeft:"blinkLeft",BlinkRight:"blinkRight",Neutral:"neutral"};function ni(t){return Math.max(Math.min(t,1),0)}var nn=class ii{constructor(){this.blinkExpressionNames=["blink","blinkLeft","blinkRight"],this.lookAtExpressionNames=["lookLeft","lookRight","lookUp","lookDown"],this.mouthExpressionNames=["aa","ee","ih","oh","ou"],this._expressions=[],this._expressionMap={}}get expressions(){return this._expressions.concat()}get expressionMap(){return Object.assign({},this._expressionMap)}get presetExpressionMap(){const e={},n=new Set(Object.values(dt));return Object.entries(this._expressionMap).forEach(([i,r])=>{n.has(i)&&(e[i]=r)}),e}get customExpressionMap(){const e={},n=new Set(Object.values(dt));return Object.entries(this._expressionMap).forEach(([i,r])=>{n.has(i)||(e[i]=r)}),e}copy(e){return this._expressions.concat().forEach(i=>{this.unregisterExpression(i)}),e._expressions.forEach(i=>{this.registerExpression(i)}),this.blinkExpressionNames=e.blinkExpressionNames.concat(),this.lookAtExpressionNames=e.lookAtExpressionNames.concat(),this.mouthExpressionNames=e.mouthExpressionNames.concat(),this}clone(){return new ii().copy(this)}getExpression(e){var n;return(n=this._expressionMap[e])!=null?n:null}registerExpression(e){this._expressions.push(e),this._expressionMap[e.expressionName]=e}unregisterExpression(e){const n=this._expressions.indexOf(e);n===-1&&console.warn("VRMExpressionManager: The specified expressions is not registered"),this._expressions.splice(n,1),delete this._expressionMap[e.expressionName]}getValue(e){var n;const i=this.getExpression(e);return(n=i==null?void 0:i.weight)!=null?n:null}setValue(e,n){const i=this.getExpression(e);i&&(i.weight=ni(n))}resetValues(){this._expressions.forEach(e=>{e.weight=0})}getExpressionTrackName(e){const n=this.getExpression(e);return n?`${n.name}.weight`:null}update(){const e=this._calculateWeightMultipliers();this._expressions.forEach(n=>{n.clearAppliedWeight()}),this._expressions.forEach(n=>{let i=1;const r=n.expressionName;this.blinkExpressionNames.indexOf(r)!==-1&&(i*=e.blink),this.lookAtExpressionNames.indexOf(r)!==-1&&(i*=e.lookAt),this.mouthExpressionNames.indexOf(r)!==-1&&(i*=e.mouth),n.applyWeight({multiplier:i})})}_calculateWeightMultipliers(){let e=1,n=1,i=1;return this._expressions.forEach(r=>{e-=r.overrideBlinkAmount,n-=r.overrideLookAtAmount,i-=r.overrideMouthAmount}),e=Math.max(0,e),n=Math.max(0,n),i=Math.max(0,i),{blink:e,lookAt:n,mouth:i}}},_e={Color:"color",EmissionColor:"emissionColor",ShadeColor:"shadeColor",RimColor:"rimColor",OutlineColor:"outlineColor"},Ir={_Color:_e.Color,_EmissionColor:_e.EmissionColor,_ShadeColor:_e.ShadeColor,_RimColor:_e.RimColor,_OutlineColor:_e.OutlineColor},Cr=new F,ri=class oi{constructor({material:e,type:n,targetValue:i,targetAlpha:r}){this.material=e,this.type=n,this.targetValue=i,this.targetAlpha=r??1;const o=this._initColorBindState(),s=this._initAlphaBindState();this._state={color:o,alpha:s}}applyWeight(e){const{color:n,alpha:i}=this._state;if(n!=null){const{propertyName:r,deltaValue:o}=n,s=this.material[r];s!=null&&s.add(Cr.copy(o).multiplyScalar(e))}if(i!=null){const{propertyName:r,deltaValue:o}=i;this.material[r]!=null&&(this.material[r]+=o*e)}}clearAppliedWeight(){const{color:e,alpha:n}=this._state;if(e!=null){const{propertyName:i,initialValue:r}=e,o=this.material[i];o!=null&&o.copy(r)}if(n!=null){const{propertyName:i,initialValue:r}=n;this.material[i]!=null&&(this.material[i]=r)}}_initColorBindState(){var e,n,i;const{material:r,type:o,targetValue:s}=this,l=this._getPropertyNameMap(),a=(n=(e=l==null?void 0:l[o])==null?void 0:e[0])!=null?n:null;if(a==null)return console.warn(`Tried to add a material color bind to the material ${(i=r.name)!=null?i:"(no name)"}, the type ${o} but the material or the type is not supported.`),null;const h=r[a].clone(),d=new F(s.r-h.r,s.g-h.g,s.b-h.b);return{propertyName:a,initialValue:h,deltaValue:d}}_initAlphaBindState(){var e,n,i;const{material:r,type:o,targetAlpha:s}=this,l=this._getPropertyNameMap(),a=(n=(e=l==null?void 0:l[o])==null?void 0:e[1])!=null?n:null;if(a==null&&s!==1)return console.warn(`Tried to add a material alpha bind to the material ${(i=r.name)!=null?i:"(no name)"}, the type ${o} but the material or the type does not support alpha.`),null;if(a==null)return null;const u=r[a],h=s-u;return{propertyName:a,initialValue:u,deltaValue:h}}_getPropertyNameMap(){var e,n;return(n=(e=Object.entries(oi._propertyNameMapMap).find(([i])=>this.material[i]===!0))==null?void 0:e[1])!=null?n:null}};ri._propertyNameMapMap={isMeshStandardMaterial:{color:["color","opacity"],emissionColor:["emissive",null]},isMeshBasicMaterial:{color:["color","opacity"]},isMToonMaterial:{color:["color","opacity"],emissionColor:["emissive",null],outlineColor:["outlineColorFactor",null],matcapColor:["matcapFactor",null],rimColor:["parametricRimColorFactor",null],shadeColor:["shadeColorFactor",null]}};var rn=ri,De=class{constructor({primitives:t,index:e,weight:n}){this.primitives=t,this.index=e,this.weight=n}applyWeight(t){this.primitives.forEach(e=>{var n;((n=e.morphTargetInfluences)==null?void 0:n[this.index])!=null&&(e.morphTargetInfluences[this.index]+=this.weight*t)})}clearAppliedWeight(){this.primitives.forEach(t=>{var e;((e=t.morphTargetInfluences)==null?void 0:e[this.index])!=null&&(t.morphTargetInfluences[this.index]=0)})}},on=new we,si=class ai{constructor({material:e,scale:n,offset:i}){var r,o;this.material=e,this.scale=n,this.offset=i;const s=(r=Object.entries(ai._propertyNamesMap).find(([l])=>e[l]===!0))==null?void 0:r[1];s==null?(console.warn(`Tried to add a texture transform bind to the material ${(o=e.name)!=null?o:"(no name)"} but the material is not supported.`),this._properties=[]):(this._properties=[],s.forEach(l=>{var a;const u=(a=e[l])==null?void 0:a.clone();if(!u)return null;e[l]=u;const h=u.offset.clone(),d=u.repeat.clone(),c=i.clone().sub(h),p=n.clone().sub(d);this._properties.push({name:l,initialOffset:h,deltaOffset:c,initialScale:d,deltaScale:p})}))}applyWeight(e){this._properties.forEach(n=>{const i=this.material[n.name];i!==void 0&&(i.offset.add(on.copy(n.deltaOffset).multiplyScalar(e)),i.repeat.add(on.copy(n.deltaScale).multiplyScalar(e)))})}clearAppliedWeight(){this._properties.forEach(e=>{const n=this.material[e.name];n!==void 0&&(n.offset.copy(e.initialOffset),n.repeat.copy(e.initialScale))})}};si._propertyNamesMap={isMeshStandardMaterial:["map","emissiveMap","bumpMap","normalMap","displacementMap","roughnessMap","metalnessMap","alphaMap"],isMeshBasicMaterial:["map","specularMap","alphaMap"],isMToonMaterial:["map","normalMap","emissiveMap","shadeMultiplyTexture","rimMultiplyTexture","outlineWidthMultiplyTexture","uvAnimationMaskTexture"]};var sn=si,Or=new Set(["1.0","1.0-beta"]),li=class ui{get name(){return"VRMExpressionLoaderPlugin"}constructor(e){this.parser=e}afterRoot(e){return E(this,null,function*(){e.userData.vrmExpressionManager=yield this._import(e)})}_import(e){return E(this,null,function*(){const n=yield this._v1Import(e);if(n)return n;const i=yield this._v0Import(e);return i||null})}_v1Import(e){return E(this,null,function*(){var n,i;const r=this.parser.json;if(!(((n=r.extensionsUsed)==null?void 0:n.indexOf("VRMC_vrm"))!==-1))return null;const s=(i=r.extensions)==null?void 0:i.VRMC_vrm;if(!s)return null;const l=s.specVersion;if(!Or.has(l))return console.warn(`VRMExpressionLoaderPlugin: Unknown VRMC_vrm specVersion "${l}"`),null;const a=s.expressions;if(!a)return null;const u=new Set(Object.values(dt)),h=new Map;a.preset!=null&&Object.entries(a.preset).forEach(([c,p])=>{if(p!=null){if(!u.has(c)){console.warn(`VRMExpressionLoaderPlugin: Unknown preset name "${c}" detected. Ignoring the expression`);return}h.set(c,p)}}),a.custom!=null&&Object.entries(a.custom).forEach(([c,p])=>{if(u.has(c)){console.warn(`VRMExpressionLoaderPlugin: Custom expression cannot have preset name "${c}". Ignoring the expression`);return}h.set(c,p)});const d=new nn;return yield Promise.all(Array.from(h.entries()).map(c=>E(this,[c],function*([p,f]){var m,_,v,M,R,y,x;const w=new Kt(p);if(e.scene.add(w),w.isBinary=(m=f.isBinary)!=null?m:!1,w.overrideBlink=(_=f.overrideBlink)!=null?_:"none",w.overrideLookAt=(v=f.overrideLookAt)!=null?v:"none",w.overrideMouth=(M=f.overrideMouth)!=null?M:"none",(R=f.morphTargetBinds)==null||R.forEach(S=>E(this,null,function*(){var A;if(S.node===void 0||S.index===void 0)return;const C=yield en(e,S.node),P=S.index;if(!C.every(L=>Array.isArray(L.morphTargetInfluences)&&P<L.morphTargetInfluences.length)){console.warn(`VRMExpressionLoaderPlugin: ${f.name} attempts to index morph #${P} but not found.`);return}w.addBind(new De({primitives:C,index:P,weight:(A=S.weight)!=null?A:1}))})),f.materialColorBinds||f.textureTransformBinds){const S=[];e.scene.traverse(A=>{const C=A.material;C&&(Array.isArray(C)?S.push(...C):S.push(C))}),(y=f.materialColorBinds)==null||y.forEach(A=>E(this,null,function*(){S.filter(P=>{var L;const O=(L=this.parser.associations.get(P))==null?void 0:L.materials;return A.material===O}).forEach(P=>{w.addBind(new rn({material:P,type:A.type,targetValue:new F().fromArray(A.targetValue),targetAlpha:A.targetValue[3]}))})})),(x=f.textureTransformBinds)==null||x.forEach(A=>E(this,null,function*(){S.filter(P=>{var L;const O=(L=this.parser.associations.get(P))==null?void 0:L.materials;return A.material===O}).forEach(P=>{var L,O;w.addBind(new sn({material:P,offset:new we().fromArray((L=A.offset)!=null?L:[0,0]),scale:new we().fromArray((O=A.scale)!=null?O:[1,1])}))})}))}d.registerExpression(w)}))),d})}_v0Import(e){return E(this,null,function*(){var n;const i=this.parser.json,r=(n=i.extensions)==null?void 0:n.VRM;if(!r)return null;const o=r.blendShapeMaster;if(!o)return null;const s=new nn,l=o.blendShapeGroups;if(!l)return s;const a=new Set;return yield Promise.all(l.map(u=>E(this,null,function*(){var h;const d=u.presetName,c=d!=null&&ui.v0v1PresetNameMap[d]||null,p=c??u.name;if(p==null){console.warn("VRMExpressionLoaderPlugin: One of custom expressions has no name. Ignoring the expression");return}if(a.has(p)){console.warn(`VRMExpressionLoaderPlugin: An expression preset ${d} has duplicated entries. Ignoring the expression`);return}a.add(p);const f=new Kt(p);e.scene.add(f),f.isBinary=(h=u.isBinary)!=null?h:!1,u.binds&&u.binds.forEach(_=>E(this,null,function*(){var v;if(_.mesh===void 0||_.index===void 0)return;const M=[];if((v=i.nodes)==null||v.forEach((y,x)=>{y.mesh===_.mesh&&M.push(x)}),M.length===0){console.warn(`VRMExpressionLoaderPlugin: ${u.name} attempts to bind a morph target to the mesh #${_.mesh} but the mesh is not found or not used in the scene. Ignoring the bind.`);return}const R=_.index;yield Promise.all(M.map(y=>E(this,null,function*(){var x;const w=yield en(e,y);if(!w.every(S=>Array.isArray(S.morphTargetInfluences)&&R<S.morphTargetInfluences.length)){console.warn(`VRMExpressionLoaderPlugin: ${u.name} attempts to index ${R}th morph but not found.`);return}f.addBind(new De({primitives:w,index:R,weight:.01*((x=_.weight)!=null?x:100)}))})))}));const m=u.materialValues;m&&m.length!==0&&m.forEach(_=>{if(_.materialName===void 0||_.propertyName===void 0||_.targetValue===void 0)return;const v=[];e.scene.traverse(R=>{if(R.material){const y=R.material;Array.isArray(y)?v.push(...y.filter(x=>(x.name===_.materialName||x.name===_.materialName+" (Outline)")&&v.indexOf(x)===-1)):y.name===_.materialName&&v.indexOf(y)===-1&&v.push(y)}});const M=_.propertyName;v.forEach(R=>{if(M==="_MainTex_ST"){const x=new we(_.targetValue[0],_.targetValue[1]),w=new we(_.targetValue[2],_.targetValue[3]);w.y=1-w.y-x.y,f.addBind(new sn({material:R,scale:x,offset:w}));return}const y=Ir[M];if(y){f.addBind(new rn({material:R,type:y,targetValue:new F().fromArray(_.targetValue),targetAlpha:_.targetValue[3]}));return}console.warn(M+" is not supported")})}),s.registerExpression(f)}))),s})}};li.v0v1PresetNameMap={a:"aa",e:"ee",i:"ih",o:"oh",u:"ou",blink:"blink",joy:"happy",angry:"angry",sorrow:"sad",fun:"relaxed",lookup:"lookUp",lookdown:"lookDown",lookleft:"lookLeft",lookright:"lookRight",blink_l:"blinkLeft",blink_r:"blinkRight",neutral:"neutral"};var Ur=li,vt=class ue{constructor(e,n){this._firstPersonOnlyLayer=ue.DEFAULT_FIRSTPERSON_ONLY_LAYER,this._thirdPersonOnlyLayer=ue.DEFAULT_THIRDPERSON_ONLY_LAYER,this._initializedLayers=!1,this.humanoid=e,this.meshAnnotations=n}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMFirstPerson: humanoid must be same in order to copy");return this.meshAnnotations=e.meshAnnotations.map(n=>({meshes:n.meshes.concat(),type:n.type})),this}clone(){return new ue(this.humanoid,this.meshAnnotations).copy(this)}get firstPersonOnlyLayer(){return this._firstPersonOnlyLayer}get thirdPersonOnlyLayer(){return this._thirdPersonOnlyLayer}setup({firstPersonOnlyLayer:e=ue.DEFAULT_FIRSTPERSON_ONLY_LAYER,thirdPersonOnlyLayer:n=ue.DEFAULT_THIRDPERSON_ONLY_LAYER}={}){this._initializedLayers||(this._firstPersonOnlyLayer=e,this._thirdPersonOnlyLayer=n,this.meshAnnotations.forEach(i=>{i.meshes.forEach(r=>{i.type==="firstPersonOnly"?(r.layers.set(this._firstPersonOnlyLayer),r.traverse(o=>o.layers.set(this._firstPersonOnlyLayer))):i.type==="thirdPersonOnly"?(r.layers.set(this._thirdPersonOnlyLayer),r.traverse(o=>o.layers.set(this._thirdPersonOnlyLayer))):i.type==="auto"&&this._createHeadlessModel(r)})}),this._initializedLayers=!0)}_excludeTriangles(e,n,i,r){let o=0;if(n!=null&&n.length>0)for(let s=0;s<e.length;s+=3){const l=e[s],a=e[s+1],u=e[s+2],h=n[l],d=i[l];if(h[0]>0&&r.includes(d[0])||h[1]>0&&r.includes(d[1])||h[2]>0&&r.includes(d[2])||h[3]>0&&r.includes(d[3]))continue;const c=n[a],p=i[a];if(c[0]>0&&r.includes(p[0])||c[1]>0&&r.includes(p[1])||c[2]>0&&r.includes(p[2])||c[3]>0&&r.includes(p[3]))continue;const f=n[u],m=i[u];f[0]>0&&r.includes(m[0])||f[1]>0&&r.includes(m[1])||f[2]>0&&r.includes(m[2])||f[3]>0&&r.includes(m[3])||(e[o++]=l,e[o++]=a,e[o++]=u)}return o}_createErasedMesh(e,n){const i=new gr(e.geometry.clone(),e.material);i.name=`${e.name}(erase)`,i.frustumCulled=e.frustumCulled,i.layers.set(this._firstPersonOnlyLayer);const r=i.geometry,o=r.getAttribute("skinIndex"),s=o instanceof Jt?[]:o.array,l=[];for(let m=0;m<s.length;m+=4)l.push([s[m],s[m+1],s[m+2],s[m+3]]);const a=r.getAttribute("skinWeight"),u=a instanceof Jt?[]:a.array,h=[];for(let m=0;m<u.length;m+=4)h.push([u[m],u[m+1],u[m+2],u[m+3]]);const d=r.getIndex();if(!d)throw new Error("The geometry doesn't have an index buffer");const c=Array.from(d.array),p=this._excludeTriangles(c,h,l,n),f=[];for(let m=0;m<p;m++)f[m]=c[m];return r.setIndex(f),e.onBeforeRender&&(i.onBeforeRender=e.onBeforeRender),i.bind(new gt(e.skeleton.bones,e.skeleton.boneInverses),new Y),i}_createHeadlessModelForSkinnedMesh(e,n){const i=[];if(n.skeleton.bones.forEach((o,s)=>{this._isEraseTarget(o)&&i.push(s)}),!i.length){n.layers.enable(this._thirdPersonOnlyLayer),n.layers.enable(this._firstPersonOnlyLayer);return}n.layers.set(this._thirdPersonOnlyLayer);const r=this._createErasedMesh(n,i);e.add(r)}_createHeadlessModel(e){if(e.type==="Group")if(e.layers.set(this._thirdPersonOnlyLayer),this._isEraseTarget(e))e.traverse(n=>n.layers.set(this._thirdPersonOnlyLayer));else{const n=new pe;n.name=`_headless_${e.name}`,n.layers.set(this._firstPersonOnlyLayer),e.parent.add(n),e.children.filter(i=>i.type==="SkinnedMesh").forEach(i=>{const r=i;this._createHeadlessModelForSkinnedMesh(n,r)})}else if(e.type==="SkinnedMesh"){const n=e;this._createHeadlessModelForSkinnedMesh(e.parent,n)}else this._isEraseTarget(e)&&(e.layers.set(this._thirdPersonOnlyLayer),e.traverse(n=>n.layers.set(this._thirdPersonOnlyLayer)))}_isEraseTarget(e){return e===this.humanoid.getRawBoneNode("head")?!0:e.parent?this._isEraseTarget(e.parent):!1}};vt.DEFAULT_FIRSTPERSON_ONLY_LAYER=9;vt.DEFAULT_THIRDPERSON_ONLY_LAYER=10;var an=vt,Nr=new Set(["1.0","1.0-beta"]),Vr=class{get name(){return"VRMFirstPersonLoaderPlugin"}constructor(t){this.parser=t}afterRoot(t){return E(this,null,function*(){const e=t.userData.vrmHumanoid;if(e!==null){if(e===void 0)throw new Error("VRMFirstPersonLoaderPlugin: vrmHumanoid is undefined. VRMHumanoidLoaderPlugin have to be used first");t.userData.vrmFirstPerson=yield this._import(t,e)}})}_import(t,e){return E(this,null,function*(){if(e==null)return null;const n=yield this._v1Import(t,e);if(n)return n;const i=yield this._v0Import(t,e);return i||null})}_v1Import(t,e){return E(this,null,function*(){var n,i;const r=this.parser.json;if(!(((n=r.extensionsUsed)==null?void 0:n.indexOf("VRMC_vrm"))!==-1))return null;const s=(i=r.extensions)==null?void 0:i.VRMC_vrm;if(!s)return null;const l=s.specVersion;if(!Nr.has(l))return console.warn(`VRMFirstPersonLoaderPlugin: Unknown VRMC_vrm specVersion "${l}"`),null;const a=s.firstPerson,u=[],h=yield tn(t);return Array.from(h.entries()).forEach(([d,c])=>{var p,f;const m=(p=a==null?void 0:a.meshAnnotations)==null?void 0:p.find(_=>_.node===d);u.push({meshes:c,type:(f=m==null?void 0:m.type)!=null?f:"auto"})}),new an(e,u)})}_v0Import(t,e){return E(this,null,function*(){var n;const i=this.parser.json,r=(n=i.extensions)==null?void 0:n.VRM;if(!r)return null;const o=r.firstPerson;if(!o)return null;const s=[],l=yield tn(t);return Array.from(l.entries()).forEach(([a,u])=>{const h=i.nodes[a],d=o.meshAnnotations?o.meshAnnotations.find(c=>c.mesh===h.mesh):void 0;s.push({meshes:u,type:this._convertV0FlagToV1Type(d==null?void 0:d.firstPersonFlag)})}),new an(e,s)})}_convertV0FlagToV1Type(t){return t==="FirstPersonOnly"?"firstPersonOnly":t==="ThirdPersonOnly"?"thirdPersonOnly":t==="Both"?"both":"auto"}},ln=new g,un=new g,Dr=new T,dn=class extends pe{constructor(t){super(),this.vrmHumanoid=t,this._boneAxesMap=new Map,Object.values(t.humanBones).forEach(e=>{const n=new vr(1);n.matrixAutoUpdate=!1,n.material.depthTest=!1,n.material.depthWrite=!1,this.add(n),this._boneAxesMap.set(e,n)})}dispose(){Array.from(this._boneAxesMap.values()).forEach(t=>{t.geometry.dispose(),t.material.dispose()})}updateMatrixWorld(t){Array.from(this._boneAxesMap.entries()).forEach(([e,n])=>{e.node.updateWorldMatrix(!0,!1),e.node.matrixWorld.decompose(ln,Dr,un);const i=ln.set(.1,.1,.1).divide(un);n.matrix.copy(e.node.matrixWorld).scale(i)}),super.updateMatrixWorld(t)}},Ge=["hips","spine","chest","upperChest","neck","head","leftEye","rightEye","jaw","leftUpperLeg","leftLowerLeg","leftFoot","leftToes","rightUpperLeg","rightLowerLeg","rightFoot","rightToes","leftShoulder","leftUpperArm","leftLowerArm","leftHand","rightShoulder","rightUpperArm","rightLowerArm","rightHand","leftThumbMetacarpal","leftThumbProximal","leftThumbDistal","leftIndexProximal","leftIndexIntermediate","leftIndexDistal","leftMiddleProximal","leftMiddleIntermediate","leftMiddleDistal","leftRingProximal","leftRingIntermediate","leftRingDistal","leftLittleProximal","leftLittleIntermediate","leftLittleDistal","rightThumbMetacarpal","rightThumbProximal","rightThumbDistal","rightIndexProximal","rightIndexIntermediate","rightIndexDistal","rightMiddleProximal","rightMiddleIntermediate","rightMiddleDistal","rightRingProximal","rightRingIntermediate","rightRingDistal","rightLittleProximal","rightLittleIntermediate","rightLittleDistal"],kr={hips:null,spine:"hips",chest:"spine",upperChest:"chest",neck:"upperChest",head:"neck",leftEye:"head",rightEye:"head",jaw:"head",leftUpperLeg:"hips",leftLowerLeg:"leftUpperLeg",leftFoot:"leftLowerLeg",leftToes:"leftFoot",rightUpperLeg:"hips",rightLowerLeg:"rightUpperLeg",rightFoot:"rightLowerLeg",rightToes:"rightFoot",leftShoulder:"upperChest",leftUpperArm:"leftShoulder",leftLowerArm:"leftUpperArm",leftHand:"leftLowerArm",rightShoulder:"upperChest",rightUpperArm:"rightShoulder",rightLowerArm:"rightUpperArm",rightHand:"rightLowerArm",leftThumbMetacarpal:"leftHand",leftThumbProximal:"leftThumbMetacarpal",leftThumbDistal:"leftThumbProximal",leftIndexProximal:"leftHand",leftIndexIntermediate:"leftIndexProximal",leftIndexDistal:"leftIndexIntermediate",leftMiddleProximal:"leftHand",leftMiddleIntermediate:"leftMiddleProximal",leftMiddleDistal:"leftMiddleIntermediate",leftRingProximal:"leftHand",leftRingIntermediate:"leftRingProximal",leftRingDistal:"leftRingIntermediate",leftLittleProximal:"leftHand",leftLittleIntermediate:"leftLittleProximal",leftLittleDistal:"leftLittleIntermediate",rightThumbMetacarpal:"rightHand",rightThumbProximal:"rightThumbMetacarpal",rightThumbDistal:"rightThumbProximal",rightIndexProximal:"rightHand",rightIndexIntermediate:"rightIndexProximal",rightIndexDistal:"rightIndexIntermediate",rightMiddleProximal:"rightHand",rightMiddleIntermediate:"rightMiddleProximal",rightMiddleDistal:"rightMiddleIntermediate",rightRingProximal:"rightHand",rightRingIntermediate:"rightRingProximal",rightRingDistal:"rightRingIntermediate",rightLittleProximal:"rightHand",rightLittleIntermediate:"rightLittleProximal",rightLittleDistal:"rightLittleIntermediate"};function di(t){return t.invert?t.invert():t.inverse(),t}var ne=new g,ie=new T,ht=class{constructor(t){this.humanBones=t,this.restPose=this.getAbsolutePose()}getAbsolutePose(){const t={};return Object.keys(this.humanBones).forEach(e=>{const n=e,i=this.getBoneNode(n);i&&(ne.copy(i.position),ie.copy(i.quaternion),t[n]={position:ne.toArray(),rotation:ie.toArray()})}),t}getPose(){const t={};return Object.keys(this.humanBones).forEach(e=>{const n=e,i=this.getBoneNode(n);if(!i)return;ne.set(0,0,0),ie.identity();const r=this.restPose[n];r!=null&&r.position&&ne.fromArray(r.position).negate(),r!=null&&r.rotation&&di(ie.fromArray(r.rotation)),ne.add(i.position),ie.premultiply(i.quaternion),t[n]={position:ne.toArray(),rotation:ie.toArray()}}),t}setPose(t){Object.entries(t).forEach(([e,n])=>{const i=e,r=this.getBoneNode(i);if(!r)return;const o=this.restPose[i];o&&(n!=null&&n.position&&(r.position.fromArray(n.position),o.position&&r.position.add(ne.fromArray(o.position))),n!=null&&n.rotation&&(r.quaternion.fromArray(n.rotation),o.rotation&&r.quaternion.multiply(ie.fromArray(o.rotation))))})}resetPose(){Object.entries(this.restPose).forEach(([t,e])=>{const n=this.getBoneNode(t);n&&(e!=null&&e.position&&n.position.fromArray(e.position),e!=null&&e.rotation&&n.quaternion.fromArray(e.rotation))})}getBone(t){var e;return(e=this.humanBones[t])!=null?e:void 0}getBoneNode(t){var e,n;return(n=(e=this.humanBones[t])==null?void 0:e.node)!=null?n:null}},Xe=new g,Br=new T,Fr=new g,hn=class hi extends ht{static _setupTransforms(e){const n=new he;n.name="VRMHumanoidRig";const i={},r={},o={};Ge.forEach(l=>{var a;const u=e.getBoneNode(l);if(u){const h=new g,d=new T;u.updateWorldMatrix(!0,!1),u.matrixWorld.decompose(h,d,Xe),i[l]=h,r[l]=u.quaternion.clone();const c=new T;(a=u.parent)==null||a.matrixWorld.decompose(Xe,c,Xe),o[l]=c}});const s={};return Ge.forEach(l=>{var a;const u=e.getBoneNode(l);if(u){const h=i[l];let d=l,c;for(;c==null&&(d=kr[d],d!=null);)c=i[d];const p=new he;p.name="Normalized_"+u.name,(d?(a=s[d])==null?void 0:a.node:n).add(p),p.position.copy(h),c&&p.position.sub(c),s[l]={node:p}}}),{rigBones:s,root:n,parentWorldRotations:o,boneRotations:r}}constructor(e){const{rigBones:n,root:i,parentWorldRotations:r,boneRotations:o}=hi._setupTransforms(e);super(n),this.original=e,this.root=i,this._parentWorldRotations=r,this._boneRotations=o}update(){Ge.forEach(e=>{const n=this.original.getBoneNode(e);if(n!=null){const i=this.getBoneNode(e),r=this._parentWorldRotations[e],o=Br.copy(r).invert(),s=this._boneRotations[e];if(n.quaternion.copy(i.quaternion).multiply(r).premultiply(o).multiply(s),e==="hips"){const l=i.getWorldPosition(Fr);n.parent.updateWorldMatrix(!0,!1);const a=n.parent.matrixWorld,u=l.applyMatrix4(a.invert());n.position.copy(u)}}})}},cn=class ci{get restPose(){return console.warn("VRMHumanoid: restPose is deprecated. Use either rawRestPose or normalizedRestPose instead."),this.rawRestPose}get rawRestPose(){return this._rawHumanBones.restPose}get normalizedRestPose(){return this._normalizedHumanBones.restPose}get humanBones(){return this._rawHumanBones.humanBones}get rawHumanBones(){return this._rawHumanBones.humanBones}get normalizedHumanBones(){return this._normalizedHumanBones.humanBones}get normalizedHumanBonesRoot(){return this._normalizedHumanBones.root}constructor(e,n){var i;this.autoUpdateHumanBones=(i=n==null?void 0:n.autoUpdateHumanBones)!=null?i:!0,this._rawHumanBones=new ht(e),this._normalizedHumanBones=new hn(this._rawHumanBones)}copy(e){return this.autoUpdateHumanBones=e.autoUpdateHumanBones,this._rawHumanBones=new ht(e.humanBones),this._normalizedHumanBones=new hn(this._rawHumanBones),this}clone(){return new ci(this.humanBones,{autoUpdateHumanBones:this.autoUpdateHumanBones}).copy(this)}getAbsolutePose(){return console.warn("VRMHumanoid: getAbsolutePose() is deprecated. Use either getRawAbsolutePose() or getNormalizedAbsolutePose() instead."),this.getRawAbsolutePose()}getRawAbsolutePose(){return this._rawHumanBones.getAbsolutePose()}getNormalizedAbsolutePose(){return this._normalizedHumanBones.getAbsolutePose()}getPose(){return console.warn("VRMHumanoid: getPose() is deprecated. Use either getRawPose() or getNormalizedPose() instead."),this.getRawPose()}getRawPose(){return this._rawHumanBones.getPose()}getNormalizedPose(){return this._normalizedHumanBones.getPose()}setPose(e){return console.warn("VRMHumanoid: setPose() is deprecated. Use either setRawPose() or setNormalizedPose() instead."),this.setRawPose(e)}setRawPose(e){return this._rawHumanBones.setPose(e)}setNormalizedPose(e){return this._normalizedHumanBones.setPose(e)}resetPose(){return console.warn("VRMHumanoid: resetPose() is deprecated. Use either resetRawPose() or resetNormalizedPose() instead."),this.resetRawPose()}resetRawPose(){return this._rawHumanBones.resetPose()}resetNormalizedPose(){return this._normalizedHumanBones.resetPose()}getBone(e){return console.warn("VRMHumanoid: getBone() is deprecated. Use either getRawBone() or getNormalizedBone() instead."),this.getRawBone(e)}getRawBone(e){return this._rawHumanBones.getBone(e)}getNormalizedBone(e){return this._normalizedHumanBones.getBone(e)}getBoneNode(e){return console.warn("VRMHumanoid: getBoneNode() is deprecated. Use either getRawBoneNode() or getNormalizedBoneNode() instead."),this.getRawBoneNode(e)}getRawBoneNode(e){return this._rawHumanBones.getBoneNode(e)}getNormalizedBoneNode(e){return this._normalizedHumanBones.getBoneNode(e)}update(){this.autoUpdateHumanBones&&this._normalizedHumanBones.update()}},Hr={Hips:"hips",Spine:"spine",Head:"head",LeftUpperLeg:"leftUpperLeg",LeftLowerLeg:"leftLowerLeg",LeftFoot:"leftFoot",RightUpperLeg:"rightUpperLeg",RightLowerLeg:"rightLowerLeg",RightFoot:"rightFoot",LeftUpperArm:"leftUpperArm",LeftLowerArm:"leftLowerArm",LeftHand:"leftHand",RightUpperArm:"rightUpperArm",RightLowerArm:"rightLowerArm",RightHand:"rightHand"},Wr=new Set(["1.0","1.0-beta"]),pn={leftThumbProximal:"leftThumbMetacarpal",leftThumbIntermediate:"leftThumbProximal",rightThumbProximal:"rightThumbMetacarpal",rightThumbIntermediate:"rightThumbProximal"},zr=class{get name(){return"VRMHumanoidLoaderPlugin"}constructor(t,e){this.parser=t,this.helperRoot=e==null?void 0:e.helperRoot,this.autoUpdateHumanBones=e==null?void 0:e.autoUpdateHumanBones}afterRoot(t){return E(this,null,function*(){t.userData.vrmHumanoid=yield this._import(t)})}_import(t){return E(this,null,function*(){const e=yield this._v1Import(t);if(e)return e;const n=yield this._v0Import(t);return n||null})}_v1Import(t){return E(this,null,function*(){var e,n;const i=this.parser.json;if(!(((e=i.extensionsUsed)==null?void 0:e.indexOf("VRMC_vrm"))!==-1))return null;const o=(n=i.extensions)==null?void 0:n.VRMC_vrm;if(!o)return null;const s=o.specVersion;if(!Wr.has(s))return console.warn(`VRMHumanoidLoaderPlugin: Unknown VRMC_vrm specVersion "${s}"`),null;const l=o.humanoid;if(!l)return null;const a=l.humanBones.leftThumbIntermediate!=null||l.humanBones.rightThumbIntermediate!=null,u={};l.humanBones!=null&&(yield Promise.all(Object.entries(l.humanBones).map(d=>E(this,[d],function*([c,p]){let f=c;const m=p.node;if(a){const v=pn[f];v!=null&&(f=v)}const _=yield this.parser.getDependency("node",m);if(_==null){console.warn(`A glTF node bound to the humanoid bone ${f} (index = ${m}) does not exist`);return}u[f]={node:_}}))));const h=new cn(this._ensureRequiredBonesExist(u),{autoUpdateHumanBones:this.autoUpdateHumanBones});if(t.scene.add(h.normalizedHumanBonesRoot),this.helperRoot){const d=new dn(h);this.helperRoot.add(d),d.renderOrder=this.helperRoot.renderOrder}return h})}_v0Import(t){return E(this,null,function*(){var e;const i=(e=this.parser.json.extensions)==null?void 0:e.VRM;if(!i)return null;const r=i.humanoid;if(!r)return null;const o={};r.humanBones!=null&&(yield Promise.all(r.humanBones.map(l=>E(this,null,function*(){const a=l.bone,u=l.node;if(a==null||u==null)return;if(u<0){console.warn(`A glTF node index for the humanoid bone ${a} is negative (${u}), ignoring this bone.`);return}const h=yield this.parser.getDependency("node",u);if(h==null){console.warn(`A glTF node bound to the humanoid bone ${a} (index = ${u}) does not exist`);return}const d=pn[a],c=d??a;if(o[c]!=null){console.warn(`Multiple bone entries for ${c} detected (index = ${u}), ignoring duplicated entries.`);return}o[c]={node:h}}))));const s=new cn(this._ensureRequiredBonesExist(o),{autoUpdateHumanBones:this.autoUpdateHumanBones});if(t.scene.add(s.normalizedHumanBonesRoot),this.helperRoot){const l=new dn(s);this.helperRoot.add(l),l.renderOrder=this.helperRoot.renderOrder}return s})}_ensureRequiredBonesExist(t){const e=Object.values(Hr).filter(n=>t[n]==null);if(e.length>0)throw new Error(`VRMHumanoidLoaderPlugin: These humanoid bones are required but not exist: ${e.join(", ")}`);return t}},fn=class extends J{constructor(){super(),this._currentTheta=0,this._currentRadius=0,this.theta=0,this.radius=0,this._currentTheta=0,this._currentRadius=0,this._attrPos=new D(new Float32Array(65*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(3*63),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;this._currentTheta!==this.theta&&(this._currentTheta=this.theta,t=!0),this._currentRadius!==this.radius&&(this._currentRadius=this.radius,t=!0),t&&this._buildPosition()}_buildPosition(){this._attrPos.setXYZ(0,0,0,0);for(let t=0;t<64;t++){const e=t/63*this._currentTheta;this._attrPos.setXYZ(t+1,this._currentRadius*Math.sin(e),0,this._currentRadius*Math.cos(e))}this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<63;t++)this._attrIndex.setXYZ(t*3,0,t+1,t+2);this._attrIndex.needsUpdate=!0}},jr=class extends J{constructor(){super(),this.radius=0,this._currentRadius=0,this.tail=new g,this._currentTail=new g,this._attrPos=new D(new Float32Array(294),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(194),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;this._currentRadius!==this.radius&&(this._currentRadius=this.radius,t=!0),this._currentTail.equals(this.tail)||(this._currentTail.copy(this.tail),t=!0),t&&this._buildPosition()}_buildPosition(){for(let t=0;t<32;t++){const e=t/16*Math.PI;this._attrPos.setXYZ(t,Math.cos(e),Math.sin(e),0),this._attrPos.setXYZ(32+t,0,Math.cos(e),Math.sin(e)),this._attrPos.setXYZ(64+t,Math.sin(e),0,Math.cos(e))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.setXYZ(96,0,0,0),this._attrPos.setXYZ(97,this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(64+t*2,32+t,32+e),this._attrIndex.setXY(128+t*2,64+t,64+e)}this._attrIndex.setXY(192,96,97),this._attrIndex.needsUpdate=!0}},be=new T,mn=new T,ge=new g,_n=new g,gn=Math.sqrt(2)/2,Gr=new T(0,0,-gn,gn),Xr=new g(0,1,0),qr=class extends pe{constructor(t){super(),this.matrixAutoUpdate=!1,this.vrmLookAt=t;{const e=new fn;e.radius=.5;const n=new Qt({color:65280,transparent:!0,opacity:.5,side:$t,depthTest:!1,depthWrite:!1});this._meshPitch=new Zt(e,n),this.add(this._meshPitch)}{const e=new fn;e.radius=.5;const n=new Qt({color:16711680,transparent:!0,opacity:.5,side:$t,depthTest:!1,depthWrite:!1});this._meshYaw=new Zt(e,n),this.add(this._meshYaw)}{const e=new jr;e.radius=.1;const n=new We({color:16777215,depthTest:!1,depthWrite:!1});this._lineTarget=new _t(e,n),this._lineTarget.frustumCulled=!1,this.add(this._lineTarget)}}dispose(){this._meshYaw.geometry.dispose(),this._meshYaw.material.dispose(),this._meshPitch.geometry.dispose(),this._meshPitch.material.dispose(),this._lineTarget.geometry.dispose(),this._lineTarget.material.dispose()}updateMatrixWorld(t){const e=I.DEG2RAD*this.vrmLookAt.yaw;this._meshYaw.geometry.theta=e,this._meshYaw.geometry.update();const n=I.DEG2RAD*this.vrmLookAt.pitch;this._meshPitch.geometry.theta=n,this._meshPitch.geometry.update(),this.vrmLookAt.getLookAtWorldPosition(ge),this.vrmLookAt.getLookAtWorldQuaternion(be),be.multiply(this.vrmLookAt.getFaceFrontQuaternion(mn)),this._meshYaw.position.copy(ge),this._meshYaw.quaternion.copy(be),this._meshPitch.position.copy(ge),this._meshPitch.quaternion.copy(be),this._meshPitch.quaternion.multiply(mn.setFromAxisAngle(Xr,e)),this._meshPitch.quaternion.multiply(Gr);const{target:i,autoUpdate:r}=this.vrmLookAt;i!=null&&r&&(i.getWorldPosition(_n).sub(ge),this._lineTarget.geometry.tail.copy(_n),this._lineTarget.geometry.update(),this._lineTarget.position.copy(ge)),super.updateMatrixWorld(t)}},Yr=new g,Qr=new g;function ct(t,e){return t.matrixWorld.decompose(Yr,e,Qr),e}function Oe(t){return[Math.atan2(-t.z,t.x),Math.atan2(t.y,Math.sqrt(t.x*t.x+t.z*t.z))]}function vn(t){const e=Math.round(t/2/Math.PI);return t-2*Math.PI*e}var Mn=new g(0,0,1),$r=new g,Zr=new g,Jr=new g,Kr=new T,qe=new T,xn=new T,eo=new T,Ye=new ce,pi=class fi{constructor(e,n){this.offsetFromHeadBone=new g,this.autoUpdate=!0,this.faceFront=new g(0,0,1),this.humanoid=e,this.applier=n,this._yaw=0,this._pitch=0,this._needsUpdate=!0,this._restHeadWorldQuaternion=this.getLookAtWorldQuaternion(new T)}get yaw(){return this._yaw}set yaw(e){this._yaw=e,this._needsUpdate=!0}get pitch(){return this._pitch}set pitch(e){this._pitch=e,this._needsUpdate=!0}get euler(){return console.warn("VRMLookAt: euler is deprecated. use getEuler() instead."),this.getEuler(new ce)}getEuler(e){return e.set(I.DEG2RAD*this._pitch,I.DEG2RAD*this._yaw,0,"YXZ")}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMLookAt: humanoid must be same in order to copy");return this.offsetFromHeadBone.copy(e.offsetFromHeadBone),this.applier=e.applier,this.autoUpdate=e.autoUpdate,this.target=e.target,this.faceFront.copy(e.faceFront),this}clone(){return new fi(this.humanoid,this.applier).copy(this)}reset(){this._yaw=0,this._pitch=0,this._needsUpdate=!0}getLookAtWorldPosition(e){const n=this.humanoid.getRawBoneNode("head");return e.copy(this.offsetFromHeadBone).applyMatrix4(n.matrixWorld)}getLookAtWorldQuaternion(e){const n=this.humanoid.getRawBoneNode("head");return ct(n,e)}getFaceFrontQuaternion(e){if(this.faceFront.distanceToSquared(Mn)<.01)return e.copy(this._restHeadWorldQuaternion).invert();const[n,i]=Oe(this.faceFront);return Ye.set(0,.5*Math.PI+n,i,"YZX"),e.setFromEuler(Ye).premultiply(eo.copy(this._restHeadWorldQuaternion).invert())}getLookAtWorldDirection(e){return this.getLookAtWorldQuaternion(qe),this.getFaceFrontQuaternion(xn),e.copy(Mn).applyQuaternion(qe).applyQuaternion(xn).applyEuler(this.getEuler(Ye))}lookAt(e){const n=Kr.copy(this._restHeadWorldQuaternion).multiply(di(this.getLookAtWorldQuaternion(qe))),i=this.getLookAtWorldPosition(Zr),r=Jr.copy(e).sub(i).applyQuaternion(n).normalize(),[o,s]=Oe(this.faceFront),[l,a]=Oe(r),u=vn(l-o),h=vn(s-a);this._yaw=I.RAD2DEG*u,this._pitch=I.RAD2DEG*h,this._needsUpdate=!0}update(e){this.target!=null&&this.autoUpdate&&this.lookAt(this.target.getWorldPosition($r)),this._needsUpdate&&(this._needsUpdate=!1,this.applier.applyYawPitch(this._yaw,this._pitch))}};pi.EULER_ORDER="YXZ";var to=pi,no=new g(0,0,1),z=new T,se=new T,B=new ce(0,0,0,"YXZ"),Ue=class{constructor(t,e,n,i,r){this.humanoid=t,this.rangeMapHorizontalInner=e,this.rangeMapHorizontalOuter=n,this.rangeMapVerticalDown=i,this.rangeMapVerticalUp=r,this.faceFront=new g(0,0,1),this._restQuatLeftEye=new T,this._restQuatRightEye=new T,this._restLeftEyeParentWorldQuat=new T,this._restRightEyeParentWorldQuat=new T;const o=this.humanoid.getRawBoneNode("leftEye"),s=this.humanoid.getRawBoneNode("rightEye");o&&(this._restQuatLeftEye.copy(o.quaternion),ct(o.parent,this._restLeftEyeParentWorldQuat)),s&&(this._restQuatRightEye.copy(s.quaternion),ct(s.parent,this._restRightEyeParentWorldQuat))}applyYawPitch(t,e){const n=this.humanoid.getRawBoneNode("leftEye"),i=this.humanoid.getRawBoneNode("rightEye"),r=this.humanoid.getNormalizedBoneNode("leftEye"),o=this.humanoid.getNormalizedBoneNode("rightEye");n&&(e<0?B.x=-I.DEG2RAD*this.rangeMapVerticalDown.map(-e):B.x=I.DEG2RAD*this.rangeMapVerticalUp.map(e),t<0?B.y=-I.DEG2RAD*this.rangeMapHorizontalInner.map(-t):B.y=I.DEG2RAD*this.rangeMapHorizontalOuter.map(t),z.setFromEuler(B),this._getWorldFaceFrontQuat(se),r.quaternion.copy(se).multiply(z).multiply(se.invert()),z.copy(this._restLeftEyeParentWorldQuat),n.quaternion.copy(r.quaternion).multiply(z).premultiply(z.invert()).multiply(this._restQuatLeftEye)),i&&(e<0?B.x=-I.DEG2RAD*this.rangeMapVerticalDown.map(-e):B.x=I.DEG2RAD*this.rangeMapVerticalUp.map(e),t<0?B.y=-I.DEG2RAD*this.rangeMapHorizontalOuter.map(-t):B.y=I.DEG2RAD*this.rangeMapHorizontalInner.map(t),z.setFromEuler(B),this._getWorldFaceFrontQuat(se),o.quaternion.copy(se).multiply(z).multiply(se.invert()),z.copy(this._restRightEyeParentWorldQuat),i.quaternion.copy(o.quaternion).multiply(z).premultiply(z.invert()).multiply(this._restQuatRightEye))}lookAt(t){console.warn("VRMLookAtBoneApplier: lookAt() is deprecated. use apply() instead.");const e=I.RAD2DEG*t.y,n=I.RAD2DEG*t.x;this.applyYawPitch(e,n)}_getWorldFaceFrontQuat(t){if(this.faceFront.distanceToSquared(no)<.01)return t.identity();const[e,n]=Oe(this.faceFront);return B.set(0,.5*Math.PI+e,n,"YZX"),t.setFromEuler(B)}};Ue.type="bone";var pt=class{constructor(t,e,n,i,r){this.expressions=t,this.rangeMapHorizontalInner=e,this.rangeMapHorizontalOuter=n,this.rangeMapVerticalDown=i,this.rangeMapVerticalUp=r}applyYawPitch(t,e){e<0?(this.expressions.setValue("lookDown",0),this.expressions.setValue("lookUp",this.rangeMapVerticalUp.map(-e))):(this.expressions.setValue("lookUp",0),this.expressions.setValue("lookDown",this.rangeMapVerticalDown.map(e))),t<0?(this.expressions.setValue("lookLeft",0),this.expressions.setValue("lookRight",this.rangeMapHorizontalOuter.map(-t))):(this.expressions.setValue("lookRight",0),this.expressions.setValue("lookLeft",this.rangeMapHorizontalOuter.map(t)))}lookAt(t){console.warn("VRMLookAtBoneApplier: lookAt() is deprecated. use apply() instead.");const e=I.RAD2DEG*t.y,n=I.RAD2DEG*t.x;this.applyYawPitch(e,n)}};pt.type="expression";var yn=class{constructor(t,e){this.inputMaxValue=t,this.outputScale=e}map(t){return this.outputScale*ni(t/this.inputMaxValue)}},io=new Set(["1.0","1.0-beta"]),Ie=.01,ro=class{get name(){return"VRMLookAtLoaderPlugin"}constructor(t,e){this.parser=t,this.helperRoot=e==null?void 0:e.helperRoot}afterRoot(t){return E(this,null,function*(){const e=t.userData.vrmHumanoid;if(e===null)return;if(e===void 0)throw new Error("VRMLookAtLoaderPlugin: vrmHumanoid is undefined. VRMHumanoidLoaderPlugin have to be used first");const n=t.userData.vrmExpressionManager;if(n!==null){if(n===void 0)throw new Error("VRMLookAtLoaderPlugin: vrmExpressionManager is undefined. VRMExpressionLoaderPlugin have to be used first");t.userData.vrmLookAt=yield this._import(t,e,n)}})}_import(t,e,n){return E(this,null,function*(){if(e==null||n==null)return null;const i=yield this._v1Import(t,e,n);if(i)return i;const r=yield this._v0Import(t,e,n);return r||null})}_v1Import(t,e,n){return E(this,null,function*(){var i,r,o;const s=this.parser.json;if(!(((i=s.extensionsUsed)==null?void 0:i.indexOf("VRMC_vrm"))!==-1))return null;const a=(r=s.extensions)==null?void 0:r.VRMC_vrm;if(!a)return null;const u=a.specVersion;if(!io.has(u))return console.warn(`VRMLookAtLoaderPlugin: Unknown VRMC_vrm specVersion "${u}"`),null;const h=a.lookAt;if(!h)return null;const d=h.type==="expression"?1:10,c=this._v1ImportRangeMap(h.rangeMapHorizontalInner,d),p=this._v1ImportRangeMap(h.rangeMapHorizontalOuter,d),f=this._v1ImportRangeMap(h.rangeMapVerticalDown,d),m=this._v1ImportRangeMap(h.rangeMapVerticalUp,d);let _;h.type==="expression"?_=new pt(n,c,p,f,m):_=new Ue(e,c,p,f,m);const v=this._importLookAt(e,_);return v.offsetFromHeadBone.fromArray((o=h.offsetFromHeadBone)!=null?o:[0,.06,0]),v})}_v1ImportRangeMap(t,e){var n,i;let r=(n=t==null?void 0:t.inputMaxValue)!=null?n:90;const o=(i=t==null?void 0:t.outputScale)!=null?i:e;return r<Ie&&(console.warn("VRMLookAtLoaderPlugin: inputMaxValue of a range map is too small. Consider reviewing the range map!"),r=Ie),new yn(r,o)}_v0Import(t,e,n){return E(this,null,function*(){var i,r,o,s;const a=(i=this.parser.json.extensions)==null?void 0:i.VRM;if(!a)return null;const u=a.firstPerson;if(!u)return null;const h=u.lookAtTypeName==="BlendShape"?1:10,d=this._v0ImportDegreeMap(u.lookAtHorizontalInner,h),c=this._v0ImportDegreeMap(u.lookAtHorizontalOuter,h),p=this._v0ImportDegreeMap(u.lookAtVerticalDown,h),f=this._v0ImportDegreeMap(u.lookAtVerticalUp,h);let m;u.lookAtTypeName==="BlendShape"?m=new pt(n,d,c,p,f):m=new Ue(e,d,c,p,f);const _=this._importLookAt(e,m);return u.firstPersonBoneOffset?_.offsetFromHeadBone.set((r=u.firstPersonBoneOffset.x)!=null?r:0,(o=u.firstPersonBoneOffset.y)!=null?o:.06,-((s=u.firstPersonBoneOffset.z)!=null?s:0)):_.offsetFromHeadBone.set(0,.06,0),_.faceFront.set(0,0,-1),m instanceof Ue&&m.faceFront.set(0,0,-1),_})}_v0ImportDegreeMap(t,e){var n,i;const r=t==null?void 0:t.curve;JSON.stringify(r)!=="[0,0,0,1,1,1,1,0]"&&console.warn("Curves of LookAtDegreeMap defined in VRM 0.0 are not supported");let o=(n=t==null?void 0:t.xRange)!=null?n:90;const s=(i=t==null?void 0:t.yRange)!=null?i:e;return o<Ie&&(console.warn("VRMLookAtLoaderPlugin: xRange of a degree map is too small. Consider reviewing the degree map!"),o=Ie),new yn(o,s)}_importLookAt(t,e){const n=new to(t,e);if(this.helperRoot){const i=new qr(n);this.helperRoot.add(i),i.renderOrder=this.helperRoot.renderOrder}return n}};function oo(t,e){return typeof t!="string"||t===""?"":(/^https?:\/\//i.test(e)&&/^\//.test(t)&&(e=e.replace(/(^https?:\/\/[^/]+).*/i,"$1")),/^(https?:)?\/\//i.test(t)||/^data:.*,.*$/i.test(t)||/^blob:.*$/i.test(t)?t:e+t)}var so=new Set(["1.0","1.0-beta"]),ao=class{get name(){return"VRMMetaLoaderPlugin"}constructor(t,e){var n,i,r;this.parser=t,this.needThumbnailImage=(n=e==null?void 0:e.needThumbnailImage)!=null?n:!1,this.acceptLicenseUrls=(i=e==null?void 0:e.acceptLicenseUrls)!=null?i:["https://vrm.dev/licenses/1.0/"],this.acceptV0Meta=(r=e==null?void 0:e.acceptV0Meta)!=null?r:!0}afterRoot(t){return E(this,null,function*(){t.userData.vrmMeta=yield this._import(t)})}_import(t){return E(this,null,function*(){const e=yield this._v1Import(t);if(e!=null)return e;const n=yield this._v0Import(t);return n??null})}_v1Import(t){return E(this,null,function*(){var e,n,i;const r=this.parser.json;if(!(((e=r.extensionsUsed)==null?void 0:e.indexOf("VRMC_vrm"))!==-1))return null;const s=(n=r.extensions)==null?void 0:n.VRMC_vrm;if(s==null)return null;const l=s.specVersion;if(!so.has(l))return console.warn(`VRMMetaLoaderPlugin: Unknown VRMC_vrm specVersion "${l}"`),null;const a=s.meta;if(!a)return null;const u=a.licenseUrl;if(!new Set(this.acceptLicenseUrls).has(u))throw new Error(`VRMMetaLoaderPlugin: The license url "${u}" is not accepted`);let d;return this.needThumbnailImage&&a.thumbnailImage!=null&&(d=(i=yield this._extractGLTFImage(a.thumbnailImage))!=null?i:void 0),{metaVersion:"1",name:a.name,version:a.version,authors:a.authors,copyrightInformation:a.copyrightInformation,contactInformation:a.contactInformation,references:a.references,thirdPartyLicenses:a.thirdPartyLicenses,thumbnailImage:d,licenseUrl:a.licenseUrl,avatarPermission:a.avatarPermission,allowExcessivelyViolentUsage:a.allowExcessivelyViolentUsage,allowExcessivelySexualUsage:a.allowExcessivelySexualUsage,commercialUsage:a.commercialUsage,allowPoliticalOrReligiousUsage:a.allowPoliticalOrReligiousUsage,allowAntisocialOrHateUsage:a.allowAntisocialOrHateUsage,creditNotation:a.creditNotation,allowRedistribution:a.allowRedistribution,modification:a.modification,otherLicenseUrl:a.otherLicenseUrl}})}_v0Import(t){return E(this,null,function*(){var e;const i=(e=this.parser.json.extensions)==null?void 0:e.VRM;if(!i)return null;const r=i.meta;if(!r)return null;if(!this.acceptV0Meta)throw new Error("VRMMetaLoaderPlugin: Attempted to load VRM0.0 meta but acceptV0Meta is false");let o;return this.needThumbnailImage&&r.texture!=null&&r.texture!==-1&&(o=yield this.parser.getDependency("texture",r.texture)),{metaVersion:"0",allowedUserName:r.allowedUserName,author:r.author,commercialUssageName:r.commercialUssageName,contactInformation:r.contactInformation,licenseName:r.licenseName,otherLicenseUrl:r.otherLicenseUrl,otherPermissionUrl:r.otherPermissionUrl,reference:r.reference,sexualUssageName:r.sexualUssageName,texture:o??void 0,title:r.title,version:r.version,violentUssageName:r.violentUssageName}})}_extractGLTFImage(t){return E(this,null,function*(){var e;const i=(e=this.parser.json.images)==null?void 0:e[t];if(i==null)return console.warn(`VRMMetaLoaderPlugin: Attempt to use images[${t}] of glTF as a thumbnail but the image doesn't exist`),null;let r=i.uri;if(i.bufferView!=null){const s=yield this.parser.getDependency("bufferView",i.bufferView),l=new Blob([s],{type:i.mimeType});r=URL.createObjectURL(l)}return r==null?(console.warn(`VRMMetaLoaderPlugin: Attempt to use images[${t}] of glTF as a thumbnail but the image couldn't load properly`),null):yield new hr().loadAsync(oo(r,this.parser.options.path)).catch(s=>(console.error(s),console.warn("VRMMetaLoaderPlugin: Failed to load a thumbnail image"),null))})}},lo=class{constructor(t){this.scene=t.scene,this.meta=t.meta,this.humanoid=t.humanoid,this.expressionManager=t.expressionManager,this.firstPerson=t.firstPerson,this.lookAt=t.lookAt}update(t){this.humanoid.update(),this.lookAt&&this.lookAt.update(t),this.expressionManager&&this.expressionManager.update()}},uo=class extends lo{constructor(t){super(t),this.materials=t.materials,this.springBoneManager=t.springBoneManager,this.nodeConstraintManager=t.nodeConstraintManager}update(t){super.update(t),this.nodeConstraintManager&&this.nodeConstraintManager.update(),this.springBoneManager&&this.springBoneManager.update(t),this.materials&&this.materials.forEach(e=>{e.update&&e.update(t)})}},ho=Object.defineProperty,wn=Object.getOwnPropertySymbols,co=Object.prototype.hasOwnProperty,po=Object.prototype.propertyIsEnumerable,Rn=(t,e,n)=>e in t?ho(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n,Tn=(t,e)=>{for(var n in e||(e={}))co.call(e,n)&&Rn(t,n,e[n]);if(wn)for(var n of wn(e))po.call(e,n)&&Rn(t,n,e[n]);return t},oe=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),fo={"":3e3,srgb:3001};function mo(t,e){parseInt(Ve,10)>=152?t.colorSpace=e:t.encoding=fo[e]}var _o=class{get pending(){return Promise.all(this._pendings)}constructor(t,e){this._parser=t,this._materialParams=e,this._pendings=[]}assignPrimitive(t,e){e!=null&&(this._materialParams[t]=e)}assignColor(t,e,n){if(e!=null){const i=new F().fromArray(e);n&&i.convertSRGBToLinear(),this._materialParams[t]=i}}assignTexture(t,e,n){return oe(this,null,function*(){const i=oe(this,null,function*(){if(e!=null){const r=yield this._parser.assignTexture(this._materialParams,t,e);if(r==null){console.warn("GLTFMToonMaterialParamsAssignHelper: Failed to load texture. The rendering result may be wrong");return}n&&mo(r,"srgb")}});return this._pendings.push(i),i})}assignTextureByIndex(t,e,n){return oe(this,null,function*(){return this.assignTexture(t,e!=null?{index:e}:void 0,n)})}},go=`// #define PHONG

varying vec3 vViewPosition;

#ifndef FLAT_SHADED
  varying vec3 vNormal;
#endif

#include <common>

// #include <uv_pars_vertex>
#ifdef MTOON_USE_UV
  varying vec2 vUv;

  // COMPAT: pre-r151 uses a common uvTransform
  #if THREE_VRM_THREE_REVISION < 151
    uniform mat3 uvTransform;
  #endif
#endif

// #include <uv2_pars_vertex>
// COMAPT: pre-r151 uses uv2 for lightMap and aoMap
#if THREE_VRM_THREE_REVISION < 151
  #if defined( USE_LIGHTMAP ) || defined( USE_AOMAP )
    attribute vec2 uv2;
    varying vec2 vUv2;
    uniform mat3 uv2Transform;
  #endif
#endif

// #include <displacementmap_pars_vertex>
// #include <envmap_pars_vertex>
#include <color_pars_vertex>
#include <fog_pars_vertex>
#include <morphtarget_pars_vertex>
#include <skinning_pars_vertex>
#include <shadowmap_pars_vertex>
#include <logdepthbuf_pars_vertex>
#include <clipping_planes_pars_vertex>

#ifdef USE_OUTLINEWIDTHMULTIPLYTEXTURE
  uniform sampler2D outlineWidthMultiplyTexture;
  uniform mat3 outlineWidthMultiplyTextureUvTransform;
#endif

uniform float outlineWidthFactor;

void main() {

  // #include <uv_vertex>
  #ifdef MTOON_USE_UV
    // COMPAT: pre-r151 uses a common uvTransform
    #if THREE_VRM_THREE_REVISION >= 151
      vUv = uv;
    #else
      vUv = ( uvTransform * vec3( uv, 1 ) ).xy;
    #endif
  #endif

  // #include <uv2_vertex>
  // COMAPT: pre-r151 uses uv2 for lightMap and aoMap
  #if THREE_VRM_THREE_REVISION < 151
    #if defined( USE_LIGHTMAP ) || defined( USE_AOMAP )
      vUv2 = ( uv2Transform * vec3( uv2, 1 ) ).xy;
    #endif
  #endif

  #include <color_vertex>

  #include <beginnormal_vertex>
  #include <morphnormal_vertex>
  #include <skinbase_vertex>
  #include <skinnormal_vertex>

  // we need this to compute the outline properly
  objectNormal = normalize( objectNormal );

  #include <defaultnormal_vertex>

  #ifndef FLAT_SHADED // Normal computed with derivatives when FLAT_SHADED
    vNormal = normalize( transformedNormal );
  #endif

  #include <begin_vertex>

  #include <morphtarget_vertex>
  #include <skinning_vertex>
  // #include <displacementmap_vertex>
  #include <project_vertex>
  #include <logdepthbuf_vertex>
  #include <clipping_planes_vertex>

  vViewPosition = - mvPosition.xyz;

  #ifdef OUTLINE
    float worldNormalLength = length( transformedNormal );
    vec3 outlineOffset = outlineWidthFactor * worldNormalLength * objectNormal;

    #ifdef USE_OUTLINEWIDTHMULTIPLYTEXTURE
      vec2 outlineWidthMultiplyTextureUv = ( outlineWidthMultiplyTextureUvTransform * vec3( vUv, 1 ) ).xy;
      float outlineTex = texture2D( outlineWidthMultiplyTexture, outlineWidthMultiplyTextureUv ).g;
      outlineOffset *= outlineTex;
    #endif

    #ifdef OUTLINE_WIDTH_SCREEN
      outlineOffset *= vViewPosition.z / projectionMatrix[ 1 ].y;
    #endif

    gl_Position = projectionMatrix * modelViewMatrix * vec4( outlineOffset + transformed, 1.0 );

    gl_Position.z += 1E-6 * gl_Position.w; // anti-artifact magic
  #endif

  #include <worldpos_vertex>
  // #include <envmap_vertex>
  #include <shadowmap_vertex>
  #include <fog_vertex>

}`,vo=`// #define PHONG

uniform vec3 litFactor;

uniform float opacity;

uniform vec3 shadeColorFactor;
#ifdef USE_SHADEMULTIPLYTEXTURE
  uniform sampler2D shadeMultiplyTexture;
  uniform mat3 shadeMultiplyTextureUvTransform;
#endif

uniform float shadingShiftFactor;
uniform float shadingToonyFactor;

#ifdef USE_SHADINGSHIFTTEXTURE
  uniform sampler2D shadingShiftTexture;
  uniform mat3 shadingShiftTextureUvTransform;
  uniform float shadingShiftTextureScale;
#endif

uniform float giEqualizationFactor;

uniform vec3 parametricRimColorFactor;
#ifdef USE_RIMMULTIPLYTEXTURE
  uniform sampler2D rimMultiplyTexture;
  uniform mat3 rimMultiplyTextureUvTransform;
#endif
uniform float rimLightingMixFactor;
uniform float parametricRimFresnelPowerFactor;
uniform float parametricRimLiftFactor;

#ifdef USE_MATCAPTEXTURE
  uniform vec3 matcapFactor;
  uniform sampler2D matcapTexture;
  uniform mat3 matcapTextureUvTransform;
#endif

uniform vec3 emissive;
uniform float emissiveIntensity;

uniform vec3 outlineColorFactor;
uniform float outlineLightingMixFactor;

#ifdef USE_UVANIMATIONMASKTEXTURE
  uniform sampler2D uvAnimationMaskTexture;
  uniform mat3 uvAnimationMaskTextureUvTransform;
#endif

uniform float uvAnimationScrollXOffset;
uniform float uvAnimationScrollYOffset;
uniform float uvAnimationRotationPhase;

#include <common>
#include <packing>
#include <dithering_pars_fragment>
#include <color_pars_fragment>

// #include <uv_pars_fragment>
#if ( defined( MTOON_USE_UV ) && !defined( MTOON_UVS_VERTEX_ONLY ) )
  varying vec2 vUv;
#endif

// #include <uv2_pars_fragment>
// COMAPT: pre-r151 uses uv2 for lightMap and aoMap
#if THREE_VRM_THREE_REVISION < 151
  #if defined( USE_LIGHTMAP ) || defined( USE_AOMAP )
    varying vec2 vUv2;
  #endif
#endif

#include <map_pars_fragment>

#ifdef USE_MAP
  uniform mat3 mapUvTransform;
#endif

// #include <alphamap_pars_fragment>

#include <alphatest_pars_fragment>

#include <aomap_pars_fragment>
// #include <lightmap_pars_fragment>
#include <emissivemap_pars_fragment>

#ifdef USE_EMISSIVEMAP
  uniform mat3 emissiveMapUvTransform;
#endif

// #include <envmap_common_pars_fragment>
// #include <envmap_pars_fragment>
// #include <cube_uv_reflection_fragment>
#include <fog_pars_fragment>

// #include <bsdfs>
// COMPAT: pre-r151 doesn't have BRDF_Lambert in <common>
#if THREE_VRM_THREE_REVISION < 151
  vec3 BRDF_Lambert( const in vec3 diffuseColor ) {
    return RECIPROCAL_PI * diffuseColor;
  }
#endif

#include <lights_pars_begin>

#include <normal_pars_fragment>

// #include <lights_phong_pars_fragment>
varying vec3 vViewPosition;

struct MToonMaterial {
  vec3 diffuseColor;
  vec3 shadeColor;
  float shadingShift;
};

float linearstep( float a, float b, float t ) {
  return clamp( ( t - a ) / ( b - a ), 0.0, 1.0 );
}

/**
 * Convert NdotL into toon shading factor using shadingShift and shadingToony
 */
float getShading(
  const in float dotNL,
  const in float shadow,
  const in float shadingShift
) {
  float shading = dotNL;
  shading = shading + shadingShift;
  shading = linearstep( -1.0 + shadingToonyFactor, 1.0 - shadingToonyFactor, shading );
  shading *= shadow;
  return shading;
}

/**
 * Mix diffuseColor and shadeColor using shading factor and light color
 */
vec3 getDiffuse(
  const in MToonMaterial material,
  const in float shading,
  in vec3 lightColor
) {
  #ifdef DEBUG_LITSHADERATE
    return vec3( BRDF_Lambert( shading * lightColor ) );
  #endif

  vec3 col = lightColor * BRDF_Lambert( mix( material.shadeColor, material.diffuseColor, shading ) );

  // The "comment out if you want to PBR absolutely" line
  #ifdef V0_COMPAT_SHADE
    col = min( col, material.diffuseColor );
  #endif

  return col;
}

// COMPAT: pre-r156 uses a struct GeometricContext
#if THREE_VRM_THREE_REVISION >= 157
  void RE_Direct_MToon( const in IncidentLight directLight, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in MToonMaterial material, const in float shadow, inout ReflectedLight reflectedLight ) {
    float dotNL = clamp( dot( geometryNormal, directLight.direction ), -1.0, 1.0 );
    vec3 irradiance = directLight.color;

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;

    irradiance *= dotNL;

    float shading = getShading( dotNL, shadow, material.shadingShift );

    // toon shaded diffuse
    reflectedLight.directDiffuse += getDiffuse( material, shading, directLight.color );
  }

  void RE_IndirectDiffuse_MToon( const in vec3 irradiance, const in vec3 geometryPosition, const in vec3 geometryNormal, const in vec3 geometryViewDir, const in vec3 geometryClearcoatNormal, const in MToonMaterial material, inout ReflectedLight reflectedLight ) {
    // indirect diffuse will use diffuseColor, no shadeColor involved
    reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;
  }
#else
  void RE_Direct_MToon( const in IncidentLight directLight, const in GeometricContext geometry, const in MToonMaterial material, const in float shadow, inout ReflectedLight reflectedLight ) {
    float dotNL = clamp( dot( geometry.normal, directLight.direction ), -1.0, 1.0 );
    vec3 irradiance = directLight.color;

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;

    irradiance *= dotNL;

    float shading = getShading( dotNL, shadow, material.shadingShift );

    // toon shaded diffuse
    reflectedLight.directDiffuse += getDiffuse( material, shading, directLight.color );
  }

  void RE_IndirectDiffuse_MToon( const in vec3 irradiance, const in GeometricContext geometry, const in MToonMaterial material, inout ReflectedLight reflectedLight ) {
    // indirect diffuse will use diffuseColor, no shadeColor involved
    reflectedLight.indirectDiffuse += irradiance * BRDF_Lambert( material.diffuseColor );

    // directSpecular will be used for rim lighting, not an actual specular
    reflectedLight.directSpecular += irradiance;
  }
#endif

#define RE_Direct RE_Direct_MToon
#define RE_IndirectDiffuse RE_IndirectDiffuse_MToon
#define Material_LightProbeLOD( material ) (0)

#include <shadowmap_pars_fragment>
// #include <bumpmap_pars_fragment>

// #include <normalmap_pars_fragment>
#ifdef USE_NORMALMAP

  uniform sampler2D normalMap;
  uniform mat3 normalMapUvTransform;
  uniform vec2 normalScale;

#endif

// COMPAT: pre-r151
// USE_NORMALMAP_OBJECTSPACE used to be OBJECTSPACE_NORMALMAP in pre-r151
#if defined( USE_NORMALMAP_OBJECTSPACE ) || defined( OBJECTSPACE_NORMALMAP )

  uniform mat3 normalMatrix;

#endif

// COMPAT: pre-r151
// USE_NORMALMAP_TANGENTSPACE used to be TANGENTSPACE_NORMALMAP in pre-r151
#if ! defined ( USE_TANGENT ) && ( defined ( USE_NORMALMAP_TANGENTSPACE ) || defined ( TANGENTSPACE_NORMALMAP ) )

  // Per-Pixel Tangent Space Normal Mapping
  // http://hacksoflife.blogspot.ch/2009/11/per-pixel-tangent-space-normal-mapping.html

  // three-vrm specific change: it requires \`uv\` as an input in order to support uv scrolls

  // Temporary compat against shader change @ Three.js r126, r151
  #if THREE_VRM_THREE_REVISION >= 151

    mat3 getTangentFrame( vec3 eye_pos, vec3 surf_norm, vec2 uv ) {

      vec3 q0 = dFdx( eye_pos.xyz );
      vec3 q1 = dFdy( eye_pos.xyz );
      vec2 st0 = dFdx( uv.st );
      vec2 st1 = dFdy( uv.st );

      vec3 N = surf_norm;

      vec3 q1perp = cross( q1, N );
      vec3 q0perp = cross( N, q0 );

      vec3 T = q1perp * st0.x + q0perp * st1.x;
      vec3 B = q1perp * st0.y + q0perp * st1.y;

      float det = max( dot( T, T ), dot( B, B ) );
      float scale = ( det == 0.0 ) ? 0.0 : inversesqrt( det );

      return mat3( T * scale, B * scale, N );

    }

  #else

    vec3 perturbNormal2Arb( vec2 uv, vec3 eye_pos, vec3 surf_norm, vec3 mapN, float faceDirection ) {

      vec3 q0 = vec3( dFdx( eye_pos.x ), dFdx( eye_pos.y ), dFdx( eye_pos.z ) );
      vec3 q1 = vec3( dFdy( eye_pos.x ), dFdy( eye_pos.y ), dFdy( eye_pos.z ) );
      vec2 st0 = dFdx( uv.st );
      vec2 st1 = dFdy( uv.st );

      vec3 N = normalize( surf_norm );

      vec3 q1perp = cross( q1, N );
      vec3 q0perp = cross( N, q0 );

      vec3 T = q1perp * st0.x + q0perp * st1.x;
      vec3 B = q1perp * st0.y + q0perp * st1.y;

      // three-vrm specific change: Workaround for the issue that happens when delta of uv = 0.0
      // TODO: Is this still required? Or shall I make a PR about it?
      if ( length( T ) == 0.0 || length( B ) == 0.0 ) {
        return surf_norm;
      }

      float det = max( dot( T, T ), dot( B, B ) );
      float scale = ( det == 0.0 ) ? 0.0 : faceDirection * inversesqrt( det );

      return normalize( T * ( mapN.x * scale ) + B * ( mapN.y * scale ) + N * mapN.z );

    }

  #endif

#endif

// #include <specularmap_pars_fragment>
#include <logdepthbuf_pars_fragment>
#include <clipping_planes_pars_fragment>

// == post correction ==========================================================
void postCorrection() {
  #include <tonemapping_fragment>
  #include <colorspace_fragment>
  #include <fog_fragment>
  #include <premultiplied_alpha_fragment>
  #include <dithering_fragment>
}

// == main procedure ===========================================================
void main() {
  #include <clipping_planes_fragment>

  vec2 uv = vec2(0.5, 0.5);

  #if ( defined( MTOON_USE_UV ) && !defined( MTOON_UVS_VERTEX_ONLY ) )
    uv = vUv;

    float uvAnimMask = 1.0;
    #ifdef USE_UVANIMATIONMASKTEXTURE
      vec2 uvAnimationMaskTextureUv = ( uvAnimationMaskTextureUvTransform * vec3( uv, 1 ) ).xy;
      uvAnimMask = texture2D( uvAnimationMaskTexture, uvAnimationMaskTextureUv ).b;
    #endif

    float uvRotCos = cos( uvAnimationRotationPhase * uvAnimMask );
    float uvRotSin = sin( uvAnimationRotationPhase * uvAnimMask );
    uv = mat2( uvRotCos, -uvRotSin, uvRotSin, uvRotCos ) * ( uv - 0.5 ) + 0.5;
    uv = uv + vec2( uvAnimationScrollXOffset, uvAnimationScrollYOffset ) * uvAnimMask;
  #endif

  #ifdef DEBUG_UV
    gl_FragColor = vec4( 0.0, 0.0, 0.0, 1.0 );
    #if ( defined( MTOON_USE_UV ) && !defined( MTOON_UVS_VERTEX_ONLY ) )
      gl_FragColor = vec4( uv, 0.0, 1.0 );
    #endif
    return;
  #endif

  vec4 diffuseColor = vec4( litFactor, opacity );
  ReflectedLight reflectedLight = ReflectedLight( vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ), vec3( 0.0 ) );
  vec3 totalEmissiveRadiance = emissive * emissiveIntensity;

  #include <logdepthbuf_fragment>

  // #include <map_fragment>
  #ifdef USE_MAP
    vec2 mapUv = ( mapUvTransform * vec3( uv, 1 ) ).xy;
    vec4 sampledDiffuseColor = texture2D( map, mapUv );
    #ifdef DECODE_VIDEO_TEXTURE
      sampledDiffuseColor = vec4( mix( pow( sampledDiffuseColor.rgb * 0.9478672986 + vec3( 0.0521327014 ), vec3( 2.4 ) ), sampledDiffuseColor.rgb * 0.0773993808, vec3( lessThanEqual( sampledDiffuseColor.rgb, vec3( 0.04045 ) ) ) ), sampledDiffuseColor.w );
    #endif
    diffuseColor *= sampledDiffuseColor;
  #endif

  // #include <color_fragment>
  #if ( defined( USE_COLOR ) && !defined( IGNORE_VERTEX_COLOR ) )
    diffuseColor.rgb *= vColor;
  #endif

  // #include <alphamap_fragment>

  #include <alphatest_fragment>

  // #include <specularmap_fragment>

  // #include <normal_fragment_begin>
  float faceDirection = gl_FrontFacing ? 1.0 : -1.0;

  #ifdef FLAT_SHADED

    vec3 fdx = dFdx( vViewPosition );
    vec3 fdy = dFdy( vViewPosition );
    vec3 normal = normalize( cross( fdx, fdy ) );

  #else

    vec3 normal = normalize( vNormal );

    #ifdef DOUBLE_SIDED

      normal *= faceDirection;

    #endif

  #endif

  #ifdef USE_NORMALMAP

    vec2 normalMapUv = ( normalMapUvTransform * vec3( uv, 1 ) ).xy;

  #endif

  #ifdef USE_NORMALMAP_TANGENTSPACE

    #ifdef USE_TANGENT

      mat3 tbn = mat3( normalize( vTangent ), normalize( vBitangent ), normal );

    #else

      mat3 tbn = getTangentFrame( - vViewPosition, normal, normalMapUv );

    #endif

    #if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )

      tbn[0] *= faceDirection;
      tbn[1] *= faceDirection;

    #endif

  #endif

  #ifdef USE_CLEARCOAT_NORMALMAP

    #ifdef USE_TANGENT

      mat3 tbn2 = mat3( normalize( vTangent ), normalize( vBitangent ), normal );

    #else

      mat3 tbn2 = getTangentFrame( - vViewPosition, normal, vClearcoatNormalMapUv );

    #endif

    #if defined( DOUBLE_SIDED ) && ! defined( FLAT_SHADED )

      tbn2[0] *= faceDirection;
      tbn2[1] *= faceDirection;

    #endif

  #endif

  // non perturbed normal for clearcoat among others

  vec3 nonPerturbedNormal = normal;

  #ifdef OUTLINE
    normal *= -1.0;
  #endif

  // #include <normal_fragment_maps>

  // COMPAT: pre-r151
  // USE_NORMALMAP_OBJECTSPACE used to be OBJECTSPACE_NORMALMAP in pre-r151
  #if defined( USE_NORMALMAP_OBJECTSPACE ) || defined( OBJECTSPACE_NORMALMAP )

    normal = texture2D( normalMap, normalMapUv ).xyz * 2.0 - 1.0; // overrides both flatShading and attribute normals

    #ifdef FLIP_SIDED

      normal = - normal;

    #endif

    #ifdef DOUBLE_SIDED

      normal = normal * faceDirection;

    #endif

    normal = normalize( normalMatrix * normal );

  // COMPAT: pre-r151
  // USE_NORMALMAP_TANGENTSPACE used to be TANGENTSPACE_NORMALMAP in pre-r151
  #elif defined( USE_NORMALMAP_TANGENTSPACE ) || defined( TANGENTSPACE_NORMALMAP )

    vec3 mapN = texture2D( normalMap, normalMapUv ).xyz * 2.0 - 1.0;
    mapN.xy *= normalScale;

    // COMPAT: pre-r151
    #if THREE_VRM_THREE_REVISION >= 151 || defined( USE_TANGENT )

      normal = normalize( tbn * mapN );

    #else

      normal = perturbNormal2Arb( uv, -vViewPosition, normal, mapN, faceDirection );

    #endif

  #endif

  // #include <emissivemap_fragment>
  #ifdef USE_EMISSIVEMAP
    vec2 emissiveMapUv = ( emissiveMapUvTransform * vec3( uv, 1 ) ).xy;
    totalEmissiveRadiance *= texture2D( emissiveMap, emissiveMapUv ).rgb;
  #endif

  #ifdef DEBUG_NORMAL
    gl_FragColor = vec4( 0.5 + 0.5 * normal, 1.0 );
    return;
  #endif

  // -- MToon: lighting --------------------------------------------------------
  // accumulation
  // #include <lights_phong_fragment>
  MToonMaterial material;

  material.diffuseColor = diffuseColor.rgb;

  material.shadeColor = shadeColorFactor;
  #ifdef USE_SHADEMULTIPLYTEXTURE
    vec2 shadeMultiplyTextureUv = ( shadeMultiplyTextureUvTransform * vec3( uv, 1 ) ).xy;
    material.shadeColor *= texture2D( shadeMultiplyTexture, shadeMultiplyTextureUv ).rgb;
  #endif

  #if ( defined( USE_COLOR ) && !defined( IGNORE_VERTEX_COLOR ) )
    material.shadeColor.rgb *= vColor;
  #endif

  material.shadingShift = shadingShiftFactor;
  #ifdef USE_SHADINGSHIFTTEXTURE
    vec2 shadingShiftTextureUv = ( shadingShiftTextureUvTransform * vec3( uv, 1 ) ).xy;
    material.shadingShift += texture2D( shadingShiftTexture, shadingShiftTextureUv ).r * shadingShiftTextureScale;
  #endif

  // #include <lights_fragment_begin>

  // MToon Specific changes:
  // Since we want to take shadows into account of shading instead of irradiance,
  // we had to modify the codes that multiplies the results of shadowmap into color of direct lights.

  // COMPAT: pre-r156 uses a struct GeometricContext
  #if THREE_VRM_THREE_REVISION >= 157
    vec3 geometryPosition = - vViewPosition;
    vec3 geometryNormal = normal;
    vec3 geometryViewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );

    vec3 geometryClearcoatNormal;

    #ifdef USE_CLEARCOAT

      geometryClearcoatNormal = clearcoatNormal;

    #endif
  #else
    GeometricContext geometry;

    geometry.position = - vViewPosition;
    geometry.normal = normal;
    geometry.viewDir = ( isOrthographic ) ? vec3( 0, 0, 1 ) : normalize( vViewPosition );

    #ifdef USE_CLEARCOAT

      geometry.clearcoatNormal = clearcoatNormal;

    #endif
  #endif

  IncidentLight directLight;

  // since these variables will be used in unrolled loop, we have to define in prior
  float shadow;

  #if ( NUM_POINT_LIGHTS > 0 ) && defined( RE_Direct )

    PointLight pointLight;
    #if defined( USE_SHADOWMAP ) && NUM_POINT_LIGHT_SHADOWS > 0
    PointLightShadow pointLightShadow;
    #endif

    #pragma unroll_loop_start
    for ( int i = 0; i < NUM_POINT_LIGHTS; i ++ ) {

      pointLight = pointLights[ i ];

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        getPointLightInfo( pointLight, geometryPosition, directLight );
      #else
        getPointLightInfo( pointLight, geometry, directLight );
      #endif

      shadow = 1.0;
      #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_POINT_LIGHT_SHADOWS )
      pointLightShadow = pointLightShadows[ i ];
      // COMPAT: pre-r166
      // r166 introduced shadowIntensity
      #if THREE_VRM_THREE_REVISION >= 166
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowIntensity, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
      #else
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getPointShadow( pointShadowMap[ i ], pointLightShadow.shadowMapSize, pointLightShadow.shadowBias, pointLightShadow.shadowRadius, vPointShadowCoord[ i ], pointLightShadow.shadowCameraNear, pointLightShadow.shadowCameraFar ) : 1.0;
      #endif
      #endif

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, shadow, reflectedLight );
      #else
        RE_Direct( directLight, geometry, material, shadow, reflectedLight );
      #endif

    }
    #pragma unroll_loop_end

  #endif

  #if ( NUM_SPOT_LIGHTS > 0 ) && defined( RE_Direct )

    SpotLight spotLight;
    // COMPAT: pre-r144 uses NUM_SPOT_LIGHT_SHADOWS, r144+ uses NUM_SPOT_LIGHT_COORDS
    #if THREE_VRM_THREE_REVISION >= 144
      #if defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_COORDS > 0
      SpotLightShadow spotLightShadow;
      #endif
    #elif defined( USE_SHADOWMAP ) && NUM_SPOT_LIGHT_SHADOWS > 0
    SpotLightShadow spotLightShadow;
    #endif

    #pragma unroll_loop_start
    for ( int i = 0; i < NUM_SPOT_LIGHTS; i ++ ) {

      spotLight = spotLights[ i ];

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        getSpotLightInfo( spotLight, geometryPosition, directLight );
      #else
        getSpotLightInfo( spotLight, geometry, directLight );
      #endif

      shadow = 1.0;
      // COMPAT: pre-r144 uses NUM_SPOT_LIGHT_SHADOWS and vSpotShadowCoord, r144+ uses NUM_SPOT_LIGHT_COORDS and vSpotLightCoord
      // COMPAT: pre-r166 does not have shadowIntensity, r166+ has shadowIntensity
      #if THREE_VRM_THREE_REVISION >= 166
        #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_COORDS )
        spotLightShadow = spotLightShadows[ i ];
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowIntensity, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
        #endif
      #elif THREE_VRM_THREE_REVISION >= 144
        #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_COORDS )
        spotLightShadow = spotLightShadows[ i ];
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotLightCoord[ i ] ) : 1.0;
        #endif
      #elif defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_SPOT_LIGHT_SHADOWS )
      spotLightShadow = spotLightShadows[ i ];
      shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( spotShadowMap[ i ], spotLightShadow.shadowMapSize, spotLightShadow.shadowBias, spotLightShadow.shadowRadius, vSpotShadowCoord[ i ] ) : 1.0;
      #endif

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, shadow, reflectedLight );
      #else
        RE_Direct( directLight, geometry, material, shadow, reflectedLight );
      #endif

    }
    #pragma unroll_loop_end

  #endif

  #if ( NUM_DIR_LIGHTS > 0 ) && defined( RE_Direct )

    DirectionalLight directionalLight;
    #if defined( USE_SHADOWMAP ) && NUM_DIR_LIGHT_SHADOWS > 0
    DirectionalLightShadow directionalLightShadow;
    #endif

    #pragma unroll_loop_start
    for ( int i = 0; i < NUM_DIR_LIGHTS; i ++ ) {

      directionalLight = directionalLights[ i ];

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        getDirectionalLightInfo( directionalLight, directLight );
      #else
        getDirectionalLightInfo( directionalLight, geometry, directLight );
      #endif

      shadow = 1.0;
      #if defined( USE_SHADOWMAP ) && ( UNROLLED_LOOP_INDEX < NUM_DIR_LIGHT_SHADOWS )
      directionalLightShadow = directionalLightShadows[ i ];
      // COMPAT: pre-r166
      // r166 introduced shadowIntensity
      #if THREE_VRM_THREE_REVISION >= 166
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowIntensity, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
      #else
        shadow = all( bvec2( directLight.visible, receiveShadow ) ) ? getShadow( directionalShadowMap[ i ], directionalLightShadow.shadowMapSize, directionalLightShadow.shadowBias, directionalLightShadow.shadowRadius, vDirectionalShadowCoord[ i ] ) : 1.0;
      #endif
      #endif

      // COMPAT: pre-r156 uses a struct GeometricContext
      #if THREE_VRM_THREE_REVISION >= 157
        RE_Direct( directLight, geometryPosition, geometryNormal, geometryViewDir, geometryClearcoatNormal, material, shadow, reflectedLight );
      #else
        RE_Direct( directLight, geometry, material, shadow, reflectedLight );
      #endif

    }
    #pragma unroll_loop_end

  #endif

  // #if ( NUM_RECT_AREA_LIGHTS > 0 ) && defined( RE_Direct_RectArea )

  //   RectAreaLight rectAreaLight;

  //   #pragma unroll_loop_start
  //   for ( int i = 0; i < NUM_RECT_AREA_LIGHTS; i ++ ) {

  //     rectAreaLight = rectAreaLights[ i ];
  //     RE_Direct_RectArea( rectAreaLight, geometry, material, reflectedLight );

  //   }
  //   #pragma unroll_loop_end

  // #endif

  #if defined( RE_IndirectDiffuse )

    vec3 iblIrradiance = vec3( 0.0 );

    vec3 irradiance = getAmbientLightIrradiance( ambientLightColor );

    // COMPAT: pre-r156 uses a struct GeometricContext
    // COMPAT: pre-r156 doesn't have a define USE_LIGHT_PROBES
    #if THREE_VRM_THREE_REVISION >= 157
      #if defined( USE_LIGHT_PROBES )
        irradiance += getLightProbeIrradiance( lightProbe, geometryNormal );
      #endif
    #else
      irradiance += getLightProbeIrradiance( lightProbe, geometry.normal );
    #endif

    #if ( NUM_HEMI_LIGHTS > 0 )

      #pragma unroll_loop_start
      for ( int i = 0; i < NUM_HEMI_LIGHTS; i ++ ) {

        // COMPAT: pre-r156 uses a struct GeometricContext
        #if THREE_VRM_THREE_REVISION >= 157
          irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometryNormal );
        #else
          irradiance += getHemisphereLightIrradiance( hemisphereLights[ i ], geometry.normal );
        #endif

      }
      #pragma unroll_loop_end

    #endif

  #endif

  // #if defined( RE_IndirectSpecular )

  //   vec3 radiance = vec3( 0.0 );
  //   vec3 clearcoatRadiance = vec3( 0.0 );

  // #endif

  #include <lights_fragment_maps>
  #include <lights_fragment_end>

  // modulation
  #include <aomap_fragment>

  vec3 col = reflectedLight.directDiffuse + reflectedLight.indirectDiffuse;

  #ifdef DEBUG_LITSHADERATE
    gl_FragColor = vec4( col, diffuseColor.a );
    postCorrection();
    return;
  #endif

  // -- MToon: rim lighting -----------------------------------------
  vec3 viewDir = normalize( vViewPosition );

  #ifndef PHYSICALLY_CORRECT_LIGHTS
    reflectedLight.directSpecular /= PI;
  #endif
  vec3 rimMix = mix( vec3( 1.0 ), reflectedLight.directSpecular, rimLightingMixFactor );

  vec3 rim = parametricRimColorFactor * pow( saturate( 1.0 - dot( viewDir, normal ) + parametricRimLiftFactor ), parametricRimFresnelPowerFactor );

  #ifdef USE_MATCAPTEXTURE
    {
      vec3 x = normalize( vec3( viewDir.z, 0.0, -viewDir.x ) );
      vec3 y = cross( viewDir, x ); // guaranteed to be normalized
      vec2 sphereUv = 0.5 + 0.5 * vec2( dot( x, normal ), -dot( y, normal ) );
      sphereUv = ( matcapTextureUvTransform * vec3( sphereUv, 1 ) ).xy;
      vec3 matcap = texture2D( matcapTexture, sphereUv ).rgb;
      rim += matcapFactor * matcap;
    }
  #endif

  #ifdef USE_RIMMULTIPLYTEXTURE
    vec2 rimMultiplyTextureUv = ( rimMultiplyTextureUvTransform * vec3( uv, 1 ) ).xy;
    rim *= texture2D( rimMultiplyTexture, rimMultiplyTextureUv ).rgb;
  #endif

  col += rimMix * rim;

  // -- MToon: Emission --------------------------------------------------------
  col += totalEmissiveRadiance;

  // #include <envmap_fragment>

  // -- Almost done! -----------------------------------------------------------
  #if defined( OUTLINE )
    col = outlineColorFactor.rgb * mix( vec3( 1.0 ), col, outlineLightingMixFactor );
  #endif

  #ifdef OPAQUE
    diffuseColor.a = 1.0;
  #endif

  gl_FragColor = vec4( col, diffuseColor.a );
  postCorrection();
}
`,Mo={None:"none"},Sn={None:"none",ScreenCoordinates:"screenCoordinates"},xo={3e3:"",3001:"srgb"};function Qe(t){return parseInt(Ve,10)>=152?t.colorSpace:xo[t.encoding]}var yo=class extends cr{constructor(t={}){var e;super({vertexShader:go,fragmentShader:vo}),this.uvAnimationScrollXSpeedFactor=0,this.uvAnimationScrollYSpeedFactor=0,this.uvAnimationRotationSpeedFactor=0,this.fog=!0,this.normalMapType=pr,this._ignoreVertexColor=!0,this._v0CompatShade=!1,this._debugMode=Mo.None,this._outlineWidthMode=Sn.None,this._isOutline=!1,t.transparentWithZWrite&&(t.depthWrite=!0),delete t.transparentWithZWrite,t.fog=!0,t.lights=!0,t.clipping=!0,this.uniforms=fr.merge([me.common,me.normalmap,me.emissivemap,me.fog,me.lights,{litFactor:{value:new F(1,1,1)},mapUvTransform:{value:new X},colorAlpha:{value:1},normalMapUvTransform:{value:new X},shadeColorFactor:{value:new F(0,0,0)},shadeMultiplyTexture:{value:null},shadeMultiplyTextureUvTransform:{value:new X},shadingShiftFactor:{value:0},shadingShiftTexture:{value:null},shadingShiftTextureUvTransform:{value:new X},shadingShiftTextureScale:{value:1},shadingToonyFactor:{value:.9},giEqualizationFactor:{value:.9},matcapFactor:{value:new F(1,1,1)},matcapTexture:{value:null},matcapTextureUvTransform:{value:new X},parametricRimColorFactor:{value:new F(0,0,0)},rimMultiplyTexture:{value:null},rimMultiplyTextureUvTransform:{value:new X},rimLightingMixFactor:{value:1},parametricRimFresnelPowerFactor:{value:5},parametricRimLiftFactor:{value:0},emissive:{value:new F(0,0,0)},emissiveIntensity:{value:1},emissiveMapUvTransform:{value:new X},outlineWidthMultiplyTexture:{value:null},outlineWidthMultiplyTextureUvTransform:{value:new X},outlineWidthFactor:{value:0},outlineColorFactor:{value:new F(0,0,0)},outlineLightingMixFactor:{value:1},uvAnimationMaskTexture:{value:null},uvAnimationMaskTextureUvTransform:{value:new X},uvAnimationScrollXOffset:{value:0},uvAnimationScrollYOffset:{value:0},uvAnimationRotationPhase:{value:0}},(e=t.uniforms)!=null?e:{}]),this.setValues(t),this._uploadUniformsWorkaround(),this.customProgramCacheKey=()=>[...Object.entries(this._generateDefines()).map(([n,i])=>`${n}:${i}`),this.matcapTexture?`matcapTextureColorSpace:${Qe(this.matcapTexture)}`:"",this.shadeMultiplyTexture?`shadeMultiplyTextureColorSpace:${Qe(this.shadeMultiplyTexture)}`:"",this.rimMultiplyTexture?`rimMultiplyTextureColorSpace:${Qe(this.rimMultiplyTexture)}`:""].join(","),this.onBeforeCompile=n=>{const i=parseInt(Ve,10),r=Object.entries(Tn(Tn({},this._generateDefines()),this.defines)).filter(([o,s])=>!!s).map(([o,s])=>`#define ${o} ${s}`).join(`
`)+`
`;n.vertexShader=r+n.vertexShader,n.fragmentShader=r+n.fragmentShader,i<154&&(n.fragmentShader=n.fragmentShader.replace("#include <colorspace_fragment>","#include <encodings_fragment>"))}}get color(){return this.uniforms.litFactor.value}set color(t){this.uniforms.litFactor.value=t}get map(){return this.uniforms.map.value}set map(t){this.uniforms.map.value=t}get normalMap(){return this.uniforms.normalMap.value}set normalMap(t){this.uniforms.normalMap.value=t}get normalScale(){return this.uniforms.normalScale.value}set normalScale(t){this.uniforms.normalScale.value=t}get emissive(){return this.uniforms.emissive.value}set emissive(t){this.uniforms.emissive.value=t}get emissiveIntensity(){return this.uniforms.emissiveIntensity.value}set emissiveIntensity(t){this.uniforms.emissiveIntensity.value=t}get emissiveMap(){return this.uniforms.emissiveMap.value}set emissiveMap(t){this.uniforms.emissiveMap.value=t}get shadeColorFactor(){return this.uniforms.shadeColorFactor.value}set shadeColorFactor(t){this.uniforms.shadeColorFactor.value=t}get shadeMultiplyTexture(){return this.uniforms.shadeMultiplyTexture.value}set shadeMultiplyTexture(t){this.uniforms.shadeMultiplyTexture.value=t}get shadingShiftFactor(){return this.uniforms.shadingShiftFactor.value}set shadingShiftFactor(t){this.uniforms.shadingShiftFactor.value=t}get shadingShiftTexture(){return this.uniforms.shadingShiftTexture.value}set shadingShiftTexture(t){this.uniforms.shadingShiftTexture.value=t}get shadingShiftTextureScale(){return this.uniforms.shadingShiftTextureScale.value}set shadingShiftTextureScale(t){this.uniforms.shadingShiftTextureScale.value=t}get shadingToonyFactor(){return this.uniforms.shadingToonyFactor.value}set shadingToonyFactor(t){this.uniforms.shadingToonyFactor.value=t}get giEqualizationFactor(){return this.uniforms.giEqualizationFactor.value}set giEqualizationFactor(t){this.uniforms.giEqualizationFactor.value=t}get matcapFactor(){return this.uniforms.matcapFactor.value}set matcapFactor(t){this.uniforms.matcapFactor.value=t}get matcapTexture(){return this.uniforms.matcapTexture.value}set matcapTexture(t){this.uniforms.matcapTexture.value=t}get parametricRimColorFactor(){return this.uniforms.parametricRimColorFactor.value}set parametricRimColorFactor(t){this.uniforms.parametricRimColorFactor.value=t}get rimMultiplyTexture(){return this.uniforms.rimMultiplyTexture.value}set rimMultiplyTexture(t){this.uniforms.rimMultiplyTexture.value=t}get rimLightingMixFactor(){return this.uniforms.rimLightingMixFactor.value}set rimLightingMixFactor(t){this.uniforms.rimLightingMixFactor.value=t}get parametricRimFresnelPowerFactor(){return this.uniforms.parametricRimFresnelPowerFactor.value}set parametricRimFresnelPowerFactor(t){this.uniforms.parametricRimFresnelPowerFactor.value=t}get parametricRimLiftFactor(){return this.uniforms.parametricRimLiftFactor.value}set parametricRimLiftFactor(t){this.uniforms.parametricRimLiftFactor.value=t}get outlineWidthMultiplyTexture(){return this.uniforms.outlineWidthMultiplyTexture.value}set outlineWidthMultiplyTexture(t){this.uniforms.outlineWidthMultiplyTexture.value=t}get outlineWidthFactor(){return this.uniforms.outlineWidthFactor.value}set outlineWidthFactor(t){this.uniforms.outlineWidthFactor.value=t}get outlineColorFactor(){return this.uniforms.outlineColorFactor.value}set outlineColorFactor(t){this.uniforms.outlineColorFactor.value=t}get outlineLightingMixFactor(){return this.uniforms.outlineLightingMixFactor.value}set outlineLightingMixFactor(t){this.uniforms.outlineLightingMixFactor.value=t}get uvAnimationMaskTexture(){return this.uniforms.uvAnimationMaskTexture.value}set uvAnimationMaskTexture(t){this.uniforms.uvAnimationMaskTexture.value=t}get uvAnimationScrollXOffset(){return this.uniforms.uvAnimationScrollXOffset.value}set uvAnimationScrollXOffset(t){this.uniforms.uvAnimationScrollXOffset.value=t}get uvAnimationScrollYOffset(){return this.uniforms.uvAnimationScrollYOffset.value}set uvAnimationScrollYOffset(t){this.uniforms.uvAnimationScrollYOffset.value=t}get uvAnimationRotationPhase(){return this.uniforms.uvAnimationRotationPhase.value}set uvAnimationRotationPhase(t){this.uniforms.uvAnimationRotationPhase.value=t}get ignoreVertexColor(){return this._ignoreVertexColor}set ignoreVertexColor(t){this._ignoreVertexColor=t,this.needsUpdate=!0}get v0CompatShade(){return this._v0CompatShade}set v0CompatShade(t){this._v0CompatShade=t,this.needsUpdate=!0}get debugMode(){return this._debugMode}set debugMode(t){this._debugMode=t,this.needsUpdate=!0}get outlineWidthMode(){return this._outlineWidthMode}set outlineWidthMode(t){this._outlineWidthMode=t,this.needsUpdate=!0}get isOutline(){return this._isOutline}set isOutline(t){this._isOutline=t,this.needsUpdate=!0}get isMToonMaterial(){return!0}update(t){this._uploadUniformsWorkaround(),this._updateUVAnimation(t)}copy(t){return super.copy(t),this.map=t.map,this.normalMap=t.normalMap,this.emissiveMap=t.emissiveMap,this.shadeMultiplyTexture=t.shadeMultiplyTexture,this.shadingShiftTexture=t.shadingShiftTexture,this.matcapTexture=t.matcapTexture,this.rimMultiplyTexture=t.rimMultiplyTexture,this.outlineWidthMultiplyTexture=t.outlineWidthMultiplyTexture,this.uvAnimationMaskTexture=t.uvAnimationMaskTexture,this.normalMapType=t.normalMapType,this.uvAnimationScrollXSpeedFactor=t.uvAnimationScrollXSpeedFactor,this.uvAnimationScrollYSpeedFactor=t.uvAnimationScrollYSpeedFactor,this.uvAnimationRotationSpeedFactor=t.uvAnimationRotationSpeedFactor,this.ignoreVertexColor=t.ignoreVertexColor,this.v0CompatShade=t.v0CompatShade,this.debugMode=t.debugMode,this.outlineWidthMode=t.outlineWidthMode,this.isOutline=t.isOutline,this.needsUpdate=!0,this}_updateUVAnimation(t){this.uniforms.uvAnimationScrollXOffset.value+=t*this.uvAnimationScrollXSpeedFactor,this.uniforms.uvAnimationScrollYOffset.value+=t*this.uvAnimationScrollYSpeedFactor,this.uniforms.uvAnimationRotationPhase.value+=t*this.uvAnimationRotationSpeedFactor,this.uniforms.alphaTest.value=this.alphaTest,this.uniformsNeedUpdate=!0}_uploadUniformsWorkaround(){this.uniforms.opacity.value=this.opacity,this._updateTextureMatrix(this.uniforms.map,this.uniforms.mapUvTransform),this._updateTextureMatrix(this.uniforms.normalMap,this.uniforms.normalMapUvTransform),this._updateTextureMatrix(this.uniforms.emissiveMap,this.uniforms.emissiveMapUvTransform),this._updateTextureMatrix(this.uniforms.shadeMultiplyTexture,this.uniforms.shadeMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.shadingShiftTexture,this.uniforms.shadingShiftTextureUvTransform),this._updateTextureMatrix(this.uniforms.matcapTexture,this.uniforms.matcapTextureUvTransform),this._updateTextureMatrix(this.uniforms.rimMultiplyTexture,this.uniforms.rimMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.outlineWidthMultiplyTexture,this.uniforms.outlineWidthMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.uvAnimationMaskTexture,this.uniforms.uvAnimationMaskTextureUvTransform),this.uniformsNeedUpdate=!0}_generateDefines(){const t=parseInt(Ve,10),e=this.outlineWidthMultiplyTexture!==null,n=this.map!==null||this.normalMap!==null||this.emissiveMap!==null||this.shadeMultiplyTexture!==null||this.shadingShiftTexture!==null||this.rimMultiplyTexture!==null||this.uvAnimationMaskTexture!==null;return{THREE_VRM_THREE_REVISION:t,OUTLINE:this._isOutline,MTOON_USE_UV:e||n,MTOON_UVS_VERTEX_ONLY:e&&!n,V0_COMPAT_SHADE:this._v0CompatShade,USE_SHADEMULTIPLYTEXTURE:this.shadeMultiplyTexture!==null,USE_SHADINGSHIFTTEXTURE:this.shadingShiftTexture!==null,USE_MATCAPTEXTURE:this.matcapTexture!==null,USE_RIMMULTIPLYTEXTURE:this.rimMultiplyTexture!==null,USE_OUTLINEWIDTHMULTIPLYTEXTURE:this._isOutline&&this.outlineWidthMultiplyTexture!==null,USE_UVANIMATIONMASKTEXTURE:this.uvAnimationMaskTexture!==null,IGNORE_VERTEX_COLOR:this._ignoreVertexColor===!0,DEBUG_NORMAL:this._debugMode==="normal",DEBUG_LITSHADERATE:this._debugMode==="litShadeRate",DEBUG_UV:this._debugMode==="uv",OUTLINE_WIDTH_SCREEN:this._isOutline&&this._outlineWidthMode===Sn.ScreenCoordinates}}_updateTextureMatrix(t,e){t.value&&(t.value.matrixAutoUpdate&&t.value.updateMatrix(),e.value.copy(t.value.matrix))}},wo=new Set(["1.0","1.0-beta"]),mi=class Ne{get name(){return Ne.EXTENSION_NAME}constructor(e,n={}){var i,r,o,s;this.parser=e,this.materialType=(i=n.materialType)!=null?i:yo,this.renderOrderOffset=(r=n.renderOrderOffset)!=null?r:0,this.v0CompatShade=(o=n.v0CompatShade)!=null?o:!1,this.debugMode=(s=n.debugMode)!=null?s:"none",this._mToonMaterialSet=new Set}beforeRoot(){return oe(this,null,function*(){this._removeUnlitExtensionIfMToonExists()})}afterRoot(e){return oe(this,null,function*(){e.userData.vrmMToonMaterials=Array.from(this._mToonMaterialSet)})}getMaterialType(e){return this._getMToonExtension(e)?this.materialType:null}extendMaterialParams(e,n){const i=this._getMToonExtension(e);return i?this._extendMaterialParams(i,n):null}loadMesh(e){return oe(this,null,function*(){var n;const i=this.parser,o=(n=i.json.meshes)==null?void 0:n[e];if(o==null)throw new Error(`MToonMaterialLoaderPlugin: Attempt to use meshes[${e}] of glTF but the mesh doesn't exist`);const s=o.primitives,l=yield i.loadMesh(e);if(s.length===1){const a=l,u=s[0].material;u!=null&&this._setupPrimitive(a,u)}else{const a=l;for(let u=0;u<s.length;u++){const h=a.children[u],d=s[u].material;d!=null&&this._setupPrimitive(h,d)}}return l})}_removeUnlitExtensionIfMToonExists(){const i=this.parser.json.materials;i==null||i.map((r,o)=>{var s;this._getMToonExtension(o)&&((s=r.extensions)!=null&&s.KHR_materials_unlit)&&delete r.extensions.KHR_materials_unlit})}_getMToonExtension(e){var n,i;const s=(n=this.parser.json.materials)==null?void 0:n[e];if(s==null){console.warn(`MToonMaterialLoaderPlugin: Attempt to use materials[${e}] of glTF but the material doesn't exist`);return}const l=(i=s.extensions)==null?void 0:i[Ne.EXTENSION_NAME];if(l==null)return;const a=l.specVersion;if(!wo.has(a)){console.warn(`MToonMaterialLoaderPlugin: Unknown ${Ne.EXTENSION_NAME} specVersion "${a}"`);return}return l}_extendMaterialParams(e,n){return oe(this,null,function*(){var i;delete n.metalness,delete n.roughness;const r=new _o(this.parser,n);r.assignPrimitive("transparentWithZWrite",e.transparentWithZWrite),r.assignColor("shadeColorFactor",e.shadeColorFactor),r.assignTexture("shadeMultiplyTexture",e.shadeMultiplyTexture,!0),r.assignPrimitive("shadingShiftFactor",e.shadingShiftFactor),r.assignTexture("shadingShiftTexture",e.shadingShiftTexture,!0),r.assignPrimitive("shadingShiftTextureScale",(i=e.shadingShiftTexture)==null?void 0:i.scale),r.assignPrimitive("shadingToonyFactor",e.shadingToonyFactor),r.assignPrimitive("giEqualizationFactor",e.giEqualizationFactor),r.assignColor("matcapFactor",e.matcapFactor),r.assignTexture("matcapTexture",e.matcapTexture,!0),r.assignColor("parametricRimColorFactor",e.parametricRimColorFactor),r.assignTexture("rimMultiplyTexture",e.rimMultiplyTexture,!0),r.assignPrimitive("rimLightingMixFactor",e.rimLightingMixFactor),r.assignPrimitive("parametricRimFresnelPowerFactor",e.parametricRimFresnelPowerFactor),r.assignPrimitive("parametricRimLiftFactor",e.parametricRimLiftFactor),r.assignPrimitive("outlineWidthMode",e.outlineWidthMode),r.assignPrimitive("outlineWidthFactor",e.outlineWidthFactor),r.assignTexture("outlineWidthMultiplyTexture",e.outlineWidthMultiplyTexture,!1),r.assignColor("outlineColorFactor",e.outlineColorFactor),r.assignPrimitive("outlineLightingMixFactor",e.outlineLightingMixFactor),r.assignTexture("uvAnimationMaskTexture",e.uvAnimationMaskTexture,!1),r.assignPrimitive("uvAnimationScrollXSpeedFactor",e.uvAnimationScrollXSpeedFactor),r.assignPrimitive("uvAnimationScrollYSpeedFactor",e.uvAnimationScrollYSpeedFactor),r.assignPrimitive("uvAnimationRotationSpeedFactor",e.uvAnimationRotationSpeedFactor),r.assignPrimitive("v0CompatShade",this.v0CompatShade),r.assignPrimitive("debugMode",this.debugMode),yield r.pending})}_setupPrimitive(e,n){const i=this._getMToonExtension(n);if(i){const r=this._parseRenderOrder(i);e.renderOrder=r+this.renderOrderOffset,this._generateOutline(e),this._addToMaterialSet(e);return}}_shouldGenerateOutline(e){return typeof e.outlineWidthMode=="string"&&e.outlineWidthMode!=="none"&&typeof e.outlineWidthFactor=="number"&&e.outlineWidthFactor>0}_generateOutline(e){const n=e.material;if(!(n instanceof ur)||!this._shouldGenerateOutline(n))return;e.material=[n];const i=n.clone();i.name+=" (Outline)",i.isOutline=!0,i.side=dr,e.material.push(i);const r=e.geometry,o=r.index?r.index.count:r.attributes.position.count/3;r.addGroup(0,o,0),r.addGroup(0,o,1)}_addToMaterialSet(e){const n=e.material,i=new Set;Array.isArray(n)?n.forEach(r=>i.add(r)):i.add(n);for(const r of i)this._mToonMaterialSet.add(r)}_parseRenderOrder(e){var n;return(e.transparentWithZWrite?0:19)+((n=e.renderQueueOffsetNumber)!=null?n:0)}};mi.EXTENSION_NAME="VRMC_materials_mtoon";var Ro=mi,To=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),_i=class ft{get name(){return ft.EXTENSION_NAME}constructor(e){this.parser=e}extendMaterialParams(e,n){return To(this,null,function*(){const i=this._getHDREmissiveMultiplierExtension(e);if(i==null)return;console.warn("VRMMaterialsHDREmissiveMultiplierLoaderPlugin: `VRMC_materials_hdr_emissiveMultiplier` is archived. Use `KHR_materials_emissive_strength` instead.");const r=i.emissiveMultiplier;n.emissiveIntensity=r})}_getHDREmissiveMultiplierExtension(e){var n,i;const s=(n=this.parser.json.materials)==null?void 0:n[e];if(s==null){console.warn(`VRMMaterialsHDREmissiveMultiplierLoaderPlugin: Attempt to use materials[${e}] of glTF but the material doesn't exist`);return}const l=(i=s.extensions)==null?void 0:i[ft.EXTENSION_NAME];if(l!=null)return l}};_i.EXTENSION_NAME="VRMC_materials_hdr_emissiveMultiplier";var So=_i,Ao=Object.defineProperty,Eo=Object.defineProperties,Po=Object.getOwnPropertyDescriptors,An=Object.getOwnPropertySymbols,Lo=Object.prototype.hasOwnProperty,bo=Object.prototype.propertyIsEnumerable,En=(t,e,n)=>e in t?Ao(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n,j=(t,e)=>{for(var n in e||(e={}))Lo.call(e,n)&&En(t,n,e[n]);if(An)for(var n of An(e))bo.call(e,n)&&En(t,n,e[n]);return t},Pn=(t,e)=>Eo(t,Po(e)),Io=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())});function ae(t){return Math.pow(t,2.2)}var Co=class{get name(){return"VRMMaterialsV0CompatPlugin"}constructor(t){var e;this.parser=t,this._renderQueueMapTransparent=new Map,this._renderQueueMapTransparentZWrite=new Map;const n=this.parser.json;n.extensionsUsed=(e=n.extensionsUsed)!=null?e:[],n.extensionsUsed.indexOf("KHR_texture_transform")===-1&&n.extensionsUsed.push("KHR_texture_transform")}beforeRoot(){return Io(this,null,function*(){var t;const e=this.parser.json,n=(t=e.extensions)==null?void 0:t.VRM,i=n==null?void 0:n.materialProperties;i&&(this._populateRenderQueueMap(i),i.forEach((r,o)=>{var s,l;const a=(s=e.materials)==null?void 0:s[o];if(a==null){console.warn(`VRMMaterialsV0CompatPlugin: Attempt to use materials[${o}] of glTF but the material doesn't exist`);return}if(r.shader==="VRM/MToon"){const u=this._parseV0MToonProperties(r,a);e.materials[o]=u}else if((l=r.shader)!=null&&l.startsWith("VRM/Unlit")){const u=this._parseV0UnlitProperties(r,a);e.materials[o]=u}else r.shader==="VRM_USE_GLTFSHADER"||console.warn(`VRMMaterialsV0CompatPlugin: Unknown shader: ${r.shader}`)}))})}_parseV0MToonProperties(t,e){var n,i,r,o,s,l,a,u,h,d,c,p,f,m,_,v,M,R,y,x,w,S,A,C,P,L,O,H,W,Q,k,b,V,$,N,Te,Z,ee,fe,yt,wt,Rt,Tt,St,At,Et,Pt,Lt,bt,It,Ct,Ot,Ut,Nt,Vt;const Dt=(i=(n=t.keywordMap)==null?void 0:n._ALPHABLEND_ON)!=null?i:!1,Ei=((r=t.floatProperties)==null?void 0:r._ZWrite)===1&&Dt,Pi=this._v0ParseRenderQueue(t),kt=(s=(o=t.keywordMap)==null?void 0:o._ALPHATEST_ON)!=null?s:!1,Li=Dt?"BLEND":kt?"MASK":"OPAQUE",bi=kt?(a=(l=t.floatProperties)==null?void 0:l._Cutoff)!=null?a:.5:void 0,Ii=((h=(u=t.floatProperties)==null?void 0:u._CullMode)!=null?h:2)===0,te=this._portTextureTransform(t),Ci=((c=(d=t.vectorProperties)==null?void 0:d._Color)!=null?c:[1,1,1,1]).map((qt,nr)=>nr===3?qt:ae(qt)),Bt=(p=t.textureProperties)==null?void 0:p._MainTex,Oi=Bt!=null?{index:Bt,extensions:j({},te)}:void 0,Ui=(m=(f=t.floatProperties)==null?void 0:f._BumpScale)!=null?m:1,Ft=(_=t.textureProperties)==null?void 0:_._BumpMap,Ni=Ft!=null?{index:Ft,scale:Ui,extensions:j({},te)}:void 0,Vi=((M=(v=t.vectorProperties)==null?void 0:v._EmissionColor)!=null?M:[0,0,0,1]).map(ae),Ht=(R=t.textureProperties)==null?void 0:R._EmissionMap,Di=Ht!=null?{index:Ht,extensions:j({},te)}:void 0,ki=((x=(y=t.vectorProperties)==null?void 0:y._ShadeColor)!=null?x:[.97,.81,.86,1]).map(ae),Wt=(w=t.textureProperties)==null?void 0:w._ShadeTexture,Bi=Wt!=null?{index:Wt,extensions:j({},te)}:void 0;let Se=(A=(S=t.floatProperties)==null?void 0:S._ShadeShift)!=null?A:0,Ae=(P=(C=t.floatProperties)==null?void 0:C._ShadeToony)!=null?P:.9;Ae=I.lerp(Ae,1,.5+.5*Se),Se=-Se-(1-Ae);const zt=(O=(L=t.floatProperties)==null?void 0:L._IndirectLightIntensity)!=null?O:.1,Fi=zt?1-zt:void 0,ze=(H=t.textureProperties)==null?void 0:H._SphereAdd,Hi=ze!=null?[1,1,1]:void 0,Wi=ze!=null?{index:ze}:void 0,zi=(Q=(W=t.floatProperties)==null?void 0:W._RimLightingMix)!=null?Q:0,jt=(k=t.textureProperties)==null?void 0:k._RimTexture,ji=jt!=null?{index:jt,extensions:j({},te)}:void 0,Gi=((V=(b=t.vectorProperties)==null?void 0:b._RimColor)!=null?V:[0,0,0,1]).map(ae),Xi=(N=($=t.floatProperties)==null?void 0:$._RimFresnelPower)!=null?N:1,qi=(Z=(Te=t.floatProperties)==null?void 0:Te._RimLift)!=null?Z:0,Yi=["none","worldCoordinates","screenCoordinates"][(fe=(ee=t.floatProperties)==null?void 0:ee._OutlineWidthMode)!=null?fe:0];let je=(wt=(yt=t.floatProperties)==null?void 0:yt._OutlineWidth)!=null?wt:0;je=.01*je;const Gt=(Rt=t.textureProperties)==null?void 0:Rt._OutlineWidthTexture,Qi=Gt!=null?{index:Gt,extensions:j({},te)}:void 0,$i=((St=(Tt=t.vectorProperties)==null?void 0:Tt._OutlineColor)!=null?St:[0,0,0]).map(ae),Zi=((Et=(At=t.floatProperties)==null?void 0:At._OutlineColorMode)!=null?Et:0)===1?(Lt=(Pt=t.floatProperties)==null?void 0:Pt._OutlineLightingMix)!=null?Lt:1:0,Xt=(bt=t.textureProperties)==null?void 0:bt._UvAnimMaskTexture,Ji=Xt!=null?{index:Xt,extensions:j({},te)}:void 0,Ki=(Ct=(It=t.floatProperties)==null?void 0:It._UvAnimScrollX)!=null?Ct:0;let Ee=(Ut=(Ot=t.floatProperties)==null?void 0:Ot._UvAnimScrollY)!=null?Ut:0;Ee!=null&&(Ee=-Ee);const er=(Vt=(Nt=t.floatProperties)==null?void 0:Nt._UvAnimRotation)!=null?Vt:0,tr={specVersion:"1.0",transparentWithZWrite:Ei,renderQueueOffsetNumber:Pi,shadeColorFactor:ki,shadeMultiplyTexture:Bi,shadingShiftFactor:Se,shadingToonyFactor:Ae,giEqualizationFactor:Fi,matcapFactor:Hi,matcapTexture:Wi,rimLightingMixFactor:zi,rimMultiplyTexture:ji,parametricRimColorFactor:Gi,parametricRimFresnelPowerFactor:Xi,parametricRimLiftFactor:qi,outlineWidthMode:Yi,outlineWidthFactor:je,outlineWidthMultiplyTexture:Qi,outlineColorFactor:$i,outlineLightingMixFactor:Zi,uvAnimationMaskTexture:Ji,uvAnimationScrollXSpeedFactor:Ki,uvAnimationScrollYSpeedFactor:Ee,uvAnimationRotationSpeedFactor:er};return Pn(j({},e),{pbrMetallicRoughness:{baseColorFactor:Ci,baseColorTexture:Oi},normalTexture:Ni,emissiveTexture:Di,emissiveFactor:Vi,alphaMode:Li,alphaCutoff:bi,doubleSided:Ii,extensions:{VRMC_materials_mtoon:tr}})}_parseV0UnlitProperties(t,e){var n,i,r,o,s;const l=t.shader==="VRM/UnlitTransparentZWrite",a=t.shader==="VRM/UnlitTransparent"||l,u=this._v0ParseRenderQueue(t),h=t.shader==="VRM/UnlitCutout",d=a?"BLEND":h?"MASK":"OPAQUE",c=h?(i=(n=t.floatProperties)==null?void 0:n._Cutoff)!=null?i:.5:void 0,p=this._portTextureTransform(t),f=((o=(r=t.vectorProperties)==null?void 0:r._Color)!=null?o:[1,1,1,1]).map(ae),m=(s=t.textureProperties)==null?void 0:s._MainTex,_=m!=null?{index:m,extensions:j({},p)}:void 0,v={specVersion:"1.0",transparentWithZWrite:l,renderQueueOffsetNumber:u,shadeColorFactor:f,shadeMultiplyTexture:_};return Pn(j({},e),{pbrMetallicRoughness:{baseColorFactor:f,baseColorTexture:_},alphaMode:d,alphaCutoff:c,extensions:{VRMC_materials_mtoon:v}})}_portTextureTransform(t){var e,n,i,r,o;const s=(e=t.vectorProperties)==null?void 0:e._MainTex;if(s==null)return{};const l=[(n=s==null?void 0:s[0])!=null?n:0,(i=s==null?void 0:s[1])!=null?i:0],a=[(r=s==null?void 0:s[2])!=null?r:1,(o=s==null?void 0:s[3])!=null?o:1];return l[1]=1-a[1]-l[1],{KHR_texture_transform:{offset:l,scale:a}}}_v0ParseRenderQueue(t){var e,n;const i=t.shader==="VRM/UnlitTransparentZWrite",r=((e=t.keywordMap)==null?void 0:e._ALPHABLEND_ON)!=null||t.shader==="VRM/UnlitTransparent"||i,o=((n=t.floatProperties)==null?void 0:n._ZWrite)===1||i;let s=0;if(r){const l=t.renderQueue;l!=null&&(o?s=this._renderQueueMapTransparentZWrite.get(l):s=this._renderQueueMapTransparent.get(l))}return s}_populateRenderQueueMap(t){const e=new Set,n=new Set;t.forEach(i=>{var r,o;const s=i.shader==="VRM/UnlitTransparentZWrite",l=((r=i.keywordMap)==null?void 0:r._ALPHABLEND_ON)!=null||i.shader==="VRM/UnlitTransparent"||s,a=((o=i.floatProperties)==null?void 0:o._ZWrite)===1||s;if(l){const u=i.renderQueue;u!=null&&(a?n.add(u):e.add(u))}}),e.size>10&&console.warn(`VRMMaterialsV0CompatPlugin: This VRM uses ${e.size} render queues for Transparent materials while VRM 1.0 only supports up to 10 render queues. The model might not be rendered correctly.`),n.size>10&&console.warn(`VRMMaterialsV0CompatPlugin: This VRM uses ${n.size} render queues for TransparentZWrite materials while VRM 1.0 only supports up to 10 render queues. The model might not be rendered correctly.`),Array.from(e).sort().forEach((i,r)=>{const o=Math.min(Math.max(r-e.size+1,-9),0);this._renderQueueMapTransparent.set(i,o)}),Array.from(n).sort().forEach((i,r)=>{const o=Math.min(Math.max(r,0),9);this._renderQueueMapTransparentZWrite.set(i,o)})}},Ln=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),K=new g,$e=class extends pe{constructor(t){super(),this._attrPosition=new D(new Float32Array([0,0,0,0,0,0]),3),this._attrPosition.setUsage(mr);const e=new J;e.setAttribute("position",this._attrPosition);const n=new We({color:16711935,depthTest:!1,depthWrite:!1});this._line=new _r(e,n),this.add(this._line),this.constraint=t}updateMatrixWorld(t){K.setFromMatrixPosition(this.constraint.destination.matrixWorld),this._attrPosition.setXYZ(0,K.x,K.y,K.z),this.constraint.source&&K.setFromMatrixPosition(this.constraint.source.matrixWorld),this._attrPosition.setXYZ(1,K.x,K.y,K.z),this._attrPosition.needsUpdate=!0,super.updateMatrixWorld(t)}};function bn(t,e){return e.set(t.elements[12],t.elements[13],t.elements[14])}var Oo=new g,Uo=new g;function No(t,e){return t.decompose(Oo,e,Uo),e}function ke(t){return t.invert?t.invert():t.inverse(),t}var Mt=class{constructor(t,e){this.destination=t,this.source=e,this.weight=1}},Vo=new g,Do=new g,ko=new g,Bo=new T,Fo=new T,Ho=new T,Wo=class extends Mt{get aimAxis(){return this._aimAxis}set aimAxis(t){this._aimAxis=t,this._v3AimAxis.set(t==="PositiveX"?1:t==="NegativeX"?-1:0,t==="PositiveY"?1:t==="NegativeY"?-1:0,t==="PositiveZ"?1:t==="NegativeZ"?-1:0)}get dependencies(){const t=new Set([this.source]);return this.destination.parent&&t.add(this.destination.parent),t}constructor(t,e){super(t,e),this._aimAxis="PositiveX",this._v3AimAxis=new g(1,0,0),this._dstRestQuat=new T}setInitState(){this._dstRestQuat.copy(this.destination.quaternion)}update(){this.destination.updateWorldMatrix(!0,!1),this.source.updateWorldMatrix(!0,!1);const t=Bo.identity(),e=Fo.identity();this.destination.parent&&(No(this.destination.parent.matrixWorld,t),ke(e.copy(t)));const n=Vo.copy(this._v3AimAxis).applyQuaternion(this._dstRestQuat).applyQuaternion(t),i=bn(this.source.matrixWorld,Do).sub(bn(this.destination.matrixWorld,ko)).normalize(),r=Ho.setFromUnitVectors(n,i).premultiply(e).multiply(t).multiply(this._dstRestQuat);this.destination.quaternion.copy(this._dstRestQuat).slerp(r,this.weight)}};function zo(t,e){const n=[t];let i=t.parent;for(;i!==null;)n.unshift(i),i=i.parent;n.forEach(r=>{e(r)})}var jo=class{constructor(){this._constraints=new Set,this._objectConstraintsMap=new Map}get constraints(){return this._constraints}addConstraint(t){this._constraints.add(t);let e=this._objectConstraintsMap.get(t.destination);e==null&&(e=new Set,this._objectConstraintsMap.set(t.destination,e)),e.add(t)}deleteConstraint(t){this._constraints.delete(t),this._objectConstraintsMap.get(t.destination).delete(t)}setInitState(){const t=new Set,e=new Set;for(const n of this._constraints)this._processConstraint(n,t,e,i=>i.setInitState())}update(){const t=new Set,e=new Set;for(const n of this._constraints)this._processConstraint(n,t,e,i=>i.update())}_processConstraint(t,e,n,i){if(n.has(t))return;if(e.has(t))throw new Error("VRMNodeConstraintManager: Circular dependency detected while updating constraints");e.add(t);const r=t.dependencies;for(const o of r)zo(o,s=>{const l=this._objectConstraintsMap.get(s);if(l)for(const a of l)this._processConstraint(a,e,n,i)});i(t),n.add(t)}},Go=new T,Xo=new T,qo=class extends Mt{get dependencies(){return new Set([this.source])}constructor(t,e){super(t,e),this._dstRestQuat=new T,this._invSrcRestQuat=new T}setInitState(){this._dstRestQuat.copy(this.destination.quaternion),ke(this._invSrcRestQuat.copy(this.source.quaternion))}update(){const t=Go.copy(this._invSrcRestQuat).multiply(this.source.quaternion),e=Xo.copy(this._dstRestQuat).multiply(t);this.destination.quaternion.copy(this._dstRestQuat).slerp(e,this.weight)}},Yo=new g,Qo=new T,$o=new T,Zo=class extends Mt{get rollAxis(){return this._rollAxis}set rollAxis(t){this._rollAxis=t,this._v3RollAxis.set(t==="X"?1:0,t==="Y"?1:0,t==="Z"?1:0)}get dependencies(){return new Set([this.source])}constructor(t,e){super(t,e),this._rollAxis="X",this._v3RollAxis=new g(1,0,0),this._dstRestQuat=new T,this._invDstRestQuat=new T,this._invSrcRestQuatMulDstRestQuat=new T}setInitState(){this._dstRestQuat.copy(this.destination.quaternion),ke(this._invDstRestQuat.copy(this._dstRestQuat)),ke(this._invSrcRestQuatMulDstRestQuat.copy(this.source.quaternion)).multiply(this._dstRestQuat)}update(){const t=Qo.copy(this._invDstRestQuat).multiply(this.source.quaternion).multiply(this._invSrcRestQuatMulDstRestQuat),e=Yo.copy(this._v3RollAxis).applyQuaternion(t),i=$o.setFromUnitVectors(e,this._v3RollAxis).premultiply(this._dstRestQuat).multiply(t);this.destination.quaternion.copy(this._dstRestQuat).slerp(i,this.weight)}},Jo=new Set(["1.0","1.0-beta"]),gi=class Re{get name(){return Re.EXTENSION_NAME}constructor(e,n){this.parser=e,this.helperRoot=n==null?void 0:n.helperRoot}afterRoot(e){return Ln(this,null,function*(){e.userData.vrmNodeConstraintManager=yield this._import(e)})}_import(e){return Ln(this,null,function*(){var n;const i=this.parser.json;if(!(((n=i.extensionsUsed)==null?void 0:n.indexOf(Re.EXTENSION_NAME))!==-1))return null;const o=new jo,s=yield this.parser.getDependencies("node");return s.forEach((l,a)=>{var u;const h=i.nodes[a],d=(u=h==null?void 0:h.extensions)==null?void 0:u[Re.EXTENSION_NAME];if(d==null)return;const c=d.specVersion;if(!Jo.has(c)){console.warn(`VRMNodeConstraintLoaderPlugin: Unknown ${Re.EXTENSION_NAME} specVersion "${c}"`);return}const p=d.constraint;if(p.roll!=null){const f=this._importRollConstraint(l,s,p.roll);o.addConstraint(f)}else if(p.aim!=null){const f=this._importAimConstraint(l,s,p.aim);o.addConstraint(f)}else if(p.rotation!=null){const f=this._importRotationConstraint(l,s,p.rotation);o.addConstraint(f)}}),e.scene.updateMatrixWorld(),o.setInitState(),o})}_importRollConstraint(e,n,i){const{source:r,rollAxis:o,weight:s}=i,l=n[r],a=new Zo(e,l);if(o!=null&&(a.rollAxis=o),s!=null&&(a.weight=s),this.helperRoot){const u=new $e(a);this.helperRoot.add(u)}return a}_importAimConstraint(e,n,i){const{source:r,aimAxis:o,weight:s}=i,l=n[r],a=new Wo(e,l);if(o!=null&&(a.aimAxis=o),s!=null&&(a.weight=s),this.helperRoot){const u=new $e(a);this.helperRoot.add(u)}return a}_importRotationConstraint(e,n,i){const{source:r,weight:o}=i,s=n[r],l=new qo(e,s);if(o!=null&&(l.weight=o),this.helperRoot){const a=new $e(l);this.helperRoot.add(a)}return l}};gi.EXTENSION_NAME="VRMC_node_constraint";var Ko=gi,Ce=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),xt=class{},Ze=new g,re=new g,vi=class extends xt{get type(){return"capsule"}constructor(t){var e,n,i,r;super(),this.offset=(e=t==null?void 0:t.offset)!=null?e:new g(0,0,0),this.tail=(n=t==null?void 0:t.tail)!=null?n:new g(0,0,0),this.radius=(i=t==null?void 0:t.radius)!=null?i:0,this.inside=(r=t==null?void 0:t.inside)!=null?r:!1}calculateCollision(t,e,n,i){Ze.setFromMatrixPosition(t),re.subVectors(this.tail,this.offset).applyMatrix4(t),re.sub(Ze);const r=re.lengthSq();i.copy(e).sub(Ze);const o=re.dot(i);o<=0||(r<=o||re.multiplyScalar(o/r),i.sub(re));const s=i.length(),l=this.inside?this.radius-n-s:s-n-this.radius;return l<0&&(i.multiplyScalar(1/s),this.inside&&i.negate()),l}},Je=new g,In=new X,Mi=class extends xt{get type(){return"plane"}constructor(t){var e,n;super(),this.offset=(e=t==null?void 0:t.offset)!=null?e:new g(0,0,0),this.normal=(n=t==null?void 0:t.normal)!=null?n:new g(0,0,1)}calculateCollision(t,e,n,i){i.setFromMatrixPosition(t),i.negate().add(e),In.getNormalMatrix(t),Je.copy(this.normal).applyNormalMatrix(In).normalize();const r=i.dot(Je)-n;return i.copy(Je),r}},es=new g,xi=class extends xt{get type(){return"sphere"}constructor(t){var e,n,i;super(),this.offset=(e=t==null?void 0:t.offset)!=null?e:new g(0,0,0),this.radius=(n=t==null?void 0:t.radius)!=null?n:0,this.inside=(i=t==null?void 0:t.inside)!=null?i:!1}calculateCollision(t,e,n,i){i.subVectors(e,es.setFromMatrixPosition(t));const r=i.length(),o=this.inside?this.radius-n-r:r-n-this.radius;return o<0&&(i.multiplyScalar(1/r),this.inside&&i.negate()),o}},G=new g,ts=class extends J{constructor(t){super(),this.worldScale=1,this._currentRadius=0,this._currentOffset=new g,this._currentTail=new g,this._shape=t,this._attrPos=new D(new Float32Array(396),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(264),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;const e=this._shape.radius/this.worldScale;this._currentRadius!==e&&(this._currentRadius=e,t=!0),this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),t=!0);const n=G.copy(this._shape.tail).divideScalar(this.worldScale);this._currentTail.distanceToSquared(n)>1e-10&&(this._currentTail.copy(n),t=!0),t&&this._buildPosition()}_buildPosition(){G.copy(this._currentTail).sub(this._currentOffset);const t=G.length()/this._currentRadius;for(let i=0;i<=16;i++){const r=i/16*Math.PI;this._attrPos.setXYZ(i,-Math.sin(r),-Math.cos(r),0),this._attrPos.setXYZ(17+i,t+Math.sin(r),Math.cos(r),0),this._attrPos.setXYZ(34+i,-Math.sin(r),0,-Math.cos(r)),this._attrPos.setXYZ(51+i,t+Math.sin(r),0,Math.cos(r))}for(let i=0;i<32;i++){const r=i/16*Math.PI;this._attrPos.setXYZ(68+i,0,Math.sin(r),Math.cos(r)),this._attrPos.setXYZ(100+i,t,Math.sin(r),Math.cos(r))}const e=Math.atan2(G.y,Math.sqrt(G.x*G.x+G.z*G.z)),n=-Math.atan2(G.z,G.x);this.rotateZ(e),this.rotateY(n),this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<34;t++){const e=(t+1)%34;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(68+t*2,34+t,34+e)}for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(136+t*2,68+t,68+e),this._attrIndex.setXY(200+t*2,100+t,100+e)}this._attrIndex.needsUpdate=!0}},ns=class extends J{constructor(t){super(),this.worldScale=1,this._currentOffset=new g,this._currentNormal=new g,this._shape=t,this._attrPos=new D(new Float32Array(6*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(10),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),t=!0),this._currentNormal.equals(this._shape.normal)||(this._currentNormal.copy(this._shape.normal),t=!0),t&&this._buildPosition()}_buildPosition(){this._attrPos.setXYZ(0,-.5,-.5,0),this._attrPos.setXYZ(1,.5,-.5,0),this._attrPos.setXYZ(2,.5,.5,0),this._attrPos.setXYZ(3,-.5,.5,0),this._attrPos.setXYZ(4,0,0,0),this._attrPos.setXYZ(5,0,0,.25),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this.lookAt(this._currentNormal),this._attrPos.needsUpdate=!0}_buildIndex(){this._attrIndex.setXY(0,0,1),this._attrIndex.setXY(2,1,2),this._attrIndex.setXY(4,2,3),this._attrIndex.setXY(6,3,0),this._attrIndex.setXY(8,4,5),this._attrIndex.needsUpdate=!0}},is=class extends J{constructor(t){super(),this.worldScale=1,this._currentRadius=0,this._currentOffset=new g,this._shape=t,this._attrPos=new D(new Float32Array(32*3*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(64*3),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;const e=this._shape.radius/this.worldScale;this._currentRadius!==e&&(this._currentRadius=e,t=!0),this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),t=!0),t&&this._buildPosition()}_buildPosition(){for(let t=0;t<32;t++){const e=t/16*Math.PI;this._attrPos.setXYZ(t,Math.cos(e),Math.sin(e),0),this._attrPos.setXYZ(32+t,0,Math.cos(e),Math.sin(e)),this._attrPos.setXYZ(64+t,Math.sin(e),0,Math.cos(e))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(64+t*2,32+t,32+e),this._attrIndex.setXY(128+t*2,64+t,64+e)}this._attrIndex.needsUpdate=!0}},rs=new g,Ke=class extends pe{constructor(t){if(super(),this.matrixAutoUpdate=!1,this.collider=t,this.collider.shape instanceof xi)this._geometry=new is(this.collider.shape);else if(this.collider.shape instanceof vi)this._geometry=new ts(this.collider.shape);else if(this.collider.shape instanceof Mi)this._geometry=new ns(this.collider.shape);else throw new Error("VRMSpringBoneColliderHelper: Unknown collider shape type detected");const e=new We({color:16711935,depthTest:!1,depthWrite:!1});this._line=new _t(this._geometry,e),this.add(this._line)}dispose(){this._geometry.dispose()}updateMatrixWorld(t){this.collider.updateWorldMatrix(!0,!1),this.matrix.copy(this.collider.matrixWorld);const e=this.matrix.elements;this._geometry.worldScale=rs.set(e[0],e[1],e[2]).length(),this._geometry.update(),super.updateMatrixWorld(t)}},os=class extends J{constructor(t){super(),this.worldScale=1,this._currentRadius=0,this._currentTail=new g,this._springBone=t,this._attrPos=new D(new Float32Array(294),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(194),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;const e=this._springBone.settings.hitRadius/this.worldScale;this._currentRadius!==e&&(this._currentRadius=e,t=!0),this._currentTail.equals(this._springBone.initialLocalChildPosition)||(this._currentTail.copy(this._springBone.initialLocalChildPosition),t=!0),t&&this._buildPosition()}_buildPosition(){for(let t=0;t<32;t++){const e=t/16*Math.PI;this._attrPos.setXYZ(t,Math.cos(e),Math.sin(e),0),this._attrPos.setXYZ(32+t,0,Math.cos(e),Math.sin(e)),this._attrPos.setXYZ(64+t,Math.sin(e),0,Math.cos(e))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.setXYZ(96,0,0,0),this._attrPos.setXYZ(97,this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(64+t*2,32+t,32+e),this._attrIndex.setXY(128+t*2,64+t,64+e)}this._attrIndex.setXY(192,96,97),this._attrIndex.needsUpdate=!0}},ss=new g,as=class extends pe{constructor(t){super(),this.matrixAutoUpdate=!1,this.springBone=t,this._geometry=new os(this.springBone);const e=new We({color:16776960,depthTest:!1,depthWrite:!1});this._line=new _t(this._geometry,e),this.add(this._line)}dispose(){this._geometry.dispose()}updateMatrixWorld(t){this.springBone.bone.updateWorldMatrix(!0,!1),this.matrix.copy(this.springBone.bone.matrixWorld);const e=this.matrix.elements;this._geometry.worldScale=ss.set(e[0],e[1],e[2]).length(),this._geometry.update(),super.updateMatrixWorld(t)}},et=class extends he{constructor(t){super(),this.colliderMatrix=new Y,this.shape=t}updateWorldMatrix(t,e){super.updateWorldMatrix(t,e),ls(this.colliderMatrix,this.matrixWorld,this.shape.offset)}};function ls(t,e,n){const i=e.elements;t.copy(e),n&&(t.elements[12]=i[0]*n.x+i[4]*n.y+i[8]*n.z+i[12],t.elements[13]=i[1]*n.x+i[5]*n.y+i[9]*n.z+i[13],t.elements[14]=i[2]*n.x+i[6]*n.y+i[10]*n.z+i[14])}var us=new Y;function ds(t){return t.invert?t.invert():t.getInverse(us.copy(t)),t}var hs=class{constructor(t){this._inverseCache=new Y,this._shouldUpdateInverse=!0,this.matrix=t;const e={set:(n,i,r)=>(this._shouldUpdateInverse=!0,n[i]=r,!0)};this._originalElements=t.elements,t.elements=new Proxy(t.elements,e)}get inverse(){return this._shouldUpdateInverse&&(ds(this._inverseCache.copy(this.matrix)),this._shouldUpdateInverse=!1),this._inverseCache}revert(){this.matrix.elements=this._originalElements}},tt=new Y,le=new g,ve=new g,Me=new g,xe=new g,cs=new Y,ps=class{constructor(t,e,n={},i=[]){this._currentTail=new g,this._prevTail=new g,this._boneAxis=new g,this._worldSpaceBoneLength=0,this._center=null,this._initialLocalMatrix=new Y,this._initialLocalRotation=new T,this._initialLocalChildPosition=new g;var r,o,s,l,a,u;this.bone=t,this.bone.matrixAutoUpdate=!1,this.child=e,this.settings={hitRadius:(r=n.hitRadius)!=null?r:0,stiffness:(o=n.stiffness)!=null?o:1,gravityPower:(s=n.gravityPower)!=null?s:0,gravityDir:(a=(l=n.gravityDir)==null?void 0:l.clone())!=null?a:new g(0,-1,0),dragForce:(u=n.dragForce)!=null?u:.4},this.colliderGroups=i}get dependencies(){const t=new Set,e=this.bone.parent;e&&t.add(e);for(let n=0;n<this.colliderGroups.length;n++)for(let i=0;i<this.colliderGroups[n].colliders.length;i++)t.add(this.colliderGroups[n].colliders[i]);return t}get center(){return this._center}set center(t){var e;(e=this._center)!=null&&e.userData.inverseCacheProxy&&(this._center.userData.inverseCacheProxy.revert(),delete this._center.userData.inverseCacheProxy),this._center=t,this._center&&(this._center.userData.inverseCacheProxy||(this._center.userData.inverseCacheProxy=new hs(this._center.matrixWorld)))}get initialLocalChildPosition(){return this._initialLocalChildPosition}get _parentMatrixWorld(){return this.bone.parent?this.bone.parent.matrixWorld:tt}setInitState(){this._initialLocalMatrix.copy(this.bone.matrix),this._initialLocalRotation.copy(this.bone.quaternion),this.child?this._initialLocalChildPosition.copy(this.child.position):this._initialLocalChildPosition.copy(this.bone.position).normalize().multiplyScalar(.07);const t=this._getMatrixWorldToCenter();this.bone.localToWorld(this._currentTail.copy(this._initialLocalChildPosition)).applyMatrix4(t),this._prevTail.copy(this._currentTail),this._boneAxis.copy(this._initialLocalChildPosition).normalize()}reset(){this.bone.quaternion.copy(this._initialLocalRotation),this.bone.updateMatrix(),this.bone.matrixWorld.multiplyMatrices(this._parentMatrixWorld,this.bone.matrix);const t=this._getMatrixWorldToCenter();this.bone.localToWorld(this._currentTail.copy(this._initialLocalChildPosition)).applyMatrix4(t),this._prevTail.copy(this._currentTail)}update(t){if(t<=0)return;this._calcWorldSpaceBoneLength();const e=ve.copy(this._boneAxis).transformDirection(this._initialLocalMatrix).transformDirection(this._parentMatrixWorld);xe.copy(this._currentTail).add(le.subVectors(this._currentTail,this._prevTail).multiplyScalar(1-this.settings.dragForce)).applyMatrix4(this._getMatrixCenterToWorld()).addScaledVector(e,this.settings.stiffness*t).addScaledVector(this.settings.gravityDir,this.settings.gravityPower*t),Me.setFromMatrixPosition(this.bone.matrixWorld),xe.sub(Me).normalize().multiplyScalar(this._worldSpaceBoneLength).add(Me),this._collision(xe),this._prevTail.copy(this._currentTail),this._currentTail.copy(xe).applyMatrix4(this._getMatrixWorldToCenter());const n=cs.multiplyMatrices(this._parentMatrixWorld,this._initialLocalMatrix).invert();this.bone.quaternion.setFromUnitVectors(this._boneAxis,le.copy(xe).applyMatrix4(n).normalize()).premultiply(this._initialLocalRotation),this.bone.updateMatrix(),this.bone.matrixWorld.multiplyMatrices(this._parentMatrixWorld,this.bone.matrix)}_collision(t){for(let e=0;e<this.colliderGroups.length;e++)for(let n=0;n<this.colliderGroups[e].colliders.length;n++){const i=this.colliderGroups[e].colliders[n],r=i.shape.calculateCollision(i.colliderMatrix,t,this.settings.hitRadius,le);if(r<0){t.addScaledVector(le,-r),t.sub(Me);const o=t.length();t.multiplyScalar(this._worldSpaceBoneLength/o).add(Me)}}}_calcWorldSpaceBoneLength(){le.setFromMatrixPosition(this.bone.matrixWorld),this.child?ve.setFromMatrixPosition(this.child.matrixWorld):(ve.copy(this._initialLocalChildPosition),ve.applyMatrix4(this.bone.matrixWorld)),this._worldSpaceBoneLength=le.sub(ve).length()}_getMatrixCenterToWorld(){return this._center?this._center.matrixWorld:tt}_getMatrixWorldToCenter(){return this._center?this._center.userData.inverseCacheProxy.inverse:tt}};function fs(t,e){const n=[];let i=t;for(;i!==null;)n.unshift(i),i=i.parent;n.forEach(r=>{e(r)})}function mt(t,e){t.children.forEach(n=>{e(n)||mt(n,e)})}function ms(t){var e;const n=new Map;for(const i of t){let r=i;do{const o=((e=n.get(r))!=null?e:0)+1;if(o===t.size)return r;n.set(r,o),r=r.parent}while(r!==null)}return null}var Cn=class{constructor(){this._joints=new Set,this._sortedJoints=[],this._hasWarnedCircularDependency=!1,this._ancestors=[],this._objectSpringBonesMap=new Map,this._isSortedJointsDirty=!1,this._relevantChildrenUpdated=this._relevantChildrenUpdated.bind(this)}get joints(){return this._joints}get springBones(){return console.warn("VRMSpringBoneManager: springBones is deprecated. use joints instead."),this._joints}get colliderGroups(){const t=new Set;return this._joints.forEach(e=>{e.colliderGroups.forEach(n=>{t.add(n)})}),Array.from(t)}get colliders(){const t=new Set;return this.colliderGroups.forEach(e=>{e.colliders.forEach(n=>{t.add(n)})}),Array.from(t)}addJoint(t){this._joints.add(t);let e=this._objectSpringBonesMap.get(t.bone);e==null&&(e=new Set,this._objectSpringBonesMap.set(t.bone,e)),e.add(t),this._isSortedJointsDirty=!0}addSpringBone(t){console.warn("VRMSpringBoneManager: addSpringBone() is deprecated. use addJoint() instead."),this.addJoint(t)}deleteJoint(t){this._joints.delete(t),this._objectSpringBonesMap.get(t.bone).delete(t),this._isSortedJointsDirty=!0}deleteSpringBone(t){console.warn("VRMSpringBoneManager: deleteSpringBone() is deprecated. use deleteJoint() instead."),this.deleteJoint(t)}setInitState(){this._sortJoints();for(let t=0;t<this._sortedJoints.length;t++){const e=this._sortedJoints[t];e.bone.updateMatrix(),e.bone.updateWorldMatrix(!1,!1),e.setInitState()}}reset(){this._sortJoints();for(let t=0;t<this._sortedJoints.length;t++){const e=this._sortedJoints[t];e.bone.updateMatrix(),e.bone.updateWorldMatrix(!1,!1),e.reset()}}update(t){this._sortJoints();for(let e=0;e<this._ancestors.length;e++)this._ancestors[e].updateWorldMatrix(e===0,!1);for(let e=0;e<this._sortedJoints.length;e++){const n=this._sortedJoints[e];n.bone.updateMatrix(),n.bone.updateWorldMatrix(!1,!1),n.update(t),mt(n.bone,this._relevantChildrenUpdated)}}_sortJoints(){if(!this._isSortedJointsDirty)return;const t=[],e=new Set,n=new Set,i=new Set;for(const o of this._joints)this._insertJointSort(o,e,n,t,i);this._sortedJoints=t;const r=ms(i);this._ancestors=[],r&&(this._ancestors.push(r),mt(r,o=>{var s,l;return((l=(s=this._objectSpringBonesMap.get(o))==null?void 0:s.size)!=null?l:0)>0?!0:(this._ancestors.push(o),!1)})),this._isSortedJointsDirty=!1}_insertJointSort(t,e,n,i,r){if(n.has(t))return;if(e.has(t)){this._hasWarnedCircularDependency||(console.warn("VRMSpringBoneManager: Circular dependency detected"),this._hasWarnedCircularDependency=!0);return}e.add(t);const o=t.dependencies;for(const s of o){let l=!1,a=null;fs(s,u=>{const h=this._objectSpringBonesMap.get(u);if(h)for(const d of h)l=!0,this._insertJointSort(d,e,n,i,r);else l||(a=u)}),a&&r.add(a)}i.push(t),n.add(t)}_relevantChildrenUpdated(t){var e,n;return((n=(e=this._objectSpringBonesMap.get(t))==null?void 0:e.size)!=null?n:0)>0?!0:(t.updateWorldMatrix(!1,!1),!1)}},On="VRMC_springBone_extended_collider",_s=new Set(["1.0","1.0-beta"]),gs=new Set(["1.0"]),yi=class de{get name(){return de.EXTENSION_NAME}constructor(e,n){var i;this.parser=e,this.jointHelperRoot=n==null?void 0:n.jointHelperRoot,this.colliderHelperRoot=n==null?void 0:n.colliderHelperRoot,this.useExtendedColliders=(i=n==null?void 0:n.useExtendedColliders)!=null?i:!0}afterRoot(e){return Ce(this,null,function*(){e.userData.vrmSpringBoneManager=yield this._import(e)})}_import(e){return Ce(this,null,function*(){const n=yield this._v1Import(e);if(n!=null)return n;const i=yield this._v0Import(e);return i??null})}_v1Import(e){return Ce(this,null,function*(){var n,i,r,o,s;const l=e.parser.json;if(!(((n=l.extensionsUsed)==null?void 0:n.indexOf(de.EXTENSION_NAME))!==-1))return null;const u=new Cn,h=yield e.parser.getDependencies("node"),d=(i=l.extensions)==null?void 0:i[de.EXTENSION_NAME];if(!d)return null;const c=d.specVersion;if(!_s.has(c))return console.warn(`VRMSpringBoneLoaderPlugin: Unknown ${de.EXTENSION_NAME} specVersion "${c}"`),null;const p=(r=d.colliders)==null?void 0:r.map((m,_)=>{var v,M,R,y,x,w,S,A,C,P,L,O,H,W,Q;const k=h[m.node];if(k==null)return console.warn(`VRMSpringBoneLoaderPlugin: The collider #${_} attempted to reference a node #${m.node} but not found. Skipping the collider`),null;const b=m.shape,V=(v=m.extensions)==null?void 0:v[On];if(this.useExtendedColliders&&V!=null){const $=V.specVersion;if(!gs.has($))console.warn(`VRMSpringBoneLoaderPlugin: Unknown ${On} specVersion "${$}". Fallbacking to the ${de.EXTENSION_NAME} definition`);else{const N=V.shape;if(N.sphere)return this._importSphereCollider(k,{offset:new g().fromArray((M=N.sphere.offset)!=null?M:[0,0,0]),radius:(R=N.sphere.radius)!=null?R:0,inside:(y=N.sphere.inside)!=null?y:!1});if(N.capsule)return this._importCapsuleCollider(k,{offset:new g().fromArray((x=N.capsule.offset)!=null?x:[0,0,0]),radius:(w=N.capsule.radius)!=null?w:0,tail:new g().fromArray((S=N.capsule.tail)!=null?S:[0,0,0]),inside:(A=N.capsule.inside)!=null?A:!1});if(N.plane)return this._importPlaneCollider(k,{offset:new g().fromArray((C=N.plane.offset)!=null?C:[0,0,0]),normal:new g().fromArray((P=N.plane.normal)!=null?P:[0,0,1])})}}if(b.sphere)return this._importSphereCollider(k,{offset:new g().fromArray((L=b.sphere.offset)!=null?L:[0,0,0]),radius:(O=b.sphere.radius)!=null?O:0,inside:!1});if(b.capsule)return this._importCapsuleCollider(k,{offset:new g().fromArray((H=b.capsule.offset)!=null?H:[0,0,0]),radius:(W=b.capsule.radius)!=null?W:0,tail:new g().fromArray((Q=b.capsule.tail)!=null?Q:[0,0,0]),inside:!1});console.warn(`VRMSpringBoneLoaderPlugin: The collider #${_} has no valid shape. Skipping the collider`)}),f=(o=d.colliderGroups)==null?void 0:o.map((m,_)=>{var v;return{colliders:((v=m.colliders)!=null?v:[]).map(R=>{const y=p==null?void 0:p[R];return y??(console.warn(`VRMSpringBoneLoaderPlugin: The collider group #${_} attempted to reference a collider #${R} but not found. Skipping the collider`),null)}).filter(R=>R!=null),name:m.name}});return(s=d.springs)==null||s.forEach((m,_)=>{var v;const M=m.joints,R=(v=m.colliderGroups)==null?void 0:v.map(w=>{const S=f==null?void 0:f[w];return S??(console.warn(`VRMSpringBoneLoaderPlugin: The spring #${_} attempted to reference a collider group #${w} but not found. Skipping the collider group`),null)}).filter(w=>w!=null),y=m.center!=null?h[m.center]:void 0;let x;M.forEach(w=>{if(x){const S=x.node,A=h[S],C=w.node,P=h[C],L={hitRadius:x.hitRadius,dragForce:x.dragForce,gravityPower:x.gravityPower,stiffness:x.stiffness,gravityDir:x.gravityDir!=null?new g().fromArray(x.gravityDir):void 0},O=this._importJoint(A,P,L,R);y&&(O.center=y),u.addJoint(O)}x=w})}),u.setInitState(),u})}_v0Import(e){return Ce(this,null,function*(){var n,i,r;const o=e.parser.json;if(!(((n=o.extensionsUsed)==null?void 0:n.indexOf("VRM"))!==-1))return null;const l=(i=o.extensions)==null?void 0:i.VRM,a=l==null?void 0:l.secondaryAnimation;if(!a)return null;const u=a==null?void 0:a.boneGroups;if(!u)return null;const h=new Cn,d=yield e.parser.getDependencies("node"),c=(r=a.colliderGroups)==null?void 0:r.map((p,f)=>{var m;const _=d[p.node];return _==null?(console.warn(`VRMSpringBoneLoaderPlugin: The collider group #${f} attempted to reference a node #${p.node} but not found. Skipping the collider group`),null):{colliders:((m=p.colliders)!=null?m:[]).map((M,R)=>{var y,x,w;const S=new g(0,0,0);return M.offset&&S.set((y=M.offset.x)!=null?y:0,(x=M.offset.y)!=null?x:0,M.offset.z?-M.offset.z:0),this._importSphereCollider(_,{offset:S,radius:(w=M.radius)!=null?w:0,inside:!1})})}});return u==null||u.forEach((p,f)=>{const m=p.bones;m&&m.forEach(_=>{var v,M,R,y;const x=d[_];if(x==null){console.warn(`VRMSpringBoneLoaderPlugin: The spring bone group #${f} attempted to reference a node #${_} but not found. Skipping the node`);return}const w=new g;p.gravityDir?w.set((v=p.gravityDir.x)!=null?v:0,(M=p.gravityDir.y)!=null?M:0,(R=p.gravityDir.z)!=null?R:0):w.set(0,-1,0);const S=p.center!=null?d[p.center]:void 0,A={hitRadius:p.hitRadius,dragForce:p.dragForce,gravityPower:p.gravityPower,stiffness:p.stiffiness,gravityDir:w},C=(y=p.colliderGroups)==null?void 0:y.map(P=>{const L=c==null?void 0:c[P];return L??(console.warn(`VRMSpringBoneLoaderPlugin: The spring #${f} attempted to reference a collider group #${P} but not found. Skipping the collider group`),null)}).filter(P=>P!=null);x.traverse(P=>{var L;const O=(L=P.children[0])!=null?L:null,H=this._importJoint(P,O,A,C);S&&(H.center=S),h.addJoint(H)})})}),e.scene.updateMatrixWorld(),h.setInitState(),h})}_importJoint(e,n,i,r){const o=new ps(e,n,i,r);if(this.jointHelperRoot){const s=new as(o);this.jointHelperRoot.add(s),s.renderOrder=this.jointHelperRoot.renderOrder}return o}_importSphereCollider(e,n){const i=new xi(n),r=new et(i);if(e.add(r),this.colliderHelperRoot){const o=new Ke(r);this.colliderHelperRoot.add(o),o.renderOrder=this.colliderHelperRoot.renderOrder}return r}_importCapsuleCollider(e,n){const i=new vi(n),r=new et(i);if(e.add(r),this.colliderHelperRoot){const o=new Ke(r);this.colliderHelperRoot.add(o),o.renderOrder=this.colliderHelperRoot.renderOrder}return r}_importPlaneCollider(e,n){const i=new Mi(n),r=new et(i);if(e.add(r),this.colliderHelperRoot){const o=new Ke(r);this.colliderHelperRoot.add(o),o.renderOrder=this.colliderHelperRoot.renderOrder}return r}};yi.EXTENSION_NAME="VRMC_springBone";var vs=yi,Ms=class{get name(){return"VRMLoaderPlugin"}constructor(t,e){var n,i,r,o,s,l,a,u,h,d;this.parser=t;const c=e==null?void 0:e.helperRoot,p=e==null?void 0:e.autoUpdateHumanBones;this.expressionPlugin=(n=e==null?void 0:e.expressionPlugin)!=null?n:new Ur(t),this.firstPersonPlugin=(i=e==null?void 0:e.firstPersonPlugin)!=null?i:new Vr(t),this.humanoidPlugin=(r=e==null?void 0:e.humanoidPlugin)!=null?r:new zr(t,{helperRoot:c,autoUpdateHumanBones:p}),this.lookAtPlugin=(o=e==null?void 0:e.lookAtPlugin)!=null?o:new ro(t,{helperRoot:c}),this.metaPlugin=(s=e==null?void 0:e.metaPlugin)!=null?s:new ao(t),this.mtoonMaterialPlugin=(l=e==null?void 0:e.mtoonMaterialPlugin)!=null?l:new Ro(t),this.materialsHDREmissiveMultiplierPlugin=(a=e==null?void 0:e.materialsHDREmissiveMultiplierPlugin)!=null?a:new So(t),this.materialsV0CompatPlugin=(u=e==null?void 0:e.materialsV0CompatPlugin)!=null?u:new Co(t),this.springBonePlugin=(h=e==null?void 0:e.springBonePlugin)!=null?h:new vs(t,{colliderHelperRoot:c,jointHelperRoot:c}),this.nodeConstraintPlugin=(d=e==null?void 0:e.nodeConstraintPlugin)!=null?d:new Ko(t,{helperRoot:c})}beforeRoot(){return Le(this,null,function*(){yield this.materialsV0CompatPlugin.beforeRoot(),yield this.mtoonMaterialPlugin.beforeRoot()})}loadMesh(t){return Le(this,null,function*(){return yield this.mtoonMaterialPlugin.loadMesh(t)})}getMaterialType(t){const e=this.mtoonMaterialPlugin.getMaterialType(t);return e??null}extendMaterialParams(t,e){return Le(this,null,function*(){yield this.materialsHDREmissiveMultiplierPlugin.extendMaterialParams(t,e),yield this.mtoonMaterialPlugin.extendMaterialParams(t,e)})}afterRoot(t){return Le(this,null,function*(){yield this.metaPlugin.afterRoot(t),yield this.humanoidPlugin.afterRoot(t),yield this.expressionPlugin.afterRoot(t),yield this.lookAtPlugin.afterRoot(t),yield this.firstPersonPlugin.afterRoot(t),yield this.springBonePlugin.afterRoot(t),yield this.nodeConstraintPlugin.afterRoot(t),yield this.mtoonMaterialPlugin.afterRoot(t);const e=t.userData.vrmMeta,n=t.userData.vrmHumanoid;if(e&&n){const i=new uo({scene:t.scene,expressionManager:t.userData.vrmExpressionManager,firstPerson:t.userData.vrmFirstPerson,humanoid:n,lookAt:t.userData.vrmLookAt,meta:e,materials:t.userData.vrmMToonMaterials,springBoneManager:t.userData.vrmSpringBoneManager,nodeConstraintManager:t.userData.vrmNodeConstraintManager});t.userData.vrm=i}})}};function xs(t){const e=new Set;return t.traverse(n=>{if(!n.isMesh)return;const i=n;e.add(i)}),e}function Un(t,e,n){if(e.size===1){const s=e.values().next().value;if(s.weight===1)return t[s.index]}const i=new Float32Array(t[0].count*3);let r=0;if(n)r=1;else for(const s of e)r+=s.weight;for(const s of e){const l=t[s.index],a=s.weight/r;for(let u=0;u<l.count;u++)i[u*3+0]+=l.getX(u)*a,i[u*3+1]+=l.getY(u)*a,i[u*3+2]+=l.getZ(u)*a}return new D(i,3)}function ys(t){var e;const n=xs(t.scene),i=new Map,r=(e=t.expressionManager)==null?void 0:e.expressionMap;if(r!=null)for(const[o,s]of Object.entries(r)){const l=new Set;for(const a of s.binds)if(a instanceof De){if(a.weight!==0)for(const u of a.primitives){let h=i.get(u);h==null&&(h=new Map,i.set(u,h));let d=h.get(o);d==null&&(d=new Set,h.set(o,d)),d.add(a)}l.add(a)}for(const a of l)s.deleteBind(a)}for(const o of n){const s=i.get(o);if(s==null)continue;const l=o.geometry.morphAttributes;o.geometry.morphAttributes={};const a=o.geometry.clone();o.geometry=a;const u=a.morphTargetsRelative,h=l.position!=null,d=l.normal!=null,c={},p={},f=[];if(h||d){h&&(c.position=[]),d&&(c.normal=[]);let m=0;for(const[_,v]of s)h&&(c.position[m]=Un(l.position,v,u)),d&&(c.normal[m]=Un(l.normal,v,u)),r==null||r[_].addBind(new De({index:m,weight:1,primitives:[o]})),p[_]=m,f.push(0),m++}a.morphAttributes=c,o.morphTargetDictionary=p,o.morphTargetInfluences=f}}function Be(t,e,n){if(t.getComponent)return t.getComponent(e,n);{let i=t.array[e*t.itemSize+n];return t.normalized&&(i=I.denormalize(i,t.array)),i}}function wi(t,e,n,i){t.setComponent?t.setComponent(e,n,i):(t.normalized&&(i=I.normalize(i,t.array)),t.array[e*t.itemSize+n]=i)}function ws(t){var e;const n=Rs(t),i=new Set;for(const d of n)i.has(d.geometry)&&(d.geometry=Ls(d.geometry)),i.add(d.geometry);const r=new Map;for(const d of i){const c=d.getAttribute("skinIndex"),p=(e=r.get(c))!=null?e:new Map;r.set(c,p);const f=d.getAttribute("skinWeight"),m=Ts(c,f);p.set(f,m)}const o=new Map;for(const d of n){const c=Ss(d,r);o.set(d,c)}const s=[];for(const[d,c]of o){let p=!1;for(const f of s)if(As(c,f.boneInverseMap)){p=!0,f.meshes.add(d);for(const[_,v]of c)f.boneInverseMap.set(_,v);break}p||s.push({boneInverseMap:c,meshes:new Set([d])})}const l=new Map,a=new nt,u=new nt,h=new nt;for(const d of s){const{boneInverseMap:c,meshes:p}=d,f=Array.from(c.keys()),m=Array.from(c.values()),_=new gt(f,m),v=u.getOrCreate(_);for(const M of p){const R=M.geometry.getAttribute("skinIndex"),y=a.getOrCreate(R),x=M.skeleton.bones,w=x.map(C=>h.getOrCreate(C)).join(","),S=`${y};${v};${w}`;let A=l.get(S);A==null&&(A=R.clone(),Es(A,x,f),l.set(S,A)),M.geometry.setAttribute("skinIndex",A)}for(const M of p)M.bind(_,new Y)}}function Rs(t){const e=new Set;return t.traverse(n=>{if(!n.isSkinnedMesh)return;const i=n;e.add(i)}),e}function Ts(t,e){const n=new Set;for(let i=0;i<t.count;i++)for(let r=0;r<t.itemSize;r++){const o=Be(t,i,r);Be(e,i,r)!==0&&n.add(o)}return n}function Ss(t,e){const n=new Map,i=t.skeleton,r=t.geometry,o=r.getAttribute("skinIndex"),s=r.getAttribute("skinWeight"),l=e.get(o),a=l==null?void 0:l.get(s);if(!a)throw new Error("Unreachable. attributeUsedIndexSetMap does not know the skin index attribute or the skin weight attribute.");for(const u of a)n.set(i.bones[u],i.boneInverses[u]);return n}function As(t,e){for(const[n,i]of t.entries()){const r=e.get(n);if(r!=null&&!Ps(i,r))return!1}return!0}function Es(t,e,n){const i=new Map;for(const o of e)i.set(o,i.size);const r=new Map;for(const[o,s]of n.entries()){const l=i.get(s);r.set(l,o)}for(let o=0;o<t.count;o++)for(let s=0;s<t.itemSize;s++){const l=Be(t,o,s),a=r.get(l);wi(t,o,s,a)}t.needsUpdate=!0}function Ps(t,e,n){if(n=n||1e-4,t.elements.length!=e.elements.length)return!1;for(let i=0,r=t.elements.length;i<r;i++)if(Math.abs(t.elements[i]-e.elements[i])>n)return!1;return!0}var nt=class{constructor(){this._objectIndexMap=new Map,this._index=0}get(t){return this._objectIndexMap.get(t)}getOrCreate(t){let e=this._objectIndexMap.get(t);return e==null&&(e=this._index,this._objectIndexMap.set(t,e),this._index++),e}};function Ls(t){var e,n,i,r;const o=new J;o.name=t.name,o.setIndex(t.index);for(const[s,l]of Object.entries(t.attributes))o.setAttribute(s,l);for(const[s,l]of Object.entries(t.morphAttributes)){const a=s;o.morphAttributes[a]=l.concat()}o.morphTargetsRelative=t.morphTargetsRelative,o.groups=[];for(const s of t.groups)o.addGroup(s.start,s.count,s.materialIndex);return o.boundingSphere=(n=(e=t.boundingSphere)==null?void 0:e.clone())!=null?n:null,o.boundingBox=(r=(i=t.boundingBox)==null?void 0:i.clone())!=null?r:null,o.drawRange.start=t.drawRange.start,o.drawRange.count=t.drawRange.count,o.userData=t.userData,o}function Nn(t){if(Object.values(t).forEach(e=>{e!=null&&e.isTexture&&e.dispose()}),t.isShaderMaterial){const e=t.uniforms;e&&Object.values(e).forEach(n=>{const i=n.value;i!=null&&i.isTexture&&i.dispose()})}t.dispose()}function bs(t){const e=t.geometry;e&&e.dispose();const n=t.skeleton;n&&n.dispose();const i=t.material;i&&(Array.isArray(i)?i.forEach(r=>Nn(r)):i&&Nn(i))}function Is(t){t.traverse(bs)}function Cs(t,e){var n,i;console.warn("VRMUtils.removeUnnecessaryJoints: removeUnnecessaryJoints is deprecated. Use combineSkeletons instead. combineSkeletons contributes more to the performance improvement. This function will be removed in the next major version.");const r=(n=e==null?void 0:e.experimentalSameBoneCounts)!=null?n:!1,o=[];t.traverse(a=>{a.type==="SkinnedMesh"&&o.push(a)});const s=new Map;let l=0;for(const a of o){const h=a.geometry.getAttribute("skinIndex");if(s.has(h))continue;const d=new Map,c=new Map;for(let p=0;p<h.count;p++)for(let f=0;f<h.itemSize;f++){const m=Be(h,p,f);let _=d.get(m);_==null&&(_=d.size,d.set(m,_),c.set(_,m)),wi(h,p,f,_)}h.needsUpdate=!0,s.set(h,c),l=Math.max(l,d.size)}for(const a of o){const h=a.geometry.getAttribute("skinIndex"),d=s.get(h),c=[],p=[],f=r?l:d.size;for(let _=0;_<f;_++){const v=(i=d.get(_))!=null?i:0;c.push(a.skeleton.bones[v]),p.push(a.skeleton.boneInverses[v])}const m=new gt(c,p);a.bind(m,new Y)}}function Os(t,e){const n=t.position.count,i=new Array(n);let r=0;const o=e.array;for(let s=0;s<o.length;s++){const l=o[s];i[l]||(i[l]=!0,r++)}return{isVertexUsed:i,vertexCount:n,verticesUsed:r}}function Us(t){const e=[],n=[];let i=0;for(let r=0;r<t.length;r++)if(t[r]){const o=i++;e[r]=o,n[o]=r}return{originalIndexNewIndexMap:e,newIndexOriginalIndexMap:n}}function Ns(t,e){var n,i,r,o;e.name=t.name,e.morphTargetsRelative=t.morphTargetsRelative,t.groups.forEach(s=>{e.addGroup(s.start,s.count,s.materialIndex)}),e.boundingBox=(i=(n=t.boundingBox)==null?void 0:n.clone())!=null?i:null,e.boundingSphere=(o=(r=t.boundingSphere)==null?void 0:r.clone())!=null?o:null,e.setDrawRange(t.drawRange.start,t.drawRange.count),e.userData=t.userData}function Vs(t,e,n){const i=e.array,r=new i.constructor(i.length);for(let o=0;o<i.length;o++){const s=i[o];r[o]=n[s]}t.setIndex(new D(r,e.itemSize,e.normalized))}function Fe(t,e,n){const i=t.constructor,r=new i(e.length*n);let o=!0;for(let s=0;s<e.length;s++){const a=e[s]*n,u=s*n;for(let h=0;h<n;h++){const d=t[a+h];r[u+h]=d,o=o&&d===0}}return[r,o]}function Ds(t){var e;const n=new Map,i=[];for(const[r,o]of Object.entries(t))if(o.isInterleavedBufferAttribute){const s=o,l=s.data,a=(e=n.get(l))!=null?e:[];n.set(l,a),a.push([r,s])}else{const s=o;i.push([r,s])}return[n,i]}function ks(t,e,n){const[i,r]=Ds(e);for(const[o,s]of i){const l=o.array,{stride:a}=o,[u,h]=Fe(l,n,a),d=new Jn(u,a);d.setUsage(o.usage);for(const[c,p]of s){const{itemSize:f,offset:m,normalized:_}=p,v=new Kn(d,f,m,_);t.setAttribute(c,v)}}for(const[o,s]of r){const l=s.array,{itemSize:a,normalized:u}=s,[h,d]=Fe(l,n,a);t.setAttribute(o,new D(h,a,u))}}function Bs(t){var e;const n=new Map,i=[];for(const[r,o]of Object.entries(t)){const s=r;for(let l=0;l<o.length;l++){const a=o[l];if(a.isInterleavedBufferAttribute){const u=a,h=u.data,d=(e=n.get(h))!=null?e:[];n.set(h,d),d.push([s,l,u])}else{const u=a;i.push([s,l,u])}}}return[n,i]}function Fs(t,e,n){var i,r;let o=!0;const[s,l]=Bs(e),a={};for(const[u,h]of s){const d=u.array,{stride:c}=u,[p,f]=Fe(d,n,c);o=o&&f;const m=new Jn(p,c);m.setUsage(u.usage);for(const[_,v,M]of h){const{itemSize:R,offset:y,normalized:x}=M,w=new Kn(m,R,y,x);(i=a[_])!=null||(a[_]=[]),a[_][v]=w}}for(const[u,h,d]of l){const c=d,p=c.array,{itemSize:f,normalized:m}=c,[_,v]=Fe(p,n,f);o=o&&v,(r=a[u])!=null||(a[u]=[]),a[u][h]=new D(_,f,m)}t.morphAttributes=o?{}:a}function Hs(t){const e=new Map;t.traverse(n=>{if(!n.isMesh)return;const i=n,r=i.geometry,o=r.index;if(o==null)return;const s=e.get(r);if(s!=null){i.geometry=s;return}const{isVertexUsed:l,vertexCount:a,verticesUsed:u}=Os(r.attributes,o);if(u===a)return;const{originalIndexNewIndexMap:h,newIndexOriginalIndexMap:d}=Us(l),c=new J;Ns(r,c),e.set(r,c),Vs(c,o,h),ks(c,r.attributes,d),Fs(c,r.morphAttributes,d),i.geometry=c}),Array.from(e.keys()).forEach(n=>{n.dispose()})}function Ws(t){var e;((e=t.meta)==null?void 0:e.metaVersion)==="0"&&(t.scene.rotation.y=Math.PI)}var q=class{constructor(){}};q.combineMorphs=ys;q.combineSkeletons=ws;q.deepDispose=Is;q.removeUnnecessaryJoints=Cs;q.removeUnnecessaryVertices=Hs;q.rotateVRM0=Ws;/*!
 * @pixiv/three-vrm-core v3.5.5
 * The implementation of core features of VRM, for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-core is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 *//*!
 * @pixiv/three-vrm-materials-mtoon v3.5.5
 * MToon (toon material) module for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-materials-mtoon is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 *//*!
 * @pixiv/three-vrm-materials-hdr-emissive-multiplier v3.5.5
 * Support VRMC_hdr_emissiveMultiplier for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-materials-hdr-emissive-multiplier is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 *//*!
 * @pixiv/three-vrm-materials-v0compat v3.5.5
 * VRM0.0 materials compatibility layer plugin for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-materials-v0compat is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 *//*!
 * @pixiv/three-vrm-node-constraint v3.5.5
 * Node constraint module for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-node-constraint is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 *//*!
 * @pixiv/three-vrm-springbone v3.5.5
 * Spring bone module for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-springbone is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */const Vn="aa";class zs{constructor(e,n=.2){U(this,"current",null);U(this,"weights",new Map);U(this,"mouth",0);U(this,"warned",new Set);U(this,"sink");U(this,"fadeSeconds");this.sink=e,this.fadeSeconds=n}setEmotion(e){return e!==null&&!this.sink.has(e)?(this.warned.has(e)||(this.warned.add(e),console.warn(`[VRM] expression "${e}" not found in model; ignoring`)),!1):(this.current=e,e!==null&&!this.weights.has(e)&&this.weights.set(e,0),!0)}clear(){this.setEmotion(null)}setMouth(e){this.mouth=e}update(e){const n=this.fadeSeconds>0?e/this.fadeSeconds:1;for(const[i,r]of this.weights){const o=i===this.current?1:0,s=r<o?Math.min(o,r+n):Math.max(o,r-n);s!==r&&(this.weights.set(i,s),this.sink.setValue(i,s)),s===0&&o===0&&this.weights.delete(i)}this.sink.has(Vn)&&this.sink.setValue(Vn,this.mouth)}}/*!
 * @pixiv/three-vrm-animation v3.5.5
 * The implementation of VRM Animation
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-animation is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */var Dn=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),js={Aa:"aa",Ih:"ih",Ou:"ou",Ee:"ee",Oh:"oh",Blink:"blink",Happy:"happy",Angry:"angry",Sad:"sad",Relaxed:"relaxed",LookUp:"lookUp",Surprised:"surprised",LookDown:"lookDown",LookLeft:"lookLeft",LookRight:"lookRight",BlinkLeft:"blinkLeft",BlinkRight:"blinkRight",Neutral:"neutral"};new F;var kn={hips:null,spine:"hips",chest:"spine",upperChest:"chest",neck:"upperChest",head:"neck",leftEye:"head",rightEye:"head",jaw:"head",leftUpperLeg:"hips",leftLowerLeg:"leftUpperLeg",leftFoot:"leftLowerLeg",leftToes:"leftFoot",rightUpperLeg:"hips",rightLowerLeg:"rightUpperLeg",rightFoot:"rightLowerLeg",rightToes:"rightFoot",leftShoulder:"upperChest",leftUpperArm:"leftShoulder",leftLowerArm:"leftUpperArm",leftHand:"leftLowerArm",rightShoulder:"upperChest",rightUpperArm:"rightShoulder",rightLowerArm:"rightUpperArm",rightHand:"rightLowerArm",leftThumbMetacarpal:"leftHand",leftThumbProximal:"leftThumbMetacarpal",leftThumbDistal:"leftThumbProximal",leftIndexProximal:"leftHand",leftIndexIntermediate:"leftIndexProximal",leftIndexDistal:"leftIndexIntermediate",leftMiddleProximal:"leftHand",leftMiddleIntermediate:"leftMiddleProximal",leftMiddleDistal:"leftMiddleIntermediate",leftRingProximal:"leftHand",leftRingIntermediate:"leftRingProximal",leftRingDistal:"leftRingIntermediate",leftLittleProximal:"leftHand",leftLittleIntermediate:"leftLittleProximal",leftLittleDistal:"leftLittleIntermediate",rightThumbMetacarpal:"rightHand",rightThumbProximal:"rightThumbMetacarpal",rightThumbDistal:"rightThumbProximal",rightIndexProximal:"rightHand",rightIndexIntermediate:"rightIndexProximal",rightIndexDistal:"rightIndexIntermediate",rightMiddleProximal:"rightHand",rightMiddleIntermediate:"rightMiddleProximal",rightMiddleDistal:"rightMiddleIntermediate",rightRingProximal:"rightHand",rightRingIntermediate:"rightRingProximal",rightRingDistal:"rightRingIntermediate",rightLittleProximal:"rightHand",rightLittleIntermediate:"rightLittleProximal",rightLittleDistal:"rightLittleIntermediate"};function Gs(t){return t.invert?t.invert():t.inverse(),t}var Xs=new g,qs=new g;function Ys(t,e){return t.matrixWorld.decompose(Xs,e,qs),e}function it(t){return[Math.atan2(-t.z,t.x),Math.atan2(t.y,Math.sqrt(t.x*t.x+t.z*t.z))]}function Bn(t){const e=Math.round(t/2/Math.PI);return t-2*Math.PI*e}var Fn=new g(0,0,1),Qs=new g,$s=new g,Zs=new g,Js=new T,rt=new T,Hn=new T,Ks=new T,ot=new ce,Ri=class Ti{constructor(e,n){this.offsetFromHeadBone=new g,this.autoUpdate=!0,this.faceFront=new g(0,0,1),this.humanoid=e,this.applier=n,this._yaw=0,this._pitch=0,this._needsUpdate=!0,this._restHeadWorldQuaternion=this.getLookAtWorldQuaternion(new T)}get yaw(){return this._yaw}set yaw(e){this._yaw=e,this._needsUpdate=!0}get pitch(){return this._pitch}set pitch(e){this._pitch=e,this._needsUpdate=!0}get euler(){return console.warn("VRMLookAt: euler is deprecated. use getEuler() instead."),this.getEuler(new ce)}getEuler(e){return e.set(I.DEG2RAD*this._pitch,I.DEG2RAD*this._yaw,0,"YXZ")}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMLookAt: humanoid must be same in order to copy");return this.offsetFromHeadBone.copy(e.offsetFromHeadBone),this.applier=e.applier,this.autoUpdate=e.autoUpdate,this.target=e.target,this.faceFront.copy(e.faceFront),this}clone(){return new Ti(this.humanoid,this.applier).copy(this)}reset(){this._yaw=0,this._pitch=0,this._needsUpdate=!0}getLookAtWorldPosition(e){const n=this.humanoid.getRawBoneNode("head");return e.copy(this.offsetFromHeadBone).applyMatrix4(n.matrixWorld)}getLookAtWorldQuaternion(e){const n=this.humanoid.getRawBoneNode("head");return Ys(n,e)}getFaceFrontQuaternion(e){if(this.faceFront.distanceToSquared(Fn)<.01)return e.copy(this._restHeadWorldQuaternion).invert();const[n,i]=it(this.faceFront);return ot.set(0,.5*Math.PI+n,i,"YZX"),e.setFromEuler(ot).premultiply(Ks.copy(this._restHeadWorldQuaternion).invert())}getLookAtWorldDirection(e){return this.getLookAtWorldQuaternion(rt),this.getFaceFrontQuaternion(Hn),e.copy(Fn).applyQuaternion(rt).applyQuaternion(Hn).applyEuler(this.getEuler(ot))}lookAt(e){const n=Js.copy(this._restHeadWorldQuaternion).multiply(Gs(this.getLookAtWorldQuaternion(rt))),i=this.getLookAtWorldPosition($s),r=Zs.copy(e).sub(i).applyQuaternion(n).normalize(),[o,s]=it(this.faceFront),[l,a]=it(r),u=Bn(l-o),h=Bn(s-a);this._yaw=I.RAD2DEG*u,this._pitch=I.RAD2DEG*h,this._needsUpdate=!0}update(e){this.target!=null&&this.autoUpdate&&this.lookAt(this.target.getWorldPosition(Qs)),this._needsUpdate&&(this._needsUpdate=!1,this.applier.applyYawPitch(this._yaw,this._pitch))}};Ri.EULER_ORDER="YXZ";var ea=Ri,Wn=180/Math.PI,st=new ce,zn=class extends he{constructor(t){super(),this.vrmLookAt=t,this.type="VRMLookAtQuaternionProxy";const e=this.rotation._onChangeCallback;this.rotation._onChange(()=>{e(),this._applyToLookAt()});const n=this.quaternion._onChangeCallback;this.quaternion._onChange(()=>{n(),this._applyToLookAt()})}_applyToLookAt(){st.setFromQuaternion(this.quaternion,ea.EULER_ORDER),this.vrmLookAt.yaw=Wn*st.y,this.vrmLookAt.pitch=Wn*st.x}};function ta(t,e,n){var i,r;const o=new Map,s=new Map;for(const[l,a]of t.humanoidTracks.rotation.entries()){const u=(i=e.getNormalizedBoneNode(l))==null?void 0:i.name;if(u!=null){const h=new yr(`${u}.quaternion`,a.times,a.values.map((d,c)=>n==="0"&&c%2===0?-d:d));s.set(l,h)}}for(const[l,a]of t.humanoidTracks.translation.entries()){const u=(r=e.getNormalizedBoneNode(l))==null?void 0:r.name;if(u!=null){const h=t.restHipsPosition.y,c=e.normalizedRestPose.hips.position[1]/h,p=a.clone();p.values=p.values.map((f,m)=>(n==="0"&&m%3!==1?-f:f)*c),p.name=`${u}.position`,o.set(l,p)}}return{translation:o,rotation:s}}function na(t,e){const n=new Map,i=new Map;for(const[r,o]of t.expressionTracks.preset.entries()){const s=e.getExpressionTrackName(r);if(s!=null){const l=o.clone();l.name=s,n.set(r,l)}}for(const[r,o]of t.expressionTracks.custom.entries()){const s=e.getExpressionTrackName(r);if(s!=null){const l=o.clone();l.name=s,i.set(r,l)}}return{preset:n,custom:i}}function ia(t,e){if(t.lookAtTrack==null)return null;const n=t.lookAtTrack.clone();return n.name=e,n}function ra(t,e){const n=[],i=ta(t,e.humanoid,e.meta.metaVersion);if(n.push(...i.translation.values()),n.push(...i.rotation.values()),e.expressionManager!=null){const r=na(t,e.expressionManager);n.push(...r.preset.values()),n.push(...r.custom.values())}if(e.lookAt!=null){let r=e.scene.children.find(s=>s instanceof zn);r==null?(console.warn("createVRMAnimationClip: VRMLookAtQuaternionProxy is not found. Creating a new one automatically. To suppress this warning, create a VRMLookAtQuaternionProxy manually"),r=new zn(e.lookAt),r.name="VRMLookAtQuaternionProxy",e.scene.add(r)):r.name===""&&(console.warn("createVRMAnimationClip: VRMLookAtQuaternionProxy is found but its name is not set. Setting the name automatically. To suppress this warning, set the name manually"),r.name="VRMLookAtQuaternionProxy");const o=ia(t,`${r.name}.quaternion`);o!=null&&n.push(o)}return new xr("Clip",t.duration,n)}var oa=class{constructor(){this.duration=0,this.restHipsPosition=new g,this.humanoidTracks={translation:new Map,rotation:new Map},this.expressionTracks={preset:new Map,custom:new Map},this.lookAtTrack=null}};function jn(t,e){const n=t.length,i=[];let r=[],o=0;for(let s=0;s<n;s++){const l=t[s];o<=0&&(o=e,r=[],i.push(r)),r.push(l),o--}return i}var sa=new Y,ye=new g,at=new T,Gn=new T,aa=new T,la=new Set(["1.0","1.0-draft"]),ua=new Set(Object.values(js)),da=class{constructor(t){this.parser=t}get name(){return"VRMC_vrm_animation"}afterRoot(t){return Dn(this,null,function*(){var e,n,i;const r=t.parser.json,o=r.extensionsUsed;if(o==null||o.indexOf(this.name)==-1)return;const s=(e=r.extensions)==null?void 0:e[this.name];if(s==null)return;const l=s.specVersion;if(l==null)console.warn("VRMAnimationLoaderPlugin: specVersion of the VRMA is not defined. Consider updating the animation file. Assuming the spec version is 1.0.");else{if(!la.has(l)){console.warn(`VRMAnimationLoaderPlugin: Unknown VRMC_vrm_animation spec version: ${l}`);return}l==="1.0-draft"&&console.warn("VRMAnimationLoaderPlugin: Using a draft spec version: 1.0-draft. Some behaviors may be different. Consider updating the animation file.")}const a=this._createNodeMap(s),u=yield this._createBoneWorldMatrixMap(t,s),h=(i=(n=s.humanoid)==null?void 0:n.humanBones.hips)==null?void 0:i.node,d=h!=null?yield t.parser.getDependency("node",h):null,c=new g;d==null||d.getWorldPosition(c),c.y<.001&&console.warn("VRMAnimationLoaderPlugin: The loaded VRM Animation might violate the VRM T-pose (The y component of the rest hips position is approximately zero or below.)");const f=t.animations.map((m,_)=>{const v=r.animations[_],M=this._parseAnimation(m,v,a,u);return M.restHipsPosition=c,M});t.userData.vrmAnimations=f})}_createNodeMap(t){var e,n,i,r,o;const s=new Map,l=new Map,a=(e=t.humanoid)==null?void 0:e.humanBones;a&&Object.entries(a).forEach(([c,p])=>{const f=p==null?void 0:p.node;f!=null&&s.set(f,c)});const u=(n=t.expressions)==null?void 0:n.preset;u&&Object.entries(u).forEach(([c,p])=>{const f=p==null?void 0:p.node;f!=null&&l.set(f,c)});const h=(i=t.expressions)==null?void 0:i.custom;h&&Object.entries(h).forEach(([c,p])=>{const{node:f}=p;l.set(f,c)});const d=(o=(r=t.lookAt)==null?void 0:r.node)!=null?o:null;return{humanoidIndexToName:s,expressionsIndexToName:l,lookAtIndex:d}}_createBoneWorldMatrixMap(t,e){return Dn(this,null,function*(){var n,i;t.scene.updateWorldMatrix(!1,!0);const r=yield t.parser.getDependencies("node"),o=new Map;if(e.humanoid==null)return o;for(const[s,l]of Object.entries(e.humanoid.humanBones)){const a=l==null?void 0:l.node;if(a!=null){const u=r[a];o.set(s,u.matrixWorld),s==="hips"&&o.set("hipsParent",(i=(n=u.parent)==null?void 0:n.matrixWorld)!=null?i:sa)}}return o})}_parseAnimation(t,e,n,i){const r=t.tracks,o=e.channels,s=new oa;return s.duration=t.duration,o.forEach((l,a)=>{const{node:u,path:h}=l.target,d=r[a];if(u==null)return;const c=n.humanoidIndexToName.get(u);if(c!=null){let f=kn[c];for(;f!=null&&i.get(f)==null;)f=kn[f];if(f==null&&(f="hipsParent"),h==="translation")if(c!=="hips")console.warn(`The loading animation contains a translation track for ${c}, which is not permitted in the VRMC_vrm_animation spec. ignoring the track`);else{const m=i.get("hipsParent"),_=jn(d.values,3).flatMap(M=>ye.fromArray(M).applyMatrix4(m).toArray()),v=d.clone();v.values=new Float32Array(_),s.humanoidTracks.translation.set(c,v)}else if(h==="rotation"){const m=i.get(c),_=i.get(f);m.decompose(ye,at,ye),at.invert(),_.decompose(ye,Gn,ye);const v=jn(d.values,4).flatMap(R=>aa.fromArray(R).premultiply(Gn).multiply(at).toArray()),M=d.clone();M.values=new Float32Array(v),s.humanoidTracks.rotation.set(c,M)}else throw new Error(`Invalid path "${h}"`);return}const p=n.expressionsIndexToName.get(u);if(p!=null){if(h==="translation"){const f=d.times,m=new Float32Array(d.values.length/3);for(let v=0;v<m.length;v++)m[v]=d.values[3*v];const _=new Mr(`${p}.weight`,f,m);ua.has(p)?s.expressionTracks.preset.set(p,_):s.expressionTracks.custom.set(p,_)}else throw new Error(`Invalid path "${h}"`);return}if(u===n.lookAtIndex)if(h==="rotation")s.lookAtTrack=d;else throw new Error(`Invalid path "${h}"`)}),s}};/*!
 * @pixiv/three-vrm-core v3.5.5
 * The implementation of core features of VRM, for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-core is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */const He="idle",lt=.3;class ha{constructor(e){U(this,"mixer");U(this,"actions",new Map);U(this,"current",null);U(this,"loader",new ei);this.vrm=e,this.mixer=new wr(e.scene),this.loader.register(n=>new da(n)),this.mixer.addEventListener("finished",()=>{this.playIdle()})}async load(e,n){try{const r=(await this.loader.loadAsync(n)).userData.vrmAnimations??[];if(!r.length)return console.warn(`[VRM] ${n} has no VRM animation`),!1;const o=ra(r[0],this.vrm),s=this.mixer.clipAction(o);return e===He?s.setLoop(Rr,Number.POSITIVE_INFINITY):(s.setLoop(Tr,1),s.clampWhenFinished=!0),this.actions.set(e,s),!0}catch(i){return console.warn(`[VRM] failed to load motion ${e}:`,i),!1}}hasClip(e){return this.actions.has(e)}crossfadeTo(e){e.reset().fadeIn(lt).play(),this.current&&this.current!==e&&this.current.fadeOut(lt),this.current=e}playIdle(){const e=this.actions.get(He);if(!e){this.current&&this.current.fadeOut(lt),this.current=null;return}this.current!==e&&this.crossfadeTo(e)}playOnce(e){const n=this.actions.get(e);return n?(this.crossfadeTo(n),!0):(console.warn(`[VRM] motion clip "${e}" not loaded; staying idle`),!1)}stop(){this.playIdle()}update(e){this.mixer.update(e)}dispose(){this.mixer.stopAllAction(),this.actions.clear(),this.current=null}}const Xn=2,qn=4,Yn=.05,Qn=.1;class ca{constructor(e=Math.random){U(this,"phase","wait");U(this,"remaining");U(this,"rng");this.rng=e,this.remaining=Xn+this.rng()*qn}update(e){return this.remaining-=e,this.phase==="wait"?this.remaining>0?0:(this.phase="close",this.remaining=Yn,.01):this.phase==="close"?this.remaining>0?1-Math.max(0,this.remaining/Yn):(this.phase="open",this.remaining=Qn,1):this.remaining>0?Math.max(0,this.remaining/Qn):(this.phase="wait",this.remaining=Xn+this.rng()*qn,0)}}const Si=.35,Ai={values:new Float32Array([Si]),frameSeconds:Number.POSITIVE_INFINITY};function ut(t,e){return String.fromCharCode(t.getUint8(e),t.getUint8(e+1),t.getUint8(e+2),t.getUint8(e+3))}function pa(t){if(t.byteLength<12)return null;const e=new DataView(t);if(ut(e,0)!=="RIFF"||ut(e,8)!=="WAVE")return null;let n=12,i=0,r=0,o=0,s=0;for(;n+8<=t.byteLength;){const l=ut(e,n),a=e.getUint32(n+4,!0),u=n+8;if(l==="fmt "){if(u+16>t.byteLength)return null;s=e.getUint16(u,!0),r=e.getUint16(u+2,!0),i=e.getUint32(u+4,!0),o=e.getUint16(u+14,!0)}else if(l==="data"){if(s!==1||o!==16||r<1||i<1)return null;const h=Math.min(t.byteLength,u+a),d=Math.floor((h-u)/2),c=new Int16Array(d);for(let p=0;p<d;p++)c[p]=e.getInt16(u+p*2,!0);return{sampleRate:i,channels:r,samples:c}}n=u+a+a%2}return null}function fa(t,e=.02){const n=Math.max(1,Math.round(t.sampleRate*e))*t.channels,i=Math.ceil(t.samples.length/n),r=new Float32Array(i);let o=0;for(let s=0;s<i;s++){let l=0;const a=s*n,u=Math.min(t.samples.length,a+n);for(let h=a;h<u;h++){const d=Math.abs(t.samples[h]);d>l&&(l=d)}r[s]=l,l>o&&(o=l)}if(o>0)for(let s=0;s<i;s++)r[s]/=o;return{values:r,frameSeconds:e}}function ma(t,e){if(e<0)return 0;if(t===Ai)return Si;const n=Math.floor(e/t.frameSeconds);return n<t.values.length?t.values[n]:0}function _a(t){const e=1/(1+Math.exp(-45*t+5));return e<.1?0:e}function ga(t){try{const e=atob(t),n=new Uint8Array(e.length);for(let i=0;i<e.length;i++)n[i]=e.charCodeAt(i);return n.buffer}catch{return null}}function va(t){const e=t.indexOf(",");if(e<0)return null;const n=ga(t.slice(e+1));if(!n)return null;const i=pa(n);return i?fa(i):null}const Ma=20;class xa{constructor(){U(this,"audio",null);U(this,"envelope",null);U(this,"smoothed",0)}begin(e){this.audio=e;const n=va(e.src);n||console.warn("[VRM] could not parse WAV for lip sync; using constant mouth"),this.envelope=n??Ai}stop(){this.audio=null,this.envelope=null,this.smoothed=0}update(e){let n=0;const i=this.audio;return i&&this.envelope&&!i.paused&&!i.ended&&(n=_a(ma(this.envelope,i.currentTime))),this.smoothed+=(n-this.smoothed)*Math.min(1,e*Ma),this.smoothed}}class ya{constructor(e,n,i){U(this,"lip",new xa);U(this,"blink",new ca);U(this,"elapsed",0);this.vrm=e,this.motions=n,this.expressions=i}beginSegment(e,n){this.lip.begin(e),n.expression!==void 0&&this.expressions.setEmotion(String(n.expression)),n.motion&&Zn(n.motion)&&this.motions.playOnce(n.motion.clip)}stop(){this.lip.stop(),this.motions.stop()}resetExpression(){this.expressions.clear()}update(e){var n,i,r;if(this.elapsed+=e,this.expressions.setMouth(this.lip.update(e)),this.expressions.update(e),(n=this.vrm.expressionManager)==null||n.setValue("blink",this.blink.update(e)),!this.motions.hasClip(He)){const o=(i=this.vrm.humanoid)==null?void 0:i.getNormalizedBoneNode("spine"),s=(r=this.vrm.humanoid)==null?void 0:r.getNormalizedBoneNode("chest");o&&(o.rotation.z=Math.sin(this.elapsed*.8)*.01),s&&(s.rotation.x=Math.sin(this.elapsed*1.6)*.01)}this.motions.update(e),this.vrm.update(e)}}const $n={distance:1.6,height:1.35};function Pa(){var d,c;const{t}=or(),{modelInfo:e}=sr(),n=Pe.useRef(null),[i,r]=Pe.useState(!1),o=(e==null?void 0:e.lookAtPointer)!==!1,s=Pe.useRef(o);s.current=o;const l=(e==null?void 0:e.url)??"",a=((d=e==null?void 0:e.camera)==null?void 0:d.distance)??$n.distance,u=((c=e==null?void 0:e.camera)==null?void 0:c.height)??$n.height,h=JSON.stringify(Object.values((e==null?void 0:e.motionMap)??{}).filter(Zn).map(p=>p.clip).sort());return Pe.useEffect(()=>{const p=n.current;if(!p||!l)return;r(!1);let f=!1,m=0,_=null,v=null,M=null,R=null,y;try{y=new Sr({antialias:!0,alpha:!0,powerPreference:"high-performance"})}catch(b){console.warn("[VRM] WebGL is unavailable:",b),r(!0);return}y.setPixelRatio(Math.min(2,window.devicePixelRatio||1)),y.setClearColor(0,0),p.appendChild(y.domElement);const x=new Ar,w=new Er(30,1,.1,50);w.position.set(0,u,a),w.lookAt(0,u,0),x.add(new Pr(16777215,4473924,1));const S=new Lr(16777215,1.2);S.position.set(1,2,3),x.add(S);const A=new he;A.position.set(0,u,a),x.add(A);const C=()=>{const b=Math.max(1,p.clientWidth),V=Math.max(1,p.clientHeight);y.setSize(b,V,!1),w.aspect=b/V,w.updateProjectionMatrix()},P=new ResizeObserver(C);P.observe(p),C();const L=b=>{if(!s.current){A.position.set(0,u,a);return}const V=p.getBoundingClientRect(),$=(b.clientX-V.left)/V.width*2-1,N=-((b.clientY-V.top)/V.height*2-1);A.position.set($*.6,u+N*.4,a*.6)};window.addEventListener("pointermove",L);const O=new ei;O.register(b=>new Ms(b)),O.load(l,async b=>{if(f)return;const V=b.userData.vrm;if(!V){console.warn("[VRM] file has no VRM extension:",l),r(!0),Yt.create({id:"vrm-load-failed",title:t("error.vrmLoad"),type:"error",duration:6e3});return}q.removeUnnecessaryVertices(b.scene),q.combineSkeletons(b.scene),q.rotateVRM0(V),_=V,_.lookAt&&(_.lookAt.target=A),x.add(_.scene),v=new ha(_);const $=l.slice(0,l.lastIndexOf("/")),N=[He,...JSON.parse(h)];if(await Promise.all(N.map(Z=>v.load(Z,`${$}/motions/${Z}.vrma`))),f)return;v.playIdle();const Te=new zs({has:Z=>{var ee;return!!((ee=_==null?void 0:_.expressionManager)!=null&&ee.getExpression(Z))},setValue:(Z,ee)=>{var fe;return(fe=_==null?void 0:_.expressionManager)==null?void 0:fe.setValue(Z,ee)}});M=new ya(_,v,Te),R=lr(M)},void 0,b=>{f||(console.warn("[VRM] load failed:",b),r(!0),Yt.create({id:"vrm-load-failed",title:t("error.vrmLoad"),type:"error",duration:6e3}))});const H=new br;let W=!0;const Q=()=>{if(!W)return;m=window.requestAnimationFrame(Q);const b=Math.min(H.getDelta(),.1);M==null||M.update(b),y.render(x,w)},k=()=>{document.hidden?(W=!1,window.cancelAnimationFrame(m)):W||(W=!0,H.getDelta(),Q())};return document.addEventListener("visibilitychange",k),Q(),()=>{f=!0,W=!1,window.cancelAnimationFrame(m),document.removeEventListener("visibilitychange",k),window.removeEventListener("pointermove",L),P.disconnect(),R==null||R(),v==null||v.dispose(),_&&(x.remove(_.scene),q.deepDispose(_.scene)),y.dispose(),y.forceContextLoss(),y.domElement.remove()}},[l,a,u,h,t]),ar.jsx("div",{ref:n,"data-avatar-renderer":"vrm","data-avatar-error":i||void 0,style:{position:"absolute",inset:0,overflow:"hidden"}})}export{Pa as VRMAvatar};

var rr=Object.defineProperty;var or=(t,e,n)=>e in t?rr(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n;var N=(t,e,n)=>or(t,typeof e!="symbol"?e+"":e,n);import{i as Jn,u as sr,a as ar,r as me,t as Qt,j as lr,b as ur}from"./main-Czde5y8M.js";import{M as dr,B as hr,V as _,Q as T,E as we,a as I,G as Re,b as $t,D as Zt,c as Jt,L as it,d as Ct,I as cr,S as pr,T as fr,U as mr,e as Ie,f as Z,C as j,g as K,O as ye,h as D,i as gr,j as ie,k as _r,l as vr,m as Kt,n as Ot,A as Mr,R as Ze,o as ke,p as Kn,q as ei,N as xr,r as yr,s as wr,t as Rr,u as ti,v as Tr,w as Sr,W as Er,x as Ar,P as Pr,H as Lr,y as br,z as Ir}from"./GLTFLoader-DsdVE1tb.js";/*!
 * @pixiv/three-vrm v3.5.5
 * VRM file loader for three.js.
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */var je=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),b=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),en=class extends ye{constructor(t){super(),this.weight=0,this.isBinary=!1,this.overrideBlink="none",this.overrideLookAt="none",this.overrideMouth="none",this._binds=[],this.name=`VRMExpression_${t}`,this.expressionName=t,this.type="VRMExpression",this.visible=!1}get binds(){return this._binds}get overrideBlinkAmount(){return this.overrideBlink==="block"?0<this.outputWeight?1:0:this.overrideBlink==="blend"?this.outputWeight:0}get overrideLookAtAmount(){return this.overrideLookAt==="block"?0<this.outputWeight?1:0:this.overrideLookAt==="blend"?this.outputWeight:0}get overrideMouthAmount(){return this.overrideMouth==="block"?0<this.outputWeight?1:0:this.overrideMouth==="blend"?this.outputWeight:0}get outputWeight(){return this.isBinary?this.weight>.5?1:0:this.weight}addBind(t){this._binds.push(t)}deleteBind(t){const e=this._binds.indexOf(t);e>=0&&this._binds.splice(e,1)}applyWeight(t){var e;let n=this.outputWeight;n*=(e=t==null?void 0:t.multiplier)!=null?e:1,this.isBinary&&n<1&&(n=0),this._binds.forEach(i=>i.applyWeight(n))}clearAppliedWeight(){this._binds.forEach(t=>t.clearAppliedWeight())}};function ni(t,e,n){var i,r;const o=t.parser.json,s=(i=o.nodes)==null?void 0:i[e];if(s==null)return console.warn(`extractPrimitivesInternal: Attempt to use nodes[${e}] of glTF but the node doesn't exist`),null;const l=s.mesh;if(l==null)return null;const a=(r=o.meshes)==null?void 0:r[l];if(a==null)return console.warn(`extractPrimitivesInternal: Attempt to use meshes[${l}] of glTF but the mesh doesn't exist`),null;const u=a.primitives.length,h=[];return n.traverse(d=>{h.length<u&&d.isMesh&&h.push(d)}),h}function tn(t,e){return b(this,null,function*(){const n=yield t.parser.getDependency("node",e);return ni(t,e,n)})}function nn(t){return b(this,null,function*(){const e=yield t.parser.getDependencies("node"),n=new Map;return e.forEach((i,r)=>{const o=ni(t,r,i);o!=null&&n.set(r,o)}),n})}var Et={Aa:"aa",Ih:"ih",Ou:"ou",Ee:"ee",Oh:"oh",Blink:"blink",Happy:"happy",Angry:"angry",Sad:"sad",Relaxed:"relaxed",LookUp:"lookUp",Surprised:"surprised",LookDown:"lookDown",LookLeft:"lookLeft",LookRight:"lookRight",BlinkLeft:"blinkLeft",BlinkRight:"blinkRight",Neutral:"neutral"};function ii(t){return Math.max(Math.min(t,1),0)}var rn=class ri{constructor(){this.blinkExpressionNames=["blink","blinkLeft","blinkRight"],this.lookAtExpressionNames=["lookLeft","lookRight","lookUp","lookDown"],this.mouthExpressionNames=["aa","ee","ih","oh","ou"],this._expressions=[],this._expressionMap={}}get expressions(){return this._expressions.concat()}get expressionMap(){return Object.assign({},this._expressionMap)}get presetExpressionMap(){const e={},n=new Set(Object.values(Et));return Object.entries(this._expressionMap).forEach(([i,r])=>{n.has(i)&&(e[i]=r)}),e}get customExpressionMap(){const e={},n=new Set(Object.values(Et));return Object.entries(this._expressionMap).forEach(([i,r])=>{n.has(i)||(e[i]=r)}),e}copy(e){return this._expressions.concat().forEach(i=>{this.unregisterExpression(i)}),e._expressions.forEach(i=>{this.registerExpression(i)}),this.blinkExpressionNames=e.blinkExpressionNames.concat(),this.lookAtExpressionNames=e.lookAtExpressionNames.concat(),this.mouthExpressionNames=e.mouthExpressionNames.concat(),this}clone(){return new ri().copy(this)}getExpression(e){var n;return(n=this._expressionMap[e])!=null?n:null}registerExpression(e){this._expressions.push(e),this._expressionMap[e.expressionName]=e}unregisterExpression(e){const n=this._expressions.indexOf(e);n===-1&&console.warn("VRMExpressionManager: The specified expressions is not registered"),this._expressions.splice(n,1),delete this._expressionMap[e.expressionName]}getValue(e){var n;const i=this.getExpression(e);return(n=i==null?void 0:i.weight)!=null?n:null}setValue(e,n){const i=this.getExpression(e);i&&(i.weight=ii(n))}resetValues(){this._expressions.forEach(e=>{e.weight=0})}getExpressionTrackName(e){const n=this.getExpression(e);return n?`${n.name}.weight`:null}update(){const e=this._calculateWeightMultipliers();this._expressions.forEach(n=>{n.clearAppliedWeight()}),this._expressions.forEach(n=>{let i=1;const r=n.expressionName;this.blinkExpressionNames.indexOf(r)!==-1&&(i*=e.blink),this.lookAtExpressionNames.indexOf(r)!==-1&&(i*=e.lookAt),this.mouthExpressionNames.indexOf(r)!==-1&&(i*=e.mouth),n.applyWeight({multiplier:i})})}_calculateWeightMultipliers(){let e=1,n=1,i=1;return this._expressions.forEach(r=>{e-=r.overrideBlinkAmount,n-=r.overrideLookAtAmount,i-=r.overrideMouthAmount}),e=Math.max(0,e),n=Math.max(0,n),i=Math.max(0,i),{blink:e,lookAt:n,mouth:i}}},Ce={Color:"color",EmissionColor:"emissionColor",ShadeColor:"shadeColor",RimColor:"rimColor",OutlineColor:"outlineColor"},Cr={_Color:Ce.Color,_EmissionColor:Ce.EmissionColor,_ShadeColor:Ce.ShadeColor,_RimColor:Ce.RimColor,_OutlineColor:Ce.OutlineColor},Or=new j,oi=class si{constructor({material:e,type:n,targetValue:i,targetAlpha:r}){this.material=e,this.type=n,this.targetValue=i,this.targetAlpha=r??1;const o=this._initColorBindState(),s=this._initAlphaBindState();this._state={color:o,alpha:s}}applyWeight(e){const{color:n,alpha:i}=this._state;if(n!=null){const{propertyName:r,deltaValue:o}=n,s=this.material[r];s!=null&&s.add(Or.copy(o).multiplyScalar(e))}if(i!=null){const{propertyName:r,deltaValue:o}=i;this.material[r]!=null&&(this.material[r]+=o*e)}}clearAppliedWeight(){const{color:e,alpha:n}=this._state;if(e!=null){const{propertyName:i,initialValue:r}=e,o=this.material[i];o!=null&&o.copy(r)}if(n!=null){const{propertyName:i,initialValue:r}=n;this.material[i]!=null&&(this.material[i]=r)}}_initColorBindState(){var e,n,i;const{material:r,type:o,targetValue:s}=this,l=this._getPropertyNameMap(),a=(n=(e=l==null?void 0:l[o])==null?void 0:e[0])!=null?n:null;if(a==null)return console.warn(`Tried to add a material color bind to the material ${(i=r.name)!=null?i:"(no name)"}, the type ${o} but the material or the type is not supported.`),null;const h=r[a].clone(),d=new j(s.r-h.r,s.g-h.g,s.b-h.b);return{propertyName:a,initialValue:h,deltaValue:d}}_initAlphaBindState(){var e,n,i;const{material:r,type:o,targetAlpha:s}=this,l=this._getPropertyNameMap(),a=(n=(e=l==null?void 0:l[o])==null?void 0:e[1])!=null?n:null;if(a==null&&s!==1)return console.warn(`Tried to add a material alpha bind to the material ${(i=r.name)!=null?i:"(no name)"}, the type ${o} but the material or the type does not support alpha.`),null;if(a==null)return null;const u=r[a],h=s-u;return{propertyName:a,initialValue:u,deltaValue:h}}_getPropertyNameMap(){var e,n;return(n=(e=Object.entries(si._propertyNameMapMap).find(([i])=>this.material[i]===!0))==null?void 0:e[1])!=null?n:null}};oi._propertyNameMapMap={isMeshStandardMaterial:{color:["color","opacity"],emissionColor:["emissive",null]},isMeshBasicMaterial:{color:["color","opacity"]},isMToonMaterial:{color:["color","opacity"],emissionColor:["emissive",null],outlineColor:["outlineColorFactor",null],matcapColor:["matcapFactor",null],rimColor:["parametricRimColorFactor",null],shadeColor:["shadeColorFactor",null]}};var on=oi,Je=class{constructor({primitives:t,index:e,weight:n}){this.primitives=t,this.index=e,this.weight=n}applyWeight(t){this.primitives.forEach(e=>{var n;((n=e.morphTargetInfluences)==null?void 0:n[this.index])!=null&&(e.morphTargetInfluences[this.index]+=this.weight*t)})}clearAppliedWeight(){this.primitives.forEach(t=>{var e;((e=t.morphTargetInfluences)==null?void 0:e[this.index])!=null&&(t.morphTargetInfluences[this.index]=0)})}},sn=new ke,ai=class li{constructor({material:e,scale:n,offset:i}){var r,o;this.material=e,this.scale=n,this.offset=i;const s=(r=Object.entries(li._propertyNamesMap).find(([l])=>e[l]===!0))==null?void 0:r[1];s==null?(console.warn(`Tried to add a texture transform bind to the material ${(o=e.name)!=null?o:"(no name)"} but the material is not supported.`),this._properties=[]):(this._properties=[],s.forEach(l=>{var a;const u=(a=e[l])==null?void 0:a.clone();if(!u)return null;e[l]=u;const h=u.offset.clone(),d=u.repeat.clone(),c=i.clone().sub(h),f=n.clone().sub(d);this._properties.push({name:l,initialOffset:h,deltaOffset:c,initialScale:d,deltaScale:f})}))}applyWeight(e){this._properties.forEach(n=>{const i=this.material[n.name];i!==void 0&&(i.offset.add(sn.copy(n.deltaOffset).multiplyScalar(e)),i.repeat.add(sn.copy(n.deltaScale).multiplyScalar(e)))})}clearAppliedWeight(){this._properties.forEach(e=>{const n=this.material[e.name];n!==void 0&&(n.offset.copy(e.initialOffset),n.repeat.copy(e.initialScale))})}};ai._propertyNamesMap={isMeshStandardMaterial:["map","emissiveMap","bumpMap","normalMap","displacementMap","roughnessMap","metalnessMap","alphaMap"],isMeshBasicMaterial:["map","specularMap","alphaMap"],isMToonMaterial:["map","normalMap","emissiveMap","shadeMultiplyTexture","rimMultiplyTexture","outlineWidthMultiplyTexture","uvAnimationMaskTexture"]};var an=ai,Ur=new Set(["1.0","1.0-beta"]),ui=class di{get name(){return"VRMExpressionLoaderPlugin"}constructor(e){this.parser=e}afterRoot(e){return b(this,null,function*(){e.userData.vrmExpressionManager=yield this._import(e)})}_import(e){return b(this,null,function*(){const n=yield this._v1Import(e);if(n)return n;const i=yield this._v0Import(e);return i||null})}_v1Import(e){return b(this,null,function*(){var n,i;const r=this.parser.json;if(!(((n=r.extensionsUsed)==null?void 0:n.indexOf("VRMC_vrm"))!==-1))return null;const s=(i=r.extensions)==null?void 0:i.VRMC_vrm;if(!s)return null;const l=s.specVersion;if(!Ur.has(l))return console.warn(`VRMExpressionLoaderPlugin: Unknown VRMC_vrm specVersion "${l}"`),null;const a=s.expressions;if(!a)return null;const u=new Set(Object.values(Et)),h=new Map;a.preset!=null&&Object.entries(a.preset).forEach(([c,f])=>{if(f!=null){if(!u.has(c)){console.warn(`VRMExpressionLoaderPlugin: Unknown preset name "${c}" detected. Ignoring the expression`);return}h.set(c,f)}}),a.custom!=null&&Object.entries(a.custom).forEach(([c,f])=>{if(u.has(c)){console.warn(`VRMExpressionLoaderPlugin: Custom expression cannot have preset name "${c}". Ignoring the expression`);return}h.set(c,f)});const d=new rn;return yield Promise.all(Array.from(h.entries()).map(c=>b(this,[c],function*([f,m]){var p,g,v,M,w,R,y;const x=new en(f);if(e.scene.add(x),x.isBinary=(p=m.isBinary)!=null?p:!1,x.overrideBlink=(g=m.overrideBlink)!=null?g:"none",x.overrideLookAt=(v=m.overrideLookAt)!=null?v:"none",x.overrideMouth=(M=m.overrideMouth)!=null?M:"none",(w=m.morphTargetBinds)==null||w.forEach(S=>b(this,null,function*(){var E;if(S.node===void 0||S.index===void 0)return;const C=yield tn(e,S.node),P=S.index;if(!C.every(L=>Array.isArray(L.morphTargetInfluences)&&P<L.morphTargetInfluences.length)){console.warn(`VRMExpressionLoaderPlugin: ${m.name} attempts to index morph #${P} but not found.`);return}x.addBind(new Je({primitives:C,index:P,weight:(E=S.weight)!=null?E:1}))})),m.materialColorBinds||m.textureTransformBinds){const S=[];e.scene.traverse(E=>{const C=E.material;C&&(Array.isArray(C)?S.push(...C):S.push(C))}),(R=m.materialColorBinds)==null||R.forEach(E=>b(this,null,function*(){S.filter(P=>{var L;const O=(L=this.parser.associations.get(P))==null?void 0:L.materials;return E.material===O}).forEach(P=>{x.addBind(new on({material:P,type:E.type,targetValue:new j().fromArray(E.targetValue),targetAlpha:E.targetValue[3]}))})})),(y=m.textureTransformBinds)==null||y.forEach(E=>b(this,null,function*(){S.filter(P=>{var L;const O=(L=this.parser.associations.get(P))==null?void 0:L.materials;return E.material===O}).forEach(P=>{var L,O;x.addBind(new an({material:P,offset:new ke().fromArray((L=E.offset)!=null?L:[0,0]),scale:new ke().fromArray((O=E.scale)!=null?O:[1,1])}))})}))}d.registerExpression(x)}))),d})}_v0Import(e){return b(this,null,function*(){var n;const i=this.parser.json,r=(n=i.extensions)==null?void 0:n.VRM;if(!r)return null;const o=r.blendShapeMaster;if(!o)return null;const s=new rn,l=o.blendShapeGroups;if(!l)return s;const a=new Set;return yield Promise.all(l.map(u=>b(this,null,function*(){var h;const d=u.presetName,c=d!=null&&di.v0v1PresetNameMap[d]||null,f=c??u.name;if(f==null){console.warn("VRMExpressionLoaderPlugin: One of custom expressions has no name. Ignoring the expression");return}if(a.has(f)){console.warn(`VRMExpressionLoaderPlugin: An expression preset ${d} has duplicated entries. Ignoring the expression`);return}a.add(f);const m=new en(f);e.scene.add(m),m.isBinary=(h=u.isBinary)!=null?h:!1,u.binds&&u.binds.forEach(g=>b(this,null,function*(){var v;if(g.mesh===void 0||g.index===void 0)return;const M=[];if((v=i.nodes)==null||v.forEach((R,y)=>{R.mesh===g.mesh&&M.push(y)}),M.length===0){console.warn(`VRMExpressionLoaderPlugin: ${u.name} attempts to bind a morph target to the mesh #${g.mesh} but the mesh is not found or not used in the scene. Ignoring the bind.`);return}const w=g.index;yield Promise.all(M.map(R=>b(this,null,function*(){var y;const x=yield tn(e,R);if(!x.every(S=>Array.isArray(S.morphTargetInfluences)&&w<S.morphTargetInfluences.length)){console.warn(`VRMExpressionLoaderPlugin: ${u.name} attempts to index ${w}th morph but not found.`);return}m.addBind(new Je({primitives:x,index:w,weight:.01*((y=g.weight)!=null?y:100)}))})))}));const p=u.materialValues;p&&p.length!==0&&p.forEach(g=>{if(g.materialName===void 0||g.propertyName===void 0||g.targetValue===void 0)return;const v=[];e.scene.traverse(w=>{if(w.material){const R=w.material;Array.isArray(R)?v.push(...R.filter(y=>(y.name===g.materialName||y.name===g.materialName+" (Outline)")&&v.indexOf(y)===-1)):R.name===g.materialName&&v.indexOf(R)===-1&&v.push(R)}});const M=g.propertyName;v.forEach(w=>{if(M==="_MainTex_ST"){const y=new ke(g.targetValue[0],g.targetValue[1]),x=new ke(g.targetValue[2],g.targetValue[3]);x.y=1-x.y-y.y,m.addBind(new an({material:w,scale:y,offset:x}));return}const R=Cr[M];if(R){m.addBind(new on({material:w,type:R,targetValue:new j().fromArray(g.targetValue),targetAlpha:g.targetValue[3]}));return}console.warn(M+" is not supported")})}),s.registerExpression(m)}))),s})}};ui.v0v1PresetNameMap={a:"aa",e:"ee",i:"ih",o:"oh",u:"ou",blink:"blink",joy:"happy",angry:"angry",sorrow:"sad",fun:"relaxed",lookup:"lookUp",lookdown:"lookDown",lookleft:"lookLeft",lookright:"lookRight",blink_l:"blinkLeft",blink_r:"blinkRight",neutral:"neutral"};var Nr=ui,Ut=class Me{constructor(e,n){this._firstPersonOnlyLayer=Me.DEFAULT_FIRSTPERSON_ONLY_LAYER,this._thirdPersonOnlyLayer=Me.DEFAULT_THIRDPERSON_ONLY_LAYER,this._initializedLayers=!1,this.humanoid=e,this.meshAnnotations=n}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMFirstPerson: humanoid must be same in order to copy");return this.meshAnnotations=e.meshAnnotations.map(n=>({meshes:n.meshes.concat(),type:n.type})),this}clone(){return new Me(this.humanoid,this.meshAnnotations).copy(this)}get firstPersonOnlyLayer(){return this._firstPersonOnlyLayer}get thirdPersonOnlyLayer(){return this._thirdPersonOnlyLayer}setup({firstPersonOnlyLayer:e=Me.DEFAULT_FIRSTPERSON_ONLY_LAYER,thirdPersonOnlyLayer:n=Me.DEFAULT_THIRDPERSON_ONLY_LAYER}={}){this._initializedLayers||(this._firstPersonOnlyLayer=e,this._thirdPersonOnlyLayer=n,this.meshAnnotations.forEach(i=>{i.meshes.forEach(r=>{i.type==="firstPersonOnly"?(r.layers.set(this._firstPersonOnlyLayer),r.traverse(o=>o.layers.set(this._firstPersonOnlyLayer))):i.type==="thirdPersonOnly"?(r.layers.set(this._thirdPersonOnlyLayer),r.traverse(o=>o.layers.set(this._thirdPersonOnlyLayer))):i.type==="auto"&&this._createHeadlessModel(r)})}),this._initializedLayers=!0)}_excludeTriangles(e,n,i,r){let o=0;if(n!=null&&n.length>0)for(let s=0;s<e.length;s+=3){const l=e[s],a=e[s+1],u=e[s+2],h=n[l],d=i[l];if(h[0]>0&&r.includes(d[0])||h[1]>0&&r.includes(d[1])||h[2]>0&&r.includes(d[2])||h[3]>0&&r.includes(d[3]))continue;const c=n[a],f=i[a];if(c[0]>0&&r.includes(f[0])||c[1]>0&&r.includes(f[1])||c[2]>0&&r.includes(f[2])||c[3]>0&&r.includes(f[3]))continue;const m=n[u],p=i[u];m[0]>0&&r.includes(p[0])||m[1]>0&&r.includes(p[1])||m[2]>0&&r.includes(p[2])||m[3]>0&&r.includes(p[3])||(e[o++]=l,e[o++]=a,e[o++]=u)}return o}_createErasedMesh(e,n){const i=new vr(e.geometry.clone(),e.material);i.name=`${e.name}(erase)`,i.frustumCulled=e.frustumCulled,i.layers.set(this._firstPersonOnlyLayer);const r=i.geometry,o=r.getAttribute("skinIndex"),s=o instanceof Kt?[]:o.array,l=[];for(let p=0;p<s.length;p+=4)l.push([s[p],s[p+1],s[p+2],s[p+3]]);const a=r.getAttribute("skinWeight"),u=a instanceof Kt?[]:a.array,h=[];for(let p=0;p<u.length;p+=4)h.push([u[p],u[p+1],u[p+2],u[p+3]]);const d=r.getIndex();if(!d)throw new Error("The geometry doesn't have an index buffer");const c=Array.from(d.array),f=this._excludeTriangles(c,h,l,n),m=[];for(let p=0;p<f;p++)m[p]=c[p];return r.setIndex(m),e.onBeforeRender&&(i.onBeforeRender=e.onBeforeRender),i.bind(new Ot(e.skeleton.bones,e.skeleton.boneInverses),new K),i}_createHeadlessModelForSkinnedMesh(e,n){const i=[];if(n.skeleton.bones.forEach((o,s)=>{this._isEraseTarget(o)&&i.push(s)}),!i.length){n.layers.enable(this._thirdPersonOnlyLayer),n.layers.enable(this._firstPersonOnlyLayer);return}n.layers.set(this._thirdPersonOnlyLayer);const r=this._createErasedMesh(n,i);e.add(r)}_createHeadlessModel(e){if(e.type==="Group")if(e.layers.set(this._thirdPersonOnlyLayer),this._isEraseTarget(e))e.traverse(n=>n.layers.set(this._thirdPersonOnlyLayer));else{const n=new Re;n.name=`_headless_${e.name}`,n.layers.set(this._firstPersonOnlyLayer),e.parent.add(n),e.children.filter(i=>i.type==="SkinnedMesh").forEach(i=>{const r=i;this._createHeadlessModelForSkinnedMesh(n,r)})}else if(e.type==="SkinnedMesh"){const n=e;this._createHeadlessModelForSkinnedMesh(e.parent,n)}else this._isEraseTarget(e)&&(e.layers.set(this._thirdPersonOnlyLayer),e.traverse(n=>n.layers.set(this._thirdPersonOnlyLayer)))}_isEraseTarget(e){return e===this.humanoid.getRawBoneNode("head")?!0:e.parent?this._isEraseTarget(e.parent):!1}};Ut.DEFAULT_FIRSTPERSON_ONLY_LAYER=9;Ut.DEFAULT_THIRDPERSON_ONLY_LAYER=10;var ln=Ut,Vr=new Set(["1.0","1.0-beta"]),Dr=class{get name(){return"VRMFirstPersonLoaderPlugin"}constructor(t){this.parser=t}afterRoot(t){return b(this,null,function*(){const e=t.userData.vrmHumanoid;if(e!==null){if(e===void 0)throw new Error("VRMFirstPersonLoaderPlugin: vrmHumanoid is undefined. VRMHumanoidLoaderPlugin have to be used first");t.userData.vrmFirstPerson=yield this._import(t,e)}})}_import(t,e){return b(this,null,function*(){if(e==null)return null;const n=yield this._v1Import(t,e);if(n)return n;const i=yield this._v0Import(t,e);return i||null})}_v1Import(t,e){return b(this,null,function*(){var n,i;const r=this.parser.json;if(!(((n=r.extensionsUsed)==null?void 0:n.indexOf("VRMC_vrm"))!==-1))return null;const s=(i=r.extensions)==null?void 0:i.VRMC_vrm;if(!s)return null;const l=s.specVersion;if(!Vr.has(l))return console.warn(`VRMFirstPersonLoaderPlugin: Unknown VRMC_vrm specVersion "${l}"`),null;const a=s.firstPerson,u=[],h=yield nn(t);return Array.from(h.entries()).forEach(([d,c])=>{var f,m;const p=(f=a==null?void 0:a.meshAnnotations)==null?void 0:f.find(g=>g.node===d);u.push({meshes:c,type:(m=p==null?void 0:p.type)!=null?m:"auto"})}),new ln(e,u)})}_v0Import(t,e){return b(this,null,function*(){var n;const i=this.parser.json,r=(n=i.extensions)==null?void 0:n.VRM;if(!r)return null;const o=r.firstPerson;if(!o)return null;const s=[],l=yield nn(t);return Array.from(l.entries()).forEach(([a,u])=>{const h=i.nodes[a],d=o.meshAnnotations?o.meshAnnotations.find(c=>c.mesh===h.mesh):void 0;s.push({meshes:u,type:this._convertV0FlagToV1Type(d==null?void 0:d.firstPersonFlag)})}),new ln(e,s)})}_convertV0FlagToV1Type(t){return t==="FirstPersonOnly"?"firstPersonOnly":t==="ThirdPersonOnly"?"thirdPersonOnly":t==="Both"?"both":"auto"}},un=new _,dn=new _,kr=new T,hn=class extends Re{constructor(t){super(),this.vrmHumanoid=t,this._boneAxesMap=new Map,Object.values(t.humanBones).forEach(e=>{const n=new Mr(1);n.matrixAutoUpdate=!1,n.material.depthTest=!1,n.material.depthWrite=!1,this.add(n),this._boneAxesMap.set(e,n)})}dispose(){Array.from(this._boneAxesMap.values()).forEach(t=>{t.geometry.dispose(),t.material.dispose()})}updateMatrixWorld(t){Array.from(this._boneAxesMap.entries()).forEach(([e,n])=>{e.node.updateWorldMatrix(!0,!1),e.node.matrixWorld.decompose(un,kr,dn);const i=un.set(.1,.1,.1).divide(dn);n.matrix.copy(e.node.matrixWorld).scale(i)}),super.updateMatrixWorld(t)}},at=["hips","spine","chest","upperChest","neck","head","leftEye","rightEye","jaw","leftUpperLeg","leftLowerLeg","leftFoot","leftToes","rightUpperLeg","rightLowerLeg","rightFoot","rightToes","leftShoulder","leftUpperArm","leftLowerArm","leftHand","rightShoulder","rightUpperArm","rightLowerArm","rightHand","leftThumbMetacarpal","leftThumbProximal","leftThumbDistal","leftIndexProximal","leftIndexIntermediate","leftIndexDistal","leftMiddleProximal","leftMiddleIntermediate","leftMiddleDistal","leftRingProximal","leftRingIntermediate","leftRingDistal","leftLittleProximal","leftLittleIntermediate","leftLittleDistal","rightThumbMetacarpal","rightThumbProximal","rightThumbDistal","rightIndexProximal","rightIndexIntermediate","rightIndexDistal","rightMiddleProximal","rightMiddleIntermediate","rightMiddleDistal","rightRingProximal","rightRingIntermediate","rightRingDistal","rightLittleProximal","rightLittleIntermediate","rightLittleDistal"],Br={hips:null,spine:"hips",chest:"spine",upperChest:"chest",neck:"upperChest",head:"neck",leftEye:"head",rightEye:"head",jaw:"head",leftUpperLeg:"hips",leftLowerLeg:"leftUpperLeg",leftFoot:"leftLowerLeg",leftToes:"leftFoot",rightUpperLeg:"hips",rightLowerLeg:"rightUpperLeg",rightFoot:"rightLowerLeg",rightToes:"rightFoot",leftShoulder:"upperChest",leftUpperArm:"leftShoulder",leftLowerArm:"leftUpperArm",leftHand:"leftLowerArm",rightShoulder:"upperChest",rightUpperArm:"rightShoulder",rightLowerArm:"rightUpperArm",rightHand:"rightLowerArm",leftThumbMetacarpal:"leftHand",leftThumbProximal:"leftThumbMetacarpal",leftThumbDistal:"leftThumbProximal",leftIndexProximal:"leftHand",leftIndexIntermediate:"leftIndexProximal",leftIndexDistal:"leftIndexIntermediate",leftMiddleProximal:"leftHand",leftMiddleIntermediate:"leftMiddleProximal",leftMiddleDistal:"leftMiddleIntermediate",leftRingProximal:"leftHand",leftRingIntermediate:"leftRingProximal",leftRingDistal:"leftRingIntermediate",leftLittleProximal:"leftHand",leftLittleIntermediate:"leftLittleProximal",leftLittleDistal:"leftLittleIntermediate",rightThumbMetacarpal:"rightHand",rightThumbProximal:"rightThumbMetacarpal",rightThumbDistal:"rightThumbProximal",rightIndexProximal:"rightHand",rightIndexIntermediate:"rightIndexProximal",rightIndexDistal:"rightIndexIntermediate",rightMiddleProximal:"rightHand",rightMiddleIntermediate:"rightMiddleProximal",rightMiddleDistal:"rightMiddleIntermediate",rightRingProximal:"rightHand",rightRingIntermediate:"rightRingProximal",rightRingDistal:"rightRingIntermediate",rightLittleProximal:"rightHand",rightLittleIntermediate:"rightLittleProximal",rightLittleDistal:"rightLittleIntermediate"};function hi(t){return t.invert?t.invert():t.inverse(),t}var le=new _,ue=new T,At=class{constructor(t){this.humanBones=t,this.restPose=this.getAbsolutePose()}getAbsolutePose(){const t={};return Object.keys(this.humanBones).forEach(e=>{const n=e,i=this.getBoneNode(n);i&&(le.copy(i.position),ue.copy(i.quaternion),t[n]={position:le.toArray(),rotation:ue.toArray()})}),t}getPose(){const t={};return Object.keys(this.humanBones).forEach(e=>{const n=e,i=this.getBoneNode(n);if(!i)return;le.set(0,0,0),ue.identity();const r=this.restPose[n];r!=null&&r.position&&le.fromArray(r.position).negate(),r!=null&&r.rotation&&hi(ue.fromArray(r.rotation)),le.add(i.position),ue.premultiply(i.quaternion),t[n]={position:le.toArray(),rotation:ue.toArray()}}),t}setPose(t){Object.entries(t).forEach(([e,n])=>{const i=e,r=this.getBoneNode(i);if(!r)return;const o=this.restPose[i];o&&(n!=null&&n.position&&(r.position.fromArray(n.position),o.position&&r.position.add(le.fromArray(o.position))),n!=null&&n.rotation&&(r.quaternion.fromArray(n.rotation),o.rotation&&r.quaternion.multiply(ue.fromArray(o.rotation))))})}resetPose(){Object.entries(this.restPose).forEach(([t,e])=>{const n=this.getBoneNode(t);n&&(e!=null&&e.position&&n.position.fromArray(e.position),e!=null&&e.rotation&&n.quaternion.fromArray(e.rotation))})}getBone(t){var e;return(e=this.humanBones[t])!=null?e:void 0}getBoneNode(t){var e,n;return(n=(e=this.humanBones[t])==null?void 0:e.node)!=null?n:null}},lt=new _,Fr=new T,Hr=new _,cn=class ci extends At{static _setupTransforms(e){const n=new ye;n.name="VRMHumanoidRig";const i={},r={},o={};at.forEach(l=>{var a;const u=e.getBoneNode(l);if(u){const h=new _,d=new T;u.updateWorldMatrix(!0,!1),u.matrixWorld.decompose(h,d,lt),i[l]=h,r[l]=u.quaternion.clone();const c=new T;(a=u.parent)==null||a.matrixWorld.decompose(lt,c,lt),o[l]=c}});const s={};return at.forEach(l=>{var a;const u=e.getBoneNode(l);if(u){const h=i[l];let d=l,c;for(;c==null&&(d=Br[d],d!=null);)c=i[d];const f=new ye;f.name="Normalized_"+u.name,(d?(a=s[d])==null?void 0:a.node:n).add(f),f.position.copy(h),c&&f.position.sub(c),s[l]={node:f}}}),{rigBones:s,root:n,parentWorldRotations:o,boneRotations:r}}constructor(e){const{rigBones:n,root:i,parentWorldRotations:r,boneRotations:o}=ci._setupTransforms(e);super(n),this.original=e,this.root=i,this._parentWorldRotations=r,this._boneRotations=o}update(){at.forEach(e=>{const n=this.original.getBoneNode(e);if(n!=null){const i=this.getBoneNode(e),r=this._parentWorldRotations[e],o=Fr.copy(r).invert(),s=this._boneRotations[e];if(n.quaternion.copy(i.quaternion).multiply(r).premultiply(o).multiply(s),e==="hips"){const l=i.getWorldPosition(Hr);n.parent.updateWorldMatrix(!0,!1);const a=n.parent.matrixWorld,u=l.applyMatrix4(a.invert());n.position.copy(u)}}})}},pn=class pi{get restPose(){return console.warn("VRMHumanoid: restPose is deprecated. Use either rawRestPose or normalizedRestPose instead."),this.rawRestPose}get rawRestPose(){return this._rawHumanBones.restPose}get normalizedRestPose(){return this._normalizedHumanBones.restPose}get humanBones(){return this._rawHumanBones.humanBones}get rawHumanBones(){return this._rawHumanBones.humanBones}get normalizedHumanBones(){return this._normalizedHumanBones.humanBones}get normalizedHumanBonesRoot(){return this._normalizedHumanBones.root}constructor(e,n){var i;this.autoUpdateHumanBones=(i=n==null?void 0:n.autoUpdateHumanBones)!=null?i:!0,this._rawHumanBones=new At(e),this._normalizedHumanBones=new cn(this._rawHumanBones)}copy(e){return this.autoUpdateHumanBones=e.autoUpdateHumanBones,this._rawHumanBones=new At(e.humanBones),this._normalizedHumanBones=new cn(this._rawHumanBones),this}clone(){return new pi(this.humanBones,{autoUpdateHumanBones:this.autoUpdateHumanBones}).copy(this)}getAbsolutePose(){return console.warn("VRMHumanoid: getAbsolutePose() is deprecated. Use either getRawAbsolutePose() or getNormalizedAbsolutePose() instead."),this.getRawAbsolutePose()}getRawAbsolutePose(){return this._rawHumanBones.getAbsolutePose()}getNormalizedAbsolutePose(){return this._normalizedHumanBones.getAbsolutePose()}getPose(){return console.warn("VRMHumanoid: getPose() is deprecated. Use either getRawPose() or getNormalizedPose() instead."),this.getRawPose()}getRawPose(){return this._rawHumanBones.getPose()}getNormalizedPose(){return this._normalizedHumanBones.getPose()}setPose(e){return console.warn("VRMHumanoid: setPose() is deprecated. Use either setRawPose() or setNormalizedPose() instead."),this.setRawPose(e)}setRawPose(e){return this._rawHumanBones.setPose(e)}setNormalizedPose(e){return this._normalizedHumanBones.setPose(e)}resetPose(){return console.warn("VRMHumanoid: resetPose() is deprecated. Use either resetRawPose() or resetNormalizedPose() instead."),this.resetRawPose()}resetRawPose(){return this._rawHumanBones.resetPose()}resetNormalizedPose(){return this._normalizedHumanBones.resetPose()}getBone(e){return console.warn("VRMHumanoid: getBone() is deprecated. Use either getRawBone() or getNormalizedBone() instead."),this.getRawBone(e)}getRawBone(e){return this._rawHumanBones.getBone(e)}getNormalizedBone(e){return this._normalizedHumanBones.getBone(e)}getBoneNode(e){return console.warn("VRMHumanoid: getBoneNode() is deprecated. Use either getRawBoneNode() or getNormalizedBoneNode() instead."),this.getRawBoneNode(e)}getRawBoneNode(e){return this._rawHumanBones.getBoneNode(e)}getNormalizedBoneNode(e){return this._normalizedHumanBones.getBoneNode(e)}update(){this.autoUpdateHumanBones&&this._normalizedHumanBones.update()}},Wr={Hips:"hips",Spine:"spine",Head:"head",LeftUpperLeg:"leftUpperLeg",LeftLowerLeg:"leftLowerLeg",LeftFoot:"leftFoot",RightUpperLeg:"rightUpperLeg",RightLowerLeg:"rightLowerLeg",RightFoot:"rightFoot",LeftUpperArm:"leftUpperArm",LeftLowerArm:"leftLowerArm",LeftHand:"leftHand",RightUpperArm:"rightUpperArm",RightLowerArm:"rightLowerArm",RightHand:"rightHand"},zr=new Set(["1.0","1.0-beta"]),fn={leftThumbProximal:"leftThumbMetacarpal",leftThumbIntermediate:"leftThumbProximal",rightThumbProximal:"rightThumbMetacarpal",rightThumbIntermediate:"rightThumbProximal"},jr=class{get name(){return"VRMHumanoidLoaderPlugin"}constructor(t,e){this.parser=t,this.helperRoot=e==null?void 0:e.helperRoot,this.autoUpdateHumanBones=e==null?void 0:e.autoUpdateHumanBones}afterRoot(t){return b(this,null,function*(){t.userData.vrmHumanoid=yield this._import(t)})}_import(t){return b(this,null,function*(){const e=yield this._v1Import(t);if(e)return e;const n=yield this._v0Import(t);return n||null})}_v1Import(t){return b(this,null,function*(){var e,n;const i=this.parser.json;if(!(((e=i.extensionsUsed)==null?void 0:e.indexOf("VRMC_vrm"))!==-1))return null;const o=(n=i.extensions)==null?void 0:n.VRMC_vrm;if(!o)return null;const s=o.specVersion;if(!zr.has(s))return console.warn(`VRMHumanoidLoaderPlugin: Unknown VRMC_vrm specVersion "${s}"`),null;const l=o.humanoid;if(!l)return null;const a=l.humanBones.leftThumbIntermediate!=null||l.humanBones.rightThumbIntermediate!=null,u={};l.humanBones!=null&&(yield Promise.all(Object.entries(l.humanBones).map(d=>b(this,[d],function*([c,f]){let m=c;const p=f.node;if(a){const v=fn[m];v!=null&&(m=v)}const g=yield this.parser.getDependency("node",p);if(g==null){console.warn(`A glTF node bound to the humanoid bone ${m} (index = ${p}) does not exist`);return}u[m]={node:g}}))));const h=new pn(this._ensureRequiredBonesExist(u),{autoUpdateHumanBones:this.autoUpdateHumanBones});if(t.scene.add(h.normalizedHumanBonesRoot),this.helperRoot){const d=new hn(h);this.helperRoot.add(d),d.renderOrder=this.helperRoot.renderOrder}return h})}_v0Import(t){return b(this,null,function*(){var e;const i=(e=this.parser.json.extensions)==null?void 0:e.VRM;if(!i)return null;const r=i.humanoid;if(!r)return null;const o={};r.humanBones!=null&&(yield Promise.all(r.humanBones.map(l=>b(this,null,function*(){const a=l.bone,u=l.node;if(a==null||u==null)return;if(u<0){console.warn(`A glTF node index for the humanoid bone ${a} is negative (${u}), ignoring this bone.`);return}const h=yield this.parser.getDependency("node",u);if(h==null){console.warn(`A glTF node bound to the humanoid bone ${a} (index = ${u}) does not exist`);return}const d=fn[a],c=d??a;if(o[c]!=null){console.warn(`Multiple bone entries for ${c} detected (index = ${u}), ignoring duplicated entries.`);return}o[c]={node:h}}))));const s=new pn(this._ensureRequiredBonesExist(o),{autoUpdateHumanBones:this.autoUpdateHumanBones});if(t.scene.add(s.normalizedHumanBonesRoot),this.helperRoot){const l=new hn(s);this.helperRoot.add(l),l.renderOrder=this.helperRoot.renderOrder}return s})}_ensureRequiredBonesExist(t){const e=Object.values(Wr).filter(n=>t[n]==null);if(e.length>0)throw new Error(`VRMHumanoidLoaderPlugin: These humanoid bones are required but not exist: ${e.join(", ")}`);return t}},mn=class extends ie{constructor(){super(),this._currentTheta=0,this._currentRadius=0,this.theta=0,this.radius=0,this._currentTheta=0,this._currentRadius=0,this._attrPos=new D(new Float32Array(65*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(3*63),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;this._currentTheta!==this.theta&&(this._currentTheta=this.theta,t=!0),this._currentRadius!==this.radius&&(this._currentRadius=this.radius,t=!0),t&&this._buildPosition()}_buildPosition(){this._attrPos.setXYZ(0,0,0,0);for(let t=0;t<64;t++){const e=t/63*this._currentTheta;this._attrPos.setXYZ(t+1,this._currentRadius*Math.sin(e),0,this._currentRadius*Math.cos(e))}this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<63;t++)this._attrIndex.setXYZ(t*3,0,t+1,t+2);this._attrIndex.needsUpdate=!0}},Xr=class extends ie{constructor(){super(),this.radius=0,this._currentRadius=0,this.tail=new _,this._currentTail=new _,this._attrPos=new D(new Float32Array(294),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(194),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;this._currentRadius!==this.radius&&(this._currentRadius=this.radius,t=!0),this._currentTail.equals(this.tail)||(this._currentTail.copy(this.tail),t=!0),t&&this._buildPosition()}_buildPosition(){for(let t=0;t<32;t++){const e=t/16*Math.PI;this._attrPos.setXYZ(t,Math.cos(e),Math.sin(e),0),this._attrPos.setXYZ(32+t,0,Math.cos(e),Math.sin(e)),this._attrPos.setXYZ(64+t,Math.sin(e),0,Math.cos(e))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.setXYZ(96,0,0,0),this._attrPos.setXYZ(97,this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(64+t*2,32+t,32+e),this._attrIndex.setXY(128+t*2,64+t,64+e)}this._attrIndex.setXY(192,96,97),this._attrIndex.needsUpdate=!0}},Xe=new T,gn=new T,Oe=new _,_n=new _,vn=Math.sqrt(2)/2,Gr=new T(0,0,-vn,vn),Yr=new _(0,1,0),qr=class extends Re{constructor(t){super(),this.matrixAutoUpdate=!1,this.vrmLookAt=t;{const e=new mn;e.radius=.5;const n=new $t({color:65280,transparent:!0,opacity:.5,side:Zt,depthTest:!1,depthWrite:!1});this._meshPitch=new Jt(e,n),this.add(this._meshPitch)}{const e=new mn;e.radius=.5;const n=new $t({color:16711680,transparent:!0,opacity:.5,side:Zt,depthTest:!1,depthWrite:!1});this._meshYaw=new Jt(e,n),this.add(this._meshYaw)}{const e=new Xr;e.radius=.1;const n=new it({color:16777215,depthTest:!1,depthWrite:!1});this._lineTarget=new Ct(e,n),this._lineTarget.frustumCulled=!1,this.add(this._lineTarget)}}dispose(){this._meshYaw.geometry.dispose(),this._meshYaw.material.dispose(),this._meshPitch.geometry.dispose(),this._meshPitch.material.dispose(),this._lineTarget.geometry.dispose(),this._lineTarget.material.dispose()}updateMatrixWorld(t){const e=I.DEG2RAD*this.vrmLookAt.yaw;this._meshYaw.geometry.theta=e,this._meshYaw.geometry.update();const n=I.DEG2RAD*this.vrmLookAt.pitch;this._meshPitch.geometry.theta=n,this._meshPitch.geometry.update(),this.vrmLookAt.getLookAtWorldPosition(Oe),this.vrmLookAt.getLookAtWorldQuaternion(Xe),Xe.multiply(this.vrmLookAt.getFaceFrontQuaternion(gn)),this._meshYaw.position.copy(Oe),this._meshYaw.quaternion.copy(Xe),this._meshPitch.position.copy(Oe),this._meshPitch.quaternion.copy(Xe),this._meshPitch.quaternion.multiply(gn.setFromAxisAngle(Yr,e)),this._meshPitch.quaternion.multiply(Gr);const{target:i,autoUpdate:r}=this.vrmLookAt;i!=null&&r&&(i.getWorldPosition(_n).sub(Oe),this._lineTarget.geometry.tail.copy(_n),this._lineTarget.geometry.update(),this._lineTarget.position.copy(Oe)),super.updateMatrixWorld(t)}},Qr=new _,$r=new _;function Pt(t,e){return t.matrixWorld.decompose(Qr,e,$r),e}function qe(t){return[Math.atan2(-t.z,t.x),Math.atan2(t.y,Math.sqrt(t.x*t.x+t.z*t.z))]}function Mn(t){const e=Math.round(t/2/Math.PI);return t-2*Math.PI*e}var xn=new _(0,0,1),Zr=new _,Jr=new _,Kr=new _,eo=new T,ut=new T,yn=new T,to=new T,dt=new we,fi=class mi{constructor(e,n){this.offsetFromHeadBone=new _,this.autoUpdate=!0,this.faceFront=new _(0,0,1),this.humanoid=e,this.applier=n,this._yaw=0,this._pitch=0,this._needsUpdate=!0,this._restHeadWorldQuaternion=this.getLookAtWorldQuaternion(new T)}get yaw(){return this._yaw}set yaw(e){this._yaw=e,this._needsUpdate=!0}get pitch(){return this._pitch}set pitch(e){this._pitch=e,this._needsUpdate=!0}get euler(){return console.warn("VRMLookAt: euler is deprecated. use getEuler() instead."),this.getEuler(new we)}getEuler(e){return e.set(I.DEG2RAD*this._pitch,I.DEG2RAD*this._yaw,0,"YXZ")}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMLookAt: humanoid must be same in order to copy");return this.offsetFromHeadBone.copy(e.offsetFromHeadBone),this.applier=e.applier,this.autoUpdate=e.autoUpdate,this.target=e.target,this.faceFront.copy(e.faceFront),this}clone(){return new mi(this.humanoid,this.applier).copy(this)}reset(){this._yaw=0,this._pitch=0,this._needsUpdate=!0}getLookAtWorldPosition(e){const n=this.humanoid.getRawBoneNode("head");return e.copy(this.offsetFromHeadBone).applyMatrix4(n.matrixWorld)}getLookAtWorldQuaternion(e){const n=this.humanoid.getRawBoneNode("head");return Pt(n,e)}getFaceFrontQuaternion(e){if(this.faceFront.distanceToSquared(xn)<.01)return e.copy(this._restHeadWorldQuaternion).invert();const[n,i]=qe(this.faceFront);return dt.set(0,.5*Math.PI+n,i,"YZX"),e.setFromEuler(dt).premultiply(to.copy(this._restHeadWorldQuaternion).invert())}getLookAtWorldDirection(e){return this.getLookAtWorldQuaternion(ut),this.getFaceFrontQuaternion(yn),e.copy(xn).applyQuaternion(ut).applyQuaternion(yn).applyEuler(this.getEuler(dt))}lookAt(e){const n=eo.copy(this._restHeadWorldQuaternion).multiply(hi(this.getLookAtWorldQuaternion(ut))),i=this.getLookAtWorldPosition(Jr),r=Kr.copy(e).sub(i).applyQuaternion(n).normalize(),[o,s]=qe(this.faceFront),[l,a]=qe(r),u=Mn(l-o),h=Mn(s-a);this._yaw=I.RAD2DEG*u,this._pitch=I.RAD2DEG*h,this._needsUpdate=!0}update(e){this.target!=null&&this.autoUpdate&&this.lookAt(this.target.getWorldPosition(Zr)),this._needsUpdate&&(this._needsUpdate=!1,this.applier.applyYawPitch(this._yaw,this._pitch))}};fi.EULER_ORDER="YXZ";var no=fi,io=new _(0,0,1),q=new T,ge=new T,z=new we(0,0,0,"YXZ"),Qe=class{constructor(t,e,n,i,r){this.humanoid=t,this.rangeMapHorizontalInner=e,this.rangeMapHorizontalOuter=n,this.rangeMapVerticalDown=i,this.rangeMapVerticalUp=r,this.faceFront=new _(0,0,1),this._restQuatLeftEye=new T,this._restQuatRightEye=new T,this._restLeftEyeParentWorldQuat=new T,this._restRightEyeParentWorldQuat=new T;const o=this.humanoid.getRawBoneNode("leftEye"),s=this.humanoid.getRawBoneNode("rightEye");o&&(this._restQuatLeftEye.copy(o.quaternion),Pt(o.parent,this._restLeftEyeParentWorldQuat)),s&&(this._restQuatRightEye.copy(s.quaternion),Pt(s.parent,this._restRightEyeParentWorldQuat))}applyYawPitch(t,e){const n=this.humanoid.getRawBoneNode("leftEye"),i=this.humanoid.getRawBoneNode("rightEye"),r=this.humanoid.getNormalizedBoneNode("leftEye"),o=this.humanoid.getNormalizedBoneNode("rightEye");n&&(e<0?z.x=-I.DEG2RAD*this.rangeMapVerticalDown.map(-e):z.x=I.DEG2RAD*this.rangeMapVerticalUp.map(e),t<0?z.y=-I.DEG2RAD*this.rangeMapHorizontalInner.map(-t):z.y=I.DEG2RAD*this.rangeMapHorizontalOuter.map(t),q.setFromEuler(z),this._getWorldFaceFrontQuat(ge),r.quaternion.copy(ge).multiply(q).multiply(ge.invert()),q.copy(this._restLeftEyeParentWorldQuat),n.quaternion.copy(r.quaternion).multiply(q).premultiply(q.invert()).multiply(this._restQuatLeftEye)),i&&(e<0?z.x=-I.DEG2RAD*this.rangeMapVerticalDown.map(-e):z.x=I.DEG2RAD*this.rangeMapVerticalUp.map(e),t<0?z.y=-I.DEG2RAD*this.rangeMapHorizontalOuter.map(-t):z.y=I.DEG2RAD*this.rangeMapHorizontalInner.map(t),q.setFromEuler(z),this._getWorldFaceFrontQuat(ge),o.quaternion.copy(ge).multiply(q).multiply(ge.invert()),q.copy(this._restRightEyeParentWorldQuat),i.quaternion.copy(o.quaternion).multiply(q).premultiply(q.invert()).multiply(this._restQuatRightEye))}lookAt(t){console.warn("VRMLookAtBoneApplier: lookAt() is deprecated. use apply() instead.");const e=I.RAD2DEG*t.y,n=I.RAD2DEG*t.x;this.applyYawPitch(e,n)}_getWorldFaceFrontQuat(t){if(this.faceFront.distanceToSquared(io)<.01)return t.identity();const[e,n]=qe(this.faceFront);return z.set(0,.5*Math.PI+e,n,"YZX"),t.setFromEuler(z)}};Qe.type="bone";var Lt=class{constructor(t,e,n,i,r){this.expressions=t,this.rangeMapHorizontalInner=e,this.rangeMapHorizontalOuter=n,this.rangeMapVerticalDown=i,this.rangeMapVerticalUp=r}applyYawPitch(t,e){e<0?(this.expressions.setValue("lookDown",0),this.expressions.setValue("lookUp",this.rangeMapVerticalUp.map(-e))):(this.expressions.setValue("lookUp",0),this.expressions.setValue("lookDown",this.rangeMapVerticalDown.map(e))),t<0?(this.expressions.setValue("lookLeft",0),this.expressions.setValue("lookRight",this.rangeMapHorizontalOuter.map(-t))):(this.expressions.setValue("lookRight",0),this.expressions.setValue("lookLeft",this.rangeMapHorizontalOuter.map(t)))}lookAt(t){console.warn("VRMLookAtBoneApplier: lookAt() is deprecated. use apply() instead.");const e=I.RAD2DEG*t.y,n=I.RAD2DEG*t.x;this.applyYawPitch(e,n)}};Lt.type="expression";var wn=class{constructor(t,e){this.inputMaxValue=t,this.outputScale=e}map(t){return this.outputScale*ii(t/this.inputMaxValue)}},ro=new Set(["1.0","1.0-beta"]),Ge=.01,oo=class{get name(){return"VRMLookAtLoaderPlugin"}constructor(t,e){this.parser=t,this.helperRoot=e==null?void 0:e.helperRoot}afterRoot(t){return b(this,null,function*(){const e=t.userData.vrmHumanoid;if(e===null)return;if(e===void 0)throw new Error("VRMLookAtLoaderPlugin: vrmHumanoid is undefined. VRMHumanoidLoaderPlugin have to be used first");const n=t.userData.vrmExpressionManager;if(n!==null){if(n===void 0)throw new Error("VRMLookAtLoaderPlugin: vrmExpressionManager is undefined. VRMExpressionLoaderPlugin have to be used first");t.userData.vrmLookAt=yield this._import(t,e,n)}})}_import(t,e,n){return b(this,null,function*(){if(e==null||n==null)return null;const i=yield this._v1Import(t,e,n);if(i)return i;const r=yield this._v0Import(t,e,n);return r||null})}_v1Import(t,e,n){return b(this,null,function*(){var i,r,o;const s=this.parser.json;if(!(((i=s.extensionsUsed)==null?void 0:i.indexOf("VRMC_vrm"))!==-1))return null;const a=(r=s.extensions)==null?void 0:r.VRMC_vrm;if(!a)return null;const u=a.specVersion;if(!ro.has(u))return console.warn(`VRMLookAtLoaderPlugin: Unknown VRMC_vrm specVersion "${u}"`),null;const h=a.lookAt;if(!h)return null;const d=h.type==="expression"?1:10,c=this._v1ImportRangeMap(h.rangeMapHorizontalInner,d),f=this._v1ImportRangeMap(h.rangeMapHorizontalOuter,d),m=this._v1ImportRangeMap(h.rangeMapVerticalDown,d),p=this._v1ImportRangeMap(h.rangeMapVerticalUp,d);let g;h.type==="expression"?g=new Lt(n,c,f,m,p):g=new Qe(e,c,f,m,p);const v=this._importLookAt(e,g);return v.offsetFromHeadBone.fromArray((o=h.offsetFromHeadBone)!=null?o:[0,.06,0]),v})}_v1ImportRangeMap(t,e){var n,i;let r=(n=t==null?void 0:t.inputMaxValue)!=null?n:90;const o=(i=t==null?void 0:t.outputScale)!=null?i:e;return r<Ge&&(console.warn("VRMLookAtLoaderPlugin: inputMaxValue of a range map is too small. Consider reviewing the range map!"),r=Ge),new wn(r,o)}_v0Import(t,e,n){return b(this,null,function*(){var i,r,o,s;const a=(i=this.parser.json.extensions)==null?void 0:i.VRM;if(!a)return null;const u=a.firstPerson;if(!u)return null;const h=u.lookAtTypeName==="BlendShape"?1:10,d=this._v0ImportDegreeMap(u.lookAtHorizontalInner,h),c=this._v0ImportDegreeMap(u.lookAtHorizontalOuter,h),f=this._v0ImportDegreeMap(u.lookAtVerticalDown,h),m=this._v0ImportDegreeMap(u.lookAtVerticalUp,h);let p;u.lookAtTypeName==="BlendShape"?p=new Lt(n,d,c,f,m):p=new Qe(e,d,c,f,m);const g=this._importLookAt(e,p);return u.firstPersonBoneOffset?g.offsetFromHeadBone.set((r=u.firstPersonBoneOffset.x)!=null?r:0,(o=u.firstPersonBoneOffset.y)!=null?o:.06,-((s=u.firstPersonBoneOffset.z)!=null?s:0)):g.offsetFromHeadBone.set(0,.06,0),g.faceFront.set(0,0,-1),p instanceof Qe&&p.faceFront.set(0,0,-1),g})}_v0ImportDegreeMap(t,e){var n,i;const r=t==null?void 0:t.curve;JSON.stringify(r)!=="[0,0,0,1,1,1,1,0]"&&console.warn("Curves of LookAtDegreeMap defined in VRM 0.0 are not supported");let o=(n=t==null?void 0:t.xRange)!=null?n:90;const s=(i=t==null?void 0:t.yRange)!=null?i:e;return o<Ge&&(console.warn("VRMLookAtLoaderPlugin: xRange of a degree map is too small. Consider reviewing the degree map!"),o=Ge),new wn(o,s)}_importLookAt(t,e){const n=new no(t,e);if(this.helperRoot){const i=new qr(n);this.helperRoot.add(i),i.renderOrder=this.helperRoot.renderOrder}return n}};function so(t,e){return typeof t!="string"||t===""?"":(/^https?:\/\//i.test(e)&&/^\//.test(t)&&(e=e.replace(/(^https?:\/\/[^/]+).*/i,"$1")),/^(https?:)?\/\//i.test(t)||/^data:.*,.*$/i.test(t)||/^blob:.*$/i.test(t)?t:e+t)}var ao=new Set(["1.0","1.0-beta"]),lo=class{get name(){return"VRMMetaLoaderPlugin"}constructor(t,e){var n,i,r;this.parser=t,this.needThumbnailImage=(n=e==null?void 0:e.needThumbnailImage)!=null?n:!1,this.acceptLicenseUrls=(i=e==null?void 0:e.acceptLicenseUrls)!=null?i:["https://vrm.dev/licenses/1.0/"],this.acceptV0Meta=(r=e==null?void 0:e.acceptV0Meta)!=null?r:!0}afterRoot(t){return b(this,null,function*(){t.userData.vrmMeta=yield this._import(t)})}_import(t){return b(this,null,function*(){const e=yield this._v1Import(t);if(e!=null)return e;const n=yield this._v0Import(t);return n??null})}_v1Import(t){return b(this,null,function*(){var e,n,i;const r=this.parser.json;if(!(((e=r.extensionsUsed)==null?void 0:e.indexOf("VRMC_vrm"))!==-1))return null;const s=(n=r.extensions)==null?void 0:n.VRMC_vrm;if(s==null)return null;const l=s.specVersion;if(!ao.has(l))return console.warn(`VRMMetaLoaderPlugin: Unknown VRMC_vrm specVersion "${l}"`),null;const a=s.meta;if(!a)return null;const u=a.licenseUrl;if(!new Set(this.acceptLicenseUrls).has(u))throw new Error(`VRMMetaLoaderPlugin: The license url "${u}" is not accepted`);let d;return this.needThumbnailImage&&a.thumbnailImage!=null&&(d=(i=yield this._extractGLTFImage(a.thumbnailImage))!=null?i:void 0),{metaVersion:"1",name:a.name,version:a.version,authors:a.authors,copyrightInformation:a.copyrightInformation,contactInformation:a.contactInformation,references:a.references,thirdPartyLicenses:a.thirdPartyLicenses,thumbnailImage:d,licenseUrl:a.licenseUrl,avatarPermission:a.avatarPermission,allowExcessivelyViolentUsage:a.allowExcessivelyViolentUsage,allowExcessivelySexualUsage:a.allowExcessivelySexualUsage,commercialUsage:a.commercialUsage,allowPoliticalOrReligiousUsage:a.allowPoliticalOrReligiousUsage,allowAntisocialOrHateUsage:a.allowAntisocialOrHateUsage,creditNotation:a.creditNotation,allowRedistribution:a.allowRedistribution,modification:a.modification,otherLicenseUrl:a.otherLicenseUrl}})}_v0Import(t){return b(this,null,function*(){var e;const i=(e=this.parser.json.extensions)==null?void 0:e.VRM;if(!i)return null;const r=i.meta;if(!r)return null;if(!this.acceptV0Meta)throw new Error("VRMMetaLoaderPlugin: Attempted to load VRM0.0 meta but acceptV0Meta is false");let o;return this.needThumbnailImage&&r.texture!=null&&r.texture!==-1&&(o=yield this.parser.getDependency("texture",r.texture)),{metaVersion:"0",allowedUserName:r.allowedUserName,author:r.author,commercialUssageName:r.commercialUssageName,contactInformation:r.contactInformation,licenseName:r.licenseName,otherLicenseUrl:r.otherLicenseUrl,otherPermissionUrl:r.otherPermissionUrl,reference:r.reference,sexualUssageName:r.sexualUssageName,texture:o??void 0,title:r.title,version:r.version,violentUssageName:r.violentUssageName}})}_extractGLTFImage(t){return b(this,null,function*(){var e;const i=(e=this.parser.json.images)==null?void 0:e[t];if(i==null)return console.warn(`VRMMetaLoaderPlugin: Attempt to use images[${t}] of glTF as a thumbnail but the image doesn't exist`),null;let r=i.uri;if(i.bufferView!=null){const s=yield this.parser.getDependency("bufferView",i.bufferView),l=new Blob([s],{type:i.mimeType});r=URL.createObjectURL(l)}return r==null?(console.warn(`VRMMetaLoaderPlugin: Attempt to use images[${t}] of glTF as a thumbnail but the image couldn't load properly`),null):yield new cr().loadAsync(so(r,this.parser.options.path)).catch(s=>(console.error(s),console.warn("VRMMetaLoaderPlugin: Failed to load a thumbnail image"),null))})}},uo=class{constructor(t){this.scene=t.scene,this.meta=t.meta,this.humanoid=t.humanoid,this.expressionManager=t.expressionManager,this.firstPerson=t.firstPerson,this.lookAt=t.lookAt}update(t){this.humanoid.update(),this.lookAt&&this.lookAt.update(t),this.expressionManager&&this.expressionManager.update()}},ho=class extends uo{constructor(t){super(t),this.materials=t.materials,this.springBoneManager=t.springBoneManager,this.nodeConstraintManager=t.nodeConstraintManager}update(t){super.update(t),this.nodeConstraintManager&&this.nodeConstraintManager.update(),this.springBoneManager&&this.springBoneManager.update(t),this.materials&&this.materials.forEach(e=>{e.update&&e.update(t)})}},co=Object.defineProperty,Rn=Object.getOwnPropertySymbols,po=Object.prototype.hasOwnProperty,fo=Object.prototype.propertyIsEnumerable,Tn=(t,e,n)=>e in t?co(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n,Sn=(t,e)=>{for(var n in e||(e={}))po.call(e,n)&&Tn(t,n,e[n]);if(Rn)for(var n of Rn(e))fo.call(e,n)&&Tn(t,n,e[n]);return t},he=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),mo={"":3e3,srgb:3001};function go(t,e){parseInt(Ze,10)>=152?t.colorSpace=e:t.encoding=mo[e]}var _o=class{get pending(){return Promise.all(this._pendings)}constructor(t,e){this._parser=t,this._materialParams=e,this._pendings=[]}assignPrimitive(t,e){e!=null&&(this._materialParams[t]=e)}assignColor(t,e,n){if(e!=null){const i=new j().fromArray(e);n&&i.convertSRGBToLinear(),this._materialParams[t]=i}}assignTexture(t,e,n){return he(this,null,function*(){const i=he(this,null,function*(){if(e!=null){const r=yield this._parser.assignTexture(this._materialParams,t,e);if(r==null){console.warn("GLTFMToonMaterialParamsAssignHelper: Failed to load texture. The rendering result may be wrong");return}n&&go(r,"srgb")}});return this._pendings.push(i),i})}assignTextureByIndex(t,e,n){return he(this,null,function*(){return this.assignTexture(t,e!=null?{index:e}:void 0,n)})}},vo=`// #define PHONG

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

}`,Mo=`// #define PHONG

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
`,xo={None:"none"},En={None:"none",ScreenCoordinates:"screenCoordinates"},yo={3e3:"",3001:"srgb"};function ht(t){return parseInt(Ze,10)>=152?t.colorSpace:yo[t.encoding]}var wo=class extends pr{constructor(t={}){var e;super({vertexShader:vo,fragmentShader:Mo}),this.uvAnimationScrollXSpeedFactor=0,this.uvAnimationScrollYSpeedFactor=0,this.uvAnimationRotationSpeedFactor=0,this.fog=!0,this.normalMapType=fr,this._ignoreVertexColor=!0,this._v0CompatShade=!1,this._debugMode=xo.None,this._outlineWidthMode=En.None,this._isOutline=!1,t.transparentWithZWrite&&(t.depthWrite=!0),delete t.transparentWithZWrite,t.fog=!0,t.lights=!0,t.clipping=!0,this.uniforms=mr.merge([Ie.common,Ie.normalmap,Ie.emissivemap,Ie.fog,Ie.lights,{litFactor:{value:new j(1,1,1)},mapUvTransform:{value:new Z},colorAlpha:{value:1},normalMapUvTransform:{value:new Z},shadeColorFactor:{value:new j(0,0,0)},shadeMultiplyTexture:{value:null},shadeMultiplyTextureUvTransform:{value:new Z},shadingShiftFactor:{value:0},shadingShiftTexture:{value:null},shadingShiftTextureUvTransform:{value:new Z},shadingShiftTextureScale:{value:1},shadingToonyFactor:{value:.9},giEqualizationFactor:{value:.9},matcapFactor:{value:new j(1,1,1)},matcapTexture:{value:null},matcapTextureUvTransform:{value:new Z},parametricRimColorFactor:{value:new j(0,0,0)},rimMultiplyTexture:{value:null},rimMultiplyTextureUvTransform:{value:new Z},rimLightingMixFactor:{value:1},parametricRimFresnelPowerFactor:{value:5},parametricRimLiftFactor:{value:0},emissive:{value:new j(0,0,0)},emissiveIntensity:{value:1},emissiveMapUvTransform:{value:new Z},outlineWidthMultiplyTexture:{value:null},outlineWidthMultiplyTextureUvTransform:{value:new Z},outlineWidthFactor:{value:0},outlineColorFactor:{value:new j(0,0,0)},outlineLightingMixFactor:{value:1},uvAnimationMaskTexture:{value:null},uvAnimationMaskTextureUvTransform:{value:new Z},uvAnimationScrollXOffset:{value:0},uvAnimationScrollYOffset:{value:0},uvAnimationRotationPhase:{value:0}},(e=t.uniforms)!=null?e:{}]),this.setValues(t),this._uploadUniformsWorkaround(),this.customProgramCacheKey=()=>[...Object.entries(this._generateDefines()).map(([n,i])=>`${n}:${i}`),this.matcapTexture?`matcapTextureColorSpace:${ht(this.matcapTexture)}`:"",this.shadeMultiplyTexture?`shadeMultiplyTextureColorSpace:${ht(this.shadeMultiplyTexture)}`:"",this.rimMultiplyTexture?`rimMultiplyTextureColorSpace:${ht(this.rimMultiplyTexture)}`:""].join(","),this.onBeforeCompile=n=>{const i=parseInt(Ze,10),r=Object.entries(Sn(Sn({},this._generateDefines()),this.defines)).filter(([o,s])=>!!s).map(([o,s])=>`#define ${o} ${s}`).join(`
`)+`
`;n.vertexShader=r+n.vertexShader,n.fragmentShader=r+n.fragmentShader,i<154&&(n.fragmentShader=n.fragmentShader.replace("#include <colorspace_fragment>","#include <encodings_fragment>"))}}get color(){return this.uniforms.litFactor.value}set color(t){this.uniforms.litFactor.value=t}get map(){return this.uniforms.map.value}set map(t){this.uniforms.map.value=t}get normalMap(){return this.uniforms.normalMap.value}set normalMap(t){this.uniforms.normalMap.value=t}get normalScale(){return this.uniforms.normalScale.value}set normalScale(t){this.uniforms.normalScale.value=t}get emissive(){return this.uniforms.emissive.value}set emissive(t){this.uniforms.emissive.value=t}get emissiveIntensity(){return this.uniforms.emissiveIntensity.value}set emissiveIntensity(t){this.uniforms.emissiveIntensity.value=t}get emissiveMap(){return this.uniforms.emissiveMap.value}set emissiveMap(t){this.uniforms.emissiveMap.value=t}get shadeColorFactor(){return this.uniforms.shadeColorFactor.value}set shadeColorFactor(t){this.uniforms.shadeColorFactor.value=t}get shadeMultiplyTexture(){return this.uniforms.shadeMultiplyTexture.value}set shadeMultiplyTexture(t){this.uniforms.shadeMultiplyTexture.value=t}get shadingShiftFactor(){return this.uniforms.shadingShiftFactor.value}set shadingShiftFactor(t){this.uniforms.shadingShiftFactor.value=t}get shadingShiftTexture(){return this.uniforms.shadingShiftTexture.value}set shadingShiftTexture(t){this.uniforms.shadingShiftTexture.value=t}get shadingShiftTextureScale(){return this.uniforms.shadingShiftTextureScale.value}set shadingShiftTextureScale(t){this.uniforms.shadingShiftTextureScale.value=t}get shadingToonyFactor(){return this.uniforms.shadingToonyFactor.value}set shadingToonyFactor(t){this.uniforms.shadingToonyFactor.value=t}get giEqualizationFactor(){return this.uniforms.giEqualizationFactor.value}set giEqualizationFactor(t){this.uniforms.giEqualizationFactor.value=t}get matcapFactor(){return this.uniforms.matcapFactor.value}set matcapFactor(t){this.uniforms.matcapFactor.value=t}get matcapTexture(){return this.uniforms.matcapTexture.value}set matcapTexture(t){this.uniforms.matcapTexture.value=t}get parametricRimColorFactor(){return this.uniforms.parametricRimColorFactor.value}set parametricRimColorFactor(t){this.uniforms.parametricRimColorFactor.value=t}get rimMultiplyTexture(){return this.uniforms.rimMultiplyTexture.value}set rimMultiplyTexture(t){this.uniforms.rimMultiplyTexture.value=t}get rimLightingMixFactor(){return this.uniforms.rimLightingMixFactor.value}set rimLightingMixFactor(t){this.uniforms.rimLightingMixFactor.value=t}get parametricRimFresnelPowerFactor(){return this.uniforms.parametricRimFresnelPowerFactor.value}set parametricRimFresnelPowerFactor(t){this.uniforms.parametricRimFresnelPowerFactor.value=t}get parametricRimLiftFactor(){return this.uniforms.parametricRimLiftFactor.value}set parametricRimLiftFactor(t){this.uniforms.parametricRimLiftFactor.value=t}get outlineWidthMultiplyTexture(){return this.uniforms.outlineWidthMultiplyTexture.value}set outlineWidthMultiplyTexture(t){this.uniforms.outlineWidthMultiplyTexture.value=t}get outlineWidthFactor(){return this.uniforms.outlineWidthFactor.value}set outlineWidthFactor(t){this.uniforms.outlineWidthFactor.value=t}get outlineColorFactor(){return this.uniforms.outlineColorFactor.value}set outlineColorFactor(t){this.uniforms.outlineColorFactor.value=t}get outlineLightingMixFactor(){return this.uniforms.outlineLightingMixFactor.value}set outlineLightingMixFactor(t){this.uniforms.outlineLightingMixFactor.value=t}get uvAnimationMaskTexture(){return this.uniforms.uvAnimationMaskTexture.value}set uvAnimationMaskTexture(t){this.uniforms.uvAnimationMaskTexture.value=t}get uvAnimationScrollXOffset(){return this.uniforms.uvAnimationScrollXOffset.value}set uvAnimationScrollXOffset(t){this.uniforms.uvAnimationScrollXOffset.value=t}get uvAnimationScrollYOffset(){return this.uniforms.uvAnimationScrollYOffset.value}set uvAnimationScrollYOffset(t){this.uniforms.uvAnimationScrollYOffset.value=t}get uvAnimationRotationPhase(){return this.uniforms.uvAnimationRotationPhase.value}set uvAnimationRotationPhase(t){this.uniforms.uvAnimationRotationPhase.value=t}get ignoreVertexColor(){return this._ignoreVertexColor}set ignoreVertexColor(t){this._ignoreVertexColor=t,this.needsUpdate=!0}get v0CompatShade(){return this._v0CompatShade}set v0CompatShade(t){this._v0CompatShade=t,this.needsUpdate=!0}get debugMode(){return this._debugMode}set debugMode(t){this._debugMode=t,this.needsUpdate=!0}get outlineWidthMode(){return this._outlineWidthMode}set outlineWidthMode(t){this._outlineWidthMode=t,this.needsUpdate=!0}get isOutline(){return this._isOutline}set isOutline(t){this._isOutline=t,this.needsUpdate=!0}get isMToonMaterial(){return!0}update(t){this._uploadUniformsWorkaround(),this._updateUVAnimation(t)}copy(t){return super.copy(t),this.map=t.map,this.normalMap=t.normalMap,this.emissiveMap=t.emissiveMap,this.shadeMultiplyTexture=t.shadeMultiplyTexture,this.shadingShiftTexture=t.shadingShiftTexture,this.matcapTexture=t.matcapTexture,this.rimMultiplyTexture=t.rimMultiplyTexture,this.outlineWidthMultiplyTexture=t.outlineWidthMultiplyTexture,this.uvAnimationMaskTexture=t.uvAnimationMaskTexture,this.normalMapType=t.normalMapType,this.uvAnimationScrollXSpeedFactor=t.uvAnimationScrollXSpeedFactor,this.uvAnimationScrollYSpeedFactor=t.uvAnimationScrollYSpeedFactor,this.uvAnimationRotationSpeedFactor=t.uvAnimationRotationSpeedFactor,this.ignoreVertexColor=t.ignoreVertexColor,this.v0CompatShade=t.v0CompatShade,this.debugMode=t.debugMode,this.outlineWidthMode=t.outlineWidthMode,this.isOutline=t.isOutline,this.needsUpdate=!0,this}_updateUVAnimation(t){this.uniforms.uvAnimationScrollXOffset.value+=t*this.uvAnimationScrollXSpeedFactor,this.uniforms.uvAnimationScrollYOffset.value+=t*this.uvAnimationScrollYSpeedFactor,this.uniforms.uvAnimationRotationPhase.value+=t*this.uvAnimationRotationSpeedFactor,this.uniforms.alphaTest.value=this.alphaTest,this.uniformsNeedUpdate=!0}_uploadUniformsWorkaround(){this.uniforms.opacity.value=this.opacity,this._updateTextureMatrix(this.uniforms.map,this.uniforms.mapUvTransform),this._updateTextureMatrix(this.uniforms.normalMap,this.uniforms.normalMapUvTransform),this._updateTextureMatrix(this.uniforms.emissiveMap,this.uniforms.emissiveMapUvTransform),this._updateTextureMatrix(this.uniforms.shadeMultiplyTexture,this.uniforms.shadeMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.shadingShiftTexture,this.uniforms.shadingShiftTextureUvTransform),this._updateTextureMatrix(this.uniforms.matcapTexture,this.uniforms.matcapTextureUvTransform),this._updateTextureMatrix(this.uniforms.rimMultiplyTexture,this.uniforms.rimMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.outlineWidthMultiplyTexture,this.uniforms.outlineWidthMultiplyTextureUvTransform),this._updateTextureMatrix(this.uniforms.uvAnimationMaskTexture,this.uniforms.uvAnimationMaskTextureUvTransform),this.uniformsNeedUpdate=!0}_generateDefines(){const t=parseInt(Ze,10),e=this.outlineWidthMultiplyTexture!==null,n=this.map!==null||this.normalMap!==null||this.emissiveMap!==null||this.shadeMultiplyTexture!==null||this.shadingShiftTexture!==null||this.rimMultiplyTexture!==null||this.uvAnimationMaskTexture!==null;return{THREE_VRM_THREE_REVISION:t,OUTLINE:this._isOutline,MTOON_USE_UV:e||n,MTOON_UVS_VERTEX_ONLY:e&&!n,V0_COMPAT_SHADE:this._v0CompatShade,USE_SHADEMULTIPLYTEXTURE:this.shadeMultiplyTexture!==null,USE_SHADINGSHIFTTEXTURE:this.shadingShiftTexture!==null,USE_MATCAPTEXTURE:this.matcapTexture!==null,USE_RIMMULTIPLYTEXTURE:this.rimMultiplyTexture!==null,USE_OUTLINEWIDTHMULTIPLYTEXTURE:this._isOutline&&this.outlineWidthMultiplyTexture!==null,USE_UVANIMATIONMASKTEXTURE:this.uvAnimationMaskTexture!==null,IGNORE_VERTEX_COLOR:this._ignoreVertexColor===!0,DEBUG_NORMAL:this._debugMode==="normal",DEBUG_LITSHADERATE:this._debugMode==="litShadeRate",DEBUG_UV:this._debugMode==="uv",OUTLINE_WIDTH_SCREEN:this._isOutline&&this._outlineWidthMode===En.ScreenCoordinates}}_updateTextureMatrix(t,e){t.value&&(t.value.matrixAutoUpdate&&t.value.updateMatrix(),e.value.copy(t.value.matrix))}},Ro=new Set(["1.0","1.0-beta"]),gi=class $e{get name(){return $e.EXTENSION_NAME}constructor(e,n={}){var i,r,o,s;this.parser=e,this.materialType=(i=n.materialType)!=null?i:wo,this.renderOrderOffset=(r=n.renderOrderOffset)!=null?r:0,this.v0CompatShade=(o=n.v0CompatShade)!=null?o:!1,this.debugMode=(s=n.debugMode)!=null?s:"none",this._mToonMaterialSet=new Set}beforeRoot(){return he(this,null,function*(){this._removeUnlitExtensionIfMToonExists()})}afterRoot(e){return he(this,null,function*(){e.userData.vrmMToonMaterials=Array.from(this._mToonMaterialSet)})}getMaterialType(e){return this._getMToonExtension(e)?this.materialType:null}extendMaterialParams(e,n){const i=this._getMToonExtension(e);return i?this._extendMaterialParams(i,n):null}loadMesh(e){return he(this,null,function*(){var n;const i=this.parser,o=(n=i.json.meshes)==null?void 0:n[e];if(o==null)throw new Error(`MToonMaterialLoaderPlugin: Attempt to use meshes[${e}] of glTF but the mesh doesn't exist`);const s=o.primitives,l=yield i.loadMesh(e);if(s.length===1){const a=l,u=s[0].material;u!=null&&this._setupPrimitive(a,u)}else{const a=l;for(let u=0;u<s.length;u++){const h=a.children[u],d=s[u].material;d!=null&&this._setupPrimitive(h,d)}}return l})}_removeUnlitExtensionIfMToonExists(){const i=this.parser.json.materials;i==null||i.map((r,o)=>{var s;this._getMToonExtension(o)&&((s=r.extensions)!=null&&s.KHR_materials_unlit)&&delete r.extensions.KHR_materials_unlit})}_getMToonExtension(e){var n,i;const s=(n=this.parser.json.materials)==null?void 0:n[e];if(s==null){console.warn(`MToonMaterialLoaderPlugin: Attempt to use materials[${e}] of glTF but the material doesn't exist`);return}const l=(i=s.extensions)==null?void 0:i[$e.EXTENSION_NAME];if(l==null)return;const a=l.specVersion;if(!Ro.has(a)){console.warn(`MToonMaterialLoaderPlugin: Unknown ${$e.EXTENSION_NAME} specVersion "${a}"`);return}return l}_extendMaterialParams(e,n){return he(this,null,function*(){var i;delete n.metalness,delete n.roughness;const r=new _o(this.parser,n);r.assignPrimitive("transparentWithZWrite",e.transparentWithZWrite),r.assignColor("shadeColorFactor",e.shadeColorFactor),r.assignTexture("shadeMultiplyTexture",e.shadeMultiplyTexture,!0),r.assignPrimitive("shadingShiftFactor",e.shadingShiftFactor),r.assignTexture("shadingShiftTexture",e.shadingShiftTexture,!0),r.assignPrimitive("shadingShiftTextureScale",(i=e.shadingShiftTexture)==null?void 0:i.scale),r.assignPrimitive("shadingToonyFactor",e.shadingToonyFactor),r.assignPrimitive("giEqualizationFactor",e.giEqualizationFactor),r.assignColor("matcapFactor",e.matcapFactor),r.assignTexture("matcapTexture",e.matcapTexture,!0),r.assignColor("parametricRimColorFactor",e.parametricRimColorFactor),r.assignTexture("rimMultiplyTexture",e.rimMultiplyTexture,!0),r.assignPrimitive("rimLightingMixFactor",e.rimLightingMixFactor),r.assignPrimitive("parametricRimFresnelPowerFactor",e.parametricRimFresnelPowerFactor),r.assignPrimitive("parametricRimLiftFactor",e.parametricRimLiftFactor),r.assignPrimitive("outlineWidthMode",e.outlineWidthMode),r.assignPrimitive("outlineWidthFactor",e.outlineWidthFactor),r.assignTexture("outlineWidthMultiplyTexture",e.outlineWidthMultiplyTexture,!1),r.assignColor("outlineColorFactor",e.outlineColorFactor),r.assignPrimitive("outlineLightingMixFactor",e.outlineLightingMixFactor),r.assignTexture("uvAnimationMaskTexture",e.uvAnimationMaskTexture,!1),r.assignPrimitive("uvAnimationScrollXSpeedFactor",e.uvAnimationScrollXSpeedFactor),r.assignPrimitive("uvAnimationScrollYSpeedFactor",e.uvAnimationScrollYSpeedFactor),r.assignPrimitive("uvAnimationRotationSpeedFactor",e.uvAnimationRotationSpeedFactor),r.assignPrimitive("v0CompatShade",this.v0CompatShade),r.assignPrimitive("debugMode",this.debugMode),yield r.pending})}_setupPrimitive(e,n){const i=this._getMToonExtension(n);if(i){const r=this._parseRenderOrder(i);e.renderOrder=r+this.renderOrderOffset,this._generateOutline(e),this._addToMaterialSet(e);return}}_shouldGenerateOutline(e){return typeof e.outlineWidthMode=="string"&&e.outlineWidthMode!=="none"&&typeof e.outlineWidthFactor=="number"&&e.outlineWidthFactor>0}_generateOutline(e){const n=e.material;if(!(n instanceof dr)||!this._shouldGenerateOutline(n))return;e.material=[n];const i=n.clone();i.name+=" (Outline)",i.isOutline=!0,i.side=hr,e.material.push(i);const r=e.geometry,o=r.index?r.index.count:r.attributes.position.count/3;r.addGroup(0,o,0),r.addGroup(0,o,1)}_addToMaterialSet(e){const n=e.material,i=new Set;Array.isArray(n)?n.forEach(r=>i.add(r)):i.add(n);for(const r of i)this._mToonMaterialSet.add(r)}_parseRenderOrder(e){var n;return(e.transparentWithZWrite?0:19)+((n=e.renderQueueOffsetNumber)!=null?n:0)}};gi.EXTENSION_NAME="VRMC_materials_mtoon";var To=gi,So=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),_i=class bt{get name(){return bt.EXTENSION_NAME}constructor(e){this.parser=e}extendMaterialParams(e,n){return So(this,null,function*(){const i=this._getHDREmissiveMultiplierExtension(e);if(i==null)return;console.warn("VRMMaterialsHDREmissiveMultiplierLoaderPlugin: `VRMC_materials_hdr_emissiveMultiplier` is archived. Use `KHR_materials_emissive_strength` instead.");const r=i.emissiveMultiplier;n.emissiveIntensity=r})}_getHDREmissiveMultiplierExtension(e){var n,i;const s=(n=this.parser.json.materials)==null?void 0:n[e];if(s==null){console.warn(`VRMMaterialsHDREmissiveMultiplierLoaderPlugin: Attempt to use materials[${e}] of glTF but the material doesn't exist`);return}const l=(i=s.extensions)==null?void 0:i[bt.EXTENSION_NAME];if(l!=null)return l}};_i.EXTENSION_NAME="VRMC_materials_hdr_emissiveMultiplier";var Eo=_i,Ao=Object.defineProperty,Po=Object.defineProperties,Lo=Object.getOwnPropertyDescriptors,An=Object.getOwnPropertySymbols,bo=Object.prototype.hasOwnProperty,Io=Object.prototype.propertyIsEnumerable,Pn=(t,e,n)=>e in t?Ao(t,e,{enumerable:!0,configurable:!0,writable:!0,value:n}):t[e]=n,Q=(t,e)=>{for(var n in e||(e={}))bo.call(e,n)&&Pn(t,n,e[n]);if(An)for(var n of An(e))Io.call(e,n)&&Pn(t,n,e[n]);return t},Ln=(t,e)=>Po(t,Lo(e)),Co=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())});function _e(t){return Math.pow(t,2.2)}var Oo=class{get name(){return"VRMMaterialsV0CompatPlugin"}constructor(t){var e;this.parser=t,this._renderQueueMapTransparent=new Map,this._renderQueueMapTransparentZWrite=new Map;const n=this.parser.json;n.extensionsUsed=(e=n.extensionsUsed)!=null?e:[],n.extensionsUsed.indexOf("KHR_texture_transform")===-1&&n.extensionsUsed.push("KHR_texture_transform")}beforeRoot(){return Co(this,null,function*(){var t;const e=this.parser.json,n=(t=e.extensions)==null?void 0:t.VRM,i=n==null?void 0:n.materialProperties;i&&(this._populateRenderQueueMap(i),i.forEach((r,o)=>{var s,l;const a=(s=e.materials)==null?void 0:s[o];if(a==null){console.warn(`VRMMaterialsV0CompatPlugin: Attempt to use materials[${o}] of glTF but the material doesn't exist`);return}if(r.shader==="VRM/MToon"){const u=this._parseV0MToonProperties(r,a);e.materials[o]=u}else if((l=r.shader)!=null&&l.startsWith("VRM/Unlit")){const u=this._parseV0UnlitProperties(r,a);e.materials[o]=u}else r.shader==="VRM_USE_GLTFSHADER"||console.warn(`VRMMaterialsV0CompatPlugin: Unknown shader: ${r.shader}`)}))})}_parseV0MToonProperties(t,e){var n,i,r,o,s,l,a,u,h,d,c,f,m,p,g,v,M,w,R,y,x,S,E,C,P,L,O,k,ee,Y,W,B,te,X,V,ce,Te,Se,se,Ee,Ae,Pe,Le,re,pe,be,A,U,ne,fe,Fe,F,H,G,Dt;const kt=(i=(n=t.keywordMap)==null?void 0:n._ALPHABLEND_ON)!=null?i:!1,Pi=((r=t.floatProperties)==null?void 0:r._ZWrite)===1&&kt,Li=this._v0ParseRenderQueue(t),Bt=(s=(o=t.keywordMap)==null?void 0:o._ALPHATEST_ON)!=null?s:!1,bi=kt?"BLEND":Bt?"MASK":"OPAQUE",Ii=Bt?(a=(l=t.floatProperties)==null?void 0:l._Cutoff)!=null?a:.5:void 0,Ci=((h=(u=t.floatProperties)==null?void 0:u._CullMode)!=null?h:2)===0,ae=this._portTextureTransform(t),Oi=((c=(d=t.vectorProperties)==null?void 0:d._Color)!=null?c:[1,1,1,1]).map((qt,ir)=>ir===3?qt:_e(qt)),Ft=(f=t.textureProperties)==null?void 0:f._MainTex,Ui=Ft!=null?{index:Ft,extensions:Q({},ae)}:void 0,Ni=(p=(m=t.floatProperties)==null?void 0:m._BumpScale)!=null?p:1,Ht=(g=t.textureProperties)==null?void 0:g._BumpMap,Vi=Ht!=null?{index:Ht,scale:Ni,extensions:Q({},ae)}:void 0,Di=((M=(v=t.vectorProperties)==null?void 0:v._EmissionColor)!=null?M:[0,0,0,1]).map(_e),Wt=(w=t.textureProperties)==null?void 0:w._EmissionMap,ki=Wt!=null?{index:Wt,extensions:Q({},ae)}:void 0,Bi=((y=(R=t.vectorProperties)==null?void 0:R._ShadeColor)!=null?y:[.97,.81,.86,1]).map(_e),zt=(x=t.textureProperties)==null?void 0:x._ShadeTexture,Fi=zt!=null?{index:zt,extensions:Q({},ae)}:void 0;let He=(E=(S=t.floatProperties)==null?void 0:S._ShadeShift)!=null?E:0,We=(P=(C=t.floatProperties)==null?void 0:C._ShadeToony)!=null?P:.9;We=I.lerp(We,1,.5+.5*He),He=-He-(1-We);const jt=(O=(L=t.floatProperties)==null?void 0:L._IndirectLightIntensity)!=null?O:.1,Hi=jt?1-jt:void 0,ot=(k=t.textureProperties)==null?void 0:k._SphereAdd,Wi=ot!=null?[1,1,1]:void 0,zi=ot!=null?{index:ot}:void 0,ji=(Y=(ee=t.floatProperties)==null?void 0:ee._RimLightingMix)!=null?Y:0,Xt=(W=t.textureProperties)==null?void 0:W._RimTexture,Xi=Xt!=null?{index:Xt,extensions:Q({},ae)}:void 0,Gi=((te=(B=t.vectorProperties)==null?void 0:B._RimColor)!=null?te:[0,0,0,1]).map(_e),Yi=(V=(X=t.floatProperties)==null?void 0:X._RimFresnelPower)!=null?V:1,qi=(Te=(ce=t.floatProperties)==null?void 0:ce._RimLift)!=null?Te:0,Qi=["none","worldCoordinates","screenCoordinates"][(se=(Se=t.floatProperties)==null?void 0:Se._OutlineWidthMode)!=null?se:0];let st=(Ae=(Ee=t.floatProperties)==null?void 0:Ee._OutlineWidth)!=null?Ae:0;st=.01*st;const Gt=(Pe=t.textureProperties)==null?void 0:Pe._OutlineWidthTexture,$i=Gt!=null?{index:Gt,extensions:Q({},ae)}:void 0,Zi=((re=(Le=t.vectorProperties)==null?void 0:Le._OutlineColor)!=null?re:[0,0,0]).map(_e),Ji=((be=(pe=t.floatProperties)==null?void 0:pe._OutlineColorMode)!=null?be:0)===1?(U=(A=t.floatProperties)==null?void 0:A._OutlineLightingMix)!=null?U:1:0,Yt=(ne=t.textureProperties)==null?void 0:ne._UvAnimMaskTexture,Ki=Yt!=null?{index:Yt,extensions:Q({},ae)}:void 0,er=(Fe=(fe=t.floatProperties)==null?void 0:fe._UvAnimScrollX)!=null?Fe:0;let ze=(H=(F=t.floatProperties)==null?void 0:F._UvAnimScrollY)!=null?H:0;ze!=null&&(ze=-ze);const tr=(Dt=(G=t.floatProperties)==null?void 0:G._UvAnimRotation)!=null?Dt:0,nr={specVersion:"1.0",transparentWithZWrite:Pi,renderQueueOffsetNumber:Li,shadeColorFactor:Bi,shadeMultiplyTexture:Fi,shadingShiftFactor:He,shadingToonyFactor:We,giEqualizationFactor:Hi,matcapFactor:Wi,matcapTexture:zi,rimLightingMixFactor:ji,rimMultiplyTexture:Xi,parametricRimColorFactor:Gi,parametricRimFresnelPowerFactor:Yi,parametricRimLiftFactor:qi,outlineWidthMode:Qi,outlineWidthFactor:st,outlineWidthMultiplyTexture:$i,outlineColorFactor:Zi,outlineLightingMixFactor:Ji,uvAnimationMaskTexture:Ki,uvAnimationScrollXSpeedFactor:er,uvAnimationScrollYSpeedFactor:ze,uvAnimationRotationSpeedFactor:tr};return Ln(Q({},e),{pbrMetallicRoughness:{baseColorFactor:Oi,baseColorTexture:Ui},normalTexture:Vi,emissiveTexture:ki,emissiveFactor:Di,alphaMode:bi,alphaCutoff:Ii,doubleSided:Ci,extensions:{VRMC_materials_mtoon:nr}})}_parseV0UnlitProperties(t,e){var n,i,r,o,s;const l=t.shader==="VRM/UnlitTransparentZWrite",a=t.shader==="VRM/UnlitTransparent"||l,u=this._v0ParseRenderQueue(t),h=t.shader==="VRM/UnlitCutout",d=a?"BLEND":h?"MASK":"OPAQUE",c=h?(i=(n=t.floatProperties)==null?void 0:n._Cutoff)!=null?i:.5:void 0,f=this._portTextureTransform(t),m=((o=(r=t.vectorProperties)==null?void 0:r._Color)!=null?o:[1,1,1,1]).map(_e),p=(s=t.textureProperties)==null?void 0:s._MainTex,g=p!=null?{index:p,extensions:Q({},f)}:void 0,v={specVersion:"1.0",transparentWithZWrite:l,renderQueueOffsetNumber:u,shadeColorFactor:m,shadeMultiplyTexture:g};return Ln(Q({},e),{pbrMetallicRoughness:{baseColorFactor:m,baseColorTexture:g},alphaMode:d,alphaCutoff:c,extensions:{VRMC_materials_mtoon:v}})}_portTextureTransform(t){var e,n,i,r,o;const s=(e=t.vectorProperties)==null?void 0:e._MainTex;if(s==null)return{};const l=[(n=s==null?void 0:s[0])!=null?n:0,(i=s==null?void 0:s[1])!=null?i:0],a=[(r=s==null?void 0:s[2])!=null?r:1,(o=s==null?void 0:s[3])!=null?o:1];return l[1]=1-a[1]-l[1],{KHR_texture_transform:{offset:l,scale:a}}}_v0ParseRenderQueue(t){var e,n;const i=t.shader==="VRM/UnlitTransparentZWrite",r=((e=t.keywordMap)==null?void 0:e._ALPHABLEND_ON)!=null||t.shader==="VRM/UnlitTransparent"||i,o=((n=t.floatProperties)==null?void 0:n._ZWrite)===1||i;let s=0;if(r){const l=t.renderQueue;l!=null&&(o?s=this._renderQueueMapTransparentZWrite.get(l):s=this._renderQueueMapTransparent.get(l))}return s}_populateRenderQueueMap(t){const e=new Set,n=new Set;t.forEach(i=>{var r,o;const s=i.shader==="VRM/UnlitTransparentZWrite",l=((r=i.keywordMap)==null?void 0:r._ALPHABLEND_ON)!=null||i.shader==="VRM/UnlitTransparent"||s,a=((o=i.floatProperties)==null?void 0:o._ZWrite)===1||s;if(l){const u=i.renderQueue;u!=null&&(a?n.add(u):e.add(u))}}),e.size>10&&console.warn(`VRMMaterialsV0CompatPlugin: This VRM uses ${e.size} render queues for Transparent materials while VRM 1.0 only supports up to 10 render queues. The model might not be rendered correctly.`),n.size>10&&console.warn(`VRMMaterialsV0CompatPlugin: This VRM uses ${n.size} render queues for TransparentZWrite materials while VRM 1.0 only supports up to 10 render queues. The model might not be rendered correctly.`),Array.from(e).sort().forEach((i,r)=>{const o=Math.min(Math.max(r-e.size+1,-9),0);this._renderQueueMapTransparent.set(i,o)}),Array.from(n).sort().forEach((i,r)=>{const o=Math.min(Math.max(r,0),9);this._renderQueueMapTransparentZWrite.set(i,o)})}},bn=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),oe=new _,ct=class extends Re{constructor(t){super(),this._attrPosition=new D(new Float32Array([0,0,0,0,0,0]),3),this._attrPosition.setUsage(gr);const e=new ie;e.setAttribute("position",this._attrPosition);const n=new it({color:16711935,depthTest:!1,depthWrite:!1});this._line=new _r(e,n),this.add(this._line),this.constraint=t}updateMatrixWorld(t){oe.setFromMatrixPosition(this.constraint.destination.matrixWorld),this._attrPosition.setXYZ(0,oe.x,oe.y,oe.z),this.constraint.source&&oe.setFromMatrixPosition(this.constraint.source.matrixWorld),this._attrPosition.setXYZ(1,oe.x,oe.y,oe.z),this._attrPosition.needsUpdate=!0,super.updateMatrixWorld(t)}};function In(t,e){return e.set(t.elements[12],t.elements[13],t.elements[14])}var Uo=new _,No=new _;function Vo(t,e){return t.decompose(Uo,e,No),e}function Ke(t){return t.invert?t.invert():t.inverse(),t}var Nt=class{constructor(t,e){this.destination=t,this.source=e,this.weight=1}},Do=new _,ko=new _,Bo=new _,Fo=new T,Ho=new T,Wo=new T,zo=class extends Nt{get aimAxis(){return this._aimAxis}set aimAxis(t){this._aimAxis=t,this._v3AimAxis.set(t==="PositiveX"?1:t==="NegativeX"?-1:0,t==="PositiveY"?1:t==="NegativeY"?-1:0,t==="PositiveZ"?1:t==="NegativeZ"?-1:0)}get dependencies(){const t=new Set([this.source]);return this.destination.parent&&t.add(this.destination.parent),t}constructor(t,e){super(t,e),this._aimAxis="PositiveX",this._v3AimAxis=new _(1,0,0),this._dstRestQuat=new T}setInitState(){this._dstRestQuat.copy(this.destination.quaternion)}update(){this.destination.updateWorldMatrix(!0,!1),this.source.updateWorldMatrix(!0,!1);const t=Fo.identity(),e=Ho.identity();this.destination.parent&&(Vo(this.destination.parent.matrixWorld,t),Ke(e.copy(t)));const n=Do.copy(this._v3AimAxis).applyQuaternion(this._dstRestQuat).applyQuaternion(t),i=In(this.source.matrixWorld,ko).sub(In(this.destination.matrixWorld,Bo)).normalize(),r=Wo.setFromUnitVectors(n,i).premultiply(e).multiply(t).multiply(this._dstRestQuat);this.destination.quaternion.copy(this._dstRestQuat).slerp(r,this.weight)}};function jo(t,e){const n=[t];let i=t.parent;for(;i!==null;)n.unshift(i),i=i.parent;n.forEach(r=>{e(r)})}var Xo=class{constructor(){this._constraints=new Set,this._objectConstraintsMap=new Map}get constraints(){return this._constraints}addConstraint(t){this._constraints.add(t);let e=this._objectConstraintsMap.get(t.destination);e==null&&(e=new Set,this._objectConstraintsMap.set(t.destination,e)),e.add(t)}deleteConstraint(t){this._constraints.delete(t),this._objectConstraintsMap.get(t.destination).delete(t)}setInitState(){const t=new Set,e=new Set;for(const n of this._constraints)this._processConstraint(n,t,e,i=>i.setInitState())}update(){const t=new Set,e=new Set;for(const n of this._constraints)this._processConstraint(n,t,e,i=>i.update())}_processConstraint(t,e,n,i){if(n.has(t))return;if(e.has(t))throw new Error("VRMNodeConstraintManager: Circular dependency detected while updating constraints");e.add(t);const r=t.dependencies;for(const o of r)jo(o,s=>{const l=this._objectConstraintsMap.get(s);if(l)for(const a of l)this._processConstraint(a,e,n,i)});i(t),n.add(t)}},Go=new T,Yo=new T,qo=class extends Nt{get dependencies(){return new Set([this.source])}constructor(t,e){super(t,e),this._dstRestQuat=new T,this._invSrcRestQuat=new T}setInitState(){this._dstRestQuat.copy(this.destination.quaternion),Ke(this._invSrcRestQuat.copy(this.source.quaternion))}update(){const t=Go.copy(this._invSrcRestQuat).multiply(this.source.quaternion),e=Yo.copy(this._dstRestQuat).multiply(t);this.destination.quaternion.copy(this._dstRestQuat).slerp(e,this.weight)}},Qo=new _,$o=new T,Zo=new T,Jo=class extends Nt{get rollAxis(){return this._rollAxis}set rollAxis(t){this._rollAxis=t,this._v3RollAxis.set(t==="X"?1:0,t==="Y"?1:0,t==="Z"?1:0)}get dependencies(){return new Set([this.source])}constructor(t,e){super(t,e),this._rollAxis="X",this._v3RollAxis=new _(1,0,0),this._dstRestQuat=new T,this._invDstRestQuat=new T,this._invSrcRestQuatMulDstRestQuat=new T}setInitState(){this._dstRestQuat.copy(this.destination.quaternion),Ke(this._invDstRestQuat.copy(this._dstRestQuat)),Ke(this._invSrcRestQuatMulDstRestQuat.copy(this.source.quaternion)).multiply(this._dstRestQuat)}update(){const t=$o.copy(this._invDstRestQuat).multiply(this.source.quaternion).multiply(this._invSrcRestQuatMulDstRestQuat),e=Qo.copy(this._v3RollAxis).applyQuaternion(t),i=Zo.setFromUnitVectors(e,this._v3RollAxis).premultiply(this._dstRestQuat).multiply(t);this.destination.quaternion.copy(this._dstRestQuat).slerp(i,this.weight)}},Ko=new Set(["1.0","1.0-beta"]),vi=class Be{get name(){return Be.EXTENSION_NAME}constructor(e,n){this.parser=e,this.helperRoot=n==null?void 0:n.helperRoot}afterRoot(e){return bn(this,null,function*(){e.userData.vrmNodeConstraintManager=yield this._import(e)})}_import(e){return bn(this,null,function*(){var n;const i=this.parser.json;if(!(((n=i.extensionsUsed)==null?void 0:n.indexOf(Be.EXTENSION_NAME))!==-1))return null;const o=new Xo,s=yield this.parser.getDependencies("node");return s.forEach((l,a)=>{var u;const h=i.nodes[a],d=(u=h==null?void 0:h.extensions)==null?void 0:u[Be.EXTENSION_NAME];if(d==null)return;const c=d.specVersion;if(!Ko.has(c)){console.warn(`VRMNodeConstraintLoaderPlugin: Unknown ${Be.EXTENSION_NAME} specVersion "${c}"`);return}const f=d.constraint;if(f.roll!=null){const m=this._importRollConstraint(l,s,f.roll);o.addConstraint(m)}else if(f.aim!=null){const m=this._importAimConstraint(l,s,f.aim);o.addConstraint(m)}else if(f.rotation!=null){const m=this._importRotationConstraint(l,s,f.rotation);o.addConstraint(m)}}),e.scene.updateMatrixWorld(),o.setInitState(),o})}_importRollConstraint(e,n,i){const{source:r,rollAxis:o,weight:s}=i,l=n[r],a=new Jo(e,l);if(o!=null&&(a.rollAxis=o),s!=null&&(a.weight=s),this.helperRoot){const u=new ct(a);this.helperRoot.add(u)}return a}_importAimConstraint(e,n,i){const{source:r,aimAxis:o,weight:s}=i,l=n[r],a=new zo(e,l);if(o!=null&&(a.aimAxis=o),s!=null&&(a.weight=s),this.helperRoot){const u=new ct(a);this.helperRoot.add(u)}return a}_importRotationConstraint(e,n,i){const{source:r,weight:o}=i,s=n[r],l=new qo(e,s);if(o!=null&&(l.weight=o),this.helperRoot){const a=new ct(l);this.helperRoot.add(a)}return l}};vi.EXTENSION_NAME="VRMC_node_constraint";var es=vi,Ye=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),Vt=class{},pt=new _,de=new _,Mi=class extends Vt{get type(){return"capsule"}constructor(t){var e,n,i,r;super(),this.offset=(e=t==null?void 0:t.offset)!=null?e:new _(0,0,0),this.tail=(n=t==null?void 0:t.tail)!=null?n:new _(0,0,0),this.radius=(i=t==null?void 0:t.radius)!=null?i:0,this.inside=(r=t==null?void 0:t.inside)!=null?r:!1}calculateCollision(t,e,n,i){pt.setFromMatrixPosition(t),de.subVectors(this.tail,this.offset).applyMatrix4(t),de.sub(pt);const r=de.lengthSq();i.copy(e).sub(pt);const o=de.dot(i);o<=0||(r<=o||de.multiplyScalar(o/r),i.sub(de));const s=i.length(),l=this.inside?this.radius-n-s:s-n-this.radius;return l<0&&(i.multiplyScalar(1/s),this.inside&&i.negate()),l}},ft=new _,Cn=new Z,xi=class extends Vt{get type(){return"plane"}constructor(t){var e,n;super(),this.offset=(e=t==null?void 0:t.offset)!=null?e:new _(0,0,0),this.normal=(n=t==null?void 0:t.normal)!=null?n:new _(0,0,1)}calculateCollision(t,e,n,i){i.setFromMatrixPosition(t),i.negate().add(e),Cn.getNormalMatrix(t),ft.copy(this.normal).applyNormalMatrix(Cn).normalize();const r=i.dot(ft)-n;return i.copy(ft),r}},ts=new _,yi=class extends Vt{get type(){return"sphere"}constructor(t){var e,n,i;super(),this.offset=(e=t==null?void 0:t.offset)!=null?e:new _(0,0,0),this.radius=(n=t==null?void 0:t.radius)!=null?n:0,this.inside=(i=t==null?void 0:t.inside)!=null?i:!1}calculateCollision(t,e,n,i){i.subVectors(e,ts.setFromMatrixPosition(t));const r=i.length(),o=this.inside?this.radius-n-r:r-n-this.radius;return o<0&&(i.multiplyScalar(1/r),this.inside&&i.negate()),o}},$=new _,ns=class extends ie{constructor(t){super(),this.worldScale=1,this._currentRadius=0,this._currentOffset=new _,this._currentTail=new _,this._shape=t,this._attrPos=new D(new Float32Array(396),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(264),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;const e=this._shape.radius/this.worldScale;this._currentRadius!==e&&(this._currentRadius=e,t=!0),this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),t=!0);const n=$.copy(this._shape.tail).divideScalar(this.worldScale);this._currentTail.distanceToSquared(n)>1e-10&&(this._currentTail.copy(n),t=!0),t&&this._buildPosition()}_buildPosition(){$.copy(this._currentTail).sub(this._currentOffset);const t=$.length()/this._currentRadius;for(let i=0;i<=16;i++){const r=i/16*Math.PI;this._attrPos.setXYZ(i,-Math.sin(r),-Math.cos(r),0),this._attrPos.setXYZ(17+i,t+Math.sin(r),Math.cos(r),0),this._attrPos.setXYZ(34+i,-Math.sin(r),0,-Math.cos(r)),this._attrPos.setXYZ(51+i,t+Math.sin(r),0,Math.cos(r))}for(let i=0;i<32;i++){const r=i/16*Math.PI;this._attrPos.setXYZ(68+i,0,Math.sin(r),Math.cos(r)),this._attrPos.setXYZ(100+i,t,Math.sin(r),Math.cos(r))}const e=Math.atan2($.y,Math.sqrt($.x*$.x+$.z*$.z)),n=-Math.atan2($.z,$.x);this.rotateZ(e),this.rotateY(n),this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<34;t++){const e=(t+1)%34;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(68+t*2,34+t,34+e)}for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(136+t*2,68+t,68+e),this._attrIndex.setXY(200+t*2,100+t,100+e)}this._attrIndex.needsUpdate=!0}},is=class extends ie{constructor(t){super(),this.worldScale=1,this._currentOffset=new _,this._currentNormal=new _,this._shape=t,this._attrPos=new D(new Float32Array(6*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(10),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),t=!0),this._currentNormal.equals(this._shape.normal)||(this._currentNormal.copy(this._shape.normal),t=!0),t&&this._buildPosition()}_buildPosition(){this._attrPos.setXYZ(0,-.5,-.5,0),this._attrPos.setXYZ(1,.5,-.5,0),this._attrPos.setXYZ(2,.5,.5,0),this._attrPos.setXYZ(3,-.5,.5,0),this._attrPos.setXYZ(4,0,0,0),this._attrPos.setXYZ(5,0,0,.25),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this.lookAt(this._currentNormal),this._attrPos.needsUpdate=!0}_buildIndex(){this._attrIndex.setXY(0,0,1),this._attrIndex.setXY(2,1,2),this._attrIndex.setXY(4,2,3),this._attrIndex.setXY(6,3,0),this._attrIndex.setXY(8,4,5),this._attrIndex.needsUpdate=!0}},rs=class extends ie{constructor(t){super(),this.worldScale=1,this._currentRadius=0,this._currentOffset=new _,this._shape=t,this._attrPos=new D(new Float32Array(32*3*3),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(64*3),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;const e=this._shape.radius/this.worldScale;this._currentRadius!==e&&(this._currentRadius=e,t=!0),this._currentOffset.equals(this._shape.offset)||(this._currentOffset.copy(this._shape.offset),t=!0),t&&this._buildPosition()}_buildPosition(){for(let t=0;t<32;t++){const e=t/16*Math.PI;this._attrPos.setXYZ(t,Math.cos(e),Math.sin(e),0),this._attrPos.setXYZ(32+t,0,Math.cos(e),Math.sin(e)),this._attrPos.setXYZ(64+t,Math.sin(e),0,Math.cos(e))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentOffset.x,this._currentOffset.y,this._currentOffset.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(64+t*2,32+t,32+e),this._attrIndex.setXY(128+t*2,64+t,64+e)}this._attrIndex.needsUpdate=!0}},os=new _,mt=class extends Re{constructor(t){if(super(),this.matrixAutoUpdate=!1,this.collider=t,this.collider.shape instanceof yi)this._geometry=new rs(this.collider.shape);else if(this.collider.shape instanceof Mi)this._geometry=new ns(this.collider.shape);else if(this.collider.shape instanceof xi)this._geometry=new is(this.collider.shape);else throw new Error("VRMSpringBoneColliderHelper: Unknown collider shape type detected");const e=new it({color:16711935,depthTest:!1,depthWrite:!1});this._line=new Ct(this._geometry,e),this.add(this._line)}dispose(){this._geometry.dispose()}updateMatrixWorld(t){this.collider.updateWorldMatrix(!0,!1),this.matrix.copy(this.collider.matrixWorld);const e=this.matrix.elements;this._geometry.worldScale=os.set(e[0],e[1],e[2]).length(),this._geometry.update(),super.updateMatrixWorld(t)}},ss=class extends ie{constructor(t){super(),this.worldScale=1,this._currentRadius=0,this._currentTail=new _,this._springBone=t,this._attrPos=new D(new Float32Array(294),3),this.setAttribute("position",this._attrPos),this._attrIndex=new D(new Uint16Array(194),1),this.setIndex(this._attrIndex),this._buildIndex(),this.update()}update(){let t=!1;const e=this._springBone.settings.hitRadius/this.worldScale;this._currentRadius!==e&&(this._currentRadius=e,t=!0),this._currentTail.equals(this._springBone.initialLocalChildPosition)||(this._currentTail.copy(this._springBone.initialLocalChildPosition),t=!0),t&&this._buildPosition()}_buildPosition(){for(let t=0;t<32;t++){const e=t/16*Math.PI;this._attrPos.setXYZ(t,Math.cos(e),Math.sin(e),0),this._attrPos.setXYZ(32+t,0,Math.cos(e),Math.sin(e)),this._attrPos.setXYZ(64+t,Math.sin(e),0,Math.cos(e))}this.scale(this._currentRadius,this._currentRadius,this._currentRadius),this.translate(this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.setXYZ(96,0,0,0),this._attrPos.setXYZ(97,this._currentTail.x,this._currentTail.y,this._currentTail.z),this._attrPos.needsUpdate=!0}_buildIndex(){for(let t=0;t<32;t++){const e=(t+1)%32;this._attrIndex.setXY(t*2,t,e),this._attrIndex.setXY(64+t*2,32+t,32+e),this._attrIndex.setXY(128+t*2,64+t,64+e)}this._attrIndex.setXY(192,96,97),this._attrIndex.needsUpdate=!0}},as=new _,ls=class extends Re{constructor(t){super(),this.matrixAutoUpdate=!1,this.springBone=t,this._geometry=new ss(this.springBone);const e=new it({color:16776960,depthTest:!1,depthWrite:!1});this._line=new Ct(this._geometry,e),this.add(this._line)}dispose(){this._geometry.dispose()}updateMatrixWorld(t){this.springBone.bone.updateWorldMatrix(!0,!1),this.matrix.copy(this.springBone.bone.matrixWorld);const e=this.matrix.elements;this._geometry.worldScale=as.set(e[0],e[1],e[2]).length(),this._geometry.update(),super.updateMatrixWorld(t)}},gt=class extends ye{constructor(t){super(),this.colliderMatrix=new K,this.shape=t}updateWorldMatrix(t,e){super.updateWorldMatrix(t,e),us(this.colliderMatrix,this.matrixWorld,this.shape.offset)}};function us(t,e,n){const i=e.elements;t.copy(e),n&&(t.elements[12]=i[0]*n.x+i[4]*n.y+i[8]*n.z+i[12],t.elements[13]=i[1]*n.x+i[5]*n.y+i[9]*n.z+i[13],t.elements[14]=i[2]*n.x+i[6]*n.y+i[10]*n.z+i[14])}var ds=new K;function hs(t){return t.invert?t.invert():t.getInverse(ds.copy(t)),t}var cs=class{constructor(t){this._inverseCache=new K,this._shouldUpdateInverse=!0,this.matrix=t;const e={set:(n,i,r)=>(this._shouldUpdateInverse=!0,n[i]=r,!0)};this._originalElements=t.elements,t.elements=new Proxy(t.elements,e)}get inverse(){return this._shouldUpdateInverse&&(hs(this._inverseCache.copy(this.matrix)),this._shouldUpdateInverse=!1),this._inverseCache}revert(){this.matrix.elements=this._originalElements}},_t=new K,ve=new _,Ue=new _,Ne=new _,Ve=new _,ps=new K,fs=class{constructor(t,e,n={},i=[]){this._currentTail=new _,this._prevTail=new _,this._boneAxis=new _,this._worldSpaceBoneLength=0,this._center=null,this._initialLocalMatrix=new K,this._initialLocalRotation=new T,this._initialLocalChildPosition=new _;var r,o,s,l,a,u;this.bone=t,this.bone.matrixAutoUpdate=!1,this.child=e,this.settings={hitRadius:(r=n.hitRadius)!=null?r:0,stiffness:(o=n.stiffness)!=null?o:1,gravityPower:(s=n.gravityPower)!=null?s:0,gravityDir:(a=(l=n.gravityDir)==null?void 0:l.clone())!=null?a:new _(0,-1,0),dragForce:(u=n.dragForce)!=null?u:.4},this.colliderGroups=i}get dependencies(){const t=new Set,e=this.bone.parent;e&&t.add(e);for(let n=0;n<this.colliderGroups.length;n++)for(let i=0;i<this.colliderGroups[n].colliders.length;i++)t.add(this.colliderGroups[n].colliders[i]);return t}get center(){return this._center}set center(t){var e;(e=this._center)!=null&&e.userData.inverseCacheProxy&&(this._center.userData.inverseCacheProxy.revert(),delete this._center.userData.inverseCacheProxy),this._center=t,this._center&&(this._center.userData.inverseCacheProxy||(this._center.userData.inverseCacheProxy=new cs(this._center.matrixWorld)))}get initialLocalChildPosition(){return this._initialLocalChildPosition}get _parentMatrixWorld(){return this.bone.parent?this.bone.parent.matrixWorld:_t}setInitState(){this._initialLocalMatrix.copy(this.bone.matrix),this._initialLocalRotation.copy(this.bone.quaternion),this.child?this._initialLocalChildPosition.copy(this.child.position):this._initialLocalChildPosition.copy(this.bone.position).normalize().multiplyScalar(.07);const t=this._getMatrixWorldToCenter();this.bone.localToWorld(this._currentTail.copy(this._initialLocalChildPosition)).applyMatrix4(t),this._prevTail.copy(this._currentTail),this._boneAxis.copy(this._initialLocalChildPosition).normalize()}reset(){this.bone.quaternion.copy(this._initialLocalRotation),this.bone.updateMatrix(),this.bone.matrixWorld.multiplyMatrices(this._parentMatrixWorld,this.bone.matrix);const t=this._getMatrixWorldToCenter();this.bone.localToWorld(this._currentTail.copy(this._initialLocalChildPosition)).applyMatrix4(t),this._prevTail.copy(this._currentTail)}update(t){if(t<=0)return;this._calcWorldSpaceBoneLength();const e=Ue.copy(this._boneAxis).transformDirection(this._initialLocalMatrix).transformDirection(this._parentMatrixWorld);Ve.copy(this._currentTail).add(ve.subVectors(this._currentTail,this._prevTail).multiplyScalar(1-this.settings.dragForce)).applyMatrix4(this._getMatrixCenterToWorld()).addScaledVector(e,this.settings.stiffness*t).addScaledVector(this.settings.gravityDir,this.settings.gravityPower*t),Ne.setFromMatrixPosition(this.bone.matrixWorld),Ve.sub(Ne).normalize().multiplyScalar(this._worldSpaceBoneLength).add(Ne),this._collision(Ve),this._prevTail.copy(this._currentTail),this._currentTail.copy(Ve).applyMatrix4(this._getMatrixWorldToCenter());const n=ps.multiplyMatrices(this._parentMatrixWorld,this._initialLocalMatrix).invert();this.bone.quaternion.setFromUnitVectors(this._boneAxis,ve.copy(Ve).applyMatrix4(n).normalize()).premultiply(this._initialLocalRotation),this.bone.updateMatrix(),this.bone.matrixWorld.multiplyMatrices(this._parentMatrixWorld,this.bone.matrix)}_collision(t){for(let e=0;e<this.colliderGroups.length;e++)for(let n=0;n<this.colliderGroups[e].colliders.length;n++){const i=this.colliderGroups[e].colliders[n],r=i.shape.calculateCollision(i.colliderMatrix,t,this.settings.hitRadius,ve);if(r<0){t.addScaledVector(ve,-r),t.sub(Ne);const o=t.length();t.multiplyScalar(this._worldSpaceBoneLength/o).add(Ne)}}}_calcWorldSpaceBoneLength(){ve.setFromMatrixPosition(this.bone.matrixWorld),this.child?Ue.setFromMatrixPosition(this.child.matrixWorld):(Ue.copy(this._initialLocalChildPosition),Ue.applyMatrix4(this.bone.matrixWorld)),this._worldSpaceBoneLength=ve.sub(Ue).length()}_getMatrixCenterToWorld(){return this._center?this._center.matrixWorld:_t}_getMatrixWorldToCenter(){return this._center?this._center.userData.inverseCacheProxy.inverse:_t}};function ms(t,e){const n=[];let i=t;for(;i!==null;)n.unshift(i),i=i.parent;n.forEach(r=>{e(r)})}function It(t,e){t.children.forEach(n=>{e(n)||It(n,e)})}function gs(t){var e;const n=new Map;for(const i of t){let r=i;do{const o=((e=n.get(r))!=null?e:0)+1;if(o===t.size)return r;n.set(r,o),r=r.parent}while(r!==null)}return null}var On=class{constructor(){this._joints=new Set,this._sortedJoints=[],this._hasWarnedCircularDependency=!1,this._ancestors=[],this._objectSpringBonesMap=new Map,this._isSortedJointsDirty=!1,this._relevantChildrenUpdated=this._relevantChildrenUpdated.bind(this)}get joints(){return this._joints}get springBones(){return console.warn("VRMSpringBoneManager: springBones is deprecated. use joints instead."),this._joints}get colliderGroups(){const t=new Set;return this._joints.forEach(e=>{e.colliderGroups.forEach(n=>{t.add(n)})}),Array.from(t)}get colliders(){const t=new Set;return this.colliderGroups.forEach(e=>{e.colliders.forEach(n=>{t.add(n)})}),Array.from(t)}addJoint(t){this._joints.add(t);let e=this._objectSpringBonesMap.get(t.bone);e==null&&(e=new Set,this._objectSpringBonesMap.set(t.bone,e)),e.add(t),this._isSortedJointsDirty=!0}addSpringBone(t){console.warn("VRMSpringBoneManager: addSpringBone() is deprecated. use addJoint() instead."),this.addJoint(t)}deleteJoint(t){this._joints.delete(t),this._objectSpringBonesMap.get(t.bone).delete(t),this._isSortedJointsDirty=!0}deleteSpringBone(t){console.warn("VRMSpringBoneManager: deleteSpringBone() is deprecated. use deleteJoint() instead."),this.deleteJoint(t)}setInitState(){this._sortJoints();for(let t=0;t<this._sortedJoints.length;t++){const e=this._sortedJoints[t];e.bone.updateMatrix(),e.bone.updateWorldMatrix(!1,!1),e.setInitState()}}reset(){this._sortJoints();for(let t=0;t<this._sortedJoints.length;t++){const e=this._sortedJoints[t];e.bone.updateMatrix(),e.bone.updateWorldMatrix(!1,!1),e.reset()}}update(t){this._sortJoints();for(let e=0;e<this._ancestors.length;e++)this._ancestors[e].updateWorldMatrix(e===0,!1);for(let e=0;e<this._sortedJoints.length;e++){const n=this._sortedJoints[e];n.bone.updateMatrix(),n.bone.updateWorldMatrix(!1,!1),n.update(t),It(n.bone,this._relevantChildrenUpdated)}}_sortJoints(){if(!this._isSortedJointsDirty)return;const t=[],e=new Set,n=new Set,i=new Set;for(const o of this._joints)this._insertJointSort(o,e,n,t,i);this._sortedJoints=t;const r=gs(i);this._ancestors=[],r&&(this._ancestors.push(r),It(r,o=>{var s,l;return((l=(s=this._objectSpringBonesMap.get(o))==null?void 0:s.size)!=null?l:0)>0?!0:(this._ancestors.push(o),!1)})),this._isSortedJointsDirty=!1}_insertJointSort(t,e,n,i,r){if(n.has(t))return;if(e.has(t)){this._hasWarnedCircularDependency||(console.warn("VRMSpringBoneManager: Circular dependency detected"),this._hasWarnedCircularDependency=!0);return}e.add(t);const o=t.dependencies;for(const s of o){let l=!1,a=null;ms(s,u=>{const h=this._objectSpringBonesMap.get(u);if(h)for(const d of h)l=!0,this._insertJointSort(d,e,n,i,r);else l||(a=u)}),a&&r.add(a)}i.push(t),n.add(t)}_relevantChildrenUpdated(t){var e,n;return((n=(e=this._objectSpringBonesMap.get(t))==null?void 0:e.size)!=null?n:0)>0?!0:(t.updateWorldMatrix(!1,!1),!1)}},Un="VRMC_springBone_extended_collider",_s=new Set(["1.0","1.0-beta"]),vs=new Set(["1.0"]),wi=class xe{get name(){return xe.EXTENSION_NAME}constructor(e,n){var i;this.parser=e,this.jointHelperRoot=n==null?void 0:n.jointHelperRoot,this.colliderHelperRoot=n==null?void 0:n.colliderHelperRoot,this.useExtendedColliders=(i=n==null?void 0:n.useExtendedColliders)!=null?i:!0}afterRoot(e){return Ye(this,null,function*(){e.userData.vrmSpringBoneManager=yield this._import(e)})}_import(e){return Ye(this,null,function*(){const n=yield this._v1Import(e);if(n!=null)return n;const i=yield this._v0Import(e);return i??null})}_v1Import(e){return Ye(this,null,function*(){var n,i,r,o,s;const l=e.parser.json;if(!(((n=l.extensionsUsed)==null?void 0:n.indexOf(xe.EXTENSION_NAME))!==-1))return null;const u=new On,h=yield e.parser.getDependencies("node"),d=(i=l.extensions)==null?void 0:i[xe.EXTENSION_NAME];if(!d)return null;const c=d.specVersion;if(!_s.has(c))return console.warn(`VRMSpringBoneLoaderPlugin: Unknown ${xe.EXTENSION_NAME} specVersion "${c}"`),null;const f=(r=d.colliders)==null?void 0:r.map((p,g)=>{var v,M,w,R,y,x,S,E,C,P,L,O,k,ee,Y;const W=h[p.node];if(W==null)return console.warn(`VRMSpringBoneLoaderPlugin: The collider #${g} attempted to reference a node #${p.node} but not found. Skipping the collider`),null;const B=p.shape,te=(v=p.extensions)==null?void 0:v[Un];if(this.useExtendedColliders&&te!=null){const X=te.specVersion;if(!vs.has(X))console.warn(`VRMSpringBoneLoaderPlugin: Unknown ${Un} specVersion "${X}". Fallbacking to the ${xe.EXTENSION_NAME} definition`);else{const V=te.shape;if(V.sphere)return this._importSphereCollider(W,{offset:new _().fromArray((M=V.sphere.offset)!=null?M:[0,0,0]),radius:(w=V.sphere.radius)!=null?w:0,inside:(R=V.sphere.inside)!=null?R:!1});if(V.capsule)return this._importCapsuleCollider(W,{offset:new _().fromArray((y=V.capsule.offset)!=null?y:[0,0,0]),radius:(x=V.capsule.radius)!=null?x:0,tail:new _().fromArray((S=V.capsule.tail)!=null?S:[0,0,0]),inside:(E=V.capsule.inside)!=null?E:!1});if(V.plane)return this._importPlaneCollider(W,{offset:new _().fromArray((C=V.plane.offset)!=null?C:[0,0,0]),normal:new _().fromArray((P=V.plane.normal)!=null?P:[0,0,1])})}}if(B.sphere)return this._importSphereCollider(W,{offset:new _().fromArray((L=B.sphere.offset)!=null?L:[0,0,0]),radius:(O=B.sphere.radius)!=null?O:0,inside:!1});if(B.capsule)return this._importCapsuleCollider(W,{offset:new _().fromArray((k=B.capsule.offset)!=null?k:[0,0,0]),radius:(ee=B.capsule.radius)!=null?ee:0,tail:new _().fromArray((Y=B.capsule.tail)!=null?Y:[0,0,0]),inside:!1});console.warn(`VRMSpringBoneLoaderPlugin: The collider #${g} has no valid shape. Skipping the collider`)}),m=(o=d.colliderGroups)==null?void 0:o.map((p,g)=>{var v;return{colliders:((v=p.colliders)!=null?v:[]).map(w=>{const R=f==null?void 0:f[w];return R??(console.warn(`VRMSpringBoneLoaderPlugin: The collider group #${g} attempted to reference a collider #${w} but not found. Skipping the collider`),null)}).filter(w=>w!=null),name:p.name}});return(s=d.springs)==null||s.forEach((p,g)=>{var v;const M=p.joints,w=(v=p.colliderGroups)==null?void 0:v.map(x=>{const S=m==null?void 0:m[x];return S??(console.warn(`VRMSpringBoneLoaderPlugin: The spring #${g} attempted to reference a collider group #${x} but not found. Skipping the collider group`),null)}).filter(x=>x!=null),R=p.center!=null?h[p.center]:void 0;let y;M.forEach(x=>{if(y){const S=y.node,E=h[S],C=x.node,P=h[C],L={hitRadius:y.hitRadius,dragForce:y.dragForce,gravityPower:y.gravityPower,stiffness:y.stiffness,gravityDir:y.gravityDir!=null?new _().fromArray(y.gravityDir):void 0},O=this._importJoint(E,P,L,w);R&&(O.center=R),u.addJoint(O)}y=x})}),u.setInitState(),u})}_v0Import(e){return Ye(this,null,function*(){var n,i,r;const o=e.parser.json;if(!(((n=o.extensionsUsed)==null?void 0:n.indexOf("VRM"))!==-1))return null;const l=(i=o.extensions)==null?void 0:i.VRM,a=l==null?void 0:l.secondaryAnimation;if(!a)return null;const u=a==null?void 0:a.boneGroups;if(!u)return null;const h=new On,d=yield e.parser.getDependencies("node"),c=(r=a.colliderGroups)==null?void 0:r.map((f,m)=>{var p;const g=d[f.node];return g==null?(console.warn(`VRMSpringBoneLoaderPlugin: The collider group #${m} attempted to reference a node #${f.node} but not found. Skipping the collider group`),null):{colliders:((p=f.colliders)!=null?p:[]).map((M,w)=>{var R,y,x;const S=new _(0,0,0);return M.offset&&S.set((R=M.offset.x)!=null?R:0,(y=M.offset.y)!=null?y:0,M.offset.z?-M.offset.z:0),this._importSphereCollider(g,{offset:S,radius:(x=M.radius)!=null?x:0,inside:!1})})}});return u==null||u.forEach((f,m)=>{const p=f.bones;p&&p.forEach(g=>{var v,M,w,R;const y=d[g];if(y==null){console.warn(`VRMSpringBoneLoaderPlugin: The spring bone group #${m} attempted to reference a node #${g} but not found. Skipping the node`);return}const x=new _;f.gravityDir?x.set((v=f.gravityDir.x)!=null?v:0,(M=f.gravityDir.y)!=null?M:0,(w=f.gravityDir.z)!=null?w:0):x.set(0,-1,0);const S=f.center!=null?d[f.center]:void 0,E={hitRadius:f.hitRadius,dragForce:f.dragForce,gravityPower:f.gravityPower,stiffness:f.stiffiness,gravityDir:x},C=(R=f.colliderGroups)==null?void 0:R.map(P=>{const L=c==null?void 0:c[P];return L??(console.warn(`VRMSpringBoneLoaderPlugin: The spring #${m} attempted to reference a collider group #${P} but not found. Skipping the collider group`),null)}).filter(P=>P!=null);y.traverse(P=>{var L;const O=(L=P.children[0])!=null?L:null,k=this._importJoint(P,O,E,C);S&&(k.center=S),h.addJoint(k)})})}),e.scene.updateMatrixWorld(),h.setInitState(),h})}_importJoint(e,n,i,r){const o=new fs(e,n,i,r);if(this.jointHelperRoot){const s=new ls(o);this.jointHelperRoot.add(s),s.renderOrder=this.jointHelperRoot.renderOrder}return o}_importSphereCollider(e,n){const i=new yi(n),r=new gt(i);if(e.add(r),this.colliderHelperRoot){const o=new mt(r);this.colliderHelperRoot.add(o),o.renderOrder=this.colliderHelperRoot.renderOrder}return r}_importCapsuleCollider(e,n){const i=new Mi(n),r=new gt(i);if(e.add(r),this.colliderHelperRoot){const o=new mt(r);this.colliderHelperRoot.add(o),o.renderOrder=this.colliderHelperRoot.renderOrder}return r}_importPlaneCollider(e,n){const i=new xi(n),r=new gt(i);if(e.add(r),this.colliderHelperRoot){const o=new mt(r);this.colliderHelperRoot.add(o),o.renderOrder=this.colliderHelperRoot.renderOrder}return r}};wi.EXTENSION_NAME="VRMC_springBone";var Ms=wi,xs=class{get name(){return"VRMLoaderPlugin"}constructor(t,e){var n,i,r,o,s,l,a,u,h,d;this.parser=t;const c=e==null?void 0:e.helperRoot,f=e==null?void 0:e.autoUpdateHumanBones;this.expressionPlugin=(n=e==null?void 0:e.expressionPlugin)!=null?n:new Nr(t),this.firstPersonPlugin=(i=e==null?void 0:e.firstPersonPlugin)!=null?i:new Dr(t),this.humanoidPlugin=(r=e==null?void 0:e.humanoidPlugin)!=null?r:new jr(t,{helperRoot:c,autoUpdateHumanBones:f}),this.lookAtPlugin=(o=e==null?void 0:e.lookAtPlugin)!=null?o:new oo(t,{helperRoot:c}),this.metaPlugin=(s=e==null?void 0:e.metaPlugin)!=null?s:new lo(t),this.mtoonMaterialPlugin=(l=e==null?void 0:e.mtoonMaterialPlugin)!=null?l:new To(t),this.materialsHDREmissiveMultiplierPlugin=(a=e==null?void 0:e.materialsHDREmissiveMultiplierPlugin)!=null?a:new Eo(t),this.materialsV0CompatPlugin=(u=e==null?void 0:e.materialsV0CompatPlugin)!=null?u:new Oo(t),this.springBonePlugin=(h=e==null?void 0:e.springBonePlugin)!=null?h:new Ms(t,{colliderHelperRoot:c,jointHelperRoot:c}),this.nodeConstraintPlugin=(d=e==null?void 0:e.nodeConstraintPlugin)!=null?d:new es(t,{helperRoot:c})}beforeRoot(){return je(this,null,function*(){yield this.materialsV0CompatPlugin.beforeRoot(),yield this.mtoonMaterialPlugin.beforeRoot()})}loadMesh(t){return je(this,null,function*(){return yield this.mtoonMaterialPlugin.loadMesh(t)})}getMaterialType(t){const e=this.mtoonMaterialPlugin.getMaterialType(t);return e??null}extendMaterialParams(t,e){return je(this,null,function*(){yield this.materialsHDREmissiveMultiplierPlugin.extendMaterialParams(t,e),yield this.mtoonMaterialPlugin.extendMaterialParams(t,e)})}afterRoot(t){return je(this,null,function*(){yield this.metaPlugin.afterRoot(t),yield this.humanoidPlugin.afterRoot(t),yield this.expressionPlugin.afterRoot(t),yield this.lookAtPlugin.afterRoot(t),yield this.firstPersonPlugin.afterRoot(t),yield this.springBonePlugin.afterRoot(t),yield this.nodeConstraintPlugin.afterRoot(t),yield this.mtoonMaterialPlugin.afterRoot(t);const e=t.userData.vrmMeta,n=t.userData.vrmHumanoid;if(e&&n){const i=new ho({scene:t.scene,expressionManager:t.userData.vrmExpressionManager,firstPerson:t.userData.vrmFirstPerson,humanoid:n,lookAt:t.userData.vrmLookAt,meta:e,materials:t.userData.vrmMToonMaterials,springBoneManager:t.userData.vrmSpringBoneManager,nodeConstraintManager:t.userData.vrmNodeConstraintManager});t.userData.vrm=i}})}};function ys(t){const e=new Set;return t.traverse(n=>{if(!n.isMesh)return;const i=n;e.add(i)}),e}function Nn(t,e,n){if(e.size===1){const s=e.values().next().value;if(s.weight===1)return t[s.index]}const i=new Float32Array(t[0].count*3);let r=0;if(n)r=1;else for(const s of e)r+=s.weight;for(const s of e){const l=t[s.index],a=s.weight/r;for(let u=0;u<l.count;u++)i[u*3+0]+=l.getX(u)*a,i[u*3+1]+=l.getY(u)*a,i[u*3+2]+=l.getZ(u)*a}return new D(i,3)}function ws(t){var e;const n=ys(t.scene),i=new Map,r=(e=t.expressionManager)==null?void 0:e.expressionMap;if(r!=null)for(const[o,s]of Object.entries(r)){const l=new Set;for(const a of s.binds)if(a instanceof Je){if(a.weight!==0)for(const u of a.primitives){let h=i.get(u);h==null&&(h=new Map,i.set(u,h));let d=h.get(o);d==null&&(d=new Set,h.set(o,d)),d.add(a)}l.add(a)}for(const a of l)s.deleteBind(a)}for(const o of n){const s=i.get(o);if(s==null)continue;const l=o.geometry.morphAttributes;o.geometry.morphAttributes={};const a=o.geometry.clone();o.geometry=a;const u=a.morphTargetsRelative,h=l.position!=null,d=l.normal!=null,c={},f={},m=[];if(h||d){h&&(c.position=[]),d&&(c.normal=[]);let p=0;for(const[g,v]of s)h&&(c.position[p]=Nn(l.position,v,u)),d&&(c.normal[p]=Nn(l.normal,v,u)),r==null||r[g].addBind(new Je({index:p,weight:1,primitives:[o]})),f[g]=p,m.push(0),p++}a.morphAttributes=c,o.morphTargetDictionary=f,o.morphTargetInfluences=m}}function et(t,e,n){if(t.getComponent)return t.getComponent(e,n);{let i=t.array[e*t.itemSize+n];return t.normalized&&(i=I.denormalize(i,t.array)),i}}function Ri(t,e,n,i){t.setComponent?t.setComponent(e,n,i):(t.normalized&&(i=I.normalize(i,t.array)),t.array[e*t.itemSize+n]=i)}function Rs(t){var e;const n=Ts(t),i=new Set;for(const d of n)i.has(d.geometry)&&(d.geometry=bs(d.geometry)),i.add(d.geometry);const r=new Map;for(const d of i){const c=d.getAttribute("skinIndex"),f=(e=r.get(c))!=null?e:new Map;r.set(c,f);const m=d.getAttribute("skinWeight"),p=Ss(c,m);f.set(m,p)}const o=new Map;for(const d of n){const c=Es(d,r);o.set(d,c)}const s=[];for(const[d,c]of o){let f=!1;for(const m of s)if(As(c,m.boneInverseMap)){f=!0,m.meshes.add(d);for(const[g,v]of c)m.boneInverseMap.set(g,v);break}f||s.push({boneInverseMap:c,meshes:new Set([d])})}const l=new Map,a=new vt,u=new vt,h=new vt;for(const d of s){const{boneInverseMap:c,meshes:f}=d,m=Array.from(c.keys()),p=Array.from(c.values()),g=new Ot(m,p),v=u.getOrCreate(g);for(const M of f){const w=M.geometry.getAttribute("skinIndex"),R=a.getOrCreate(w),y=M.skeleton.bones,x=y.map(C=>h.getOrCreate(C)).join(","),S=`${R};${v};${x}`;let E=l.get(S);E==null&&(E=w.clone(),Ps(E,y,m),l.set(S,E)),M.geometry.setAttribute("skinIndex",E)}for(const M of f)M.bind(g,new K)}}function Ts(t){const e=new Set;return t.traverse(n=>{if(!n.isSkinnedMesh)return;const i=n;e.add(i)}),e}function Ss(t,e){const n=new Set;for(let i=0;i<t.count;i++)for(let r=0;r<t.itemSize;r++){const o=et(t,i,r);et(e,i,r)!==0&&n.add(o)}return n}function Es(t,e){const n=new Map,i=t.skeleton,r=t.geometry,o=r.getAttribute("skinIndex"),s=r.getAttribute("skinWeight"),l=e.get(o),a=l==null?void 0:l.get(s);if(!a)throw new Error("Unreachable. attributeUsedIndexSetMap does not know the skin index attribute or the skin weight attribute.");for(const u of a)n.set(i.bones[u],i.boneInverses[u]);return n}function As(t,e){for(const[n,i]of t.entries()){const r=e.get(n);if(r!=null&&!Ls(i,r))return!1}return!0}function Ps(t,e,n){const i=new Map;for(const o of e)i.set(o,i.size);const r=new Map;for(const[o,s]of n.entries()){const l=i.get(s);r.set(l,o)}for(let o=0;o<t.count;o++)for(let s=0;s<t.itemSize;s++){const l=et(t,o,s),a=r.get(l);Ri(t,o,s,a)}t.needsUpdate=!0}function Ls(t,e,n){if(n=n||1e-4,t.elements.length!=e.elements.length)return!1;for(let i=0,r=t.elements.length;i<r;i++)if(Math.abs(t.elements[i]-e.elements[i])>n)return!1;return!0}var vt=class{constructor(){this._objectIndexMap=new Map,this._index=0}get(t){return this._objectIndexMap.get(t)}getOrCreate(t){let e=this._objectIndexMap.get(t);return e==null&&(e=this._index,this._objectIndexMap.set(t,e),this._index++),e}};function bs(t){var e,n,i,r;const o=new ie;o.name=t.name,o.setIndex(t.index);for(const[s,l]of Object.entries(t.attributes))o.setAttribute(s,l);for(const[s,l]of Object.entries(t.morphAttributes)){const a=s;o.morphAttributes[a]=l.concat()}o.morphTargetsRelative=t.morphTargetsRelative,o.groups=[];for(const s of t.groups)o.addGroup(s.start,s.count,s.materialIndex);return o.boundingSphere=(n=(e=t.boundingSphere)==null?void 0:e.clone())!=null?n:null,o.boundingBox=(r=(i=t.boundingBox)==null?void 0:i.clone())!=null?r:null,o.drawRange.start=t.drawRange.start,o.drawRange.count=t.drawRange.count,o.userData=t.userData,o}function Vn(t){if(Object.values(t).forEach(e=>{e!=null&&e.isTexture&&e.dispose()}),t.isShaderMaterial){const e=t.uniforms;e&&Object.values(e).forEach(n=>{const i=n.value;i!=null&&i.isTexture&&i.dispose()})}t.dispose()}function Is(t){const e=t.geometry;e&&e.dispose();const n=t.skeleton;n&&n.dispose();const i=t.material;i&&(Array.isArray(i)?i.forEach(r=>Vn(r)):i&&Vn(i))}function Cs(t){t.traverse(Is)}function Os(t,e){var n,i;console.warn("VRMUtils.removeUnnecessaryJoints: removeUnnecessaryJoints is deprecated. Use combineSkeletons instead. combineSkeletons contributes more to the performance improvement. This function will be removed in the next major version.");const r=(n=e==null?void 0:e.experimentalSameBoneCounts)!=null?n:!1,o=[];t.traverse(a=>{a.type==="SkinnedMesh"&&o.push(a)});const s=new Map;let l=0;for(const a of o){const h=a.geometry.getAttribute("skinIndex");if(s.has(h))continue;const d=new Map,c=new Map;for(let f=0;f<h.count;f++)for(let m=0;m<h.itemSize;m++){const p=et(h,f,m);let g=d.get(p);g==null&&(g=d.size,d.set(p,g),c.set(g,p)),Ri(h,f,m,g)}h.needsUpdate=!0,s.set(h,c),l=Math.max(l,d.size)}for(const a of o){const h=a.geometry.getAttribute("skinIndex"),d=s.get(h),c=[],f=[],m=r?l:d.size;for(let g=0;g<m;g++){const v=(i=d.get(g))!=null?i:0;c.push(a.skeleton.bones[v]),f.push(a.skeleton.boneInverses[v])}const p=new Ot(c,f);a.bind(p,new K)}}function Us(t,e){const n=t.position.count,i=new Array(n);let r=0;const o=e.array;for(let s=0;s<o.length;s++){const l=o[s];i[l]||(i[l]=!0,r++)}return{isVertexUsed:i,vertexCount:n,verticesUsed:r}}function Ns(t){const e=[],n=[];let i=0;for(let r=0;r<t.length;r++)if(t[r]){const o=i++;e[r]=o,n[o]=r}return{originalIndexNewIndexMap:e,newIndexOriginalIndexMap:n}}function Vs(t,e){var n,i,r,o;e.name=t.name,e.morphTargetsRelative=t.morphTargetsRelative,t.groups.forEach(s=>{e.addGroup(s.start,s.count,s.materialIndex)}),e.boundingBox=(i=(n=t.boundingBox)==null?void 0:n.clone())!=null?i:null,e.boundingSphere=(o=(r=t.boundingSphere)==null?void 0:r.clone())!=null?o:null,e.setDrawRange(t.drawRange.start,t.drawRange.count),e.userData=t.userData}function Ds(t,e,n){const i=e.array,r=new i.constructor(i.length);for(let o=0;o<i.length;o++){const s=i[o];r[o]=n[s]}t.setIndex(new D(r,e.itemSize,e.normalized))}function tt(t,e,n){const i=t.constructor,r=new i(e.length*n);let o=!0;for(let s=0;s<e.length;s++){const a=e[s]*n,u=s*n;for(let h=0;h<n;h++){const d=t[a+h];r[u+h]=d,o=o&&d===0}}return[r,o]}function ks(t){var e;const n=new Map,i=[];for(const[r,o]of Object.entries(t))if(o.isInterleavedBufferAttribute){const s=o,l=s.data,a=(e=n.get(l))!=null?e:[];n.set(l,a),a.push([r,s])}else{const s=o;i.push([r,s])}return[n,i]}function Bs(t,e,n){const[i,r]=ks(e);for(const[o,s]of i){const l=o.array,{stride:a}=o,[u,h]=tt(l,n,a),d=new Kn(u,a);d.setUsage(o.usage);for(const[c,f]of s){const{itemSize:m,offset:p,normalized:g}=f,v=new ei(d,m,p,g);t.setAttribute(c,v)}}for(const[o,s]of r){const l=s.array,{itemSize:a,normalized:u}=s,[h,d]=tt(l,n,a);t.setAttribute(o,new D(h,a,u))}}function Fs(t){var e;const n=new Map,i=[];for(const[r,o]of Object.entries(t)){const s=r;for(let l=0;l<o.length;l++){const a=o[l];if(a.isInterleavedBufferAttribute){const u=a,h=u.data,d=(e=n.get(h))!=null?e:[];n.set(h,d),d.push([s,l,u])}else{const u=a;i.push([s,l,u])}}}return[n,i]}function Hs(t,e,n){var i,r;let o=!0;const[s,l]=Fs(e),a={};for(const[u,h]of s){const d=u.array,{stride:c}=u,[f,m]=tt(d,n,c);o=o&&m;const p=new Kn(f,c);p.setUsage(u.usage);for(const[g,v,M]of h){const{itemSize:w,offset:R,normalized:y}=M,x=new ei(p,w,R,y);(i=a[g])!=null||(a[g]=[]),a[g][v]=x}}for(const[u,h,d]of l){const c=d,f=c.array,{itemSize:m,normalized:p}=c,[g,v]=tt(f,n,m);o=o&&v,(r=a[u])!=null||(a[u]=[]),a[u][h]=new D(g,m,p)}t.morphAttributes=o?{}:a}function Ws(t){const e=new Map;t.traverse(n=>{if(!n.isMesh)return;const i=n,r=i.geometry,o=r.index;if(o==null)return;const s=e.get(r);if(s!=null){i.geometry=s;return}const{isVertexUsed:l,vertexCount:a,verticesUsed:u}=Us(r.attributes,o);if(u===a)return;const{originalIndexNewIndexMap:h,newIndexOriginalIndexMap:d}=Ns(l),c=new ie;Vs(r,c),e.set(r,c),Ds(c,o,h),Bs(c,r.attributes,d),Hs(c,r.morphAttributes,d),i.geometry=c}),Array.from(e.keys()).forEach(n=>{n.dispose()})}function zs(t){var e;((e=t.meta)==null?void 0:e.metaVersion)==="0"&&(t.scene.rotation.y=Math.PI)}var J=class{constructor(){}};J.combineMorphs=ws;J.combineSkeletons=Rs;J.deepDispose=Cs;J.removeUnnecessaryJoints=Os;J.removeUnnecessaryVertices=Ws;J.rotateVRM0=zs;/*!
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
 */const Dn="aa",js=.7,Xs=.05;class rt{constructor(e,n=.2){N(this,"current",null);N(this,"intensity",1);N(this,"weights",new Map);N(this,"mouth",0);N(this,"warned",new Set);N(this,"sink");N(this,"fadeSeconds");this.sink=e,this.fadeSeconds=n}setEmotion(e,n=1){return e!==null&&!this.sink.has(e)?(this.warned.has(e)||(this.warned.add(e),console.warn(`[VRM] expression "${e}" not found in model; ignoring`)),!1):(this.current=e,this.intensity=Math.max(0,Math.min(1,n)),e!==null&&!this.weights.has(e)&&this.weights.set(e,0),!0)}clear(){this.setEmotion(null)}setMouth(e){this.mouth=e}multiplier(e){var i,r,o,s;let n=0;for(const[l,a]of this.weights){const u=e==="mouth"?(r=(i=this.sink).overrideMouth)==null?void 0:r.call(i,l):(s=(o=this.sink).overrideBlink)==null?void 0:s.call(o,l);u==="block"?n+=a>0?1:0:u==="blend"&&(n+=a)}return Math.max(0,1-n)}blinkMultiplier(){return this.multiplier("blink")}static compensate(e,n){return n<=Xs?e:Math.min(1,e/n)}update(e){const n=this.fadeSeconds>0?e/this.fadeSeconds:1;for(const[i,r]of this.weights){const o=i===this.current?js*this.intensity:0,s=r<o?Math.min(o,r+n):Math.max(o,r-n);s!==r&&(this.weights.set(i,s),this.sink.setValue(i,s)),s===0&&o===0&&this.weights.delete(i)}this.sink.has(Dn)&&this.sink.setValue(Dn,rt.compensate(this.mouth,this.multiplier("mouth")))}}/*!
 * @pixiv/three-vrm-animation v3.5.5
 * The implementation of VRM Animation
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-animation is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */var kn=(t,e,n)=>new Promise((i,r)=>{var o=a=>{try{l(n.next(a))}catch(u){r(u)}},s=a=>{try{l(n.throw(a))}catch(u){r(u)}},l=a=>a.done?i(a.value):Promise.resolve(a.value).then(o,s);l((n=n.apply(t,e)).next())}),Gs={Aa:"aa",Ih:"ih",Ou:"ou",Ee:"ee",Oh:"oh",Blink:"blink",Happy:"happy",Angry:"angry",Sad:"sad",Relaxed:"relaxed",LookUp:"lookUp",Surprised:"surprised",LookDown:"lookDown",LookLeft:"lookLeft",LookRight:"lookRight",BlinkLeft:"blinkLeft",BlinkRight:"blinkRight",Neutral:"neutral"};new j;var Bn={hips:null,spine:"hips",chest:"spine",upperChest:"chest",neck:"upperChest",head:"neck",leftEye:"head",rightEye:"head",jaw:"head",leftUpperLeg:"hips",leftLowerLeg:"leftUpperLeg",leftFoot:"leftLowerLeg",leftToes:"leftFoot",rightUpperLeg:"hips",rightLowerLeg:"rightUpperLeg",rightFoot:"rightLowerLeg",rightToes:"rightFoot",leftShoulder:"upperChest",leftUpperArm:"leftShoulder",leftLowerArm:"leftUpperArm",leftHand:"leftLowerArm",rightShoulder:"upperChest",rightUpperArm:"rightShoulder",rightLowerArm:"rightUpperArm",rightHand:"rightLowerArm",leftThumbMetacarpal:"leftHand",leftThumbProximal:"leftThumbMetacarpal",leftThumbDistal:"leftThumbProximal",leftIndexProximal:"leftHand",leftIndexIntermediate:"leftIndexProximal",leftIndexDistal:"leftIndexIntermediate",leftMiddleProximal:"leftHand",leftMiddleIntermediate:"leftMiddleProximal",leftMiddleDistal:"leftMiddleIntermediate",leftRingProximal:"leftHand",leftRingIntermediate:"leftRingProximal",leftRingDistal:"leftRingIntermediate",leftLittleProximal:"leftHand",leftLittleIntermediate:"leftLittleProximal",leftLittleDistal:"leftLittleIntermediate",rightThumbMetacarpal:"rightHand",rightThumbProximal:"rightThumbMetacarpal",rightThumbDistal:"rightThumbProximal",rightIndexProximal:"rightHand",rightIndexIntermediate:"rightIndexProximal",rightIndexDistal:"rightIndexIntermediate",rightMiddleProximal:"rightHand",rightMiddleIntermediate:"rightMiddleProximal",rightMiddleDistal:"rightMiddleIntermediate",rightRingProximal:"rightHand",rightRingIntermediate:"rightRingProximal",rightRingDistal:"rightRingIntermediate",rightLittleProximal:"rightHand",rightLittleIntermediate:"rightLittleProximal",rightLittleDistal:"rightLittleIntermediate"};function Ys(t){return t.invert?t.invert():t.inverse(),t}var qs=new _,Qs=new _;function $s(t,e){return t.matrixWorld.decompose(qs,e,Qs),e}function Mt(t){return[Math.atan2(-t.z,t.x),Math.atan2(t.y,Math.sqrt(t.x*t.x+t.z*t.z))]}function Fn(t){const e=Math.round(t/2/Math.PI);return t-2*Math.PI*e}var Hn=new _(0,0,1),Zs=new _,Js=new _,Ks=new _,ea=new T,xt=new T,Wn=new T,ta=new T,yt=new we,Ti=class Si{constructor(e,n){this.offsetFromHeadBone=new _,this.autoUpdate=!0,this.faceFront=new _(0,0,1),this.humanoid=e,this.applier=n,this._yaw=0,this._pitch=0,this._needsUpdate=!0,this._restHeadWorldQuaternion=this.getLookAtWorldQuaternion(new T)}get yaw(){return this._yaw}set yaw(e){this._yaw=e,this._needsUpdate=!0}get pitch(){return this._pitch}set pitch(e){this._pitch=e,this._needsUpdate=!0}get euler(){return console.warn("VRMLookAt: euler is deprecated. use getEuler() instead."),this.getEuler(new we)}getEuler(e){return e.set(I.DEG2RAD*this._pitch,I.DEG2RAD*this._yaw,0,"YXZ")}copy(e){if(this.humanoid!==e.humanoid)throw new Error("VRMLookAt: humanoid must be same in order to copy");return this.offsetFromHeadBone.copy(e.offsetFromHeadBone),this.applier=e.applier,this.autoUpdate=e.autoUpdate,this.target=e.target,this.faceFront.copy(e.faceFront),this}clone(){return new Si(this.humanoid,this.applier).copy(this)}reset(){this._yaw=0,this._pitch=0,this._needsUpdate=!0}getLookAtWorldPosition(e){const n=this.humanoid.getRawBoneNode("head");return e.copy(this.offsetFromHeadBone).applyMatrix4(n.matrixWorld)}getLookAtWorldQuaternion(e){const n=this.humanoid.getRawBoneNode("head");return $s(n,e)}getFaceFrontQuaternion(e){if(this.faceFront.distanceToSquared(Hn)<.01)return e.copy(this._restHeadWorldQuaternion).invert();const[n,i]=Mt(this.faceFront);return yt.set(0,.5*Math.PI+n,i,"YZX"),e.setFromEuler(yt).premultiply(ta.copy(this._restHeadWorldQuaternion).invert())}getLookAtWorldDirection(e){return this.getLookAtWorldQuaternion(xt),this.getFaceFrontQuaternion(Wn),e.copy(Hn).applyQuaternion(xt).applyQuaternion(Wn).applyEuler(this.getEuler(yt))}lookAt(e){const n=ea.copy(this._restHeadWorldQuaternion).multiply(Ys(this.getLookAtWorldQuaternion(xt))),i=this.getLookAtWorldPosition(Js),r=Ks.copy(e).sub(i).applyQuaternion(n).normalize(),[o,s]=Mt(this.faceFront),[l,a]=Mt(r),u=Fn(l-o),h=Fn(s-a);this._yaw=I.RAD2DEG*u,this._pitch=I.RAD2DEG*h,this._needsUpdate=!0}update(e){this.target!=null&&this.autoUpdate&&this.lookAt(this.target.getWorldPosition(Zs)),this._needsUpdate&&(this._needsUpdate=!1,this.applier.applyYawPitch(this._yaw,this._pitch))}};Ti.EULER_ORDER="YXZ";var na=Ti,zn=180/Math.PI,wt=new we,jn=class extends ye{constructor(t){super(),this.vrmLookAt=t,this.type="VRMLookAtQuaternionProxy";const e=this.rotation._onChangeCallback;this.rotation._onChange(()=>{e(),this._applyToLookAt()});const n=this.quaternion._onChangeCallback;this.quaternion._onChange(()=>{n(),this._applyToLookAt()})}_applyToLookAt(){wt.setFromQuaternion(this.quaternion,na.EULER_ORDER),this.vrmLookAt.yaw=zn*wt.y,this.vrmLookAt.pitch=zn*wt.x}};function ia(t,e,n){var i,r;const o=new Map,s=new Map;for(const[l,a]of t.humanoidTracks.rotation.entries()){const u=(i=e.getNormalizedBoneNode(l))==null?void 0:i.name;if(u!=null){const h=new wr(`${u}.quaternion`,a.times,a.values.map((d,c)=>n==="0"&&c%2===0?-d:d));s.set(l,h)}}for(const[l,a]of t.humanoidTracks.translation.entries()){const u=(r=e.getNormalizedBoneNode(l))==null?void 0:r.name;if(u!=null){const h=t.restHipsPosition.y,c=e.normalizedRestPose.hips.position[1]/h,f=a.clone();f.values=f.values.map((m,p)=>(n==="0"&&p%3!==1?-m:m)*c),f.name=`${u}.position`,o.set(l,f)}}return{translation:o,rotation:s}}function ra(t,e){const n=new Map,i=new Map;for(const[r,o]of t.expressionTracks.preset.entries()){const s=e.getExpressionTrackName(r);if(s!=null){const l=o.clone();l.name=s,n.set(r,l)}}for(const[r,o]of t.expressionTracks.custom.entries()){const s=e.getExpressionTrackName(r);if(s!=null){const l=o.clone();l.name=s,i.set(r,l)}}return{preset:n,custom:i}}function oa(t,e){if(t.lookAtTrack==null)return null;const n=t.lookAtTrack.clone();return n.name=e,n}function sa(t,e){const n=[],i=ia(t,e.humanoid,e.meta.metaVersion);if(n.push(...i.translation.values()),n.push(...i.rotation.values()),e.expressionManager!=null){const r=ra(t,e.expressionManager);n.push(...r.preset.values()),n.push(...r.custom.values())}if(e.lookAt!=null){let r=e.scene.children.find(s=>s instanceof jn);r==null?(console.warn("createVRMAnimationClip: VRMLookAtQuaternionProxy is not found. Creating a new one automatically. To suppress this warning, create a VRMLookAtQuaternionProxy manually"),r=new jn(e.lookAt),r.name="VRMLookAtQuaternionProxy",e.scene.add(r)):r.name===""&&(console.warn("createVRMAnimationClip: VRMLookAtQuaternionProxy is found but its name is not set. Setting the name automatically. To suppress this warning, set the name manually"),r.name="VRMLookAtQuaternionProxy");const o=oa(t,`${r.name}.quaternion`);o!=null&&n.push(o)}return new yr("Clip",t.duration,n)}var aa=class{constructor(){this.duration=0,this.restHipsPosition=new _,this.humanoidTracks={translation:new Map,rotation:new Map},this.expressionTracks={preset:new Map,custom:new Map},this.lookAtTrack=null}};function Xn(t,e){const n=t.length,i=[];let r=[],o=0;for(let s=0;s<n;s++){const l=t[s];o<=0&&(o=e,r=[],i.push(r)),r.push(l),o--}return i}var la=new K,De=new _,Rt=new T,Gn=new T,ua=new T,da=new Set(["1.0","1.0-draft"]),ha=new Set(Object.values(Gs)),ca=class{constructor(t){this.parser=t}get name(){return"VRMC_vrm_animation"}afterRoot(t){return kn(this,null,function*(){var e,n,i;const r=t.parser.json,o=r.extensionsUsed;if(o==null||o.indexOf(this.name)==-1)return;const s=(e=r.extensions)==null?void 0:e[this.name];if(s==null)return;const l=s.specVersion;if(l==null)console.warn("VRMAnimationLoaderPlugin: specVersion of the VRMA is not defined. Consider updating the animation file. Assuming the spec version is 1.0.");else{if(!da.has(l)){console.warn(`VRMAnimationLoaderPlugin: Unknown VRMC_vrm_animation spec version: ${l}`);return}l==="1.0-draft"&&console.warn("VRMAnimationLoaderPlugin: Using a draft spec version: 1.0-draft. Some behaviors may be different. Consider updating the animation file.")}const a=this._createNodeMap(s),u=yield this._createBoneWorldMatrixMap(t,s),h=(i=(n=s.humanoid)==null?void 0:n.humanBones.hips)==null?void 0:i.node,d=h!=null?yield t.parser.getDependency("node",h):null,c=new _;d==null||d.getWorldPosition(c),c.y<.001&&console.warn("VRMAnimationLoaderPlugin: The loaded VRM Animation might violate the VRM T-pose (The y component of the rest hips position is approximately zero or below.)");const m=t.animations.map((p,g)=>{const v=r.animations[g],M=this._parseAnimation(p,v,a,u);return M.restHipsPosition=c,M});t.userData.vrmAnimations=m})}_createNodeMap(t){var e,n,i,r,o;const s=new Map,l=new Map,a=(e=t.humanoid)==null?void 0:e.humanBones;a&&Object.entries(a).forEach(([c,f])=>{const m=f==null?void 0:f.node;m!=null&&s.set(m,c)});const u=(n=t.expressions)==null?void 0:n.preset;u&&Object.entries(u).forEach(([c,f])=>{const m=f==null?void 0:f.node;m!=null&&l.set(m,c)});const h=(i=t.expressions)==null?void 0:i.custom;h&&Object.entries(h).forEach(([c,f])=>{const{node:m}=f;l.set(m,c)});const d=(o=(r=t.lookAt)==null?void 0:r.node)!=null?o:null;return{humanoidIndexToName:s,expressionsIndexToName:l,lookAtIndex:d}}_createBoneWorldMatrixMap(t,e){return kn(this,null,function*(){var n,i;t.scene.updateWorldMatrix(!1,!0);const r=yield t.parser.getDependencies("node"),o=new Map;if(e.humanoid==null)return o;for(const[s,l]of Object.entries(e.humanoid.humanBones)){const a=l==null?void 0:l.node;if(a!=null){const u=r[a];o.set(s,u.matrixWorld),s==="hips"&&o.set("hipsParent",(i=(n=u.parent)==null?void 0:n.matrixWorld)!=null?i:la)}}return o})}_parseAnimation(t,e,n,i){const r=t.tracks,o=e.channels,s=new aa;return s.duration=t.duration,o.forEach((l,a)=>{const{node:u,path:h}=l.target,d=r[a];if(u==null)return;const c=n.humanoidIndexToName.get(u);if(c!=null){let m=Bn[c];for(;m!=null&&i.get(m)==null;)m=Bn[m];if(m==null&&(m="hipsParent"),h==="translation")if(c!=="hips")console.warn(`The loading animation contains a translation track for ${c}, which is not permitted in the VRMC_vrm_animation spec. ignoring the track`);else{const p=i.get("hipsParent"),g=Xn(d.values,3).flatMap(M=>De.fromArray(M).applyMatrix4(p).toArray()),v=d.clone();v.values=new Float32Array(g),s.humanoidTracks.translation.set(c,v)}else if(h==="rotation"){const p=i.get(c),g=i.get(m);p.decompose(De,Rt,De),Rt.invert(),g.decompose(De,Gn,De);const v=Xn(d.values,4).flatMap(w=>ua.fromArray(w).premultiply(Gn).multiply(Rt).toArray()),M=d.clone();M.values=new Float32Array(v),s.humanoidTracks.rotation.set(c,M)}else throw new Error(`Invalid path "${h}"`);return}const f=n.expressionsIndexToName.get(u);if(f!=null){if(h==="translation"){const m=d.times,p=new Float32Array(d.values.length/3);for(let v=0;v<p.length;v++)p[v]=d.values[3*v];const g=new xr(`${f}.weight`,m,p);ha.has(f)?s.expressionTracks.preset.set(f,g):s.expressionTracks.custom.set(f,g)}else throw new Error(`Invalid path "${h}"`);return}if(u===n.lookAtIndex)if(h==="rotation")s.lookAtTrack=d;else throw new Error(`Invalid path "${h}"`)}),s}};/*!
 * @pixiv/three-vrm-core v3.5.5
 * The implementation of core features of VRM, for @pixiv/three-vrm
 *
 * Copyright (c) 2019-2026 pixiv Inc.
 * @pixiv/three-vrm-core is distributed under MIT License
 * https://github.com/pixiv/three-vrm/blob/release/LICENSE
 */const nt="idle",Tt=.3;class pa{constructor(e){N(this,"mixer");N(this,"actions",new Map);N(this,"current",null);N(this,"loader",new ti);this.vrm=e,this.mixer=new Rr(e.scene),this.loader.register(n=>new ca(n)),this.mixer.addEventListener("finished",()=>{this.playIdle()})}async load(e,n){try{const r=(await this.loader.loadAsync(n)).userData.vrmAnimations??[];if(!r.length)return console.warn(`[VRM] ${n} has no VRM animation`),!1;const o=sa(r[0],this.vrm),s=this.mixer.clipAction(o);return e===nt?s.setLoop(Tr,Number.POSITIVE_INFINITY):(s.setLoop(Sr,1),s.clampWhenFinished=!0),this.actions.set(e,s),!0}catch(i){return console.warn(`[VRM] failed to load motion ${e}:`,i),!1}}hasClip(e){return this.actions.has(e)}crossfadeTo(e,n=1){e.reset(),e.weight=n,e.fadeIn(Tt).play(),this.current&&this.current!==e&&this.current.fadeOut(Tt),this.current=e}playIdle(){const e=this.actions.get(nt);if(!e){this.current&&this.current.fadeOut(Tt),this.current=null;return}this.current!==e&&this.crossfadeTo(e)}playOnce(e,n=1){const i=this.actions.get(e);return i?n<.05?!1:(this.crossfadeTo(i,Math.max(0,Math.min(1,n))),!0):(console.warn(`[VRM] motion clip "${e}" not loaded; staying idle`),!1)}stop(){this.playIdle()}update(e){this.mixer.update(e)}dispose(){this.mixer.stopAllAction(),this.actions.clear(),this.current=null}}const Yn=2,qn=4,Qn=.05,$n=.1;class fa{constructor(e=Math.random){N(this,"phase","wait");N(this,"remaining");N(this,"rng");this.rng=e,this.remaining=Yn+this.rng()*qn}update(e){return this.remaining-=e,this.phase==="wait"?this.remaining>0?0:(this.phase="close",this.remaining=Qn,.01):this.phase==="close"?this.remaining>0?1-Math.max(0,this.remaining/Qn):(this.phase="open",this.remaining=$n,1):this.remaining>0?Math.max(0,this.remaining/$n):(this.phase="wait",this.remaining=Yn+this.rng()*qn,0)}}const Ei=.35,Ai={values:new Float32Array([Ei]),frameSeconds:Number.POSITIVE_INFINITY};function St(t,e){return String.fromCharCode(t.getUint8(e),t.getUint8(e+1),t.getUint8(e+2),t.getUint8(e+3))}function ma(t){if(t.byteLength<12)return null;const e=new DataView(t);if(St(e,0)!=="RIFF"||St(e,8)!=="WAVE")return null;let n=12,i=0,r=0,o=0,s=0;for(;n+8<=t.byteLength;){const l=St(e,n),a=e.getUint32(n+4,!0),u=n+8;if(l==="fmt "){if(u+16>t.byteLength)return null;s=e.getUint16(u,!0),r=e.getUint16(u+2,!0),i=e.getUint32(u+4,!0),o=e.getUint16(u+14,!0)}else if(l==="data"){if(s!==1||o!==16||r<1||i<1)return null;const h=Math.min(t.byteLength,u+a),d=Math.floor((h-u)/2),c=new Int16Array(d);for(let f=0;f<d;f++)c[f]=e.getInt16(u+f*2,!0);return{sampleRate:i,channels:r,samples:c}}n=u+a+a%2}return null}function ga(t,e=.02){const n=Math.max(1,Math.round(t.sampleRate*e))*t.channels,i=Math.ceil(t.samples.length/n),r=new Float32Array(i);let o=0;for(let s=0;s<i;s++){let l=0;const a=s*n,u=Math.min(t.samples.length,a+n);for(let h=a;h<u;h++){const d=Math.abs(t.samples[h]);d>l&&(l=d)}r[s]=l,l>o&&(o=l)}if(o>0)for(let s=0;s<i;s++)r[s]/=o;return{values:r,frameSeconds:e}}function _a(t,e){if(e<0)return 0;if(t===Ai)return Ei;const n=Math.floor(e/t.frameSeconds);return n<t.values.length?t.values[n]:0}function va(t){const e=1/(1+Math.exp(-45*t+5));return e<.1?0:e}function Ma(t){try{const e=atob(t),n=new Uint8Array(e.length);for(let i=0;i<e.length;i++)n[i]=e.charCodeAt(i);return n.buffer}catch{return null}}function xa(t){const e=t.indexOf(",");if(e<0)return null;const n=Ma(t.slice(e+1));if(!n)return null;const i=ma(n);return i?ga(i):null}const ya=20;class wa{constructor(){N(this,"audio",null);N(this,"envelope",null);N(this,"smoothed",0)}begin(e){this.audio=e;const n=xa(e.src);n||console.warn("[VRM] could not parse WAV for lip sync; using constant mouth"),this.envelope=n??Ai}stop(){this.audio=null,this.envelope=null,this.smoothed=0}update(e){let n=0;const i=this.audio;return i&&this.envelope&&!i.paused&&!i.ended&&(n=va(_a(this.envelope,i.currentTime))),this.smoothed+=(n-this.smoothed)*Math.min(1,e*ya),this.smoothed}}class Ra{constructor(e,n,i){N(this,"lip",new wa);N(this,"blink",new fa);N(this,"elapsed",0);this.vrm=e,this.motions=n,this.expressions=i}beginSegment(e,n){this.lip.begin(e),n.expression!==void 0&&this.expressions.setEmotion(String(n.expression),n.intensity??1),n.motion&&Jn(n.motion)&&this.motions.playOnce(n.motion.clip,n.motion.intensity??1)}stop(){this.lip.stop(),this.motions.stop()}resetExpression(){this.expressions.clear()}update(e){var n,i,r;if(this.elapsed+=e,this.expressions.setMouth(this.lip.update(e)),this.expressions.update(e),(n=this.vrm.expressionManager)==null||n.setValue("blink",rt.compensate(this.blink.update(e),this.expressions.blinkMultiplier())),!this.motions.hasClip(nt)){const o=(i=this.vrm.humanoid)==null?void 0:i.getNormalizedBoneNode("spine"),s=(r=this.vrm.humanoid)==null?void 0:r.getNormalizedBoneNode("chest");o&&(o.rotation.z=Math.sin(this.elapsed*.8)*.01),s&&(s.rotation.x=Math.sin(this.elapsed*1.6)*.01)}this.motions.update(e),this.vrm.update(e)}}const Zn={distance:1.6,height:1.35},Ta=.4,Sa=8,Ea=.0015;function Oa(){var f,m;const{t}=sr(),{modelInfo:e}=ar(),n=me.useRef(null),[i,r]=me.useState(!1),o=(e==null?void 0:e.lookAtPointer)!==!1,s=me.useRef(o);s.current=o;const l=me.useRef(!0);l.current=(e==null?void 0:e.pointerInteractive)!==!1;const a=me.useRef(!0);a.current=(e==null?void 0:e.scrollToResize)!==!1;const u=(e==null?void 0:e.url)??"",h=((f=e==null?void 0:e.camera)==null?void 0:f.distance)??Zn.distance,d=((m=e==null?void 0:e.camera)==null?void 0:m.height)??Zn.height,c=JSON.stringify(Object.values((e==null?void 0:e.motionMap)??{}).filter(Jn).map(p=>p.clip).sort());return me.useEffect(()=>{const p=n.current;if(!p||!u)return;r(!1);let g=!1,v=0,M=null,w=null,R=null,y=null,x;try{x=new Er({antialias:!0,alpha:!0,powerPreference:"high-performance"})}catch(A){console.warn("[VRM] WebGL is unavailable:",A),r(!0);return}x.setPixelRatio(Math.min(2,window.devicePixelRatio||1)),x.setClearColor(0,0),p.appendChild(x.domElement),x.domElement.style.width="100%",x.domElement.style.height="100%",x.domElement.style.display="block";const S=new Ar,E=new Pr(30,1,.1,50);S.add(new Lr(16777215,4473924,1));const C=new br(16777215,1.2);C.position.set(1,2,3),S.add(C);const P=new ye;S.add(P);let L=0,O=0,k=h;const ee=()=>P.position.set(L,d+O,k),Y=()=>{E.position.set(L,d+O,k),E.lookAt(L,d+O,0),s.current||ee()};Y(),ee();const W=()=>{const A=Math.max(1,p.clientWidth),U=Math.max(1,p.clientHeight);x.setSize(A,U,!1),E.aspect=A/U,E.updateProjectionMatrix()},B=new ResizeObserver(W);B.observe(p),W();const te=A=>{if(!s.current){ee();return}const U=p.getBoundingClientRect(),ne=(A.clientX-U.left)/U.width*2-1,fe=-((A.clientY-U.top)/U.height*2-1);P.position.set(L+ne*.6,d+O+fe*.4,k*.6)};window.addEventListener("pointermove",te);let X=!1,V=0,ce=0;const Te=A=>{var U;A.button!==0||!l.current||(X=!0,V=A.clientX,ce=A.clientY,(U=p.setPointerCapture)==null||U.call(p,A.pointerId))},Se=A=>{if(!X)return;if(!l.current){X=!1;return}const U=Math.max(1,p.clientHeight),ne=2*k*Math.tan(E.fov*Math.PI/360)/U;L-=(A.clientX-V)*ne,O+=(A.clientY-ce)*ne,V=A.clientX,ce=A.clientY,Y()},se=A=>{var U;X&&(X=!1,(U=p.releasePointerCapture)==null||U.call(p,A.pointerId))},Ee=A=>{a.current&&(A.preventDefault(),k=Math.min(Sa,Math.max(Ta,k*(1+A.deltaY*Ea))),Y())},Ae=()=>{L=0,O=0,k=h,Y()};p.addEventListener("pointerdown",Te),p.addEventListener("pointermove",Se),p.addEventListener("pointerup",se),p.addEventListener("pointercancel",se),p.addEventListener("wheel",Ee,{passive:!1}),p.addEventListener("dblclick",Ae);const Pe=new ti;Pe.register(A=>new xs(A)),Pe.load(u,async A=>{if(g)return;const U=A.userData.vrm;if(!U){console.warn("[VRM] file has no VRM extension:",u),r(!0),Qt.create({id:"vrm-load-failed",title:t("error.vrmLoad"),type:"error",duration:6e3});return}J.removeUnnecessaryVertices(A.scene),J.combineSkeletons(A.scene),J.rotateVRM0(U),M=U,M.lookAt&&(M.lookAt.target=P),S.add(M.scene),w=new pa(M);const ne=u.slice(0,u.lastIndexOf("/")),fe=[nt,...JSON.parse(c)];if(await Promise.all(fe.map(F=>w.load(F,`${ne}/motions/${F}.vrma`))),g)return;w.playIdle();const Fe=new rt({has:F=>{var H;return!!((H=M==null?void 0:M.expressionManager)!=null&&H.getExpression(F))},setValue:(F,H)=>{var G;return(G=M==null?void 0:M.expressionManager)==null?void 0:G.setValue(F,H)},overrideMouth:F=>{var H,G;return(G=(H=M==null?void 0:M.expressionManager)==null?void 0:H.getExpression(F))==null?void 0:G.overrideMouth},overrideBlink:F=>{var H,G;return(G=(H=M==null?void 0:M.expressionManager)==null?void 0:H.getExpression(F))==null?void 0:G.overrideBlink}});R=new Ra(M,w,Fe),y=ur(R)},void 0,A=>{g||(console.warn("[VRM] load failed:",A),r(!0),Qt.create({id:"vrm-load-failed",title:t("error.vrmLoad"),type:"error",duration:6e3}))});const Le=new Ir;let re=!0;const pe=()=>{if(!re)return;v=window.requestAnimationFrame(pe);const A=Math.min(Le.getDelta(),.1);R==null||R.update(A),x.render(S,E)},be=()=>{document.hidden?(re=!1,window.cancelAnimationFrame(v)):re||(re=!0,Le.getDelta(),pe())};return document.addEventListener("visibilitychange",be),pe(),()=>{g=!0,re=!1,window.cancelAnimationFrame(v),document.removeEventListener("visibilitychange",be),window.removeEventListener("pointermove",te),p.removeEventListener("pointerdown",Te),p.removeEventListener("pointermove",Se),p.removeEventListener("pointerup",se),p.removeEventListener("pointercancel",se),p.removeEventListener("wheel",Ee),p.removeEventListener("dblclick",Ae),B.disconnect(),y==null||y(),w==null||w.dispose(),M&&(S.remove(M.scene),J.deepDispose(M.scene)),x.dispose(),x.forceContextLoss(),x.domElement.remove()}},[u,h,d,c,t]),lr.jsx("div",{ref:n,"data-avatar-renderer":"vrm","data-avatar-error":i||void 0,style:{position:"absolute",inset:0,overflow:"hidden"}})}export{Oa as VRMAvatar};

#!/usr/bin/env python3
"""Render real template thumbnails for confirmation before scaffold."""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import tempfile
import webbrowser
from pathlib import Path

from background_presets import background_ui_label, effective_background
from capability_catalog import decor_ui_label, template_ui_label, variant_ui_label
from design_quality import audit_summary, has_media, slide_quality
from editor_bindings import annotate_editable_fragment
from fill_slots import FILLERS, apply_media_attributes, effective_backdrop_text, inject_backdrop_text
from media_assets import verify_outline_media
from outline_schema import validate_outline
from palette_tokens import PALETTES, canonical_name, named_palette, normalize_palette
from profile_tokens import SHAPE_META, SHAPE_PROFILES, TYPE_META, TYPE_PROFILES


ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "assets" / "templates"
RUNTIME_CSS = (ROOT / "assets" / "runtime" / "deck.css").read_text(encoding="utf-8")
RUNTIME_JS = (ROOT / "assets" / "runtime" / "deck.js").read_text(encoding="utf-8")
CSS_BLOCK = re.compile(r"/\*\s*OIL-SLIDE-CSS:START\s*\*/(.*?)/\*\s*OIL-SLIDE-CSS:END\s*\*/", re.S)
HTML_BLOCK = re.compile(r"<!--\s*OIL-SLIDE:START\s*-->(.*?)<!--\s*OIL-SLIDE:END\s*-->", re.S)


EDITOR_FRAME_CSS = r"""
[data-edit-path]{min-width:0;max-width:100%;overflow-wrap:anywhere;word-break:break-word;cursor:text;border-radius:10px;outline:2px dashed transparent;outline-offset:-3px;box-shadow:none;caret-color:var(--ink);transition:outline-color .16s ease,outline-offset .22s cubic-bezier(.22,1,.36,1)}
[data-edit-path][contenteditable="plaintext-only"]:hover{outline-color:color-mix(in srgb,var(--ink) 30%,transparent)}
[data-edit-path]:focus{outline-color:color-mix(in srgb,var(--accent) 74%,var(--ink) 26%);outline-offset:-1px;animation:oil-editor-focus-in .22s cubic-bezier(.22,1,.36,1)}
[data-edit-path]:empty::after{content:"点击输入";color:var(--ink-3);opacity:.58;font-weight:500}
body[data-oil-authoring="true"] .oil-slide{user-select:none}
body[data-oil-authoring="true"] [data-edit-path]{user-select:text;-webkit-user-select:text}
@keyframes oil-editor-focus-in{from{outline-color:color-mix(in srgb,var(--ink) 30%,transparent);outline-offset:-3px}to{outline-color:color-mix(in srgb,var(--accent) 74%,var(--ink) 26%);outline-offset:-1px}}
@media(prefers-reduced-motion:reduce){[data-edit-path]{transition:none}[data-edit-path]:focus{animation:none}}
"""


EDITOR_FRAME_JS = r"""
(() => {
  const editable = [...document.querySelectorAll('[data-edit-path]')];
  const timers = new WeakMap();
  const composing = new WeakSet();
  const normalized = value => String(value || '').replace(/\s+/g, ' ').trim();
  function post(type, detail={}) { parent.postMessage({type, slideId:document.querySelector('.oil-slide')?.dataset.slideId || '', ...detail}, '*'); }
  function setInteractive(interactive) {
    editable.forEach(node => {
      if (!interactive) node.blur();
      node.setAttribute('contenteditable', interactive ? 'plaintext-only' : 'false');
      node.style.cursor = interactive ? '' : 'default';
    });
  }
  function sync(path, value, source) {
    editable.filter(node => node !== source && node.dataset.editPath === path).forEach(node => { node.textContent = value; });
  }
  function send(node, immediate=false) {
    clearTimeout(timers.get(node));
    const task = () => {
      const value = normalized(node.textContent);
      if (node.textContent !== value) node.textContent = value;
      sync(node.dataset.editPath, value, node);
      post('oil-ppt-editor-edit', {path:node.dataset.editPath, value});
      setTimeout(report, 40);
    };
    if (immediate) task(); else timers.set(node, setTimeout(task, 320));
  }
  function report() {
    dispatchEvent(new Event('resize'));
    requestAnimationFrame(() => requestAnimationFrame(() => {
      const issues = new Map();
      editable.forEach(node => {
        const path = node.dataset.editPath;
        if (!path || !node.getClientRects().length || getComputedStyle(node).display === 'none') return;
        const overflow = node.scrollWidth > node.clientWidth + 1 || node.scrollHeight > node.clientHeight + 1;
        const reason = overflow ? 'text-overflow' : '';
        if (!reason) return;
        const issue = {path, reason, metrics:node.dataset.textMetrics || ''};
        issues.set(path, issue);
      });
      post('oil-ppt-editor-report', {issues:[...issues.values()]});
    }));
  }
  editable.forEach(node => {
    node.setAttribute('contenteditable', 'false');
    node.style.cursor = 'default';
    node.setAttribute('spellcheck', 'false');
    node.setAttribute('role', 'textbox');
    node.setAttribute('aria-label', '编辑这段文字');
    node.addEventListener('focus', () => post('oil-ppt-editor-focus', {path:node.dataset.editPath}));
    node.addEventListener('input', () => {
      const raw = String(node.textContent || '');
      sync(node.dataset.editPath, raw, node);
      post('oil-ppt-editor-local-edit', {path:node.dataset.editPath, value:raw});
      dispatchEvent(new Event('resize'));
      if (!composing.has(node)) send(node);
    });
    node.addEventListener('compositionstart', () => composing.add(node));
    node.addEventListener('compositionend', () => { composing.delete(node); send(node); });
    node.addEventListener('blur', () => send(node, true));
    node.addEventListener('keydown', event => {
      if (event.isComposing || event.keyCode === 229) return;
      if (event.key === 'Escape') { event.preventDefault(); node.blur(); }
      if (event.key === 'Enter') { event.preventDefault(); node.blur(); }
    });
    node.addEventListener('paste', event => {
      event.preventDefault();
      const text = normalized(event.clipboardData?.getData('text/plain'));
      const selection = getSelection();
      if (!selection?.rangeCount) return;
      const range = selection.getRangeAt(0);
      range.deleteContents();
      const textNode = document.createTextNode(text);
      range.insertNode(textNode);
      range.setStartAfter(textNode);
      range.collapse(true);
      selection.removeAllRanges();
      selection.addRange(range);
      node.dispatchEvent(new InputEvent('input', {bubbles:true, inputType:'insertText', data:text}));
    });
  });
  addEventListener('message', event => {
    const message = event.data || {};
    if (message.type === 'oil-ppt-editor-sync' && message.values) {
      editable.forEach(node => {
        if (!(node.dataset.editPath in message.values) || (!message.force && node === document.activeElement)) return;
        node.textContent = message.values[node.dataset.editPath];
      });
      report();
    }
    if (message.type === 'oil-ppt-editor-request-report') report();
    if (message.type === 'oil-ppt-editor-mode') setInteractive(Boolean(message.interactive));
    if (message.type === 'oil-ppt-editor-lock') setInteractive(false);
  });
  post('oil-ppt-editor-ready', {paths:editable.map(node => node.dataset.editPath)});
  report();
})();
"""


PREVIEW_SHELL_CSS = r"""
.palette-option:disabled{opacity:.62;cursor:default}
.page-card{position:relative}.frame-wrap{position:relative}.frame-wrap>iframe{pointer-events:none}.preview-open{position:absolute;inset:0;z-index:3;border:0;border-radius:11px;background:transparent;color:transparent;cursor:zoom-in}.preview-open:focus-visible{outline:3px solid #292929;outline-offset:4px}
.slide-lightbox{width:min(96vw,1680px);height:min(96vh,1000px);max-width:none;max-height:calc(100vh - 20px);padding:0;border:1px solid rgba(41,41,41,.08);border-radius:24px;background:#f7f7f5;box-shadow:0 30px 88px rgba(0,0,0,.22),0 1px 0 rgba(255,255,255,.8) inset;overflow:hidden}.slide-lightbox[open]{display:grid;grid-template-rows:auto minmax(0,1fr) auto;animation:oil-lightbox-in .28s cubic-bezier(.22,1,.36,1)}.slide-lightbox::backdrop{background:rgba(28,28,26,.44);backdrop-filter:blur(12px) saturate(.9)}.slide-lightbox[open]::backdrop{animation:oil-backdrop-in .22s ease-out}.lightbox-bar{height:62px;padding:0 14px 0 22px;display:flex;align-items:center;gap:10px;border-bottom:1px solid #dededb;background:rgba(255,255,255,.94)}.lightbox-bar strong{min-width:0;margin-right:auto;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.lightbox-page{color:#777;font-size:13px}.lightbox-bar button{height:38px;min-width:38px;padding:0 13px;border:1px solid #dededb;border-radius:12px;background:#fff;color:#292929;font:650 14px/1 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;cursor:pointer}.lightbox-bar button:hover{border-color:#aaa;background:#fafafa}.lightbox-bar button:disabled{opacity:.38;cursor:default}.lightbox-stage{min-height:0;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:minmax(0,1fr);place-items:center;padding:18px;overflow:hidden;background:#efefed}.lightbox-stage iframe{min-width:0;min-height:0;width:auto;height:100%;max-width:100%;max-height:100%;aspect-ratio:16/9;border:0;border-radius:13px;box-shadow:0 12px 38px rgba(0,0,0,.1);background:#fff}
@keyframes oil-lightbox-in{from{opacity:0;transform:translateY(12px) scale(.985)}to{opacity:1;transform:none}}@keyframes oil-backdrop-in{from{background:rgba(28,28,26,0);backdrop-filter:blur(0)}to{background:rgba(28,28,26,.44);backdrop-filter:blur(12px) saturate(.9)}}
.editor-toolbar{position:fixed;z-index:40;left:50%;bottom:20px;transform:translateX(-50%);width:min(920px,calc(100% - 28px));min-height:68px;padding:12px 14px 12px 18px;display:flex;align-items:center;gap:12px;border:1px solid rgba(41,41,41,.14);border-radius:20px;background:rgba(255,255,255,.94);box-shadow:0 18px 54px rgba(0,0,0,.16);backdrop-filter:blur(18px)}.editor-state{min-width:0;margin-right:auto;display:flex;align-items:center;gap:10px}.editor-dot{width:9px;height:9px;border-radius:50%;background:#61a56d;box-shadow:0 0 0 5px rgba(97,165,109,.13)}.editor-state strong{font-size:14px}.editor-state span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#777;font-size:13px}.editor-actions{display:flex;gap:8px}.editor-actions button{height:42px;padding:0 15px;border:1px solid #dededb;border-radius:13px;background:#fff;color:#292929;font:700 13px/1 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;cursor:pointer}.editor-actions button:hover:not(:disabled){border-color:#999}.editor-actions button:disabled{opacity:.38;cursor:default}.editor-actions .finish{border-color:#292929;background:#292929;color:#fff}.editor-errors{position:fixed;z-index:39;left:50%;bottom:102px;transform:translateX(-50%);width:min(920px,calc(100% - 28px));padding:16px 18px;border:1px solid #e6b5aa;border-radius:18px;background:#fff8f5;box-shadow:0 14px 40px rgba(0,0,0,.12);color:#7b3328}.editor-errors strong{display:block;margin-bottom:6px}.editor-errors ul{margin:0;padding-left:20px;font-size:13px;line-height:1.55}
.slide-lightbox .editor-toolbar{position:static;z-index:auto;left:auto;bottom:auto;transform:none;width:100%;min-height:66px;border-width:1px 0 0;border-radius:0;box-shadow:none;backdrop-filter:none}.slide-lightbox .editor-errors{position:absolute;z-index:2;bottom:78px;width:min(920px,calc(100% - 28px))}
@media(max-width:720px){.slide-lightbox{width:100vw;height:100dvh;max-height:100dvh;border-radius:0}.lightbox-bar{height:56px;padding-left:12px}.lightbox-bar strong{display:none}.lightbox-stage{padding:8px}.lightbox-stage iframe{width:100%;height:auto;max-height:100%}.editor-toolbar{bottom:10px;padding:10px 10px 10px 14px;flex-wrap:wrap}.editor-state{width:100%}.editor-actions{width:100%;display:grid;grid-template-columns:repeat(4,1fr)}.editor-actions button{padding:0 8px}.editor-errors{bottom:132px}}
@media(prefers-reduced-motion:reduce){.slide-lightbox[open],.slide-lightbox[open]::backdrop{animation:none}}
"""


PREVIEW_SHELL_JS = r"""
(() => {
  const cards = [...document.querySelectorAll('.page-card')];
  const dialog = document.querySelector('#slide-lightbox');
  const viewer = dialog?.querySelector('iframe');
  const title = dialog?.querySelector('.lightbox-title');
  const page = dialog?.querySelector('.lightbox-page');
  const previous = dialog?.querySelector('[data-lightbox-prev]');
  const next = dialog?.querySelector('[data-lightbox-next]');
  const editorToolbar = document.querySelector('.editor-toolbar');
  const editorErrors = document.querySelector('.editor-errors');
  const toolbarHome = editorToolbar ? {parent:editorToolbar.parentNode,next:editorToolbar.nextSibling} : null;
  const errorsHome = editorErrors ? {parent:editorErrors.parentNode,next:editorErrors.nextSibling} : null;
  let active = 0;
  function restore(element, home) {
    if (!element || !home?.parent) return;
    if (home.next?.parentNode === home.parent) home.parent.insertBefore(element, home.next);
    else home.parent.append(element);
  }
  function dockEditor() {
    if (editorErrors) dialog.append(editorErrors);
    if (editorToolbar) dialog.append(editorToolbar);
  }
  function show(index) {
    if (!dialog || !viewer || !cards.length) return;
    active = Math.max(0, Math.min(cards.length - 1, index));
    const source = cards[active].querySelector('iframe');
    viewer.srcdoc = source?.srcdoc || '';
    title.textContent = source?.title || `第 ${active + 1} 页`;
    page.textContent = `${active + 1} / ${cards.length}`;
    previous.disabled = active === 0;
    next.disabled = active === cards.length - 1;
  }
  function open(index) {
    show(index);
    dockEditor();
    if (!dialog.open) dialog.showModal();
  }
  cards.forEach((card, index) => card.querySelector('.preview-open')?.addEventListener('click', () => open(index)));
  previous?.addEventListener('click', () => show(active - 1));
  next?.addEventListener('click', () => show(active + 1));
  dialog?.querySelector('[data-lightbox-close]')?.addEventListener('click', () => dialog.close());
  dialog?.addEventListener('click', event => { if (event.target === dialog) dialog.close(); });
  dialog?.addEventListener('close', () => { restore(editorToolbar, toolbarHome); restore(editorErrors, errorsHome); });
  dialog?.addEventListener('keydown', event => {
    if (event.key === 'Escape') { event.preventDefault(); dialog.close(); }
    if (event.key === 'ArrowLeft') { event.preventDefault(); show(active - 1); }
    if (event.key === 'ArrowRight') { event.preventDefault(); show(active + 1); }
  });
})();
"""


def editor_shell_js(token: str, recovery_id: str) -> str:
    token_json = json.dumps(token, ensure_ascii=False)
    recovery_key_json = json.dumps(f"oil-ppt.text-editor-recovery/v1/{recovery_id}", ensure_ascii=False)
    return r"""
(() => {
  const token=__TOKEN__;
  const status=document.querySelector('#editor-status');
  const dot=document.querySelector('.editor-dot');
  const errors=document.querySelector('#editor-errors');
  const undo=document.querySelector('[data-editor-undo]');
  const redo=document.querySelector('[data-editor-redo]');
  const finish=document.querySelector('[data-editor-finish]');
  const editorDialog=document.querySelector('#slide-lightbox');
  const editorViewer=editorDialog?.querySelector('iframe');
  let pending=0;
  const saveErrors=new Map();
  let changedPaths=new Set();
  let latestValues={};
  const recoveryKey=__RECOVERY_KEY__;
  let leaseOwner=false;
  let releaseLeaseHold=()=>{};
  let leaseUnavailableMessage='';
  let recovery={};
  try { recovery=JSON.parse(localStorage.getItem(recoveryKey)||'{}')||{}; } catch (_) { recovery={}; }
  const reports=new Map();
  let mutationQueue=Promise.resolve();
  function setStatus(message, state='saved') {
    status.textContent=message;
    dot.style.background=state==='error'?'#d45b49':state==='saving'?'#e2a629':'#61a56d';
  }
  function setHistory(state={}) {
    undo.disabled=!state.can_undo;
    redo.disabled=!state.can_redo;
    if (state.changed_paths) changedPaths=new Set(state.changed_paths);
  }
  function fieldLabel(path='') {
    const match=path.match(/^\/slides\/(\d+)\/(.+)$/);
    if (!match) return '当前文字';
    const tail=match[2];
    const label=tail==='title'?'标题':tail==='content'?'正文':tail.endsWith('/title')?'小标题':tail.endsWith('/body')?'说明':tail.endsWith('/label')?'标签':'文字';
    return `第 ${Number(match[1])+1} 页 · ${label}`;
  }
  function showErrors(items) {
    if (!items?.length) { errors.hidden=true; errors.querySelector('ul').innerHTML=''; return; }
    errors.hidden=false;
    const labels={"text-overflow":"文字已经超出容器"};
    errors.querySelector('ul').innerHTML=items.map(item=>`<li>${fieldLabel(item.path)}：${labels[item.reason]||item.message||item.reason}</li>`).join('');
  }
  function lockEditor(message='另一个标签页正在编辑这份演示，请回到原标签页继续。') {
    document.body.classList.add('is-editor-readonly');
    document.querySelectorAll('.editor-actions button').forEach(button=>button.disabled=true);
    document.querySelectorAll('iframe').forEach(frame=>frame.contentWindow?.postMessage({type:'oil-ppt-editor-lock'},'*'));
    showErrors([{message}]); setStatus('当前标签页只读','error');
  }
  function syncEditorMode() {
    document.querySelectorAll('iframe').forEach(frame=>frame.contentWindow?.postMessage({
      type:'oil-ppt-editor-mode',
      interactive:leaseOwner && frame===editorViewer
    },'*'));
  }
  function ensureLease() {
    if (leaseOwner) return true;
    lockEditor(leaseUnavailableMessage||'当前标签页没有编辑权限。');
    return false;
  }
  function releaseLease() {
    if (!leaseOwner) return;
    leaseOwner=false;
    releaseLeaseHold();
    releaseLeaseHold=()=>{};
    syncEditorMode();
  }
  const leaseReady=new Promise(resolve=>{
    if (!navigator.locks?.request) {
      leaseUnavailableMessage='当前浏览器不支持安全的并发编辑保护，请使用最新版浏览器。';
      resolve(false);
      return;
    }
    navigator.locks.request(`oil-ppt-editor/${recoveryKey}`,{mode:'exclusive',ifAvailable:true},async lock=>{
      if (!lock) {
        leaseUnavailableMessage='另一个标签页正在编辑这份演示，请回到原标签页继续。';
        resolve(false);
        return;
      }
      await new Promise(release=>{
        releaseLeaseHold=release;
        leaseOwner=true;
        syncEditorMode();
        resolve(true);
      });
    }).catch(error=>{
      leaseUnavailableMessage=`无法取得编辑权限：${error.message}`;
      resolve(false);
    });
  });
  async function api(path, payload={}) {
    const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json','X-Oil-Ppt-Token':token},body:JSON.stringify(payload)});
    const result=await response.json();
    if (!response.ok || !result.ok) throw new Error((result.errors||[result.message||'操作失败']).join('；'));
    return result;
  }
  function broadcast(values, force=false) {
    if (!values) return;
    latestValues={...latestValues,...values};
    document.querySelectorAll('iframe').forEach(frame=>frame.contentWindow?.postMessage({type:'oil-ppt-editor-sync',values,force},'*'));
  }
  function persistRecovery() {
    if (Object.keys(recovery).length) localStorage.setItem(recoveryKey,JSON.stringify(recovery));
    else localStorage.removeItem(recoveryKey);
  }
  function normalized(value) { return String(value||'').replace(/\s+/g,' ').trim(); }
  function enqueue(task) {
    const result=mutationQueue.then(task,task);
    mutationQueue=result.catch(()=>{});
    return result;
  }
  function save(path,value) {
    pending+=1; finish.disabled=true; setStatus('正在保存…','saving');
    return enqueue(async()=>{
      try {
        const result=await api('/api/edit',{path,value});
        if (path in recovery && normalized(recovery[path])===normalized(value)) { delete recovery[path]; persistRecovery(); }
        saveErrors.delete(path); setHistory(result); broadcast({...result.values,...recovery}); showErrors([]);
      } catch (error) {
        saveErrors.set(path,error.message); showErrors([{message:error.message}]); setStatus('保存失败','error');
      } finally {
        pending-=1; finish.disabled=pending>0;
        if (!pending && !saveErrors.size) setStatus('已自动保存');
      }
    });
  }
  function saveErrorMessage() { return [...saveErrors.values()][0]||'仍有文字正在保存，请稍后再试'; }
  async function waitForPending() {
    const deadline=Date.now()+4000;
    while(pending>0 && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,50));
    return pending===0;
  }
  async function settlePending() {
    return await waitForPending() && !saveErrors.size;
  }
  async function flushEdits() {
    const entries=Object.entries(recovery);
    if (entries.length) await Promise.all(entries.map(([path,value])=>save(path,value)));
    return await settlePending() && !Object.keys(recovery).length;
  }
  async function historyAction(path) {
    if (!ensureLease()) return;
    if (!await flushEdits()) { showErrors([{message:saveErrorMessage()}]); return; }
    return enqueue(async()=>{
      try { const result=await api(path); setHistory(result); broadcast(result.values,true); showErrors([]); setStatus('已自动保存'); }
      catch (error) { showErrors([{message:error.message}]); setStatus('操作失败','error'); }
    });
  }
  addEventListener('message', event => {
    const message=event.data||{};
    if (message.type==='oil-ppt-editor-ready') {
      event.source?.postMessage({type:'oil-ppt-editor-mode',interactive:leaseOwner && event.source===editorViewer?.contentWindow},'*');
      event.source?.postMessage({type:'oil-ppt-editor-sync',values:latestValues,force:true},'*');
    }
    if (message.type==='oil-ppt-editor-local-edit') {
      if (!ensureLease()) return;
      recovery[message.path]=String(message.value||''); persistRecovery();
      broadcast({[message.path]:recovery[message.path]});
    }
    if (message.type==='oil-ppt-editor-edit' && ensureLease()) { broadcast({[message.path]:message.value}); save(message.path,message.value); }
    if (message.type==='oil-ppt-editor-report') reports.set(event.source,message.issues||[]);
  });
  undo.addEventListener('click',()=>historyAction('/api/undo'));
  redo.addEventListener('click',()=>historyAction('/api/redo'));
  document.querySelector('[data-editor-discard]').addEventListener('click',async()=>{
    if (!ensureLease()) return;
    if (!confirm('还原这次文字编辑？已经保存的编辑草稿会被删除。')) return;
    if (!await waitForPending()) { showErrors([{message:'仍有文字正在保存，请稍后再试'}]); return; }
    try { await enqueue(()=>api('/api/discard')); recovery={}; persistRecovery(); releaseLease(); location.reload(); }
    catch (error) { showErrors([{message:error.message}]); }
  });
  finish.addEventListener('click',async()=>{
    if (!ensureLease()) return;
    if (!await flushEdits()) { showErrors([{message:saveErrorMessage()}]); return; }
    finish.disabled=true; setStatus('正在检查页面…','saving');
    reports.clear();
    const frames=[...document.querySelectorAll('.page-card iframe')];
    const dialog=document.querySelector('#slide-lightbox');
    const viewer=dialog?.querySelector('iframe');
    if (dialog?.open && viewer?.srcdoc) frames.push(viewer);
    const expected=new Set(frames.map(frame=>frame.contentWindow).filter(Boolean));
    expected.forEach(frame=>frame.postMessage({type:'oil-ppt-editor-request-report'},'*'));
    const deadline=Date.now()+1600;
    while ([...expected].some(frame=>!reports.has(frame)) && Date.now()<deadline) await new Promise(resolve=>setTimeout(resolve,40));
    const missing=[...expected].filter(frame=>!reports.has(frame)).length;
    if (missing) { finish.disabled=false; showErrors([{message:`还有 ${missing} 个页面尚未完成检查，请稍后重试`}]); setStatus('页面检查未完成','error'); return; }
    const issues=[...reports.values()].flat().filter(item=>changedPaths.has(item.path) && item.reason==='text-overflow');
    const byPath=new Map();
    issues.forEach(item=>byPath.set(item.path,item));
    const unique=[...byPath.values()];
    if (unique.length) { finish.disabled=false; showErrors(unique); setStatus(`还有 ${unique.length} 处需要处理`,'error'); return; }
    setStatus('正在生成新的正式预览…','saving');
    try { const result=await enqueue(()=>api('/api/finish',{issues:unique,report_complete:true,expected_frames:expected.size})); recovery={}; persistRecovery(); releaseLease(); location.href=result.preview_url; }
    catch (error) { finish.disabled=false; showErrors([{message:error.message}]); setStatus('完成编辑失败','error'); }
  });
  leaseReady.then(owner=>{
    if (!owner) lockEditor(leaseUnavailableMessage||'另一个标签页正在编辑这份演示，请回到原标签页继续。');
    return enqueue(()=>api('/api/state'));
  }).then(result=>{
    setHistory(result); broadcast(result.values);
    if (!leaseOwner) return;
    if (Object.keys(recovery).length) { broadcast(recovery,true); Object.entries(recovery).forEach(([path,value])=>save(path,value)); }
  }).catch(error=>{showErrors([{message:error.message}]);setStatus('无法读取编辑草稿','error');});
  addEventListener('pagehide',releaseLease);
})();
""".replace("__TOKEN__", token_json).replace("__RECOVERY_KEY__", recovery_key_json)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("outline", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--no-open", action="store_true")
    return parser.parse_args()


def esc(value: object) -> str:
    return html.escape(str(value or ""), quote=True)


def atomic_write_text(path: Path, value: str) -> None:
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(value)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def palette_for(data: dict) -> dict[str, str]:
    raw = data["palette"]
    if isinstance(raw, str):
        return named_palette(raw)
    return normalize_palette(raw)


def theme_css(data: dict) -> str:
    palette = palette_for(data)
    typography = TYPE_PROFILES[data["typography"]]
    shape = SHAPE_PROFILES[data["shape"]]
    return ":root{" + "".join((
        f"--slide-bg:{palette['canvas']};--stage-bg:{palette['canvas']};",
        f"--ink:{palette['ink']};--ink-2:{palette['ink_2']};--ink-3:{palette['ink_3']};",
        f"--border:{palette['border']};--surface:{palette['surface']};--surface-2:{palette['surface_2']};",
        f"--accent:{palette['accent']};--accent-mark:{palette['accent']};--accent-fill:{palette['accent_fill']};",
        f"--accent-soft:{palette['accent_soft']};--accent-wash:{palette['accent_soft']};--accent-strong:{palette['accent_strong']};",
        f"--accent-ink:{palette['accent_strong']};--ambient:{palette['surface']};",
        f"--accent-alt:{palette['accent_alt']};--accent-alt-soft:{palette['accent_alt_soft']};",
        f"--accent-warm:{palette['accent_warm']};--accent-warm-soft:{palette['accent_warm_soft']};",
        f"--grid-color:color-mix(in srgb,{palette['ink']} 3.2%,transparent);",
        f"--font-zh:{typography['zh']};--font-ui:{typography['ui']};",
        f"--surface-radius:{shape['radius']};--surface-radius-sm:{shape['radius_sm']};--surface-radius-lg:{shape['radius_lg']};",
        f"--media-radius:{shape['media_radius']};--icon-radius:{shape['icon_radius']};--surface-shadow:{shape['shadow']};",
    )) + "}"


def prepared_slide(slide: dict, index: int, *, authoring: bool = False) -> tuple[str, str]:
    raw = (TEMPLATES / f"{slide['template']}.html").read_text(encoding="utf-8")
    title = html.escape(slide["title"], quote=True)
    raw = (raw.replace("__ID__", slide["id"])
              .replace("__TITLE__", title)
              .replace("__INDEX__", f"{index:02d}")
              .replace("__VARIANT__", html.escape(slide["variant"], quote=True))
              .replace("__DECOR__", html.escape(slide["decor"], quote=True)))
    css = CSS_BLOCK.search(raw).group(1)
    fragment = HTML_BLOCK.search(raw).group(1).strip()
    section = re.compile(r"<section\b(?P<attrs>[^>]*)>", re.I)
    match = section.search(fragment)
    attrs = match.group("attrs")
    additions = []
    if not re.search(r"\bdata-variant\s*=", attrs, re.I):
        additions.append(f' data-variant="{html.escape(slide["variant"], quote=True)}"')
    if not re.search(r"\bdata-component-decor\s*=", attrs, re.I):
        additions.append(f' data-component-decor="{html.escape(slide["decor"], quote=True)}"')
    if additions:
        fragment = fragment[:match.end() - 1] + "".join(additions) + fragment[match.end() - 1:]
    background = effective_background(slide)
    fragment, count = re.subn(
        r'(data-bg=["\'])[^"\']+(["\'])',
        rf'\g<1>{html.escape(background, quote=True)}\g<2>',
        fragment,
        count=1,
    )
    if count != 1:
        raise SystemExit(f"Template {slide['template']} does not expose data-bg.")
    filler = FILLERS[slide["template"]]
    fragment = filler(fragment, slide)
    fragment = apply_media_attributes(fragment, slide)
    fragment = inject_backdrop_text(fragment, slide)
    fragment = fragment.replace('src="../', 'src="')
    if slide.get("highlight"):
        phrase = html.escape(slide["highlight"], quote=True)
        marked = title.replace(phrase, f'<span class="hl">{phrase}</span>', 1)
        fragment = fragment.replace(f">{title}</h1>", f">{marked}</h1>", 1)
    if authoring:
        fragment = annotate_editable_fragment(fragment, slide, index - 1)
    return css, fragment


def iframe_document(data: dict, slide: dict, index: int, *, authoring: bool = False) -> str:
    css, fragment = prepared_slide(slide, index, authoring=authoring)
    editor_css = EDITOR_FRAME_CSS if authoring else ""
    editor_js = f"<script>{EDITOR_FRAME_JS}</script>" if authoring else ""
    author_attr = ' data-oil-authoring="true"' if authoring else ""
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{RUNTIME_CSS}{theme_css(data)}{css}{editor_css}</style></head>
<body data-oil-mode="preview"{author_attr} data-type-profile="{esc(data['typography'])}" data-shape-profile="{esc(data['shape'])}">
<div class="slide-preview-viewport"><div class="slide-preview-shell"><div class="slide-preview-stage">{fragment}</div></div></div>
<script>{RUNTIME_JS}</script>{editor_js}</body></html>"""


def visual_label(slide: dict) -> str:
    image = slide.get("image") or slide.get("media") or slide.get("artifact_image")
    if image:
        return f"素材：{Path(str(image)).name}"
    task = str(slide.get("visual_task") or "").strip()
    return f"视觉计划：{task}" if task else "纯排版 / 程序化结构"


def palette_controls(data: dict, *, readonly: bool = False) -> str:
    raw = data["palette"]
    if not isinstance(raw, str):
        palette = palette_for(data)
        return f'<span class="swatch" style="--swatch:{esc(palette["accent"])}">品牌配色 {esc(palette["name"])}</span>'
    selected = canonical_name(raw)
    buttons = []
    disabled = " disabled" if readonly else ""
    for name, tokens in PALETTES.items():
        state = " is-selected" if name == selected else ""
        buttons.append(
            f'<button type="button" class="palette-option{state}" data-palette="{esc(name)}" '
            f'style="--swatch:{esc(tokens["accent"])}" aria-pressed="{str(name == selected).lower()}"{disabled}>{esc(name)}</button>'
        )
    return (
        '<div class="palette-picker" aria-label="选择配色">'
        f'<span class="setting-label">配色{"（文字编辑时只读）" if readonly else ""}</span>'
        f'{"".join(buttons)}'
        '</div>'
    )


def rhythm_panel(data: dict, slides: list[dict]) -> str:
    background_codes = {
        "grid-fade": "GF", "grid-wide": "GW", "soft-spotlight": "SS",
        "block-field": "BF", "media-owned": "MO",
    }
    silhouette_codes = {
        "bleed": "BL", "browser": "BR", "canvas": "CV", "card-grid": "CG", "diagram": "DG",
        "editorial-list": "EL", "focal": "FC", "metric": "MT", "rail": "RL", "split": "SP",
        "matrix": "MX",
        "state-panel": "SW", "step-grid": "ST", "timeline": "TL", "two-panel": "TP",
    }

    def cells(kind: str) -> str:
        items = []
        for index, slide in enumerate(slides, start=1):
            background = effective_background(slide)
            silhouette = slide_quality(slide)["silhouette"]
            if kind == "background":
                value = background_codes[background]
                title = background
                class_name = f"bg-{background}"
            elif kind == "silhouette":
                value = silhouette_codes.get(silhouette, silhouette[:2].upper())
                title = silhouette
                class_name = ""
            elif kind == "backdrop":
                backdrop = effective_backdrop_text(slide)
                value = "Aa" if backdrop else "·"
                title = backdrop or "无背景大字"
                class_name = "is-highlight" if backdrop else ""
            elif kind == "media":
                if not has_media(slide):
                    value, title, class_name = "·", "无媒体", ""
                elif silhouette == "bleed":
                    value, title, class_name = "满", "全屏 / 出血媒体", "is-highlight"
                else:
                    value, title, class_name = "框", "安全区内媒体", ""
            else:
                value = "●" if slide.get("highlight") else "·"
                title = slide.get("highlight") or "无标题划线强调"
                class_name = "is-highlight" if slide.get("highlight") else ""
            items.append(
                f'<span class="rhythm-cell {class_name}" title="{index:02d} · {esc(slide["title"])} · {esc(title)}">'
                f'<small>{index:02d}</small><i>{esc(value)}</i></span>'
            )
        return "".join(items)

    def issue_hint(item: dict) -> str:
        suggestion = item.get("suggestion") or {}
        changes = suggestion.get("set_background") or {}
        if changes:
            return "建议：" + "，".join(f"{slide_id} → {background}" for slide_id, background in changes.items())
        candidates = suggestion.get("candidate_slides") or []
        templates = suggestion.get("templates") or []
        if templates and candidates:
            return "候选页：" + "、".join(candidates) + "；可选：" + " / ".join(templates)
        if templates:
            return "可选：" + " / ".join(templates)
        if candidates:
            return "候选页：" + "、".join(candidates)
        return str(suggestion.get("action") or "")

    summary = audit_summary(data)
    aesthetic_codes = {
        "background-monotony", "background-class-monotony", "background-run", "highlight-absence", "highlight-saturation",
        "backdrop-saturation", "component-dominance", "missing-focal-beat",
        "missing-cinematic-beat", "media-shape-monotony", "inset-media-run", "specialized-capability-suggestion",
    }
    issues = [item for item in summary["issues"] if item["code"] in aesthetic_codes]
    issue_html = "".join(
        f'<li><code>{esc(item["code"])}</code><span>{esc(item["message"])}</span>'
        f'<em>{esc(issue_hint(item))}</em></li>' for item in issues
    ) or '<li class="is-ok">背景、版式与强调节奏没有发现明显重复。</li>'
    return f'''<section class="rhythm-panel" aria-label="整套演示节奏检查">
<div class="rhythm-head"><div><strong>整套节奏</strong><span>程序根据 Outline 自动生成；提示只出现在预览壳层。</span></div><ul>{issue_html}</ul></div>
<div class="rhythm-row"><b>背景</b><div class="rhythm-cells">{cells("background")}</div></div>
<div class="rhythm-row"><b>版式</b><div class="rhythm-cells">{cells("silhouette")}</div></div>
<div class="rhythm-row"><b>媒体</b><div class="rhythm-cells">{cells("media")}</div></div>
<div class="rhythm-row"><b>强调</b><div class="rhythm-cells">{cells("highlight")}</div></div>
<div class="rhythm-row"><b>背景字</b><div class="rhythm-cells">{cells("backdrop")}</div></div>
</section>'''


def validate_asset_paths(data: dict, base: Path) -> None:
    root = base.resolve()
    for index, slide in enumerate(data.get("slides") or [], start=1):
        value = slide.get("image") or slide.get("media") or slide.get("artifact_image")
        if not value:
            continue
        path = (root / str(value)).resolve()
        if root not in path.parents:
            raise SystemExit(f"Outline slide {index} asset must stay inside the project: {value}")
        if not path.is_file():
            raise SystemExit(f"Outline slide {index} asset is missing: {value}")
    verify_outline_media(data, base)


def render(data: dict, *, authoring: bool = False, editor_token: str = "", editor_recovery_id: str = "") -> str:
    slides = validate_outline(data, TEMPLATES)
    palette = palette_for(data)
    cards = []
    for index, slide in enumerate(slides, start=1):
        document = html.escape(iframe_document(data, slide, index, authoring=authoring), quote=True)
        open_label = f"打开第 {index} 页"
        background = effective_background(slide)
        cards.append(f"""<article class="page-card" data-page-index="{index - 1}"><div class="meta"><b>{index:02d}</b><span title="版式">{esc(template_ui_label(slide['template']))}</span><span title="布局">{esc(variant_ui_label(slide['variant']))}</span><span title="装饰">{esc(decor_ui_label(slide['decor']))}</span><span title="背景">{esc(background_ui_label(background))}</span></div>
<div class="frame-wrap"><iframe title="{esc(slide['title'])}" srcdoc="{document}" tabindex="-1" aria-hidden="true"></iframe><button class="preview-open" type="button" aria-label="{esc(open_label)}"></button></div><p>{esc(visual_label(slide))}</p></article>""")
    palette_json = json.dumps({name: named_palette(name) for name in PALETTES}, ensure_ascii=False).replace("</", "<\\/")
    selected_palette = palette["name"]
    author_class = " class=\"is-authoring\"" if authoring else ""
    editor_toolbar = ""
    editor_script = ""
    if authoring:
        if not editor_token:
            raise ValueError("authoring preview requires an editor token")
        if not editor_recovery_id:
            raise ValueError("authoring preview requires a project-bound recovery id")
        editor_toolbar = """<section id="editor-errors" class="editor-errors" hidden aria-live="assertive"><strong>这些文字还需要处理</strong><ul></ul></section>
<aside class="editor-toolbar" aria-label="文字编辑工具栏"><div class="editor-state"><i class="editor-dot"></i><strong>文字编辑</strong><span id="editor-status">已自动保存</span></div><div class="editor-actions"><button type="button" data-editor-undo>撤销</button><button type="button" data-editor-redo>重做</button><button type="button" data-editor-discard>还原</button><button type="button" class="finish" data-editor-finish>完成编辑</button></div></aside>"""
        editor_script = f"<script>{editor_shell_js(editor_token, editor_recovery_id)}</script>"
    lightbox = f"""<dialog id="slide-lightbox" class="slide-lightbox" aria-label="幻灯片大图预览"><header class="lightbox-bar"><strong class="lightbox-title"></strong><span class="lightbox-page"></span><button type="button" data-lightbox-prev aria-label="上一页">←</button><button type="button" data-lightbox-next aria-label="下一页">→</button><button type="button" data-lightbox-close>关闭</button></header><div class="lightbox-stage"><iframe title="大图预览"></iframe></div>{editor_toolbar}</dialog>"""
    return f"""<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(data['title'])} · 预览</title>
<style>*{{box-sizing:border-box}}body{{margin:0;background:#f5f5f4;color:#292929;font-family:-apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{width:min(1500px,calc(100% - 40px));margin:auto;padding:44px 0 90px}}header{{margin-bottom:24px}}h1{{margin:0;font-size:40px}}.settings{{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 28px}}.settings>span,.meta span{{padding:7px 10px;border-radius:999px;background:#fff;border:1px solid #e5e5e5;font-size:12px}}.swatch{{display:inline-flex!important;align-items:center;gap:7px}}.swatch::before,.palette-option::before{{content:"";width:12px;height:12px;border-radius:3px;background:var(--swatch);border:1px solid rgba(0,0,0,.06)}}.palette-picker{{display:flex;align-items:center;gap:7px;flex-wrap:wrap;padding:7px;border:1px solid #dedede;border-radius:14px;background:#fff}}.setting-label{{padding:0 5px;font-size:12px;color:#777}}.palette-option{{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border:1px solid #e5e5e5;border-radius:999px;background:#fff;color:#555;font:600 12px/1 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif;cursor:pointer}}.palette-option:hover{{border-color:#aaa}}.palette-option.is-selected{{border-color:#292929;background:#292929;color:#fff}}.rhythm-panel{{margin:0 0 28px;padding:18px;border:1px solid #dedede;border-radius:18px;background:#fff;box-shadow:0 10px 30px rgba(0,0,0,.035)}}.rhythm-head{{display:grid;grid-template-columns:minmax(220px,.7fr) minmax(0,1.3fr);gap:24px;margin-bottom:14px}}.rhythm-head>div{{display:flex;align-items:baseline;gap:10px}}.rhythm-head strong{{font-size:16px}}.rhythm-head span{{color:#888;font-size:12px}}.rhythm-head ul{{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end;margin:0;padding:0;list-style:none}}.rhythm-head li{{display:flex;gap:7px;align-items:center;flex-wrap:wrap;padding:6px 9px;border-radius:9px;background:#fff8df;color:#6d5a16;font-size:11px}}.rhythm-head li.is-ok{{background:#f4f6f2;color:#65705e}}.rhythm-head code{{font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace}}.rhythm-head em{{width:100%;padding-left:calc(7px + 10ch);color:#8c772c;font-style:normal}}.rhythm-row{{display:grid;grid-template-columns:52px minmax(0,1fr);gap:10px;align-items:center;margin-top:8px}}.rhythm-row>b{{color:#777;font-size:12px}}.rhythm-cells{{display:grid;grid-template-columns:repeat({len(slides)},minmax(24px,1fr));gap:5px}}.rhythm-cell{{min-width:0;height:34px;display:grid;grid-template-rows:11px 1fr;place-items:center;border:1px solid #ececec;border-radius:7px;background:#fafafa;color:#a3a3a3;overflow:hidden}}.rhythm-cell small{{font:600 8px/1 ui-monospace,SFMono-Regular,Menlo,monospace;color:#aaa}}.rhythm-cell i{{font:700 10px/1 ui-monospace,SFMono-Regular,Menlo,monospace;font-style:normal}}.rhythm-cell.is-highlight i{{color:#292929}}.rhythm-cell.bg-grid-fade{{background:linear-gradient(145deg,#fff,#f5f5f4)}}.rhythm-cell.bg-grid-wide{{background:repeating-linear-gradient(90deg,#fafafa 0 5px,#ededeb 5px 6px)}}.rhythm-cell.bg-soft-spotlight{{background:radial-gradient(circle at 30% 28%,#e4e4e1,#fff 58%)}}.rhythm-cell.bg-block-field{{background:linear-gradient(145deg,#fff 0 44%,#eee 44% 72%,#f7e9ae 72%)}}.rhythm-cell.bg-media-owned{{background:#fff}}.pages{{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}}article{{padding:14px;border-radius:18px;background:#fff;border:1px solid #e5e5e5}}.meta{{display:flex;align-items:center;gap:7px;margin-bottom:11px}}.meta b{{margin-right:auto}}iframe{{display:block;width:100%;aspect-ratio:16/9;border:1px solid #eee;border-radius:11px;background:#fff}}article p{{margin:10px 2px 0;color:#777;font-size:12px}}@media(max-width:900px){{.rhythm-head{{grid-template-columns:1fr}}.rhythm-head ul{{justify-content:flex-start}}.rhythm-panel{{overflow-x:auto}}.rhythm-row{{min-width:720px}}.pages{{grid-template-columns:1fr}}}}{PREVIEW_SHELL_CSS}</style></head><body{author_class}><main>
<header><h1>{esc(data['title'])}</h1></header>
<div class="settings">{palette_controls(data, readonly=authoring)}<span>字体 {esc(TYPE_META[data['typography']]['label'])}</span><span>圆角 {esc(SHAPE_META[data['shape']]['label'])}</span><span>鼠标翻页 {'开启' if data['click_navigation'] else '关闭'}</span></div>
{rhythm_panel(data, slides)}
<section class="pages">{''.join(cards)}</section></main>{lightbox}
<script>
const palettes={palette_json};
const tokenMap={{canvas:"--slide-bg",ink:"--ink",ink_2:"--ink-2",ink_3:"--ink-3",border:"--border",surface:"--surface",surface_2:"--surface-2",accent:"--accent",accent_fill:"--accent-fill",accent_soft:"--accent-soft",accent_strong:"--accent-strong",accent_alt:"--accent-alt",accent_alt_soft:"--accent-alt-soft",accent_warm:"--accent-warm",accent_warm_soft:"--accent-warm-soft"}};
let activePalette={json.dumps(selected_palette)};
function applyPalette(name){{
  const values=palettes[name];
  if(!values)return;
  activePalette=name;
  document.querySelectorAll('.palette-option').forEach(button=>{{const selected=button.dataset.palette===name;button.classList.toggle('is-selected',selected);button.setAttribute('aria-pressed',String(selected));}});
  document.querySelectorAll('iframe').forEach(frame=>{{
    const update=()=>{{const root=frame.contentDocument?.documentElement;if(!root)return;Object.entries(tokenMap).forEach(([key,variable])=>root.style.setProperty(variable,values[key]));root.style.setProperty('--accent-mark',values.accent);root.style.setProperty('--accent-wash',values.accent_soft);root.style.setProperty('--accent-ink',values.accent_strong);root.style.setProperty('--ambient',values.surface);frame.contentWindow?.dispatchEvent(new Event('resize'));}};
    if(frame.contentDocument?.readyState==='complete')update();else frame.addEventListener('load',update,{{once:true}});
  }});
}}
document.querySelectorAll('.palette-option').forEach(button=>button.addEventListener('click',()=>applyPalette(button.dataset.palette)));
document.querySelectorAll('iframe').forEach(frame=>frame.addEventListener('load',()=>applyPalette(activePalette)));
applyPalette(activePalette);
</script><script>{PREVIEW_SHELL_JS}</script>{editor_script}</body></html>"""


def main() -> None:
    args = parse_args()
    outline = args.outline.expanduser().resolve()
    if not outline.is_file():
        raise SystemExit(f"Outline file not found: {outline}")
    data = json.loads(outline.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise SystemExit("Outline JSON must be an object.")
    validate_asset_paths(data, outline.parent)
    target = (args.out or outline.parent / "预览.html").expanduser().resolve()
    if target.parent != outline.parent or target.suffix.lower() not in {".html", ".htm"} or target == outline:
        raise SystemExit("Preview output must be a distinct HTML file directly inside the project root.")
    atomic_write_text(target, render(data))
    print(f"Created preview: {target}")
    if not args.no_open and not webbrowser.open(target.as_uri()):
        print("Browser did not open automatically. Open the preview HTML manually.")


if __name__ == "__main__":
    main()

import { KVService, MicroService, createApp } from "kikx-sdk";

let app = null;
let micro = null;
let kv = null;
let started = false;
let available = false;

export function isKikxRuntime() {
  return Boolean(window.parent && window.parent !== window);
}

export function getApp() {
  if (!app) {
    app = createApp();
  }
  return app;
}

export async function connectRuntime() {
  if (started) {
    return available;
  }
  started = true;

  if (!isKikxRuntime()) {
    available = false;
    return false;
  }

  try {
    const instance = getApp();
    micro = new MicroService(instance);
    kv = new KVService(instance);
    await instance.run();
    available = true;
    return true;
  } catch {
    available = false;
    return false;
  }
}

export function getMicro() {
  return micro;
}

export function getKv() {
  return kv;
}

export function hasKikx() {
  return available;
}
